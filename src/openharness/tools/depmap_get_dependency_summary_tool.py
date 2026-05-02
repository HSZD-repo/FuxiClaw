"""Tool for summarizing one gene's dependency profile from DepMap."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.depmap_api import contains_query, DepmapApiError, fetch_depmap_csv, find_first_nonempty


class DepmapGetDependencySummaryToolInput(BaseModel):
    """Arguments for DepMap dependency summary lookup."""

    gene: str = Field(description="Gene symbol such as KRAS, EGFR, or ERBB2")
    dataset: str | None = Field(
        default=None,
        description="Optional dataset filter such as DependencyEnum.Chronos_Combined",
    )
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the DepMap download API base URL, useful for testing or mirrors.",
    )


class DepmapGetDependencySummaryTool(BaseTool):
    """Return a compact dependency summary for one gene from DepMap."""

    name = "depmap_get_dependency_summary"
    description = "Summarize DepMap dependency signals for one gene."
    input_model = DepmapGetDependencySummaryToolInput

    def is_read_only(self, arguments: DepmapGetDependencySummaryToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: DepmapGetDependencySummaryToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            rows = await fetch_depmap_csv("gene_dep_summary", api_base_url=arguments.api_base_url)
        except DepmapApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        matches = [
            row for row in rows
            if contains_query(row, arguments.gene, "gene_name", "Gene", "HugoSymbol", "symbol")
        ]
        if arguments.dataset:
            matches = [
                row for row in matches
                if arguments.dataset.lower() in find_first_nonempty(row, "dataset", "Dataset").lower()
            ]
        if not matches:
            return ToolResult(
                output=f"No DepMap dependency summary matched gene={arguments.gene}",
                is_error=True,
            )

        preferred = _pick_preferred_row(matches)
        gene_name = find_first_nonempty(preferred, "gene_name", "Gene", "HugoSymbol", "symbol", "gene")
        dataset = find_first_nonempty(preferred, "dataset", "Dataset")
        dependent = find_first_nonempty(preferred, "dependent_cell_lines", "Dependent Cell Lines")
        with_data = find_first_nonempty(preferred, "cell_lines_with_data", "Cell Lines With Data")
        strongly_selective = find_first_nonempty(preferred, "strongly_selective", "Strongly Selective")
        common_essential = find_first_nonempty(preferred, "common_essential", "Common Essential")

        lines = [
            "DepMap dependency summary",
            f"Gene: {gene_name or arguments.gene}",
        ]
        if dataset:
            lines.append(f"Dataset: {dataset}")
        if dependent or with_data:
            lines.append(f"Dependent cell lines: {dependent or '?'} / {with_data or '?'}")
        if strongly_selective:
            lines.append(f"Strongly selective: {strongly_selective}")
        if common_essential:
            lines.append(f"Common essential: {common_essential}")
        lines.extend(
            [
                "",
                "Summary",
                _build_summary(gene_name or arguments.gene, dependent, with_data, strongly_selective, common_essential),
                "",
                "Source",
                "https://depmap.org/portal/api/download/gene_dep_summary",
            ]
        )
        return ToolResult(output="\n".join(lines))


def _pick_preferred_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        dataset = find_first_nonempty(row, "dataset", "Dataset")
        if "chronos_combined" in dataset.lower():
            return row
    return rows[0]


def _build_summary(
    gene_name: str,
    dependent: str,
    with_data: str,
    strongly_selective: str,
    common_essential: str,
) -> str:
    parts = [f"{gene_name} has a DepMap dependency summary row."]
    if dependent and with_data:
        parts.append(f"Portal summary reports {dependent} dependent cell lines out of {with_data} profiled lines.")
    if strongly_selective:
        parts.append(f"Strongly selective flag: {strongly_selective}.")
    if common_essential:
        parts.append(f"Common essential flag: {common_essential}.")
    return " ".join(parts)
