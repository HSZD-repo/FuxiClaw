"""Execute commands inside an OpenSandbox-managed Docker container."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from hashlib import sha1
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.sandbox.opensandbox_models import TaskStatus
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult, register_step_cancel_handle


class SandboxExecInput(BaseModel):
    environment: str = Field(description="Sandbox environment name (e.g. 'bioinformatics')")
    command: str = Field(description="Shell command to execute inside the container")
    timeout: int = Field(default=300, ge=1, le=3600, description="Timeout in seconds")
    background: bool = Field(
        default=False,
        description="Run as background task (returns task_id; poll with sandbox_status)",
    )


class SandboxExecTool(BaseTool):
    """Run commands in a prebuilt container via OpenSandbox (opensandbox SDK + server)."""

    name = "sandbox_exec"
    description = (
        "Execute a command inside an OpenSandbox Docker container with a configured image "
        "(see sandboxes/envs.yaml). The container persists for the current session. "
        "Use sandbox_list_envs first to pick an environment. "
        "User-attached files for this turn are copied to /workspace/uploads/ before the command runs. "
        "Write outputs under /workspace/output for host mirroring. "
        "For long commands use background=true, then sandbox_status with the task_id."
    )
    input_model = SandboxExecInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return False

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
                    "version_label": f"sandbox_exec · {dest.name}",
                }
            )
        return published

    async def execute(self, arguments: SandboxExecInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from openharness.sandbox.opensandbox_bridge import get_shared_bridge, sdk_available
        except ImportError:
            return ToolResult(
                output="OpenSandbox bridge failed to load.",
                is_error=True,
            )

        if not sdk_available:
            return ToolResult(
                output=(
                    "opensandbox SDK is not installed. Install with: "
                    "pip install 'openharness-ai[opensandbox]' or pip install opensandbox"
                ),
                is_error=True,
            )

        session_id = str(context.metadata.get("session_id") or "default")

        try:
            bridge = get_shared_bridge()

            attachments = context.metadata.get("attachments", [])
            injected: list[str] = []
            if attachments:
                paths = [a["path"] for a in attachments if isinstance(a, dict) and a.get("path")]
                if paths:
                    injected = await bridge.inject_files(arguments.environment, session_id, paths)

            if arguments.background:
                task_id = await bridge.exec_background(
                    arguments.environment,
                    session_id,
                    arguments.command,
                )
                await register_step_cancel_handle(
                    context,
                    lambda **_: bridge.cancel_task(task_id),
                    kind="sandbox_task",
                    label=f"sandbox task {task_id}",
                )
                return ToolResult(
                    output=json.dumps({"task_id": task_id, "status": "running"}, indent=2),
                    metadata={"task_id": task_id},
                )

            task_id = await bridge.exec_background(
                arguments.environment,
                session_id,
                arguments.command,
            )
            await register_step_cancel_handle(
                context,
                lambda **_: bridge.cancel_task(task_id),
                kind="sandbox_task",
                label=f"sandbox task {task_id}",
            )

            deadline = time.monotonic() + arguments.timeout
            while True:
                info = await bridge.poll_task(task_id)
                if info.status != TaskStatus.RUNNING:
                    result_output = info.output
                    result_exit_code = info.exit_code if info.exit_code is not None else 0
                    result_output_files = info.output_files
                    break
                if time.monotonic() >= deadline:
                    await bridge.cancel_task(task_id)
                    return ToolResult(
                        output=f"Sandbox command timed out after {arguments.timeout} seconds.\n\nPartial output:\n{info.output or '(no output)'}",
                        is_error=True,
                        metadata={
                            "task_id": task_id,
                            "timed_out": True,
                            "environment": arguments.environment,
                            "session_id": session_id,
                        },
                    )
                await asyncio.sleep(1.0)

            output_parts: list[str] = []
            if injected:
                names = [Path(p).name for p in injected]
                output_parts.append(
                    f"[Injected {len(injected)} file(s) into /workspace/uploads/: {', '.join(names)}]"
                )
            output_parts.append(result_output)
            if result_output_files:
                output_parts.append("\n--- Output Files ---")
                for f in result_output_files:
                    output_parts.append(f"  {f.name} ({f.size} bytes, {f.mime_type})")

            file_dicts = self._publish_output_files(
                cwd=context.cwd,
                session_id=session_id,
                files=result_output_files,
            )

            return ToolResult(
                output="\n".join(output_parts),
                is_error=result_exit_code != 0,
                metadata={
                    "exit_code": result_exit_code,
                    "output_files": file_dicts,
                    "environment": arguments.environment,
                    "session_id": session_id,
                    "injected_files": injected,
                    "task_id": task_id,
                },
            )
        except Exception as exc:
            return ToolResult(output=f"Sandbox execution error: {exc}", is_error=True)
