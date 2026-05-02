"""Declared runtime control capabilities for tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ToolControlKind = Literal[
    "subprocess",
    "sandbox_task",
    "background_task",
    "agent_run",
    "async_task",
    "cooperative_task",
    "fast",
]


@dataclass(frozen=True)
class ToolControlCapability:
    """How a tool can be interrupted while it is the active step."""

    kind: ToolControlKind
    supports_step_control: bool
    supports_deep_cancel: bool
    label: str
    notes: str


SUBPROCESS_CONTROL = ToolControlCapability(
    kind="subprocess",
    supports_step_control=True,
    supports_deep_cancel=True,
    label="Subprocess",
    notes="Registers a live subprocess so stop/skip can terminate the OS process.",
)
SANDBOX_TASK_CONTROL = ToolControlCapability(
    kind="sandbox_task",
    supports_step_control=True,
    supports_deep_cancel=True,
    label="Sandbox task",
    notes="Registers the remote sandbox task id so stop/skip can cancel it in the sandbox backend.",
)
BACKGROUND_TASK_CONTROL = ToolControlCapability(
    kind="background_task",
    supports_step_control=True,
    supports_deep_cancel=True,
    label="Background task",
    notes="Registers the created OpenHarness background task so stop/skip can stop it.",
)
AGENT_RUN_CONTROL = ToolControlCapability(
    kind="agent_run",
    supports_step_control=True,
    supports_deep_cancel=True,
    label="Agent run",
    notes="Registers the spawned agent id so stop/skip can shut it down.",
)
ASYNC_TASK_CONTROL = ToolControlCapability(
    kind="async_task",
    supports_step_control=True,
    supports_deep_cancel=True,
    label="Async task",
    notes="Registers an async cancellation handle for network, MCP, or timer work.",
)
COOPERATIVE_TASK_CONTROL = ToolControlCapability(
    kind="cooperative_task",
    supports_step_control=True,
    supports_deep_cancel=False,
    label="Cooperative task",
    notes="Falls back to cancelling the active asyncio tool task; blocking sync work may finish before cancellation lands.",
)
FAST_TOOL_CONTROL = ToolControlCapability(
    kind="fast",
    supports_step_control=True,
    supports_deep_cancel=False,
    label="Fast tool",
    notes="Expected to complete quickly; the active tool task can still be cancelled while running.",
)


TOOL_CONTROL_CAPABILITIES: dict[str, ToolControlCapability] = {
    "agent": AGENT_RUN_CONTROL,
    "ask_user_question": ASYNC_TASK_CONTROL,
    "bash": SUBPROCESS_CONTROL,
    "brief": FAST_TOOL_CONTROL,
    "config": FAST_TOOL_CONTROL,
    "cron_create": FAST_TOOL_CONTROL,
    "cron_delete": FAST_TOOL_CONTROL,
    "cron_list": FAST_TOOL_CONTROL,
    "cron_toggle": FAST_TOOL_CONTROL,
    "depmap_get_dependency_summary": COOPERATIVE_TASK_CONTROL,
    "depmap_search_cell_lines": COOPERATIVE_TASK_CONTROL,
    "depmap_search_gene": COOPERATIVE_TASK_CONTROL,
    "edit_file": FAST_TOOL_CONTROL,
    "enrichment_barplot": COOPERATIVE_TASK_CONTROL,
    "enrichment_dotplot": COOPERATIVE_TASK_CONTROL,
    "enter_plan_mode": FAST_TOOL_CONTROL,
    "enter_worktree": COOPERATIVE_TASK_CONTROL,
    "exit_plan_mode": FAST_TOOL_CONTROL,
    "exit_worktree": COOPERATIVE_TASK_CONTROL,
    "expression_boxplot": COOPERATIVE_TASK_CONTROL,
    "forest_plot": COOPERATIVE_TASK_CONTROL,
    "gdc_search_cases": COOPERATIVE_TASK_CONTROL,
    "gdc_search_files": COOPERATIVE_TASK_CONTROL,
    "gdc_search_projects": COOPERATIVE_TASK_CONTROL,
    "gdsc_get_release_overview": COOPERATIVE_TASK_CONTROL,
    "gdsc_list_release_files": COOPERATIVE_TASK_CONTROL,
    "gdsc_search_compounds_annotation": COOPERATIVE_TASK_CONTROL,
    "glob": SUBPROCESS_CONTROL,
    "grep": SUBPROCESS_CONTROL,
    "gtex_get_median_expression": COOPERATIVE_TASK_CONTROL,
    "gtex_list_tissues": COOPERATIVE_TASK_CONTROL,
    "gtex_search_gene": COOPERATIVE_TASK_CONTROL,
    "heatmap_plot": COOPERATIVE_TASK_CONTROL,
    "list_mcp_resources": FAST_TOOL_CONTROL,
    "lsp": COOPERATIVE_TASK_CONTROL,
    "mcp_auth": ASYNC_TASK_CONTROL,
    "memory": FAST_TOOL_CONTROL,
    "network_plot": COOPERATIVE_TASK_CONTROL,
    "notebook_edit": FAST_TOOL_CONTROL,
    "pca_plot": COOPERATIVE_TASK_CONTROL,
    "read_file": FAST_TOOL_CONTROL,
    "read_mcp_resource": ASYNC_TASK_CONTROL,
    "remote_trigger": SUBPROCESS_CONTROL,
    "sandbox_cancel": ASYNC_TASK_CONTROL,
    "sandbox_exec": SANDBOX_TASK_CONTROL,
    "sandbox_list_envs": COOPERATIVE_TASK_CONTROL,
    "sandbox_status": ASYNC_TASK_CONTROL,
    "send_message": ASYNC_TASK_CONTROL,
    "skill": FAST_TOOL_CONTROL,
    "sleep": ASYNC_TASK_CONTROL,
    "string_get_enrichment": COOPERATIVE_TASK_CONTROL,
    "string_get_network": COOPERATIVE_TASK_CONTROL,
    "string_search_entity": COOPERATIVE_TASK_CONTROL,
    "survival_curve": COOPERATIVE_TASK_CONTROL,
    "task_create": BACKGROUND_TASK_CONTROL,
    "task_get": FAST_TOOL_CONTROL,
    "task_list": FAST_TOOL_CONTROL,
    "task_output": FAST_TOOL_CONTROL,
    "task_stop": ASYNC_TASK_CONTROL,
    "task_update": FAST_TOOL_CONTROL,
    "team_create": FAST_TOOL_CONTROL,
    "team_delete": FAST_TOOL_CONTROL,
    "todo_write": FAST_TOOL_CONTROL,
    "tool_search": FAST_TOOL_CONTROL,
    "umap_plot": COOPERATIVE_TASK_CONTROL,
    "volcano_plot": COOPERATIVE_TASK_CONTROL,
    "web_fetch": ASYNC_TASK_CONTROL,
    "web_search": ASYNC_TASK_CONTROL,
    "write_file": FAST_TOOL_CONTROL,
}


def get_tool_control_capability(tool_name: str) -> ToolControlCapability:
    """Return the declared runtime control capability for a tool."""
    if tool_name.startswith("mcp__"):
        return ASYNC_TASK_CONTROL
    return TOOL_CONTROL_CAPABILITIES.get(tool_name, COOPERATIVE_TASK_CONTROL)
