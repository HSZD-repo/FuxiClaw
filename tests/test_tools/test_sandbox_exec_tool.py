"""Tests for sandbox execution tool control hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from openharness.sandbox.opensandbox_models import TaskInfo, TaskStatus
from openharness.tools.base import ToolExecutionContext
from openharness.tools.sandbox_exec_tool import SandboxExecInput, SandboxExecTool


class _FakeBridge:
    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.polls = 0

    async def exec_background(self, environment: str, session_id: str, command: str) -> str:
        assert environment == "demo"
        assert session_id == "session-1"
        assert command == "echo hi"
        return "task-123"

    async def poll_task(self, task_id: str) -> TaskInfo:
        assert task_id == "task-123"
        self.polls += 1
        return TaskInfo(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            output="hi\n",
            exit_code=0,
        )

    async def cancel_task(self, task_id: str) -> bool:
        self.cancelled.append(task_id)
        return True


@pytest.mark.asyncio
async def test_sandbox_exec_foreground_registers_sandbox_cancel_handle(tmp_path: Path, monkeypatch):
    bridge = _FakeBridge()
    monkeypatch.setattr("openharness.sandbox.opensandbox_bridge.sdk_available", True)
    monkeypatch.setattr("openharness.sandbox.opensandbox_bridge.get_shared_bridge", lambda: bridge)

    registered: dict[str, object] = {}

    def _register_cancel_handle(**kwargs) -> None:
        registered.update(kwargs)

    result = await SandboxExecTool().execute(
        SandboxExecInput(environment="demo", command="echo hi", timeout=5),
        ToolExecutionContext(
            cwd=tmp_path,
            metadata={
                "session_id": "session-1",
                "tool_name": "sandbox_exec",
                "tool_use_id": "tool-1",
                "_register_step_cancel_handle": _register_cancel_handle,
            },
        ),
    )

    assert result.is_error is False
    assert result.output == "hi\n"
    assert result.metadata["task_id"] == "task-123"
    assert registered["tool_name"] == "sandbox_exec"
    assert registered["tool_use_id"] == "tool-1"
    assert registered["cancel_kind"] == "sandbox_task"

    cancel = registered["cancel"]
    assert callable(cancel)
    await cancel(action="stop")
    assert bridge.cancelled == ["task-123"]
