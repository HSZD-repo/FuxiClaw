"""Tests for glob tool runtime control hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from openharness.tools.base import ToolExecutionContext
from openharness.tools.glob_tool import GlobTool, GlobToolInput


class _FakeStdout:
    def __init__(self) -> None:
        self._lines = [b"./a.py\n", b""]

    async def readline(self) -> bytes:
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self) -> None:
        self.stdout = _FakeStdout()
        self.stderr = None
        self.returncode = None

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int | None:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


@pytest.mark.asyncio
async def test_glob_tool_registers_cancel_handle_for_rg_process(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("openharness.tools.glob_tool.shutil.which", lambda _: "/usr/bin/rg")
    fake_process = _FakeProcess()
    registered: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    def _register_cancel_handle(**kwargs):
        registered.update(kwargs)

    monkeypatch.setattr(
        "openharness.tools.glob_tool.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    result = await GlobTool().execute(
        GlobToolInput(pattern="**/*.py"),
        ToolExecutionContext(
            cwd=tmp_path,
            metadata={
                "tool_name": "glob",
                "tool_use_id": "tool-glob",
                "_register_step_cancel_handle": _register_cancel_handle,
            },
        ),
    )

    assert result.is_error is False
    assert result.output == "./a.py"
    assert registered["tool_name"] == "glob"
    assert registered["tool_use_id"] == "tool-glob"
    assert registered["cancel_kind"] == "subprocess"
