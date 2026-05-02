"""Cancel a background OpenSandbox task."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SandboxCancelInput(BaseModel):
    task_id: str = Field(description="task_id returned by sandbox_exec with background=true")


class SandboxCancelTool(BaseTool):
    name = "sandbox_cancel"
    description = (
        "Cancel a background sandbox task. Use the task_id from sandbox_exec when background=true."
    )
    input_model = SandboxCancelInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return False

    async def execute(self, arguments: SandboxCancelInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from openharness.sandbox.opensandbox_bridge import get_shared_bridge, sdk_available
        except ImportError:
            return ToolResult(output="OpenSandbox bridge failed to load.", is_error=True)

        if not sdk_available:
            return ToolResult(output="opensandbox SDK is not installed.", is_error=True)

        bridge = get_shared_bridge()

        success = await bridge.cancel_task(arguments.task_id)
        if success:
            return ToolResult(output=f"Task {arguments.task_id} has been cancelled.")
        return ToolResult(
            output=f"Failed to cancel task {arguments.task_id}. It may have already finished.",
            is_error=True,
        )
