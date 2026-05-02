"""Core tool-aware query loop."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import mimetypes
import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable

from openharness.api.client import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiRetryEvent,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage, ToolResultBlock
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
from openharness.hooks import HookEvent, HookExecutor
from openharness.memory import add_structured_memory_entry
from openharness.permissions.checker import PermissionChecker
from openharness.tools.base import ToolExecutionContext
from openharness.tools.base import ToolRegistry

AUTO_COMPACT_STATUS_MESSAGE = "Auto-compacting conversation memory to keep things fast and focused."
REACTIVE_COMPACT_STATUS_MESSAGE = "Prompt too long; compacting conversation memory and retrying."

log = logging.getLogger(__name__)


PermissionPrompt = Callable[[str, str], Awaitable[bool]]
AskUserPrompt = Callable[[str], Awaitable[str]]

MAX_TRACKED_READ_FILES = 6
MAX_TRACKED_SKILLS = 8
MAX_TRACKED_ASYNC_AGENT_EVENTS = 8
MAX_TRACKED_WORK_LOG = 10
MAX_TRACKED_USER_GOALS = 5
MAX_TRACKED_ACTIVE_ARTIFACTS = 8
MAX_TRACKED_VERIFIED_WORK = 10
MAX_ARTIFACT_DISCOVERY_FILES = 5000
MAX_ARTIFACT_DISCOVERY_DEPTH = 4

ARTIFACT_DISCOVERY_EXTENSIONS = {
    ".bam",
    ".bed",
    ".bmp",
    ".c",
    ".cfg",
    ".conf",
    ".cpp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".fa",
    ".fasta",
    ".fastq",
    ".fq",
    ".gif",
    ".gff",
    ".gff3",
    ".gmt",
    ".go",
    ".gro",
    ".gtf",
    ".gz",
    ".h",
    ".h5",
    ".h5ad",
    ".hpp",
    ".htm",
    ".html",
    ".ico",
    ".ini",
    ".java",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".log",
    ".lua",
    ".m",
    ".maf",
    ".md",
    ".mlx",
    ".mol2",
    ".mtx",
    ".pdb",
    ".pdf",
    ".php",
    ".pl",
    ".png",
    ".pptx",
    ".py",
    ".r",
    ".rb",
    ".rdata",
    ".rds",
    ".rs",
    ".sam",
    ".scala",
    ".sh",
    ".sql",
    ".svg",
    ".swift",
    ".tab",
    ".tar",
    ".toml",
    ".ts",
    ".tsv",
    ".tsx",
    ".txt",
    ".vcf",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".xyz",
    ".yaml",
    ".yml",
    ".zip",
}
ARTIFACT_DISCOVERY_FILENAMES = {".env"}
ARTIFACT_DISCOVERY_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def _is_prompt_too_long_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        needle in text
        for needle in (
            "prompt too long",
            "context length",
            "maximum context",
            "context window",
            "too many tokens",
            "too large for the model",
            "maximum context length",
        )
    )


class MaxTurnsExceeded(RuntimeError):
    """Raised when the agent exceeds the configured max_turns for one user prompt."""

    def __init__(self, max_turns: int) -> None:
        super().__init__(f"Exceeded maximum turn limit ({max_turns})")
        self.max_turns = max_turns


@dataclass
class QueryContext:
    """Context shared across a query run."""

    api_client: SupportsStreamingMessages
    tool_registry: ToolRegistry
    permission_checker: PermissionChecker
    cwd: Path
    model: str
    system_prompt: str
    max_tokens: int
    context_window_tokens: int | None = None
    auto_compact_threshold_tokens: int | None = None
    permission_prompt: PermissionPrompt | None = None
    ask_user_prompt: AskUserPrompt | None = None
    max_turns: int | None = 200
    tool_execution_mode: str = "serial"
    hook_executor: HookExecutor | None = None
    tool_metadata: dict[str, object] | None = None


def _is_discoverable_artifact_path(path: Path) -> bool:
    name = path.name.lower()
    return name in ARTIFACT_DISCOVERY_FILENAMES or path.suffix.lower() in ARTIFACT_DISCOVERY_EXTENSIONS


def _iter_candidate_artifact_files(cwd: Path) -> list[Path]:
    candidates: list[Path] = []
    root_depth = len(cwd.parts)
    for dirpath, dirnames, filenames in os.walk(cwd):
        current = Path(dirpath)
        depth = len(current.parts) - root_depth
        if depth >= MAX_ARTIFACT_DISCOVERY_DEPTH:
            dirnames[:] = []
        else:
            dirnames[:] = [
                name
                for name in dirnames
                if name not in ARTIFACT_DISCOVERY_EXCLUDED_DIRS
                and not name.startswith(".")
            ]

        for filename in filenames:
            child = current / filename
            if not _is_discoverable_artifact_path(child):
                continue
            candidates.append(child)
            if len(candidates) >= MAX_ARTIFACT_DISCOVERY_FILES:
                return candidates
    return candidates


def _snapshot_artifacts(cwd: Path) -> dict[str, tuple[int, int]]:
    """Capture artifact-like files under cwd by relative path, size, and mtime."""
    snapshot: dict[str, tuple[int, int]] = {}
    for child in _iter_candidate_artifact_files(cwd):
        if not child.is_file():
            continue
        try:
            stat = child.stat()
            rel = str(child.relative_to(cwd))
        except OSError:
            continue
        snapshot[rel] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def _discover_artifacts_after_tool(
    cwd: Path,
    before: dict[str, tuple[int, int]],
    *,
    tool_label: str,
) -> list[dict[str, Any]]:
    after = _snapshot_artifacts(cwd)
    changed_paths = [
        rel_path
        for rel_path, fingerprint in after.items()
        if rel_path not in before or before[rel_path] != fingerprint
    ]
    changed_paths.sort(key=lambda rel_path: after[rel_path][1])

    refs: list[dict[str, Any]] = []
    for rel_path in changed_paths:
        path = cwd / rel_path
        try:
            stat = path.stat()
        except OSError:
            continue
        display_name = path.name if path.parent == cwd else rel_path
        mime, _ = mimetypes.guess_type(display_name)
        absolute_path = str(path.resolve())
        refs.append(
            {
                "name": display_name,
                "path": absolute_path,
                "size": stat.st_size,
                "size_bytes": stat.st_size,
                "mime_type": mime or "application/octet-stream",
                "url": "/api/artifacts/file?path="
                f"{urllib.parse.quote(absolute_path, safe='')}",
                "version_label": f"{tool_label} - {display_name}",
            }
        )
    return refs


def _merge_output_file_metadata(metadata: dict[str, Any], discovered: list[dict[str, Any]]) -> dict[str, Any]:
    if not discovered:
        return metadata

    next_metadata = dict(metadata)
    existing = next_metadata.get("output_files")
    output_files = list(existing) if isinstance(existing, list) else []
    seen: set[str] = set()
    for file_ref in output_files:
        if not isinstance(file_ref, dict):
            continue
        key = str(file_ref.get("url") or file_ref.get("path") or file_ref.get("name") or "")
        if key:
            seen.add(key)

    for file_ref in discovered:
        key = str(file_ref.get("url") or file_ref.get("path") or file_ref.get("name") or "")
        if key and key in seen:
            continue
        output_files.append(file_ref)
        if key:
            seen.add(key)
    next_metadata["output_files"] = output_files
    return next_metadata


def _append_capped_unique(bucket: list[Any], value: Any, *, limit: int) -> None:
    if value in bucket:
        bucket.remove(value)
    bucket.append(value)
    if len(bucket) > limit:
        del bucket[:-limit]


def _task_focus_state(tool_metadata: dict[str, object] | None) -> dict[str, object]:
    if tool_metadata is None:
        return {}
    value = tool_metadata.setdefault(
        "task_focus_state",
        {
            "goal": "",
            "recent_goals": [],
            "active_artifacts": [],
            "verified_state": [],
            "next_step": "",
        },
    )
    if isinstance(value, dict):
        value.setdefault("goal", "")
        value.setdefault("recent_goals", [])
        value.setdefault("active_artifacts", [])
        value.setdefault("verified_state", [])
        value.setdefault("next_step", "")
        return value
    replacement = {
        "goal": "",
        "recent_goals": [],
        "active_artifacts": [],
        "verified_state": [],
        "next_step": "",
    }
    tool_metadata["task_focus_state"] = replacement
    return replacement


def _summarize_focus_text(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    return normalized[:240]


def remember_user_goal(
    tool_metadata: dict[str, object] | None,
    prompt: str,
) -> None:
    state = _task_focus_state(tool_metadata)
    summary = _summarize_focus_text(prompt)
    if not summary:
        return
    recent_goals = state.setdefault("recent_goals", [])
    if isinstance(recent_goals, list):
        _append_capped_unique(recent_goals, summary, limit=MAX_TRACKED_USER_GOALS)
    state["goal"] = summary


def _remember_active_artifact(
    tool_metadata: dict[str, object] | None,
    artifact: str,
) -> None:
    normalized = artifact.strip()
    if not normalized:
        return
    state = _task_focus_state(tool_metadata)
    artifacts = state.setdefault("active_artifacts", [])
    if isinstance(artifacts, list):
        _append_capped_unique(artifacts, normalized[:240], limit=MAX_TRACKED_ACTIVE_ARTIFACTS)


def _remember_verified_work(
    tool_metadata: dict[str, object] | None,
    entry: str,
) -> None:
    normalized = entry.strip()
    if not normalized:
        return
    bucket = _tool_metadata_bucket(tool_metadata, "recent_verified_work")
    _append_capped_unique(bucket, normalized[:320], limit=MAX_TRACKED_VERIFIED_WORK)
    state = _task_focus_state(tool_metadata)
    verified_state = state.setdefault("verified_state", [])
    if isinstance(verified_state, list):
        _append_capped_unique(verified_state, normalized[:320], limit=MAX_TRACKED_VERIFIED_WORK)


def _tool_metadata_bucket(
    tool_metadata: dict[str, object] | None,
    key: str,
) -> list[Any]:
    if tool_metadata is None:
        return []
    value = tool_metadata.setdefault(key, [])
    if isinstance(value, list):
        return value
    replacement: list[Any] = []
    tool_metadata[key] = replacement
    return replacement


def _remember_read_file(
    tool_metadata: dict[str, object] | None,
    *,
    path: str,
    offset: int,
    limit: int,
    output: str,
) -> None:
    bucket = _tool_metadata_bucket(tool_metadata, "read_file_state")
    preview_lines = [line.strip() for line in output.splitlines()[:6] if line.strip()]
    entry = {
        "path": path,
        "span": f"lines {offset + 1}-{offset + limit}",
        "preview": " | ".join(preview_lines)[:320],
        "timestamp": time.time(),
    }
    if isinstance(bucket, list):
        bucket[:] = [
            existing
            for existing in bucket
            if not isinstance(existing, dict) or str(existing.get("path") or "") != path
        ]
        bucket.append(entry)
        if len(bucket) > MAX_TRACKED_READ_FILES:
            del bucket[:-MAX_TRACKED_READ_FILES]


def _remember_skill_invocation(
    tool_metadata: dict[str, object] | None,
    *,
    skill_name: str,
) -> None:
    bucket = _tool_metadata_bucket(tool_metadata, "invoked_skills")
    normalized = skill_name.strip()
    if not normalized:
        return
    if normalized in bucket:
        bucket.remove(normalized)
    bucket.append(normalized)
    if len(bucket) > MAX_TRACKED_SKILLS:
        del bucket[:-MAX_TRACKED_SKILLS]


def _remember_async_agent_activity(
    tool_metadata: dict[str, object] | None,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    output: str,
) -> None:
    bucket = _tool_metadata_bucket(tool_metadata, "async_agent_state")
    if tool_name == "agent":
        description = str(tool_input.get("description") or tool_input.get("prompt") or "").strip()
        summary = f"Spawned async agent. {description}".strip()
        if output.strip():
            summary = f"{summary} [{output.strip()[:180]}]".strip()
    elif tool_name == "send_message":
        target = str(tool_input.get("task_id") or "").strip()
        summary = f"Sent follow-up message to async agent {target}".strip()
    else:
        summary = output.strip()[:220] or f"Async agent activity via {tool_name}"
    bucket.append(summary)
    if len(bucket) > MAX_TRACKED_ASYNC_AGENT_EVENTS:
        del bucket[:-MAX_TRACKED_ASYNC_AGENT_EVENTS]


def _remember_work_log(
    tool_metadata: dict[str, object] | None,
    *,
    entry: str,
) -> None:
    bucket = _tool_metadata_bucket(tool_metadata, "recent_work_log")
    normalized = entry.strip()
    if not normalized:
        return
    bucket.append(normalized[:320])
    if len(bucket) > MAX_TRACKED_WORK_LOG:
        del bucket[:-MAX_TRACKED_WORK_LOG]


def _update_plan_mode(tool_metadata: dict[str, object] | None, mode: str) -> None:
    if tool_metadata is None:
        return
    tool_metadata["permission_mode"] = mode


def _record_tool_carryover(
    context: QueryContext,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    tool_output: str,
    is_error: bool,
    resolved_file_path: str | None,
) -> None:
    if is_error:
        return
    if resolved_file_path is not None:
        _remember_active_artifact(context.tool_metadata, resolved_file_path)
    if tool_name == "read_file" and resolved_file_path is not None:
        offset = int(tool_input.get("offset") or 0)
        limit = int(tool_input.get("limit") or 200)
        _remember_read_file(
            context.tool_metadata,
            path=resolved_file_path,
            offset=offset,
            limit=limit,
            output=tool_output,
        )
        _remember_verified_work(
            context.tool_metadata,
            f"Inspected file {resolved_file_path} (lines {offset + 1}-{offset + limit})",
        )
    elif tool_name == "skill":
        _remember_skill_invocation(
            context.tool_metadata,
            skill_name=str(tool_input.get("name") or ""),
        )
        skill_name = str(tool_input.get("name") or "").strip()
        if skill_name:
            _remember_active_artifact(context.tool_metadata, f"skill:{skill_name}")
            _remember_verified_work(context.tool_metadata, f"Loaded skill {skill_name}")
    elif tool_name in {"agent", "send_message"}:
        _remember_async_agent_activity(
            context.tool_metadata,
            tool_name=tool_name,
            tool_input=tool_input,
            output=tool_output,
        )
        description = str(tool_input.get("description") or tool_input.get("prompt") or tool_name).strip()
        _remember_verified_work(
            context.tool_metadata,
            f"Confirmed async-agent activity via {tool_name}: {description[:180]}",
        )
    elif tool_name == "enter_plan_mode":
        _update_plan_mode(context.tool_metadata, "plan")
    elif tool_name == "exit_plan_mode":
        _update_plan_mode(context.tool_metadata, "default")
    elif tool_name == "web_fetch":
        url = str(tool_input.get("url") or "").strip()
        if url:
            _remember_active_artifact(context.tool_metadata, url)
            _remember_verified_work(context.tool_metadata, f"Fetched remote content from {url}")
    elif tool_name == "web_search":
        query = str(tool_input.get("query") or "").strip()
        if query:
            _remember_verified_work(context.tool_metadata, f"Ran web search for {query[:180]}")
    elif tool_name == "glob":
        pattern = str(tool_input.get("pattern") or "").strip()
        if pattern:
            _remember_verified_work(context.tool_metadata, f"Expanded glob pattern {pattern[:180]}")
    elif tool_name == "grep":
        pattern = str(tool_input.get("pattern") or "").strip()
        if pattern:
            _remember_verified_work(context.tool_metadata, f"Checked repository matches for grep pattern {pattern[:180]}")
    elif tool_name == "bash":
        command = str(tool_input.get("command") or "").strip()
        summary = tool_output.splitlines()[0].strip() if tool_output.strip() else "no output"
        _remember_verified_work(
            context.tool_metadata,
            f"Ran bash command {command[:160]} [{summary[:120]}]",
        )
    if tool_name == "read_file" and resolved_file_path is not None:
        _remember_work_log(
            context.tool_metadata,
            entry=f"Read file {resolved_file_path}",
        )
    elif tool_name == "bash":
        command = str(tool_input.get("command") or "").strip()
        summary = tool_output.splitlines()[0].strip() if tool_output.strip() else "no output"
        _remember_work_log(
            context.tool_metadata,
            entry=f"Ran bash: {command[:160]} [{summary[:120]}]",
        )
    elif tool_name == "grep":
        pattern = str(tool_input.get("pattern") or "").strip()
        _remember_work_log(
            context.tool_metadata,
            entry=f"Searched with grep pattern={pattern[:160]}",
        )
    elif tool_name == "skill":
        _remember_work_log(
            context.tool_metadata,
            entry=f"Loaded skill {str(tool_input.get('name') or '').strip()}",
        )
    elif tool_name in {"agent", "send_message"}:
        _remember_work_log(
            context.tool_metadata,
            entry=f"Async agent action via {tool_name}",
        )
    elif tool_name == "enter_plan_mode":
        _remember_work_log(context.tool_metadata, entry="Entered plan mode")
    elif tool_name == "exit_plan_mode":
        _remember_work_log(context.tool_metadata, entry="Exited plan mode")


async def run_query(
    context: QueryContext,
    messages: list[ConversationMessage],
) -> AsyncIterator[tuple[StreamEvent, UsageSnapshot | None]]:
    """Run the conversation loop until the model stops requesting tools.

    Auto-compaction is checked at the start of each turn.  When the
    estimated token count exceeds the model's auto-compact threshold,
    the engine first tries a cheap microcompact (clearing old tool result
    content) and, if that is not enough, performs a full LLM-based
    summarization of older messages.
    """
    from openharness.services.compact import (
        AutoCompactState,
        auto_compact_if_needed,
    )

    compact_state = AutoCompactState()
    reactive_compact_attempted = False
    last_compaction_result: tuple[list[ConversationMessage], bool] = (messages, False)

    async def _stream_compaction(
        *,
        trigger: str,
        force: bool = False,
    ) -> AsyncIterator[tuple[StreamEvent, UsageSnapshot | None]]:
        nonlocal last_compaction_result
        progress_queue: asyncio.Queue[CompactProgressEvent] = asyncio.Queue()

        async def _progress(event: CompactProgressEvent) -> None:
            await progress_queue.put(event)

        task = asyncio.create_task(
            auto_compact_if_needed(
                messages,
                api_client=context.api_client,
                model=context.model,
                system_prompt=context.system_prompt,
                state=compact_state,
                progress_callback=_progress,
                force=force,
                trigger=trigger,
                hook_executor=context.hook_executor,
                carryover_metadata=context.tool_metadata,
                context_window_tokens=context.context_window_tokens,
                auto_compact_threshold_tokens=context.auto_compact_threshold_tokens,
            )
        )
        while True:
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=0.05)
                yield event, None
            except asyncio.TimeoutError:
                if task.done():
                    break
                continue
        while not progress_queue.empty():
            yield progress_queue.get_nowait(), None
        last_compaction_result = await task
        return

    turn_count = 0
    while context.max_turns is None or turn_count < context.max_turns:
        turn_count += 1
        # --- auto-compact check before calling the model ---------------
        async for event, usage in _stream_compaction(trigger="auto"):
            yield event, usage
        messages, was_compacted = last_compaction_result
        # ---------------------------------------------------------------

        final_message: ConversationMessage | None = None
        usage = UsageSnapshot()

        try:
            async for event in context.api_client.stream_message(
                ApiMessageRequest(
                    model=context.model,
                    messages=messages,
                    system_prompt=context.system_prompt,
                    max_tokens=context.max_tokens,
                    tools=context.tool_registry.to_api_schema(),
                )
            ):
                if isinstance(event, ApiTextDeltaEvent):
                    yield AssistantTextDelta(text=event.text), None
                    continue
                if isinstance(event, ApiRetryEvent):
                    yield StatusEvent(
                        message=(
                            f"Request failed; retrying in {event.delay_seconds:.1f}s "
                            f"(attempt {event.attempt + 1} of {event.max_attempts}): {event.message}"
                        )
                    ), None
                    continue

                if isinstance(event, ApiMessageCompleteEvent):
                    final_message = event.message
                    usage = event.usage
        except Exception as exc:
            error_msg = str(exc)
            if not reactive_compact_attempted and _is_prompt_too_long_error(exc):
                reactive_compact_attempted = True
                yield StatusEvent(message=REACTIVE_COMPACT_STATUS_MESSAGE), None
                async for event, usage in _stream_compaction(trigger="reactive", force=True):
                    yield event, usage
                messages, was_compacted = last_compaction_result
                if was_compacted:
                    continue
            if "connect" in error_msg.lower() or "timeout" in error_msg.lower() or "network" in error_msg.lower():
                yield ErrorEvent(message=f"Network error: {error_msg}. Check your internet connection and try again."), None
            else:
                yield ErrorEvent(message=f"API error: {error_msg}"), None
            return

        if final_message is None:
            raise RuntimeError("Model stream finished without a final message")

        coordinator_context_message: ConversationMessage | None = None
        if context.system_prompt.startswith("You are a **coordinator**."):
            if messages and messages[-1].role == "user" and messages[-1].text.startswith("# Coordinator User Context"):
                coordinator_context_message = messages.pop()

        if final_message.role == "assistant" and final_message.is_effectively_empty():
            log.warning("dropping empty assistant message from provider response")
            yield ErrorEvent(
                message=(
                    "Model returned an empty assistant message. "
                    "The turn was ignored to keep the session healthy."
                )
            ), usage
            return

        messages.append(final_message)
        yield AssistantTurnComplete(message=final_message, usage=usage), usage

        if coordinator_context_message is not None:
            messages.append(coordinator_context_message)

        if not final_message.tool_uses:
            return

        tool_calls = final_message.tool_uses

        execution_mode = str(context.tool_execution_mode or "serial").strip().lower()
        use_parallel_tools = execution_mode == "parallel"

        if len(tool_calls) == 1 or not use_parallel_tools:
            # Single tool: sequential (stream events immediately)
            tool_results = []
            for tc in tool_calls:
                yield ToolExecutionStarted(
                    tool_name=tc.name, tool_input=tc.input, tool_use_id=tc.id,
                ), None
                tool_task = asyncio.create_task(_execute_tool_call(context, tc.name, tc.id, tc.input))
                try:
                    result = await tool_task
                except asyncio.CancelledError:
                    result = _user_controlled_tool_result(context, tool_name=tc.name, tool_use_id=tc.id)
                    if result is None:
                        raise
                yield ToolExecutionCompleted(
                    tool_name=tc.name,
                    output=result.content,
                    is_error=result.is_error,
                    tool_use_id=tc.id,
                    metadata=getattr(result, "metadata", None),
                ), None
                tool_results.append(result)
        else:
            # Multiple tools: execute concurrently, emit events after
            for tc in tool_calls:
                yield ToolExecutionStarted(
                    tool_name=tc.name, tool_input=tc.input, tool_use_id=tc.id,
                ), None

            async def _run(tc):
                return await _execute_tool_call(context, tc.name, tc.id, tc.input)

            # Use return_exceptions=True so a single failing tool does not abandon
            # its siblings as cancelled coroutines and leave the conversation with
            # un-replied tool_use blocks (Anthropic's API rejects the next request
            # on the session if any tool_use is missing a matching tool_result).
            tool_tasks = [asyncio.create_task(_run(tc)) for tc in tool_calls]
            raw_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
            tool_results = []
            for tc, result in zip(tool_calls, raw_results):
                if isinstance(result, asyncio.CancelledError):
                    controlled = _user_controlled_tool_result(
                        context,
                        tool_name=tc.name,
                        tool_use_id=tc.id,
                    )
                    if controlled is not None:
                        tool_results.append(controlled)
                        continue
                if isinstance(result, BaseException):
                    log.exception(
                        "tool execution raised: name=%s id=%s",
                        tc.name,
                        tc.id,
                        exc_info=result,
                    )
                    result = ToolResultBlock(
                        tool_use_id=tc.id,
                        content=f"Tool {tc.name} failed: {type(result).__name__}: {result}",
                        is_error=True,
                    )
                tool_results.append(result)

            for tc, result in zip(tool_calls, tool_results):
                yield ToolExecutionCompleted(
                    tool_name=tc.name,
                    output=result.content,
                    is_error=result.is_error,
                    tool_use_id=tc.id,
                    metadata=getattr(result, "metadata", None),
                ), None

        messages.append(ConversationMessage(role="user", content=tool_results))
        runtime_control_state = (context.tool_metadata or {}).get("_runtime_control_state")
        if isinstance(runtime_control_state, dict):
            targeted_tool_id = runtime_control_state.get("target_tool_use_id")
            handled_target = (
                targeted_tool_id is None
                or any(getattr(result, "tool_use_id", None) == targeted_tool_id for result in tool_results)
            )
            if handled_target and runtime_control_state.get("action") == "skip":
                runtime_control_state.clear()
            stop_after_tool = bool(runtime_control_state.get("abort_after_tool"))
            if stop_after_tool and handled_target:
                runtime_control_state.clear()
                return

    if context.max_turns is not None:
        raise MaxTurnsExceeded(context.max_turns)
    raise RuntimeError("Query loop exited without a max_turns limit or final response")


async def _execute_tool_call(
    context: QueryContext,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, object],
) -> ToolResultBlock:
    if context.hook_executor is not None:
        pre_hooks = await context.hook_executor.execute(
            HookEvent.PRE_TOOL_USE,
            {"tool_name": tool_name, "tool_input": tool_input, "event": HookEvent.PRE_TOOL_USE.value},
        )
        if pre_hooks.blocked:
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=pre_hooks.reason or f"pre_tool_use hook blocked {tool_name}",
                is_error=True,
            )

    log.debug("tool_call start: %s id=%s", tool_name, tool_use_id)

    tool = context.tool_registry.get(tool_name)
    if tool is None:
        log.warning("unknown tool: %s", tool_name)
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=f"Unknown tool: {tool_name}",
            is_error=True,
        )

    try:
        parsed_input = tool.input_model.model_validate(tool_input)
    except Exception as exc:
        log.warning("invalid input for %s: %s", tool_name, exc)
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=f"Invalid input for {tool_name}: {exc}",
            is_error=True,
        )
    await _notify_running_task(
        context,
        tool_name=tool_name,
        tool_use_id=tool_use_id,
    )

    # Normalize common tool inputs before permission checks so path rules apply
    # consistently across built-in tools that use `file_path`, `path`, or
    # directory-scoped roots such as `glob`/`grep`.
    _file_path = _resolve_permission_file_path(context.cwd, tool_input, parsed_input)
    _command = _extract_permission_command(tool_input, parsed_input)
    read_only = tool.is_read_only(parsed_input)
    log.debug("permission check: %s read_only=%s path=%s cmd=%s",
              tool_name, read_only, _file_path, _command and _command[:80])
    decision = context.permission_checker.evaluate(
        tool_name,
        is_read_only=read_only,
        file_path=_file_path,
        command=_command,
    )
    if not decision.allowed:
        if decision.requires_confirmation and context.permission_prompt is not None:
            log.debug("permission prompt for %s: %s", tool_name, decision.reason)
            confirmed = await context.permission_prompt(tool_name, decision.reason)
            if not confirmed:
                log.debug("permission denied by user for %s", tool_name)
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    content=decision.reason or f"Permission denied for {tool_name}",
                    is_error=True,
                )
        else:
            log.debug("permission blocked for %s: %s", tool_name, decision.reason)
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=decision.reason or f"Permission denied for {tool_name}",
                is_error=True,
            )

    log.debug("executing %s ...", tool_name)
    artifact_snapshot = _snapshot_artifacts(context.cwd) if not read_only else {}
    t0 = time.monotonic()
    result = await tool.execute(
        parsed_input,
        ToolExecutionContext(
            cwd=context.cwd,
            metadata={
                "tool_registry": context.tool_registry,
                "ask_user_prompt": context.ask_user_prompt,
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                **(context.tool_metadata or {}),
            },
        ),
    )
    elapsed = time.monotonic() - t0
    log.debug("executed %s in %.2fs err=%s output_len=%d",
              tool_name, elapsed, result.is_error, len(result.output or ""))
    discovered_artifacts = (
        _discover_artifacts_after_tool(context.cwd, artifact_snapshot, tool_label=tool_name)
        if not read_only
        else []
    )
    result_metadata = _merge_output_file_metadata(result.metadata or {}, discovered_artifacts)
    auto_memory = _auto_save_environment_failure_memory(
        context,
        tool_name=tool_name,
        tool_input=tool_input,
        output=result.output,
        is_error=result.is_error,
    )
    tool_result = ToolResultBlock(
        tool_use_id=tool_use_id,
        content=_append_memory_hint_for_failed_environment_tool(
            tool_name,
            tool_input,
            result.output,
            result.is_error,
            context,
            auto_memory=auto_memory,
        ),
        is_error=result.is_error,
        metadata=result_metadata,
    )
    _record_tool_carryover(
        context,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_result.content,
        is_error=tool_result.is_error,
        resolved_file_path=_file_path,
    )
    if context.hook_executor is not None:
        await context.hook_executor.execute(
            HookEvent.POST_TOOL_USE,
            {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_result.content,
                "tool_is_error": tool_result.is_error,
                "event": HookEvent.POST_TOOL_USE.value,
            },
        )
    return tool_result


async def _notify_running_task(
    context: QueryContext,
    *,
    tool_name: str,
    tool_use_id: str,
) -> None:
    hook = (context.tool_metadata or {}).get("_register_running_task")
    if not callable(hook):
        return
    task = asyncio.current_task()
    if task is None:
        return
    result = hook(
        tool_use_id=tool_use_id,
        tool_name=tool_name,
        task=task,
    )
    if inspect.isawaitable(result):
        await result


def _user_controlled_tool_result(
    context: QueryContext,
    *,
    tool_name: str,
    tool_use_id: str,
) -> ToolResultBlock | None:
    control_state = (context.tool_metadata or {}).get("_runtime_control_state")
    if not isinstance(control_state, dict):
        return None
    target = control_state.get("target_tool_use_id")
    if target not in {None, tool_use_id}:
        return None
    action = str(control_state.get("action") or "").strip().lower()
    if action == "skip":
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=(
                f"{tool_name} was skipped by the user because the step appeared stuck or needed follow-up. "
                "Do not retry the same step unchanged. Choose a safer, non-interactive, or narrower alternative."
            ),
            is_error=True,
            metadata={"interrupted_by_user": True, "user_action": "skip"},
        )
    if action == "stop":
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=f"{tool_name} was cancelled by the user.",
            is_error=True,
            metadata={"interrupted_by_user": True, "user_action": "stop"},
        )
    return None


def _append_memory_hint_for_failed_environment_tool(
    tool_name: str,
    tool_input: dict[str, object],
    output: str,
    is_error: bool,
    context: QueryContext,
    *,
    auto_memory: str | None = None,
) -> str:
    """Nudge the model to persist stable environment failures without preloading memory."""
    if not is_error or tool_name not in {"bash", "sandbox_exec"}:
        return output
    if context.tool_registry.get("memory") is None:
        return output
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return output
    if auto_memory:
        return (
            (output or "").rstrip()
            + f"\n\n[Persistent memory: saved known_failure memory `{auto_memory}` for future sessions.]"
        )
    hint = (
        "\n\n[Memory hint: If this failure reflects a stable fact about the user's "
        "environment, Docker/OpenSandbox setup, installed bioinformatics tools, paths, "
        "or permissions, save a compact known_failure memory with the failed command "
        "pattern and a working alternative. Do not save transient task progress or raw logs.]"
    )
    return (output or "").rstrip() + hint


_STABLE_FAILURE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"command not found|not recognized as an internal|executable file not found", re.I), "command_unavailable"),
    (re.compile(r"no such file or directory|cannot stat|path does not exist", re.I), "missing_path"),
    (re.compile(r"permission denied|operation not permitted", re.I), "permission"),
    (re.compile(r"no module named|module not found|package .* is not installed", re.I), "missing_package"),
    (re.compile(r"docker:.*not found|image .* not found|no such container|cannot connect to the docker daemon", re.I), "docker"),
    (re.compile(r"opensandbox|sandbox execution error|environment .* not found", re.I), "opensandbox"),
)


def _classify_stable_environment_failure(output: str) -> str | None:
    for pattern, failure_type in _STABLE_FAILURE_PATTERNS:
        if pattern.search(output):
            return failure_type
    return None


def _auto_save_environment_failure_memory(
    context: QueryContext,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    output: str,
    is_error: bool,
) -> str | None:
    """Persist compact known failures that are likely stable environment facts."""
    if not is_error or tool_name not in {"bash", "sandbox_exec"}:
        return None
    if context.tool_registry.get("memory") is None:
        return None
    command = str(tool_input.get("command") or "").strip()
    if not command:
        return None
    failure_type = _classify_stable_environment_failure(output or "")
    if failure_type is None:
        return None

    digest = hashlib.sha1(f"{tool_name}\n{command}\n{failure_type}".encode("utf-8")).hexdigest()[:10]
    title = f"Known failure {failure_type} {digest}"
    lesson = _build_failure_memory_content(
        context,
        tool_name=tool_name,
        command=command,
        output=output or "",
        failure_type=failure_type,
    )
    keywords = _memory_keywords_from_failure(command, output or "", failure_type)
    try:
        path = add_structured_memory_entry(
            context.cwd,
            title=title,
            content=lesson,
            memory_type="known_failure",
            scope="opensandbox" if tool_name == "sandbox_exec" else "host",
            keywords=keywords,
            priority="high",
        )
        return path.name
    except Exception as exc:
        log.debug("auto memory save failed for %s: %s", tool_name, exc)
        return None


def _build_failure_memory_content(
    context: QueryContext,
    *,
    tool_name: str,
    command: str,
    output: str,
    failure_type: str,
) -> str:
    goal = ""
    state = _task_focus_state(context.tool_metadata)
    if isinstance(state.get("goal"), str):
        goal = state["goal"]
    failure_line = _first_interesting_failure_line(output)
    lines = [
        f"Known failure type: {failure_type}",
        f"Tool: {tool_name}",
        f"Failed command pattern: `{_compact_command(command)}`",
    ]
    if goal:
        lines.append(f"User task when observed: {goal}")
    if failure_line:
        lines.append(f"Failure signal: {failure_line}")
    lines.append(
        "Lesson: Do not repeat this command pattern in future sessions without changing the environment or choosing a verified alternative."
    )
    return "\n".join(lines)


def _first_interesting_failure_line(output: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(word in stripped.lower() for word in ("error", "not found", "permission", "no such", "module")):
            return stripped[:300]
    return " ".join(output.split())[:300]


def _compact_command(command: str) -> str:
    compact = " ".join(command.split())
    return compact[:240]


def _memory_keywords_from_failure(command: str, output: str, failure_type: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_.-]{3,}", f"{command} {output}")
    blocked = {"usr", "bin", "env", "the", "and", "for", "with", "error", "failed"}
    keywords: list[str] = [failure_type]
    for token in tokens:
        lowered = token.lower().strip(".")
        if lowered in blocked or lowered.isdigit():
            continue
        if lowered not in keywords:
            keywords.append(lowered)
        if len(keywords) >= 12:
            break
    return keywords


def _resolve_permission_file_path(
    cwd: Path,
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    for key in ("file_path", "path", "root"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = cwd / path
            return str(path.resolve())

    for attr in ("file_path", "path", "root"):
        value = getattr(parsed_input, attr, None)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = cwd / path
            return str(path.resolve())

    return None


def _extract_permission_command(
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    value = raw_input.get("command")
    if isinstance(value, str) and value.strip():
        return value

    value = getattr(parsed_input, "command", None)
    if isinstance(value, str) and value.strip():
        return value

    return None
