"""Built-in tool registration."""

from openharness.tools.ask_user_question_tool import AskUserQuestionTool
from openharness.tools.agent_tool import AgentTool
from openharness.tools.bash_tool import BashTool
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult
from openharness.tools.brief_tool import BriefTool
from openharness.tools.config_tool import ConfigTool
from openharness.tools.control import ToolControlCapability, get_tool_control_capability
from openharness.tools.cron_create_tool import CronCreateTool
from openharness.tools.cron_delete_tool import CronDeleteTool
from openharness.tools.cron_list_tool import CronListTool
from openharness.tools.cron_toggle_tool import CronToggleTool
from openharness.tools.depmap_get_dependency_summary_tool import DepmapGetDependencySummaryTool
from openharness.tools.depmap_search_cell_lines_tool import DepmapSearchCellLinesTool
from openharness.tools.depmap_search_gene_tool import DepmapSearchGeneTool
from openharness.tools.enter_plan_mode_tool import EnterPlanModeTool
from openharness.tools.gdc_search_cases_tool import GdcSearchCasesTool
from openharness.tools.gdc_search_files_tool import GdcSearchFilesTool
from openharness.tools.gdc_search_projects_tool import GdcSearchProjectsTool
from openharness.tools.gdsc_get_release_overview_tool import GdscGetReleaseOverviewTool
from openharness.tools.gdsc_list_release_files_tool import GdscListReleaseFilesTool
from openharness.tools.gdsc_search_compounds_annotation_tool import GdscSearchCompoundsAnnotationTool
from openharness.tools.gtex_get_median_expression_tool import GtexGetMedianExpressionTool
from openharness.tools.gtex_list_tissues_tool import GtexListTissuesTool
from openharness.tools.gtex_search_gene_tool import GtexSearchGeneTool
from openharness.tools.enter_worktree_tool import EnterWorktreeTool
from openharness.tools.exit_plan_mode_tool import ExitPlanModeTool
from openharness.tools.exit_worktree_tool import ExitWorktreeTool
from openharness.tools.file_edit_tool import FileEditTool
from openharness.tools.file_read_tool import FileReadTool
from openharness.tools.file_write_tool import FileWriteTool
from openharness.tools.enrichment_barplot_tool import EnrichmentBarplotTool
from openharness.tools.enrichment_dotplot_tool import EnrichmentDotplotTool
from openharness.tools.expression_boxplot_tool import ExpressionBoxplotTool
from openharness.tools.forest_plot_tool import ForestPlotTool
from openharness.tools.glob_tool import GlobTool
from openharness.tools.grep_tool import GrepTool
from openharness.tools.heatmap_plot_tool import HeatmapPlotTool
from openharness.tools.list_mcp_resources_tool import ListMcpResourcesTool
from openharness.tools.string_get_enrichment_tool import StringGetEnrichmentTool
from openharness.tools.string_get_network_tool import StringGetNetworkTool
from openharness.tools.string_search_entity_tool import StringSearchEntityTool
from openharness.tools.lsp_tool import LspTool
from openharness.tools.mcp_auth_tool import McpAuthTool
from openharness.tools.mcp_tool import McpToolAdapter
from openharness.tools.memory_tool import MemoryTool
from openharness.tools.network_plot_tool import NetworkPlotTool
from openharness.tools.notebook_edit_tool import NotebookEditTool
from openharness.tools.pca_plot_tool import PcaPlotTool
from openharness.tools.read_mcp_resource_tool import ReadMcpResourceTool
from openharness.tools.remote_trigger_tool import RemoteTriggerTool
from openharness.tools.sandbox_cancel_tool import SandboxCancelTool
from openharness.tools.sandbox_exec_tool import SandboxExecTool
from openharness.tools.sandbox_list_envs_tool import SandboxListEnvsTool
from openharness.tools.sandbox_status_tool import SandboxStatusTool
from openharness.tools.send_message_tool import SendMessageTool
from openharness.tools.skill_tool import SkillTool
from openharness.tools.sleep_tool import SleepTool
from openharness.tools.survival_curve_tool import SurvivalCurveTool
from openharness.tools.task_create_tool import TaskCreateTool
from openharness.tools.task_get_tool import TaskGetTool
from openharness.tools.task_list_tool import TaskListTool
from openharness.tools.task_output_tool import TaskOutputTool
from openharness.tools.task_stop_tool import TaskStopTool
from openharness.tools.task_update_tool import TaskUpdateTool
from openharness.tools.team_create_tool import TeamCreateTool
from openharness.tools.team_delete_tool import TeamDeleteTool
from openharness.tools.todo_write_tool import TodoWriteTool
from openharness.tools.tool_search_tool import ToolSearchTool
from openharness.tools.umap_plot_tool import UmapPlotTool
from openharness.tools.volcano_plot_tool import VolcanoPlotTool
from openharness.tools.web_fetch_tool import WebFetchTool
from openharness.tools.web_search_tool import WebSearchTool


def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    """Return the default built-in tool registry."""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        SandboxListEnvsTool(),
        SandboxExecTool(),
        SandboxStatusTool(),
        SandboxCancelTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        LspTool(),
        McpAuthTool(),
        GlobTool(),
        GrepTool(),
        DepmapSearchGeneTool(),
        DepmapGetDependencySummaryTool(),
        DepmapSearchCellLinesTool(),
        GdcSearchProjectsTool(),
        GdcSearchCasesTool(),
        GdcSearchFilesTool(),
        GtexListTissuesTool(),
        GtexSearchGeneTool(),
        GtexGetMedianExpressionTool(),
        GdscListReleaseFilesTool(),
        GdscGetReleaseOverviewTool(),
        GdscSearchCompoundsAnnotationTool(),
        StringSearchEntityTool(),
        StringGetNetworkTool(),
        StringGetEnrichmentTool(),
        EnrichmentBarplotTool(),
        EnrichmentDotplotTool(),
        ExpressionBoxplotTool(),
        ForestPlotTool(),
        NetworkPlotTool(),
        HeatmapPlotTool(),
        PcaPlotTool(),
        UmapPlotTool(),
        VolcanoPlotTool(),
        SurvivalCurveTool(),
        SkillTool(),
        ToolSearchTool(),
        WebFetchTool(),
        WebSearchTool(),
        ConfigTool(),
        MemoryTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
    ):
        registry.register(tool)
    if mcp_manager is not None:
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        for tool_info in mcp_manager.list_tools():
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    return registry


__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "ToolControlCapability",
    "create_default_tool_registry",
    "get_tool_control_capability",
]
