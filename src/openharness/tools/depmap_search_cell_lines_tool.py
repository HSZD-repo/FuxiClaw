"""Tool for searching DepMap cell line metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.depmap_api import (
    choose_model_metadata_file,
    contains_query,
    DepmapApiError,
    fetch_depmap_csv,
    find_first_nonempty,
)


class DepmapSearchCellLinesToolInput(BaseModel):
    """Arguments for DepMap cell line search."""

    query: str = Field(description="Cell line name, lineage, or disease keyword such as breast, lung, or MCF7")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of matching cell lines to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the DepMap download API base URL, useful for testing or mirrors.",
    )


class DepmapSearchCellLinesTool(BaseTool):
    """Return matching cell line metadata from a DepMap model export."""

    name = "depmap_search_cell_lines"
    description = "Search DepMap cell line metadata by name, lineage, or disease context."
    input_model = DepmapSearchCellLinesToolInput

    def is_read_only(self, arguments: DepmapSearchCellLinesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: DepmapSearchCellLinesToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            file_rows = await fetch_depmap_csv("files", api_base_url=arguments.api_base_url)
        except DepmapApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        metadata_file = choose_model_metadata_file(file_rows)
        if metadata_file is None:
            return ToolResult(output="Could not locate a DepMap model metadata file.", is_error=True)

        model_url = find_first_nonempty(metadata_file, "url", "download_url", "downloadUrl", "signed_url")
        model_name = find_first_nonempty(metadata_file, "filename", "name", "display_name")
        if not model_url:
            return ToolResult(output="DepMap model metadata file did not include a download URL.", is_error=True)

        try:
            rows = await fetch_depmap_csv(model_url, api_base_url=arguments.api_base_url)
        except DepmapApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        matches = [
            row for row in rows
            if contains_query(
                row,
                arguments.query,
                "ModelID",
                "model_id",
                "StrippedCellLineName",
                "CCLEName",
                "OncotreeLineage",
                "PrimaryDisease",
                "Primary Site",
                "OncotreePrimaryDisease",
            )
        ]
        if not matches:
            return ToolResult(output=f"No DepMap cell lines matched: {arguments.query}", is_error=True)

        lines = [
            "DepMap cell line search results",
            f"Query: {arguments.query}",
            f"Metadata file: {model_name or '(unknown)'}",
            "",
            "Top cell line matches",
        ]
        for index, row in enumerate(matches[: arguments.limit], start=1):
            model_id = find_first_nonempty(row, "ModelID", "model_id")
            display_name = find_first_nonempty(row, "StrippedCellLineName", "CCLEName", "cell_line_name")
            lineage = find_first_nonempty(row, "OncotreeLineage", "lineage")
            disease = find_first_nonempty(row, "PrimaryDisease", "OncotreePrimaryDisease", "primary_disease")
            site = find_first_nonempty(row, "Primary Site", "primary_site")
            lines.append(f"{index}. {display_name or model_id or '(unknown cell line)'}")
            if model_id:
                lines.append(f"   Model ID: {model_id}")
            if lineage:
                lines.append(f"   Lineage: {lineage}")
            if disease:
                lines.append(f"   Disease: {disease}")
            if site:
                lines.append(f"   Primary site: {site}")
        lines.extend(["", "Source", "https://depmap.org/portal/api/download/files"])
        return ToolResult(output="\n".join(lines))
