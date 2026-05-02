"""File reading tool."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

# Read entire small files into memory; stream large files so multi‑MB MAFs do not
# exhaust RAM or produce huge tool payloads (wide MAF rows can be very large).
_STREAM_BYTES_THRESHOLD = 1024 * 1024
_MAX_CHARS_PER_LINE = 4000
_MAX_TOOL_OUTPUT_CHARS = 32000


class FileReadToolInput(BaseModel):
    """Arguments for the file read tool."""

    path: str = Field(description="Path of the file to read")
    offset: int = Field(default=0, ge=0, description="Zero-based starting line")
    limit: int = Field(default=200, ge=1, le=2000, description="Number of lines to return")


class FileReadTool(BaseTool):
    """Read a UTF-8 text file with line numbers."""

    name = "read_file"
    description = "Read a text file from the local repository."
    input_model = FileReadToolInput

    def is_read_only(self, arguments: FileReadToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: FileReadToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.path)

        from openharness.sandbox.session import is_docker_sandbox_active

        if is_docker_sandbox_active():
            from openharness.sandbox.path_validator import validate_sandbox_path

            allowed, reason = validate_sandbox_path(path, context.cwd)
            if not allowed:
                return ToolResult(output=f"Sandbox: {reason}", is_error=True)

        if not path.exists():
            return ToolResult(output=f"File not found: {path}", is_error=True)
        if path.is_dir():
            return ToolResult(output=f"Cannot read directory: {path}", is_error=True)

        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0

        if file_size > _STREAM_BYTES_THRESHOLD:
            if _binary_prefix_contains_nul(path):
                return ToolResult(output=f"Binary file cannot be read as text: {path}", is_error=True)
            selected = _read_line_window_streaming(
                path,
                offset=arguments.offset,
                limit=arguments.limit,
                max_line_chars=_MAX_CHARS_PER_LINE,
            )
        else:
            raw = path.read_bytes()
            if b"\x00" in raw:
                return ToolResult(output=f"Binary file cannot be read as text: {path}", is_error=True)

            text = raw.decode("utf-8", errors="replace")
            lines = text.splitlines()
            raw_selected = lines[arguments.offset : arguments.offset + arguments.limit]
            selected = [_truncate_line(line, _MAX_CHARS_PER_LINE) for line in raw_selected]

        numbered = [
            f"{arguments.offset + index + 1:>6}\t{line}"
            for index, line in enumerate(selected)
        ]
        if not numbered:
            return ToolResult(output=f"(no content in selected range for {path})")
        body = "\n".join(numbered)
        if len(body) > _MAX_TOOL_OUTPUT_CHARS:
            body = (
                f"{body[:_MAX_TOOL_OUTPUT_CHARS]}\n\n"
                f"...[read_file output truncated at {_MAX_TOOL_OUTPUT_CHARS} characters; "
                f"use a smaller limit, smaller offset window, or bash head/tail for wide tables]..."
            )
        return ToolResult(output=body)


def _truncate_line(line: str, max_chars: int) -> str:
    if len(line) <= max_chars:
        return line
    return f"{line[:max_chars]}...[line truncated]"


def _binary_prefix_contains_nul(path: Path, max_bytes: int = 65536) -> bool:
    try:
        with path.open("rb") as handle:
            prefix = handle.read(max_bytes)
    except OSError:
        return False
    return b"\x00" in prefix


def _read_line_window_streaming(
    path: Path,
    *,
    offset: int,
    limit: int,
    max_line_chars: int,
) -> list[str]:
    """Return up to *limit* lines starting at zero-based *offset* without loading the whole file."""
    out: list[str] = []
    skip_remaining = offset
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\r\n")
                if skip_remaining > 0:
                    skip_remaining -= 1
                    continue
                out.append(_truncate_line(line, max_line_chars))
                if len(out) >= limit:
                    break
    except OSError as exc:
        return [f"(could not open or read file: {path}: {exc})"]
    return out


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()
