"""Tests for declared tool runtime control capabilities."""

from __future__ import annotations

from openharness.tools import create_default_tool_registry
from openharness.tools.control import TOOL_CONTROL_CAPABILITIES, get_tool_control_capability


def test_default_tools_have_declared_control_capabilities():
    registry = create_default_tool_registry()
    tool_names = {tool.name for tool in registry.list_tools()}
    optional_mcp_tools = {"list_mcp_resources", "read_mcp_resource"}

    missing = sorted(tool_names - set(TOOL_CONTROL_CAPABILITIES))
    stale = sorted(set(TOOL_CONTROL_CAPABILITIES) - tool_names - optional_mcp_tools)

    assert missing == []
    assert stale == []

    for tool_name in tool_names:
        capability = get_tool_control_capability(tool_name)
        assert capability.supports_step_control is True
        assert capability.kind
        assert capability.label
        assert capability.notes


def test_dynamic_mcp_tools_are_declared_async_cancellable():
    capability = get_tool_control_capability("mcp__demo__long_running_tool")

    assert capability.kind == "async_task"
    assert capability.supports_step_control is True
    assert capability.supports_deep_cancel is True
