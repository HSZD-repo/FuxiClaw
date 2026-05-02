"""WebSocket-backed host that reuses the full OpenHarness runtime/tool registry."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from openharness.engine.messages import ConversationMessage, sanitize_conversation_messages
from openharness.services.session_storage import list_session_snapshots, save_session_snapshot
from openharness.ui.backend_host import BackendHostConfig, ReactBackendHost
from openharness.ui.protocol import BackendEvent, FrontendRequest
from openharness.ui.runtime import refresh_runtime_client

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"}
MAX_INLINE_SIZE = 200_000


class WebBackendHost(ReactBackendHost):
    """Run the same runtime as the CLI/TUI, but over a Starlette WebSocket."""

    def __init__(
        self,
        config: BackendHostConfig,
        websocket: WebSocket,
        *,
        session_id_override: str | None = None,
        write_lock: asyncio.Lock | None = None,
    ) -> None:
        super().__init__(config)
        if write_lock is not None:
            self._write_lock = write_lock
        self._ws = websocket
        self._pending_attachments: list[dict[str, object]] = []
        self._session_id_override = session_id_override

    async def run(self) -> int:
        result = await super().run()
        return result

    async def _emit(self, event: BackendEvent) -> None:
        async with self._write_lock:
            try:
                if self._session_id_override and self._bundle is not None:
                    self.apply_session_id(self._session_id_override)
                    self._session_id_override = None
                payload = event.model_dump(exclude_none=True)
                if self._bundle is not None:
                    payload["session_id"] = self._bundle.session_id
                await self._ws.send_json(payload)
            except Exception:
                logger.warning("Failed to send event to WebSocket, connection may be closed")
                self._running = False

    async def _read_requests(self) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return

    async def receive(self, request: FrontendRequest) -> None:
        if request.type == "permission_response" and request.request_id:
            if request.trust_session and request.allowed:
                self._enable_full_auto()
            fut = self._permission_requests.get(request.request_id)
            if fut and not fut.done():
                fut.set_result(bool(request.allowed))
            return

        if request.type == "question_response" and request.request_id:
            fut = self._question_requests.get(request.request_id)
            if fut and not fut.done():
                fut.set_result(request.answer or "")
            return

        if request.type == "step_control":
            await self._handle_step_control(request)
            return

        if request.type == "session_control":
            await self._handle_session_control(request)
            return

        if request.type == "refresh_settings":
            refreshed = await self.refresh_runtime_settings()
            if not refreshed:
                await self._emit(
                    BackendEvent(
                        type="error",
                        message="Settings saved. The current session is busy, so the new provider/model will apply on the next run.",
                    )
                )
            return

        if request.type == "submit_line" and request.attachments:
            self._pending_attachments = [
                {
                    "filename": a.filename,
                    "path": a.path,
                    "size": a.size,
                    "mime_type": a.mime_type,
                }
                for a in request.attachments
            ]
            request = self._expand_attachments(request)
        else:
            self._pending_attachments = []

        await self._request_queue.put(request)

    @staticmethod
    def _expand_attachments(request: FrontendRequest) -> FrontendRequest:
        if not request.attachments:
            return request

        parts: list[str] = []
        for att in request.attachments:
            ext = Path(att.filename).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                parts.append(f"[Attached image: {att.filename} ({att.size} bytes) at {att.path}]")
            else:
                parts.append(f"[Attached file: {att.filename} ({att.size} bytes) at {att.path}]")

        attachment_context = "\n\n".join(parts)
        user_text = request.line or ""
        combined = f"{attachment_context}\n\n{user_text}" if user_text else attachment_context

        return FrontendRequest(
            type=request.type,
            line=combined,
            command=request.command,
            value=request.value,
            request_id=request.request_id,
            allowed=request.allowed,
            trust_session=request.trust_session,
            answer=request.answer,
            attachments=None,
            session_id=request.session_id,
            summary=request.summary,
        )

    async def _process_line(self, line: str, *, transcript_line: str | None = None) -> bool:
        if self._bundle is not None and self._pending_attachments:
            self._bundle.engine.tool_metadata["attachments"] = self._pending_attachments
        try:
            should_continue = await super()._process_line(line, transcript_line=transcript_line)
            await self._emit_session_list()
            return should_continue
        finally:
            if self._bundle is not None:
                self._bundle.engine.tool_metadata.pop("attachments", None)
            self._pending_attachments = []

    async def _emit_session_list(self) -> None:
        if self._bundle is None:
            return
        async with self._write_lock:
            try:
                await self._ws.send_json(
                    {
                        "type": "session_list",
                        "sessions": list_session_snapshots(self._bundle.cwd),
                    }
                )
            except Exception:
                logger.warning("Failed to send session list to WebSocket")
                self._running = False

    @property
    def is_busy(self) -> bool:
        return self._busy

    async def refresh_runtime_settings(self) -> bool:
        """Reload provider/model/auth settings into the live runtime."""
        if self._bundle is None or self._busy:
            return False
        refresh_runtime_client(self._bundle)
        await self._emit(BackendEvent.state_snapshot(self._bundle.app_state.get()))
        return True

    def apply_session_id(self, session_id: str) -> None:
        """Rebind the live runtime to a specific persisted session id."""
        if self._bundle is None:
            return
        self._bundle.session_id = session_id
        self._bundle.engine.tool_metadata["session_id"] = session_id

    def load_snapshot_messages(self, messages: list[ConversationMessage]) -> None:
        if self._bundle is None:
            return
        self._bundle.engine.clear()
        self._bundle.engine.load_messages(messages)

    def save_snapshot(self) -> None:
        if self._bundle is None:
            return
        messages = sanitize_conversation_messages(self._bundle.engine.messages)
        if not messages:
            return
        save_session_snapshot(
            cwd=self._bundle.cwd,
            model=self._bundle.engine.model,
            system_prompt=self._bundle.engine.system_prompt,
            messages=messages,
            usage=self._bundle.engine.total_usage,
            session_id=self._bundle.session_id,
            tool_metadata=self._bundle.engine.tool_metadata,
        )

    async def stop(self) -> None:
        await self._request_queue.put(FrontendRequest(type="shutdown"))
