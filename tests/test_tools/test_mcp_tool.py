"""Tests for MCP tool adapters — input model generation and argument serialization."""

import pytest
from pydantic import ValidationError

from openharness.mcp.types import McpToolInfo
from openharness.tools.base import ToolExecutionContext
from openharness.tools.mcp_tool import McpToolAdapter, _input_model_from_schema


class TestInputModelFromSchema:
    """Verify _input_model_from_schema maps JSON Schema types correctly."""

    def test_required_string_rejects_none(self):
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        Model = _input_model_from_schema("search", schema)
        with pytest.raises(ValidationError):
            Model(query=None)

    def test_required_string_accepts_value(self):
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        Model = _input_model_from_schema("search", schema)
        m = Model(query="zigzag")
        assert m.query == "zigzag"

    def test_optional_string_defaults_to_none(self):
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "wing": {"type": "string"},
            },
            "required": ["query"],
        }
        Model = _input_model_from_schema("search", schema)
        m = Model(query="test")
        assert m.wing is None

    def test_exclude_none_omits_optional_keeps_required(self):
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "wing": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        }
        Model = _input_model_from_schema("search", schema)
        m = Model(query="test")
        dumped = m.model_dump(mode="json", exclude_none=True)
        assert dumped == {"query": "test"}

    def test_all_json_types_mapped(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "score": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array"},
                "meta": {"type": "object"},
            },
            "required": ["name", "count", "score", "active", "tags", "meta"],
        }
        Model = _input_model_from_schema("full", schema)
        m = Model(name="x", count=1, score=0.5, active=True, tags=["a"], meta={"k": "v"})
        dumped = m.model_dump(mode="json")
        assert dumped == {
            "name": "x", "count": 1, "score": 0.5,
            "active": True, "tags": ["a"], "meta": {"k": "v"},
        }

    def test_empty_schema_creates_valid_model(self):
        Model = _input_model_from_schema("empty", {"type": "object"})
        m = Model()
        assert m.model_dump(mode="json") == {}

    def test_model_rejects_null_for_required_integer(self):
        schema = {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
            "required": ["limit"],
        }
        Model = _input_model_from_schema("limited", schema)
        with pytest.raises(ValidationError):
            Model(limit=None)


class _FakeMcpManager:
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        assert server_name == "demo"
        assert tool_name == "search"
        assert arguments == {"query": "openharness"}
        return "ok"


@pytest.mark.asyncio
async def test_mcp_tool_adapter_registers_async_cancel_handle(tmp_path):
    tool_info = McpToolInfo(
        server_name="demo",
        name="search",
        description="search",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    adapter = McpToolAdapter(_FakeMcpManager(), tool_info)  # type: ignore[arg-type]
    registered: dict[str, object] = {}

    def _register_cancel_handle(**kwargs):
        registered.update(kwargs)

    result = await adapter.execute(
        adapter.input_model(query="openharness"),
        ToolExecutionContext(
            cwd=tmp_path,
            metadata={
                "tool_name": adapter.name,
                "tool_use_id": "tool-mcp",
                "_register_step_cancel_handle": _register_cancel_handle,
            },
        ),
    )

    assert result.is_error is False
    assert result.output == "ok"
    assert registered["tool_name"] == adapter.name
    assert registered["tool_use_id"] == "tool-mcp"
    assert registered["cancel_kind"] == "async_task"
