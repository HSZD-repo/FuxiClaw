"""Bridge between OpenHarness tools and the OpenSandbox Python SDK."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from openharness.sandbox.opensandbox_envs import get_environment
from openharness.sandbox.opensandbox_models import ExecResult, OutputFile, TaskInfo, TaskStatus

logger = logging.getLogger(__name__)

try:
    from opensandbox import Sandbox
    from opensandbox.config.connection import ConnectionConfig
    from opensandbox.models.execd import ExecutionHandlers, RunCommandOpts

    _SDK_AVAILABLE = True
except ImportError:
    Sandbox = Any  # type: ignore[misc, assignment]
    ConnectionConfig = Any  # type: ignore[misc, assignment]
    ExecutionHandlers = Any  # type: ignore[misc, assignment]
    RunCommandOpts = Any  # type: ignore[misc, assignment]
    _SDK_AVAILABLE = False

_WORKSPACE_DIR = "/workspace"
_OUTPUT_DIR = f"{_WORKSPACE_DIR}/output"


def _get_connection_config() -> Any:
    if not _SDK_AVAILABLE:
        return None
    # Runtime import succeeded; ConnectionConfig is the real class.
    toml_path = Path.home() / ".sandbox.toml"
    if not toml_path.exists():
        return None
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        host = data.get("server", {}).get("host", "localhost")
        port = data.get("server", {}).get("port", 8080)
        return ConnectionConfig(domain=f"{host}:{port}")
    except Exception:
        return None


def _host_workspace(session_id: str) -> Path:
    d = Path.home() / ".openharness" / "sandbox-workspace" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


class OpenSandboxBridge:
    """Lifecycle + exec for OpenSandbox containers (one process)."""

    def __init__(self) -> None:
        if not _SDK_AVAILABLE:
            raise RuntimeError("opensandbox SDK is not installed. Install optional extra: opensandbox")
        self._sandboxes: dict[str, Sandbox] = {}
        self._background_tasks: dict[str, _BackgroundTask] = {}
        self._connection_config = _get_connection_config()

    async def create_or_reuse(self, env_name: str, session_id: str) -> Sandbox:
        key = f"{env_name}:{session_id}"
        if key in self._sandboxes:
            logger.debug("Reusing sandbox for %s", key)
            return self._sandboxes[key]

        env = get_environment(env_name)
        if env is None:
            raise ValueError(f"Unknown sandbox environment: {env_name!r}")

        resource = {
            "cpu": str(env.resources.cpu),
            "memory": env.resources.memory.upper().replace("G", "Gi"),
        }

        logger.info("Creating sandbox env=%s session=%s image=%s", env_name, session_id, env.image)
        create_kwargs: dict[str, Any] = {
            "timeout": None,
            "resource": resource,
            "env": {"OPENHARNESS_SESSION": session_id},
            "metadata": {"env": env_name, "session": session_id},
        }
        if self._connection_config is not None:
            create_kwargs["connection_config"] = self._connection_config
        sandbox = await Sandbox.create(env.image, **create_kwargs)

        await sandbox.commands.run(f"mkdir -p {_OUTPUT_DIR} /workspace/uploads")
        self._sandboxes[key] = sandbox
        logger.info("Sandbox created: id=%s", getattr(sandbox, "id", "?"))
        return sandbox

    async def _mirror_output_files_to_host(self, sandbox: Sandbox, session_id: str, files: list[OutputFile]) -> None:
        """Replace *files* entries with host paths under ~/.openharness/sandbox-workspace/.../output/."""
        if not files:
            return
        local_output = _host_workspace(session_id) / "output"
        local_output.mkdir(parents=True, exist_ok=True)
        for f in files:
            try:
                data = await sandbox.files.read_bytes(f.path)
                local_path = local_output / f.name
                local_path.write_bytes(data)
                f.path = str(local_path.resolve())
                f.size = len(data)
            except Exception:
                logger.warning("Failed to download output from sandbox: %s", f.path, exc_info=True)

    async def exec_command(
        self,
        env_name: str,
        session_id: str,
        command: str,
        *,
        timeout: int = 300,
    ) -> ExecResult:
        sandbox = await self.create_or_reuse(env_name, session_id)

        collected: list[str] = []

        async def _on_stdout(msg: Any) -> None:
            text = msg.text if hasattr(msg, "text") else str(msg)
            collected.append(text)

        handlers = ExecutionHandlers(on_stdout=_on_stdout, on_stderr=_on_stdout)
        opts = RunCommandOpts(
            timeout=timedelta(seconds=timeout),
            working_directory=_WORKSPACE_DIR,
        )

        execution = await sandbox.commands.run(command, opts=opts, handlers=handlers)

        exit_code = execution.exit_code if hasattr(execution, "exit_code") else 0
        output = "".join(collected) or (execution.text if hasattr(execution, "text") else "")

        output_files = await self._scan_output_files(sandbox)
        await self._mirror_output_files_to_host(sandbox, session_id, output_files)

        return ExecResult(
            output=output,
            exit_code=exit_code or 0,
            output_files=output_files,
        )

    async def exec_background(self, env_name: str, session_id: str, command: str) -> str:
        sandbox = await self.create_or_reuse(env_name, session_id)

        opts = RunCommandOpts(background=True, working_directory=_WORKSPACE_DIR)
        execution = await sandbox.commands.run(command, opts=opts)

        task_id = execution.id or str(uuid.uuid4())
        self._background_tasks[task_id] = _BackgroundTask(
            sandbox=sandbox,
            execution_id=task_id,
            env_name=env_name,
            session_id=session_id,
        )
        logger.info("Background task started: task_id=%s", task_id)
        return task_id

    async def poll_task(self, task_id: str) -> TaskInfo:
        bt = self._background_tasks.get(task_id)
        if bt is None:
            return TaskInfo(task_id=task_id, status=TaskStatus.FAILED, output=f"Unknown task: {task_id}")

        try:
            status = await bt.sandbox.commands.get_command_status(bt.execution_id)
        except Exception as exc:
            return TaskInfo(task_id=task_id, status=TaskStatus.FAILED, output=str(exc))

        running = status.running if status.running is not None else False
        exit_code = status.exit_code

        logs_text = ""
        try:
            logs = await bt.sandbox.commands.get_background_command_logs(bt.execution_id)
            logs_text = logs.content or ""
        except Exception:
            pass

        if running:
            return TaskInfo(task_id=task_id, status=TaskStatus.RUNNING, output=logs_text)

        output_files = await self._scan_output_files(bt.sandbox)
        await self._mirror_output_files_to_host(bt.sandbox, bt.session_id, output_files)

        task_status = TaskStatus.COMPLETED if (exit_code or 0) == 0 else TaskStatus.FAILED
        return TaskInfo(
            task_id=task_id,
            status=task_status,
            output=logs_text,
            exit_code=exit_code,
            output_files=output_files,
        )

    async def cancel_task(self, task_id: str) -> bool:
        bt = self._background_tasks.get(task_id)
        if bt is None:
            return False
        try:
            await bt.sandbox.commands.interrupt(bt.execution_id)
            logger.info("Task cancelled: %s", task_id)
            return True
        except Exception:
            logger.warning("Failed to cancel task %s", task_id, exc_info=True)
            return False

    async def _scan_output_files(self, sandbox: Sandbox) -> list[OutputFile]:
        try:
            result = await sandbox.commands.run(
                f'find {_OUTPUT_DIR} -type f -printf "%s %p\\n" 2>/dev/null || true'
            )
            text = result.text if hasattr(result, "text") else ""
            if hasattr(result, "logs") and result.logs and result.logs.stdout:
                text = "\n".join(m.text for m in result.logs.stdout)
        except Exception:
            return []

        files: list[OutputFile] = []
        for line in (text or "").strip().splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) != 2:
                continue
            size_str, filepath = parts
            name = filepath.rsplit("/", 1)[-1]
            mime, _ = mimetypes.guess_type(name)
            files.append(
                OutputFile(
                    path=filepath,
                    name=name,
                    size=int(size_str) if size_str.isdigit() else 0,
                    mime_type=mime or "application/octet-stream",
                )
            )
        return files

    async def inject_files(self, env_name: str, session_id: str, file_paths: list[str]) -> list[str]:
        """Copy host files into ``/workspace/uploads/`` with unique names to avoid collisions."""
        sandbox = await self.create_or_reuse(env_name, session_id)
        await sandbox.commands.run("mkdir -p /workspace/uploads")
        injected: list[str] = []
        for raw in file_paths:
            try:
                p = Path(raw).expanduser().resolve()
            except OSError:
                logger.warning("inject_files: invalid path %s", raw)
                continue
            if not p.is_file():
                logger.warning("inject_files: missing or not a file: %s (resolved %s)", raw, p)
                continue
            try:
                data = p.read_bytes()
                unique = f"{uuid.uuid4().hex[:8]}_{p.name}"
                container_path = f"/workspace/uploads/{unique}"
                await sandbox.files.write_file(container_path, data)
                injected.append(container_path)
                logger.info("Injected host %s -> %s (%d bytes)", p, container_path, len(data))
            except Exception:
                logger.warning("Failed to inject %s", raw, exc_info=True)
        return injected

    async def cleanup(self, session_id: str) -> None:
        to_remove = [k for k in self._sandboxes if k.endswith(f":{session_id}")]
        for key in to_remove:
            sandbox = self._sandboxes.pop(key)
            try:
                await sandbox.kill()
                await sandbox.close()
                logger.info("Sandbox deleted: %s", key)
            except Exception:
                logger.warning("Failed to delete sandbox %s", key, exc_info=True)

    async def cleanup_all(self) -> None:
        for key, sandbox in list(self._sandboxes.items()):
            try:
                await sandbox.kill()
                await sandbox.close()
            except Exception:
                logger.warning("Failed to delete sandbox %s", key, exc_info=True)
        self._sandboxes.clear()
        self._background_tasks.clear()


class _BackgroundTask:
    __slots__ = ("sandbox", "execution_id", "env_name", "session_id")

    def __init__(self, sandbox: Sandbox, execution_id: str, env_name: str, session_id: str) -> None:
        self.sandbox = sandbox
        self.execution_id = execution_id
        self.env_name = env_name
        self.session_id = session_id


# Alias expected by tools
_SHARED_BRIDGE: OpenSandboxBridge | None = None


def get_shared_bridge() -> OpenSandboxBridge:
    """Return the process-wide OpenSandbox bridge singleton.

    ToolExecutionContext.metadata is copied per tool invocation, so storing the bridge
    there does not persist across calls. Reusing one process-wide bridge ensures one
    sandbox container per (environment, session_id) key instead of recreating a
    container on every tool call.
    """
    global _SHARED_BRIDGE
    if _SHARED_BRIDGE is None:
        _SHARED_BRIDGE = OpenSandboxBridge()
    return _SHARED_BRIDGE


async def cleanup_shared_session(session_id: str) -> None:
    global _SHARED_BRIDGE
    if _SHARED_BRIDGE is None:
        return
    await _SHARED_BRIDGE.cleanup(session_id)


async def cleanup_all_shared_bridges() -> None:
    global _SHARED_BRIDGE
    if _SHARED_BRIDGE is None:
        return
    await _SHARED_BRIDGE.cleanup_all()
    _SHARED_BRIDGE = None


SandboxBridge = OpenSandboxBridge

sdk_available = _SDK_AVAILABLE
