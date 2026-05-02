"""Tool for searching GTEx gene metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gtex_api import extract_records, GtexApiError, request_gtex_json


class GtexSearchGeneToolInput(BaseModel):
    """Arguments for GTEx gene search."""

    gene: str = Field(description="Gene symbol or GENCODE identifier such as TP53 or ENSG00000141510")
    dataset_id: str = Field(default="gtex_v8", description="GTEx dataset identifier such as gtex_v8 or gtex_v10")
    items_per_page: int = Field(default=10, ge=1, le=50, description="Maximum number of gene matches to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GTEx API base URL, useful for testing or mirrors.",
    )


class GtexSearchGeneTool(BaseTool):
    """Return matching GTEx gene metadata for a symbol or GENCODE id."""

    name = "gtex_search_gene"
    description = "Search GTEx gene metadata by gene symbol or GENCODE identifier."
    input_model = GtexSearchGeneToolInput

    def is_read_only(self, arguments: GtexSearchGeneToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GtexSearchGeneToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            payload = await request_gtex_json(
                "reference/gene",
                api_base_url=arguments.api_base_url,
                geneId=arguments.gene,
                gencodeVersion="v26",
                genomeBuild="GRCh38/hg38",
                page=0,
                itemsPerPage=arguments.items_per_page,
            )
        except GtexApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        records = extract_records(payload, "genes", "gene")
        if not records:
            return ToolResult(output=f"No GTEx genes matched: {arguments.gene}", is_error=True)

        lines = [
            "GTEx gene search results",
            f"Query: {arguments.gene}",
            f"Dataset: {arguments.dataset_id}",
            "",
            "Top gene matches",
        ]
        for index, item in enumerate(records, start=1):
            symbol = str(item.get("geneSymbol") or item.get("symbol") or "(unknown)")
            gencode_id = str(item.get("gencodeId") or item.get("geneId") or "(unknown)")
            lines.append(f"{index}. {symbol}")
            lines.append(f"   GENCODE ID: {gencode_id}")
            if item.get("geneSymbolUpper"):
                lines.append(f"   Symbol upper: {item['geneSymbolUpper']}")
            if item.get("chromosome"):
                lines.append(f"   Chromosome: {item['chromosome']}")
            if item.get("start") is not None and item.get("end") is not None:
                lines.append(f"   Coordinates: {item['start']} - {item['end']}")
        lines.extend(["", "Source", "https://gtexportal.org/api/v2/reference/gene"])
        return ToolResult(output="\n".join(lines))
