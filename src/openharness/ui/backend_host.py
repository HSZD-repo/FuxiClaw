"""JSON-lines backend host for the React terminal frontend."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from openharness.api.client import SupportsStreamingMessages
from openharness.auth.manager import AuthManager
from openharness.config.settings import CLAUDE_MODEL_ALIAS_OPTIONS, resolve_model_setting
from openharness.bridge import get_bridge_manager
from openharness.themes import list_themes
from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.tools.control import get_tool_control_capability
from openharness.output_styles import load_output_styles
from openharness.tasks import get_task_manager
from openharness.ui.protocol import BackendEvent, FrontendRequest, TranscriptItem
from openharness.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime
from openharness.services.session_backend import SessionBackend
from openharness.permissions.modes import PermissionMode

log = logging.getLogger(__name__)

_PROTOCOL_PREFIX = "OHJSON:"
StepCancelHandle = Callable[..., Awaitable[None] | None]


@dataclass(frozen=True)
class BackendHostConfig:
    """Configuration for one backend host session."""

    model: str | None = None
    max_turns: int | None = None
    base_url: str | None = None
    system_prompt: str | None = None
    api_key: str | None = None
    api_format: str | None = None
    active_profile: str | None = None
    api_client: SupportsStreamingMessages | None = None
    cwd: str | None = None
    restore_messages: list[dict] | None = None
    restore_tool_metadata: dict[str, object] | None = None
    enforce_max_turns: bool = True
    permission_mode: str | None = None
    session_backend: SessionBackend | None = None
    extra_skill_dirs: tuple[str, ...] = ()
    extra_plugin_roots: tuple[str, ...] = ()


@dataclass
class RunningStep:
    """Live runtime metadata for the foreground tool currently executing."""

    tool_use_id: str
    tool_name: str
    started_at: int
    last_heartbeat_at: int
    command_preview: str | None = None
    heartbeat_task: asyncio.Task[None] | None = None
    task: asyncio.Task[object] | None = None
    process: asyncio.subprocess.Process | None = None
    cancel_handle: StepCancelHandle | None = None
    cancel_kind: str | None = None
    cancel_label: str | None = None
    defer_stalled_until: int = 0
    waiting_for_permission: bool = False


class ReactBackendHost:
    """Drive the OpenHarness runtime over a structured stdin/stdout protocol."""

    def __init__(self, config: BackendHostConfig) -> None:
        self._config = config
        self._bundle = None
        self._write_lock = asyncio.Lock()
        self._request_queue: asyncio.Queue[FrontendRequest] = asyncio.Queue()
        self._permission_requests: dict[str, asyncio.Future[bool]] = {}
        self._question_requests: dict[str, asyncio.Future[str]] = {}
        self._permission_lock = asyncio.Lock()
        self._busy = False
        self._running = True
        # Track last tool input per name for rich event emission
        self._last_tool_inputs: dict[str, dict] = {}
        self._active_line_task: asyncio.Task[bool] | None = None
        self._current_step: RunningStep | None = None
        self._runtime_control_state: dict[str, object] = {}

    async def run(self) -> int:
        self._bundle = await build_runtime(
            model=self._config.model,
            max_turns=self._config.max_turns,
            base_url=self._config.base_url,
            system_prompt=self._config.system_prompt,
            api_key=self._config.api_key,
            api_format=self._config.api_format,
            active_profile=self._config.active_profile,
            api_client=self._config.api_client,
            cwd=self._config.cwd,
            restore_messages=self._config.restore_messages,
            restore_tool_metadata=self._config.restore_tool_metadata,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
            enforce_max_turns=self._config.enforce_max_turns,
            permission_mode=self._config.permission_mode,
            session_backend=self._config.session_backend,
            extra_skill_dirs=self._config.extra_skill_dirs,
            extra_plugin_roots=self._config.extra_plugin_roots,
        )
        await start_runtime(self._bundle)
        await self._emit(
            BackendEvent.ready(
                self._bundle.app_state.get(),
                get_task_manager().list_tasks(),
                [f"/{command.name}" for command in self._bundle.commands.list_commands()],
            )
        )
        await self._emit(self._status_snapshot())

        reader = asyncio.create_task(self._read_requests())
        try:
            while self._running:
                request = await self._request_queue.get()
                if request.type == "shutdown":
                    await self._emit(BackendEvent(type="shutdown"))
                    break
                if request.type in ("permission_response", "question_response"):
                    continue
                if request.type == "step_control":
                    await self._handle_step_control(request)
                    continue
                if request.type == "session_control":
                    await self._handle_session_control(request)
                    continue
                if request.type == "refresh_settings":
                    if self._bundle is not None and not self._busy:
                        from openharness.ui.runtime import refresh_runtime_client

                        refresh_runtime_client(self._bundle)
                        await self._emit(BackendEvent.state_snapshot(self._bundle.app_state.get()))
                    elif self._busy:
                        await self._emit(
                            BackendEvent(
                                type="error",
                                message="Settings saved. The current session is busy, so the new provider/model will apply on the next run.",
                            )
                        )
                    continue
                if request.type == "list_sessions":
                    await self._handle_list_sessions()
                    continue
                if request.type == "select_command":
                    await self._handle_select_command(request.command or "")
                    continue
                if request.type == "apply_select_command":
                    if self._busy:
                        await self._emit(BackendEvent(type="error", message="Session is busy"))
                        continue
                    self._busy = True
                    try:
                        should_continue = await self._apply_select_command(
                            request.command or "",
                            request.value or "",
                        )
                    finally:
                        self._busy = False
                    if not should_continue:
                        await self._emit(BackendEvent(type="shutdown"))
                        break
                    continue
                if request.type != "submit_line":
                    await self._emit(BackendEvent(type="error", message=f"Unknown request type: {request.type}"))
                    continue
                if self._busy:
                    await self._emit(BackendEvent(type="error", message="Session is busy"))
                    continue
                line = (request.line or "").strip()
                if not line:
                    continue
                self._busy = True
                try:
                    self._active_line_task = asyncio.create_task(self._process_line(line))
                    should_continue = await self._active_line_task
                finally:
                    self._active_line_task = None
                    self._busy = False
                if not should_continue:
                    await self._emit(BackendEvent(type="shutdown"))
                    break
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader
            if self._bundle is not None:
                await close_runtime(self._bundle)
        return 0

    async def _read_requests(self) -> None:
        while True:
            raw = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not raw:
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return
            payload = raw.decode("utf-8").strip()
            if not payload:
                continue
            try:
                request = FrontendRequest.model_validate_json(payload)
            except Exception as exc:  # pragma: no cover - defensive protocol handling
                await self._emit(BackendEvent(type="error", message=f"Invalid request: {exc}"))
                continue
            if request.type == "permission_response" and request.request_id in self._permission_requests:
                future = self._permission_requests[request.request_id]
                if not future.done():
                    if request.trust_session and request.allowed:
                        self._enable_full_auto()
                    future.set_result(bool(request.allowed))
                    if request.trust_session and request.allowed and self._bundle is not None:
                        await self._emit(self._status_snapshot())
                continue
            if request.type == "question_response" and request.request_id in self._question_requests:
                future = self._question_requests[request.request_id]
                if not future.done():
                    future.set_result(request.answer or "")
                continue
            if request.type == "step_control":
                await self._handle_step_control(request)
                continue
            if request.type == "session_control":
                await self._handle_session_control(request)
                continue
            await self._request_queue.put(request)

    async def _process_line(self, line: str, *, transcript_line: str | None = None) -> bool:
        assert self._bundle is not None
        self._bundle.engine.tool_metadata["_runtime_control_state"] = self._runtime_control_state
        self._bundle.engine.tool_metadata["_register_running_process"] = self._register_running_process
        self._bundle.engine.tool_metadata["_register_running_task"] = self._register_running_task
        self._bundle.engine.tool_metadata["_register_step_cancel_handle"] = self._register_step_cancel_handle
        await self._emit(
            BackendEvent(type="transcript_item", item=TranscriptItem(role="user", text=transcript_line or line))
        )

        async def _print_system(message: str) -> None:
            await self._emit(
                BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=message))
            )

        async def _render_event(event: StreamEvent) -> None:
            if isinstance(event, AssistantTextDelta):
                await self._emit(BackendEvent(type="assistant_delta", message=event.text))
                return
            if isinstance(event, CompactProgressEvent):
                await self._emit(
                    BackendEvent(
                        type="compact_progress",
                        compact_phase=event.phase,
                        compact_trigger=event.trigger,
                        attempt=event.attempt,
                        compact_checkpoint=event.checkpoint,
                        compact_metadata=event.metadata,
                        message=event.message,
                    )
                )
                return
            if isinstance(event, AssistantTurnComplete):
                await self._emit(
                    BackendEvent(
                        type="assistant_complete",
                        message=event.message.text.strip(),
                        item=TranscriptItem(role="assistant", text=event.message.text.strip()),
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                return
            if isinstance(event, ToolExecutionStarted):
                self._last_tool_inputs[event.tool_name] = event.tool_input or {}
                tool_item = self._start_running_step(event)
                await self._emit(
                    BackendEvent(
                        type="tool_started",
                        tool_name=event.tool_name,
                        tool_input=event.tool_input,
                        item=tool_item,
                    )
                )
                return
            if isinstance(event, ToolExecutionCompleted):
                completed_item = self._complete_running_step(event)
                await self._emit(
                    BackendEvent(
                        type="tool_completed",
                        tool_name=event.tool_name,
                        output=event.output,
                        is_error=event.is_error,
                        item=completed_item,
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                await self._emit(self._status_snapshot())
                # Emit todo_update when TodoWrite tool runs
                if event.tool_name in ("TodoWrite", "todo_write"):
                    tool_input = self._last_tool_inputs.get(event.tool_name, {})
                    # TodoWrite input may have 'todos' list or markdown content field
                    todos = tool_input.get("todos") or tool_input.get("content") or []
                    if isinstance(todos, list) and todos:
                        lines = []
                        for item in todos:
                            if isinstance(item, dict):
                                checked = item.get("status", "") in ("done", "completed", "x", True)
                                text = item.get("content") or item.get("text") or str(item)
                                lines.append(f"- [{'x' if checked else ' '}] {text}")
                        if lines:
                            await self._emit(BackendEvent(type="todo_update", todo_markdown="\n".join(lines)))
                    else:
                        await self._emit_todo_update_from_output(event.output)
                # Emit plan_mode_change when plan-related tools complete
                if event.tool_name in ("set_permission_mode", "plan_mode"):
                    assert self._bundle is not None
                    new_mode = self._bundle.app_state.get().permission_mode
                    await self._emit(BackendEvent(type="plan_mode_change", plan_mode=new_mode))
                return
            if isinstance(event, ErrorEvent):
                await self._emit(BackendEvent(type="error", message=event.message))
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return
            if isinstance(event, StatusEvent):
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return

        async def _clear_output() -> None:
            await self._emit(BackendEvent(type="clear_transcript"))

        try:
            should_continue = await handle_line(
                self._bundle,
                line,
                print_system=_print_system,
                render_event=_render_event,
                clear_output=_clear_output,
            )
        except asyncio.CancelledError:
            if self._runtime_control_state.get("session_stop_requested"):
                await self._emit(
                    BackendEvent(
                        type="transcript_item",
                        item=TranscriptItem(role="system", text="Stopped current run."),
                    )
                )
                should_continue = True
            else:
                raise
        finally:
            self._bundle.engine.tool_metadata.pop("_runtime_control_state", None)
            self._bundle.engine.tool_metadata.pop("_register_running_process", None)
            self._bundle.engine.tool_metadata.pop("_register_running_task", None)
            self._bundle.engine.tool_metadata.pop("_register_step_cancel_handle", None)
            self._runtime_control_state.clear()
            await self._stop_running_step()
        await self._emit(self._status_snapshot())
        await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
        await self._emit(BackendEvent(type="line_complete"))
        return should_continue

    def _start_running_step(self, event: ToolExecutionStarted) -> TranscriptItem:
        started_at = int(time.time() * 1000)
        control_capability = get_tool_control_capability(event.tool_name)
        metadata = {
            "started_at": started_at,
            "last_heartbeat_at": started_at,
            "status_message": "Running",
            "supports_step_control": control_capability.supports_step_control,
            "declared_control_kind": control_capability.kind,
            "declared_control_label": control_capability.label,
            "declared_deep_cancel": control_capability.supports_deep_cancel,
        }
        command_preview = None
        if event.tool_name == "bash":
            command_preview = str((event.tool_input or {}).get("command") or "").strip() or None
        self._current_step = RunningStep(
            tool_use_id=event.tool_use_id or uuid4().hex,
            tool_name=event.tool_name,
            started_at=started_at,
            last_heartbeat_at=started_at,
            command_preview=command_preview,
        )
        self._current_step.heartbeat_task = asyncio.create_task(
            self._emit_tool_heartbeats(self._current_step.tool_use_id)
        )
        return TranscriptItem(
            role="tool",
            text=f"{event.tool_name} {json.dumps(event.tool_input, ensure_ascii=True)}",
            tool_name=event.tool_name,
            tool_input=event.tool_input,
            tool_use_id=self._current_step.tool_use_id,
            tool_status="running",
            metadata=metadata,
            timestamp=started_at,
        )

    def _complete_running_step(self, event: ToolExecutionCompleted) -> TranscriptItem:
        step = self._current_step
        completed_at = int(time.time() * 1000)
        metadata = dict(event.metadata or {})
        tool_status = "error" if event.is_error else "success"
        text = event.output
        if step is not None and step.tool_use_id == event.tool_use_id:
            metadata.update(
                {
                    "started_at": step.started_at,
                    "last_heartbeat_at": step.last_heartbeat_at,
                    "completed_at": completed_at,
                }
            )
            action = str(self._runtime_control_state.get("action") or metadata.get("user_action") or "")
            if action == "skip":
                tool_status = "skipped"
                metadata["status_message"] = "Skipped by user"
            elif action == "stop":
                tool_status = "cancelled"
                metadata["status_message"] = "Cancelled by user"
            else:
                metadata["status_message"] = "Error" if event.is_error else "Done"
        return TranscriptItem(
            role="tool",
            text=text,
            tool_name=event.tool_name,
            is_error=event.is_error,
            tool_use_id=event.tool_use_id,
            tool_status=tool_status,  # type: ignore[arg-type]
            metadata=metadata,
            timestamp=completed_at,
        )

    async def _emit_tool_heartbeats(self, tool_use_id: str) -> None:
        try:
            while self._running:
                await asyncio.sleep(2.0)
                step = self._current_step
                if step is None or step.tool_use_id != tool_use_id:
                    return
                now = int(time.time() * 1000)
                status, status_message = self._runtime_phase_for_step(step, now=now)
                step.last_heartbeat_at = now
                await self._emit(
                    BackendEvent(
                        type="tool_heartbeat",
                        tool_name=step.tool_name,
                        item=TranscriptItem(
                            role="tool",
                            text=status_message,
                            tool_name=step.tool_name,
                            tool_use_id=step.tool_use_id,
                            tool_status=status,  # type: ignore[arg-type]
                            metadata={
                                "started_at": step.started_at,
                                "last_heartbeat_at": now,
                                "status_message": status_message,
                                "supports_step_control": True,
                                "supports_deep_cancel": step.cancel_handle is not None or step.process is not None,
                                "cancel_kind": step.cancel_kind,
                                "cancel_label": step.cancel_label,
                                "command_preview": step.command_preview,
                            },
                            timestamp=step.started_at,
                        ),
                    )
                )
        except asyncio.CancelledError:
            return

    def _runtime_phase_for_step(
        self,
        step: RunningStep,
        *,
        now: int,
    ) -> tuple[str, str]:
        if step.waiting_for_permission:
            return "waiting_permission", "Waiting for permission"
        elapsed_ms = max(0, now - step.started_at)
        if elapsed_ms >= 20_000 and now >= step.defer_stalled_until:
            return "stalled", "Possibly waiting for input"
        if elapsed_ms >= 8_000:
            return "waiting_output", "Running, waiting for output"
        return "running", "Running"

    async def _emit_running_step_status(
        self,
        step: RunningStep,
        *,
        status: str,
        status_message: str,
    ) -> None:
        now = int(time.time() * 1000)
        step.last_heartbeat_at = now
        await self._emit(
            BackendEvent(
                type="tool_heartbeat",
                tool_name=step.tool_name,
                item=TranscriptItem(
                    role="tool",
                    text=status_message,
                    tool_name=step.tool_name,
                    tool_use_id=step.tool_use_id,
                    tool_status=status,  # type: ignore[arg-type]
                    metadata={
                        "started_at": step.started_at,
                        "last_heartbeat_at": now,
                        "status_message": status_message,
                        "supports_step_control": True,
                        "supports_deep_cancel": step.cancel_handle is not None or step.process is not None,
                        "cancel_kind": step.cancel_kind,
                        "cancel_label": step.cancel_label,
                        "command_preview": step.command_preview,
                    },
                    timestamp=step.started_at,
                ),
            )
        )

    async def _stop_running_step(self) -> None:
        step = self._current_step
        self._current_step = None
        if step is None:
            return
        task = step.heartbeat_task
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _handle_step_control(self, request: FrontendRequest) -> None:
        action = request.action
        step = self._current_step
        if action not in {"stop", "skip", "wait"}:
            await self._emit(BackendEvent(type="error", message="Unknown step control action"))
            return
        if step is None or not request.tool_use_id or request.tool_use_id != step.tool_use_id:
            await self._emit(BackendEvent(type="error", message="No matching running step to control"))
            return
        if action == "wait":
            step.defer_stalled_until = int(time.time() * 1000) + 15_000
            now = int(time.time() * 1000)
            status, status_message = self._runtime_phase_for_step(step, now=now)
            step.last_heartbeat_at = now
            await self._emit(
                BackendEvent(
                    type="tool_heartbeat",
                    tool_name=step.tool_name,
                    item=TranscriptItem(
                        role="tool",
                        text=status_message,
                        tool_name=step.tool_name,
                        tool_use_id=step.tool_use_id,
                        tool_status=status,  # type: ignore[arg-type]
                        metadata={
                            "started_at": step.started_at,
                            "last_heartbeat_at": now,
                            "status_message": status_message,
                            "supports_step_control": True,
                            "supports_deep_cancel": step.cancel_handle is not None or step.process is not None,
                            "cancel_kind": step.cancel_kind,
                            "cancel_label": step.cancel_label,
                            "command_preview": step.command_preview,
                        },
                        timestamp=step.started_at,
                    ),
                )
            )
            return
        if (
            step.cancel_handle is None
            and
            (step.task is None or step.task.done())
            and (step.process is None or step.process.returncode is not None)
        ):
            await self._emit(BackendEvent(type="error", message="This step cannot be interrupted right now"))
            return
        self._runtime_control_state.clear()
        self._runtime_control_state.update(
            {
                "action": action,
                "target_tool_use_id": step.tool_use_id,
                "abort_after_tool": False,
            }
        )
        await self._cancel_running_step(step, action=action)

    async def _handle_session_control(self, request: FrontendRequest) -> None:
        if request.action != "stop":
            await self._emit(BackendEvent(type="error", message="Unknown session control action"))
            return
        active_task = self._active_line_task
        if active_task is None or active_task.done():
            return
        step = self._current_step
        if step is not None:
            if (
                step.cancel_handle is None
                and
                (step.task is None or step.task.done())
                and (step.process is None or step.process.returncode is not None)
            ):
                await self._emit(BackendEvent(type="error", message="This session cannot be interrupted right now"))
                return
            self._runtime_control_state.clear()
            self._runtime_control_state.update(
                {
                    "action": "stop",
                    "target_tool_use_id": step.tool_use_id,
                    "abort_after_tool": True,
                    "session_stop_requested": True,
                }
            )
            await self._cancel_running_step(step, action="stop")
            return
        self._runtime_control_state.clear()
        self._runtime_control_state.update(
            {
                "action": "stop",
                "abort_after_tool": True,
                "session_stop_requested": True,
            }
        )
        active_task.cancel()

    def _register_running_process(
        self,
        *,
        tool_use_id: str | None,
        tool_name: str | None,
        process: asyncio.subprocess.Process,
        command: str,
    ) -> None:
        step = self._current_step
        if step is None:
            return
        if tool_use_id and tool_use_id != step.tool_use_id:
            return
        if tool_name and tool_name != step.tool_name:
            return
        step.process = process
        step.command_preview = command

    def _register_running_task(
        self,
        *,
        tool_use_id: str | None,
        tool_name: str | None,
        task: asyncio.Task[object],
    ) -> None:
        step = self._current_step
        if step is None:
            return
        if tool_use_id and tool_use_id != step.tool_use_id:
            return
        if tool_name and tool_name != step.tool_name:
            return
        step.task = task

    def _register_step_cancel_handle(
        self,
        *,
        tool_use_id: str | None,
        tool_name: str | None,
        cancel: StepCancelHandle,
        cancel_kind: str,
        cancel_label: str | None = None,
    ) -> None:
        step = self._current_step
        if step is None:
            return
        if tool_use_id and tool_use_id != step.tool_use_id:
            return
        if tool_name and tool_name != step.tool_name:
            return
        step.cancel_handle = cancel
        step.cancel_kind = cancel_kind
        step.cancel_label = cancel_label

    async def _cancel_running_step(self, step: RunningStep, *, action: str) -> None:
        if step.cancel_handle is not None:
            try:
                result = step.cancel_handle(action=action)
                if inspect.isawaitable(result):
                    await result
            except TypeError:
                result = step.cancel_handle(action)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                log.warning(
                    "step cancel handle failed: tool=%s id=%s kind=%s",
                    step.tool_name,
                    step.tool_use_id,
                    step.cancel_kind,
                    exc_info=True,
                )
        if step.process is not None and step.process.returncode is None:
            step.process.terminate()
            asyncio.create_task(self._force_kill_process_if_needed(step.process))
        if step.task is not None and not step.task.done():
            step.task.cancel()

    async def _force_kill_process_if_needed(self, process: asyncio.subprocess.Process) -> None:
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def _apply_select_command(self, command_name: str, value: str) -> bool:
        command = command_name.strip().lstrip("/").lower()
        selected = value.strip()
        line = self._build_select_command_line(command, selected)
        if line is None:
            await self._emit(BackendEvent(type="error", message=f"Unknown select command: {command_name}"))
            await self._emit(BackendEvent(type="line_complete"))
            return True
        return await self._process_line(line, transcript_line=f"/{command}")

    def _build_select_command_line(self, command: str, value: str) -> str | None:
        if command == "provider":
            return f"/provider {value}"
        if command == "resume":
            return f"/resume {value}" if value else "/resume"
        if command == "permissions":
            return f"/permissions {value}"
        if command == "theme":
            return f"/theme {value}"
        if command == "output-style":
            return f"/output-style {value}"
        if command == "effort":
            return f"/effort {value}"
        if command == "passes":
            return f"/passes {value}"
        if command == "turns":
            return f"/turns {value}"
        if command == "fast":
            return f"/fast {value}"
        if command == "vim":
            return f"/vim {value}"
        if command == "voice":
            return f"/voice {value}"
        if command == "model":
            return f"/model {value}"
        return None

    def _status_snapshot(self) -> BackendEvent:
        assert self._bundle is not None
        return BackendEvent.status_snapshot(
            state=self._bundle.app_state.get(),
            mcp_servers=self._bundle.mcp_manager.list_statuses(),
            bridge_sessions=get_bridge_manager().list_sessions(),
        )

    async def _emit_todo_update_from_output(self, output: str) -> None:
        """Emit a todo_update event by extracting markdown checklist from tool output."""
        # TodoWrite tools typically echo back the written content
        # We look for markdown checklist patterns in the output
        lines = output.splitlines()
        checklist_lines = [line for line in lines if line.strip().startswith("- [")]
        if checklist_lines:
            markdown = "\n".join(checklist_lines)
            await self._emit(BackendEvent(type="todo_update", todo_markdown=markdown))

    def _emit_swarm_status(self, teammates: list[dict], notifications: list[dict] | None = None) -> None:
        """Emit a swarm_status event synchronously (schedule as coroutine)."""
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(
            self._emit(BackendEvent(type="swarm_status", swarm_teammates=teammates, swarm_notifications=notifications))
        )

    async def _handle_list_sessions(self) -> None:
        import time as _time

        assert self._bundle is not None
        sessions = self._bundle.session_backend.list_snapshots(self._bundle.cwd, limit=10)
        options = []
        for s in sessions:
            ts = _time.strftime("%m/%d %H:%M", _time.localtime(s["created_at"]))
            summary = s.get("summary", "")[:50] or "(no summary)"
            options.append({
                "value": s["session_id"],
                "label": f"{ts}  {s['message_count']}msg  {summary}",
            })
        await self._emit(
            BackendEvent(
                type="select_request",
                modal={"kind": "select", "title": "Resume Session", "command": "resume"},
                select_options=options,
            )
        )

    async def _handle_select_command(self, command_name: str) -> None:
        assert self._bundle is not None
        command = command_name.strip().lstrip("/").lower()
        if command == "resume":
            await self._handle_list_sessions()
            return

        settings = self._bundle.current_settings()
        state = self._bundle.app_state.get()
        _, active_profile = settings.resolve_profile()
        current_model = settings.model

        if command == "provider":
            statuses = AuthManager(settings).get_profile_statuses()
            options = [
                {
                    "value": name,
                    "label": info["label"],
                    "description": f"{info['provider']} / {info['auth_source']}" + (" [missing auth]" if not info["configured"] else ""),
                    "active": info["active"],
                }
                for name, info in statuses.items()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Provider Profile", "command": "provider"},
                    select_options=options,
                )
            )
            return

        if command == "permissions":
            options = [
                {
                    "value": "default",
                    "label": "Default",
                    "description": "Ask before write/execute operations",
                    "active": settings.permission.mode.value == "default",
                },
                {
                    "value": "full_auto",
                    "label": "Auto",
                    "description": "Allow all tools automatically",
                    "active": settings.permission.mode.value == "full_auto",
                },
                {
                    "value": "plan",
                    "label": "Plan Mode",
                    "description": "Block all write operations",
                    "active": settings.permission.mode.value == "plan",
                },
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Permission Mode", "command": "permissions"},
                    select_options=options,
                )
            )
            return

        if command == "theme":
            options = [
                {
                    "value": name,
                    "label": name,
                    "active": name == settings.theme,
                }
                for name in list_themes()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Theme", "command": "theme"},
                    select_options=options,
                )
            )
            return

        if command == "output-style":
            options = [
                {
                    "value": style.name,
                    "label": style.name,
                    "description": style.source,
                    "active": style.name == settings.output_style,
                }
                for style in load_output_styles()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Output Style", "command": "output-style"},
                    select_options=options,
                )
            )
            return

        if command == "effort":
            options = [
                {"value": "low", "label": "Low", "description": "Fastest responses", "active": settings.effort == "low"},
                {"value": "medium", "label": "Medium", "description": "Balanced reasoning", "active": settings.effort == "medium"},
                {"value": "high", "label": "High", "description": "Deepest reasoning", "active": settings.effort == "high"},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Reasoning Effort", "command": "effort"},
                    select_options=options,
                )
            )
            return

        if command == "passes":
            current = int(state.passes or settings.passes)
            options = [
                {"value": str(value), "label": f"{value} pass{'es' if value != 1 else ''}", "active": value == current}
                for value in range(1, 9)
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Reasoning Passes", "command": "passes"},
                    select_options=options,
                )
            )
            return

        if command == "turns":
            current = self._bundle.engine.max_turns
            values = {32, 64, 128, 200, 256, 512}
            if isinstance(current, int):
                values.add(current)
            options = [{"value": "unlimited", "label": "Unlimited", "description": "Do not hard-stop this session", "active": current is None}]
            options.extend(
                {"value": str(value), "label": f"{value} turns", "active": value == current}
                for value in sorted(values)
            )
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Max Turns", "command": "turns"},
                    select_options=options,
                )
            )
            return

        if command == "fast":
            current = bool(state.fast_mode)
            options = [
                {"value": "on", "label": "On", "description": "Prefer shorter, faster responses", "active": current},
                {"value": "off", "label": "Off", "description": "Use normal response mode", "active": not current},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Fast Mode", "command": "fast"},
                    select_options=options,
                )
            )
            return

        if command == "vim":
            current = bool(state.vim_enabled)
            options = [
                {"value": "on", "label": "On", "description": "Enable Vim keybindings", "active": current},
                {"value": "off", "label": "Off", "description": "Use standard keybindings", "active": not current},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Vim Mode", "command": "vim"},
                    select_options=options,
                )
            )
            return

        if command == "voice":
            current = bool(state.voice_enabled)
            options = [
                {"value": "on", "label": "On", "description": state.voice_reason or "Enable voice mode", "active": current},
                {"value": "off", "label": "Off", "description": "Disable voice mode", "active": not current},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Voice Mode", "command": "voice"},
                    select_options=options,
                )
            )
            return

        if command == "model":
            options = self._model_select_options(current_model, active_profile.provider, active_profile.allowed_models)
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Model", "command": "model"},
                    select_options=options,
                )
            )
            return

        await self._emit(BackendEvent(type="error", message=f"No selector available for /{command}"))

    def _model_select_options(self, current_model: str, provider: str, allowed_models: list[str] | None = None) -> list[dict[str, object]]:
        provider_name = provider.lower()
        if provider_name in {"anthropic", "anthropic_claude"}:
            resolved_current = resolve_model_setting(current_model, provider_name)
            return [
                {
                    "value": value,
                    "label": label,
                    "description": description,
                    "active": value == current_model
                    or resolve_model_setting(value, provider_name) == resolved_current,
                }
                for value, label, description in CLAUDE_MODEL_ALIAS_OPTIONS
            ]
        if allowed_models:
            return [
                {
                    "value": value,
                    "label": value,
                    "description": "Allowed for this profile",
                    "active": value == current_model,
                }
                for value in allowed_models
            ]
        families: list[tuple[str, str]] = []
        if provider_name in {"openai-codex", "openai", "openai-compatible", "openrouter", "github_copilot"}:
            families.extend(
                [
                    ("gpt-5.4", "OpenAI flagship"),
                    ("gpt-5", "General GPT-5"),
                    ("gpt-4.1", "Stable GPT-4.1"),
                    ("o4-mini", "Fast reasoning"),
                ]
            )
        elif provider_name in {"moonshot", "moonshot-compatible"}:
            families.extend(
                [
                    ("kimi-k2.5", "Moonshot K2.5"),
                    ("kimi-k2-turbo-preview", "Faster Moonshot"),
                ]
            )
        elif provider_name == "dashscope":
            families.extend(
                [
                    ("qwen3.5-flash", "Fast Qwen"),
                    ("qwen3-max", "Strong Qwen"),
                    ("deepseek-r1", "Reasoning model"),
                ]
            )
        elif provider_name == "gemini":
            families.extend(
                [
                    ("gemini-2.5-pro", "Gemini Pro"),
                    ("gemini-2.5-flash", "Gemini Flash"),
                ]
            )
        elif provider_name == "minimax":
            families.extend(
                [
                    ("MiniMax-M2.7", "MiniMax flagship"),
                    ("MiniMax-M2.7-highspeed", "MiniMax fast"),
                ]
            )
        elif provider_name == "deepseek":
            families.extend(
                [
                    ("deepseek-v4-flash", "DeepSeek fast"),
                    ("deepseek-v4-pro", "DeepSeek pro"),
                ]
            )
        elif provider_name == "zhipu":
            families.append(("glm-5.1", "GLM flagship"))
        elif provider_name == "mimo":
            families.append(("mimo-2.5", "MiMo flagship"))

        seen: set[str] = set()
        options: list[dict[str, object]] = []
        for value, description in [(current_model, "Current model"), *families]:
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(
                {
                    "value": value,
                    "label": value,
                    "description": description,
                    "active": value == current_model,
                }
            )
        return options

    def _enable_full_auto(self) -> None:
        """Switch the live session checker to FULL_AUTO (trust-this-session).

        Mutates the checker already referenced by QueryEngine so in-flight
        turns see the new mode immediately.
        """
        if self._bundle is None:
            return
        checker = self._bundle.engine._permission_checker
        checker._settings.mode = PermissionMode.FULL_AUTO
        self._bundle.engine.tool_metadata["permission_mode"] = PermissionMode.FULL_AUTO.value
        self._bundle.app_state.set(permission_mode=PermissionMode.FULL_AUTO.value)
        log.info("Session switched to FULL_AUTO (trust this session)")

    async def _ask_permission(self, tool_name: str, reason: str) -> bool:
        async with self._permission_lock:
            request_id = uuid4().hex
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            self._permission_requests[request_id] = future
            step = self._current_step
            if step is not None:
                step.waiting_for_permission = True
                await self._emit_running_step_status(
                    step,
                    status="waiting_permission",
                    status_message="Waiting for permission",
                )
            await self._emit(
                BackendEvent(
                    type="modal_request",
                    modal={
                        "kind": "permission",
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "reason": reason,
                    },
                )
            )
            try:
                allowed = await future
                if step is not None:
                    step.waiting_for_permission = False
                    if allowed:
                        await self._emit_running_step_status(
                            step,
                            status="running",
                            status_message="Running",
                        )
                return allowed
            except asyncio.CancelledError:
                if step is not None:
                    step.waiting_for_permission = False
                raise
            finally:
                self._permission_requests.pop(request_id, None)
                await self._emit(BackendEvent(type="modal_request", modal=None))

    async def _ask_question(self, question: str) -> str:
        request_id = uuid4().hex
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._question_requests[request_id] = future
        await self._emit(
            BackendEvent(
                type="modal_request",
                modal={
                    "kind": "question",
                    "request_id": request_id,
                    "question": question,
                },
            )
        )
        try:
            return await future
        finally:
            self._question_requests.pop(request_id, None)

    async def _emit(self, event: BackendEvent) -> None:
        log.debug("emit event: type=%s tool=%s", event.type, getattr(event, "tool_name", None))
        async with self._write_lock:
            payload = _PROTOCOL_PREFIX + event.model_dump_json() + "\n"
            buffer = getattr(sys.stdout, "buffer", None)
            if buffer is not None:
                buffer.write(payload.encode("utf-8"))
                buffer.flush()
                return
            sys.stdout.write(payload)
            sys.stdout.flush()


async def run_backend_host(
    *,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
    active_profile: str | None = None,
    cwd: str | None = None,
    api_client: SupportsStreamingMessages | None = None,
    restore_messages: list[dict] | None = None,
    restore_tool_metadata: dict[str, object] | None = None,
    enforce_max_turns: bool = True,
    permission_mode: str | None = None,
    session_backend: SessionBackend | None = None,
    extra_skill_dirs: tuple[str | Path, ...] = (),
    extra_plugin_roots: tuple[str | Path, ...] = (),
) -> int:
    """Run the structured React backend host."""
    if cwd:
        os.chdir(cwd)
    host = ReactBackendHost(
        BackendHostConfig(
            model=model,
            max_turns=max_turns,
            base_url=base_url,
            system_prompt=system_prompt,
            api_key=api_key,
            api_format=api_format,
            active_profile=active_profile,
            api_client=api_client,
            cwd=cwd,
            restore_messages=restore_messages,
            restore_tool_metadata=restore_tool_metadata,
            enforce_max_turns=enforce_max_turns,
            permission_mode=permission_mode,
            session_backend=session_backend,
            extra_skill_dirs=tuple(str(Path(path).expanduser().resolve()) for path in extra_skill_dirs),
            extra_plugin_roots=tuple(str(Path(path).expanduser().resolve()) for path in extra_plugin_roots),
        )
    )
    return await host.run()


__all__ = ["run_backend_host", "ReactBackendHost", "BackendHostConfig"]
