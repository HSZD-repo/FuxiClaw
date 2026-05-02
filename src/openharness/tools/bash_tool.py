"""Shell command execution tool."""

from __future__ import annotations

import asyncio
import inspect
import shlex
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from pydantic import BaseModel, Field

from openharness.sandbox import SandboxUnavailableError
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult, register_step_cancel_handle
from openharness.utils.shell import create_shell_subprocess


class BashToolInput(BaseModel):
    """Arguments for the bash tool."""

    command: str = Field(description="Shell command to execute")
    cwd: str | None = Field(default=None, description="Working directory override")
    timeout_seconds: int = Field(default=600, ge=1, le=600)


class BashTool(BaseTool):
    """Execute a shell command with stdout/stderr capture."""

    name = "bash"
    description = "Run a shell command in the local repository."
    input_model = BashToolInput

    async def execute(self, arguments: BashToolInput, context: ToolExecutionContext) -> ToolResult:
        cwd = Path(arguments.cwd).expanduser() if arguments.cwd else context.cwd
        command = _normalize_git_command(arguments.command)
        preflight_error = _preflight_interactive_command(command)
        if preflight_error is not None:
            return ToolResult(
                output=preflight_error,
                is_error=True,
                metadata={"interactive_required": True},
            )
        process: asyncio.subprocess.Process | None = None
        try:
            process = await create_shell_subprocess(
                command,
                cwd=cwd,
                prefer_pty=True,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await _notify_running_process(context.metadata, process=process, command=command)
            await register_step_cancel_handle(
                context,
                lambda **_: _terminate_process(process, force=False),
                kind="subprocess",
                label="bash subprocess",
            )
        except SandboxUnavailableError as exc:
            return ToolResult(output=str(exc), is_error=True)
        except asyncio.CancelledError:
            if process is not None:
                await _terminate_process(process, force=False)
            raise

        try:
            await asyncio.wait_for(process.wait(), timeout=arguments.timeout_seconds)
        except asyncio.TimeoutError:
            output_buffer = await _drain_available_output(process.stdout)
            await _terminate_process(process, force=True)
            output_buffer.extend(await _read_remaining_output(process))
            return ToolResult(
                output=_format_timeout_output(
                    output_buffer,
                    command=command,
                    timeout_seconds=arguments.timeout_seconds,
                ),
                is_error=True,
                metadata={"returncode": process.returncode, "timed_out": True},
            )
        except asyncio.CancelledError:
            await _terminate_process(process, force=False)
            raise

        output_buffer = await _read_remaining_output(process)
        control_result = _user_controlled_result(
            context.metadata,
            process=process,
            output_buffer=output_buffer,
        )
        if control_result is not None:
            return control_result
        text = _format_output(output_buffer)
        return ToolResult(
            output=text,
            is_error=process.returncode != 0,
            metadata={"returncode": process.returncode, "command": command},
        )


RunningProcessHook = Callable[..., Awaitable[None] | None]


async def _notify_running_process(
    metadata: dict[str, Any],
    *,
    process: asyncio.subprocess.Process,
    command: str,
) -> None:
    hook = metadata.get("_register_running_process")
    if not callable(hook):
        return
    result = hook(
        tool_use_id=metadata.get("tool_use_id"),
        tool_name=metadata.get("tool_name"),
        process=process,
        command=command,
    )
    if inspect.isawaitable(result):
        await result


def _user_controlled_result(
    metadata: dict[str, Any],
    *,
    process: asyncio.subprocess.Process,
    output_buffer: bytearray,
) -> ToolResult | None:
    control_state = metadata.get("_runtime_control_state")
    if not isinstance(control_state, dict):
        return None
    if control_state.get("target_tool_use_id") not in {None, metadata.get("tool_use_id")}:
        return None
    action = control_state.get("action")
    if action not in {"stop", "skip"}:
        return None
    if process.returncode not in {-15, -9, 143, 137}:
        return None
    captured = _format_output(output_buffer)
    if action == "skip":
        message = (
            "Execution was skipped by the user because the command appeared stuck or required "
            "interactive follow-up. Do not retry the same interactive command. Choose a "
            "non-interactive or read-only alternative."
        )
        if captured != "(no output)":
            message = f"{message}\n\nPartial output:\n{captured}"
        return ToolResult(
            output=message,
            is_error=True,
            metadata={
                "returncode": process.returncode,
                "interrupted_by_user": True,
                "user_action": "skip",
            },
        )
    return ToolResult(
        output="Execution was cancelled by the user.",
        is_error=True,
        metadata={
            "returncode": process.returncode,
            "interrupted_by_user": True,
            "user_action": "stop",
        },
    )


async def _terminate_process(process: asyncio.subprocess.Process, *, force: bool) -> None:
    if process.returncode is not None:
        return
    if force:
        process.kill()
        await process.wait()
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def _read_remaining_output(process: asyncio.subprocess.Process) -> bytearray:
    output_buffer = bytearray()
    if process.stdout is not None:
        output_buffer.extend(await process.stdout.read())
    return output_buffer


async def _drain_available_output(
    stream: asyncio.StreamReader | None,
    *,
    read_timeout: float = 0.05,
) -> bytearray:
    output_buffer = bytearray()
    if stream is None:
        return output_buffer
    while True:
        try:
            chunk = await asyncio.wait_for(stream.read(65536), timeout=read_timeout)
        except asyncio.TimeoutError:
            return output_buffer
        if not chunk:
            return output_buffer
        output_buffer.extend(chunk)


def _format_output(output_buffer: bytearray) -> str:
    text = output_buffer.decode("utf-8", errors="replace").replace("\r\n", "\n")
    text = text.removeprefix("^D\x08\x08").removeprefix("\x04\x08\x08").strip()
    if not text:
        return "(no output)"
    if len(text) > 12000:
        return f"{text[:12000]}\n...[truncated]..."
    return text


def _format_timeout_output(output_buffer: bytearray, *, command: str, timeout_seconds: int) -> str:
    parts = [f"Command timed out after {timeout_seconds} seconds."]
    text = _format_output(output_buffer)
    if text != "(no output)":
        parts.extend(["", "Partial output:", text])
    hint = _interactive_command_hint(command=command, output=text)
    if hint:
        parts.extend(["", hint])
    return "\n".join(parts)


def _preflight_interactive_command(command: str) -> str | None:
    lowered_command = command.lower()
    if not (_looks_like_interactive_scaffold(lowered_command) or _looks_like_interactive_git(lowered_command)):
        return None
    if _looks_like_interactive_git(lowered_command):
        return (
            "This git command is likely to wait for interactive input. "
            "The bash tool is non-interactive, so prefer non-interactive git flags "
            "(for example --no-edit, --no-pager, or a read-only alternative) before continuing."
        )
    return (
        "This command appears to require interactive input before it can continue. "
        "The bash tool is non-interactive, so it cannot answer installer/scaffold prompts live. "
        "Prefer non-interactive flags (for example --yes, -y, --skip-install, --defaults, --non-interactive), "
        "or run the scaffolding step once in an external terminal before asking the agent to continue."
    )


def _interactive_command_hint(*, command: str, output: str) -> str | None:
    lowered_command = command.lower()
    if (
        _looks_like_interactive_scaffold(lowered_command)
        or _looks_like_interactive_git(lowered_command)
        or _looks_like_prompt(output)
    ):
        return (
            "This command appears to require interactive input. "
            "The bash tool is non-interactive, so prefer non-interactive flags "
            "(for example --yes, -y, --skip-install, or similar) or run the "
            "scaffolding step once in an external terminal before continuing."
        )
    return None


def _looks_like_interactive_scaffold(lowered_command: str) -> bool:
    scaffold_markers: tuple[str, ...] = (
        "create-next-app",
        "npm create ",
        "pnpm create ",
        "yarn create ",
        "bun create ",
        "pnpm dlx ",
        "npm init ",
        "pnpm init ",
        "yarn init ",
        "bunx create-",
        "npx create-",
    )
    non_interactive_markers: tuple[str, ...] = (
        "--yes",
        " -y",
        "--skip-install",
        "--defaults",
        "--non-interactive",
        "--ci",
    )
    return any(marker in lowered_command for marker in scaffold_markers) and not any(
        marker in lowered_command for marker in non_interactive_markers
    )


def _looks_like_prompt(output: str) -> bool:
    if not output:
        return False
    prompt_markers: Iterable[str] = (
        "would you like",
        "ok to proceed",
        "select an option",
        "which",
        "press enter to continue",
        "?",
    )
    lowered_output = output.lower()
    return any(marker in lowered_output for marker in prompt_markers)


def _looks_like_interactive_git(lowered_command: str) -> bool:
    interactive_git_markers: tuple[str, ...] = (
        "git commit",
        "git rebase -i",
        "git add -p",
        "git checkout -p",
        "git restore -p",
        "git mergetool",
    )
    non_interactive_git_markers: tuple[str, ...] = (
        "--no-edit",
        "--amend --no-edit",
    )
    return any(marker in lowered_command for marker in interactive_git_markers) and not any(
        marker in lowered_command for marker in non_interactive_git_markers
    )


def _normalize_git_command(command: str) -> str:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return command
    if len(parts) < 2 or parts[0] != "git":
        return command
    subcommand = parts[1]
    if subcommand not in {"diff", "log", "show", "branch", "blame"}:
        return command
    if "--no-pager" not in parts[1:]:
        parts.insert(1, "--no-pager")
    return f"GIT_PAGER=cat TERM=dumb {shlex.join(parts)}"
