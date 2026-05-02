"""Tool for searching DepMap gene dependency summary metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.depmap_api import contains_query, DepmapApiError, fetch_depmap_csv, find_first_nonempty


class DepmapSearchGeneToolInput(BaseModel):
    """Arguments for DepMap gene search."""

    gene: str = Field(description="Gene symbol or partial gene name such as KRAS or EGFR")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of matching rows to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the DepMap download API base URL, useful for testing or mirrors.",
    )


class DepmapSearchGeneTool(BaseTool):
    """Return matching rows from the DepMap gene dependency summary export."""

    name = "depmap_search_gene"
    description = "Search DepMap gene dependency summary metadata by gene symbol."
    input_model = DepmapSearchGeneToolInput

    def is_read_only(self, arguments: DepmapSearchGeneToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: DepmapSearchGeneToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            rows = await fetch_depmap_csv("gene_dep_summary", api_base_url=arguments.api_base_url)
        except DepmapApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        matches = [
            row for row in rows
            if contains_query(row, arguments.gene, "gene_name", "Gene", "HugoSymbol", "symbol")
        ]
        if not matches:
            return ToolResult(output=f"No DepMap genes matched: {arguments.gene}", is_error=True)

        lines = [
            "DepMap gene search results",
            f"Query: {arguments.gene}",
            "",
            "Top gene matches",
        ]
        for index, row in enumerate(matches[: arguments.limit], start=1):
            gene_name = find_first_nonempty(row, "gene_name", "Gene", "HugoSymbol", "symbol", "gene")
            dataset = find_first_nonempty(row, "dataset", "Dataset")
            entrez_id = find_first_nonempty(row, "entrez_id", "Entrez ID", "entrez")
            lines.append(f"{index}. {gene_name or '(unknown gene)'}")
            if dataset:
                lines.append(f"   Dataset: {dataset}")
            if entrez_id:
                lines.append(f"   Entrez ID: {entrez_id}")
            dependent = find_first_nonempty(row, "dependent_cell_lines", "Dependent Cell Lines")
            with_data = find_first_nonempty(row, "cell_lines_with_data", "Cell Lines With Data")
            if dependent or with_data:
                lines.append(f"   Dependent lines: {dependent or '?'} / {with_data or '?'}")
        lines.extend(["", "Source", "https://depmap.org/portal/api/download/gene_dep_summary"])
        return ToolResult(output="\n".join(lines))
