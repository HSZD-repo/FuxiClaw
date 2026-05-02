"""Tool for listing GTEx tissues."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gtex_api import extract_records, GtexApiError, request_gtex_json


class GtexListTissuesToolInput(BaseModel):
    """Arguments for GTEx tissue listing."""

    dataset_id: str = Field(default="gtex_v8", description="GTEx dataset identifier such as gtex_v8 or gtex_v10")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of tissues to summarize")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GTEx API base URL, useful for testing or mirrors.",
    )


class GtexListTissuesTool(BaseTool):
    """Return a compact summary of GTEx tissue metadata."""

    name = "gtex_list_tissues"
    description = "List GTEx tissues and summarize available tissue metadata."
    input_model = GtexListTissuesToolInput

    def is_read_only(self, arguments: GtexListTissuesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GtexListTissuesToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            payload = await request_gtex_json(
                "dataset/tissueSiteDetail",
                api_base_url=arguments.api_base_url,
                datasetId=arguments.dataset_id,
                itemsPerPage=arguments.limit,
            )
        except GtexApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        records = extract_records(payload, "tissueSiteDetails", "tissueSiteDetail")
        if not records:
            return ToolResult(output="No GTEx tissues were returned.", is_error=True)

        lines = [
            "GTEx tissue list",
            f"Dataset: {arguments.dataset_id}",
            f"Returned tissues: {min(len(records), arguments.limit)}",
            "",
            "Top tissues",
        ]
        for index, item in enumerate(records[: arguments.limit], start=1):
            detail_id = str(item.get("tissueSiteDetailId") or "(unknown)")
            detail_name = str(item.get("tissueSiteDetail") or item.get("tissueSiteDetailAbbr") or "")
            lines.append(f"{index}. {detail_id}")
            if detail_name:
                lines.append(f"   Name: {detail_name}")
            if item.get("ontologyId"):
                lines.append(f"   Ontology: {item['ontologyId']}")
            if item.get("colorHex"):
                lines.append(f"   Color: {item['colorHex']}")
        lines.extend(["", "Source", "https://gtexportal.org/api/v2/dataset/tissueSiteDetail"])
        return ToolResult(output="\n".join(lines))
