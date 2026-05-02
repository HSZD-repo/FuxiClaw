"""Poll status of a background OpenSandbox task."""

from __future__ import annotations

import json
import shutil
from hashlib import sha1
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SandboxStatusInput(BaseModel):
    task_id: str = Field(description="task_id returned by sandbox_exec with background=true")


class SandboxStatusTool(BaseTool):
    name = "sandbox_status"
    description = (
        "Poll a background sandbox task started with sandbox_exec(background=true). "
        "Returns status, logs, and output files when complete."
    )
    input_model = SandboxStatusInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return True

    @staticmethod
    def _session_output_dir(cwd: Path, session_id: str) -> Path:
        path = Path(cwd).resolve()
        digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
        root = Path.home() / ".openharness" / "data" / "web_sessions" / f"{path.name}-{digest}" / "output" / session_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _publish_output_files(
        cls,
        *,
        cwd: Path,
        session_id: str,
        files: list,
    ) -> list[dict[str, object]]:
        out_dir = cls._session_output_dir(cwd, session_id)
        published: list[dict[str, object]] = []
        for f in files:
            src = Path(str(f.path))
            if not src.is_file():
                continue
            dest = out_dir / (f.name or src.name)
            try:
                shutil.copy2(src, dest)
            except Exception:
                continue
            published.append(
                {
                    "name": dest.name,
                    "path": dest.name,
                    "size": dest.stat().st_size,
                    "size_bytes": dest.stat().st_size,
                    "mime_type": getattr(f, "mime_type", "application/octet-stream"),
                    "url": f"/api/session-output/{session_id}/{dest.name}",
                    "version_label": f"sandbox_status · {dest.name}",
                }
            )
        return published

    async def execute(self, arguments: SandboxStatusInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from openharness.sandbox.opensandbox_bridge import get_shared_bridge, sdk_available
            from openharness.sandbox.opensandbox_models import TaskStatus
        except ImportError:
            return ToolResult(output="OpenSandbox bridge failed to load.", is_error=True)

        if not sdk_available:
            return ToolResult(output="opensandbox SDK is not installed.", is_error=True)

        bridge = get_shared_bridge()

        session_id = str(context.metadata.get("session_id") or "default")
        info = await bridge.poll_task(arguments.task_id)

        payload = {
            "task_id": info.task_id,
            "status": info.status.value,
            "output": info.output,
            "exit_code": info.exit_code,
            "output_files": self._publish_output_files(
                cwd=context.cwd,
                session_id=session_id,
                files=info.output_files,
            ),
        }

        return ToolResult(
            output=json.dumps(payload, indent=2, ensure_ascii=False),
            is_error=info.status == TaskStatus.FAILED,
            metadata={
                "task_id": info.task_id,
                "sandbox_status": info.status.value,
                "output_files": payload["output_files"],
            },
        )
