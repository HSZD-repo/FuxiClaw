"""Tests for the persistent memory tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openharness.tools import create_default_tool_registry
from openharness.tools.base import ToolExecutionContext
from openharness.tools.memory_tool import MemoryTool, MemoryToolInput


@pytest.mark.asyncio
async def test_memory_tool_add_and_search(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENHARNESS_DATA_DIR", str(tmp_path / "data"))
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    tool = MemoryTool()
    context = ToolExecutionContext(cwd=project_dir)

    add_result = await tool.execute(
        MemoryToolInput(
            action="add",
            title="Conda unavailable",
            content="Conda is unavailable in the bioinformatics Docker container. Use the prebuilt image.",
            memory_type="known_failure",
            scope="docker",
            keywords=["conda", "docker"],
            priority="high",
        ),
        context,
    )
    assert not add_result.is_error

    search_result = await tool.execute(
        MemoryToolInput(action="search", query="conda docker", limit=3),
        context,
    )
    payload = json.loads(search_result.output)
    assert payload["results"]
    assert payload["results"][0]["type"] == "known_failure"


def test_memory_tool_is_registered():
    registry = create_default_tool_registry()
    assert registry.get("memory") is not None
