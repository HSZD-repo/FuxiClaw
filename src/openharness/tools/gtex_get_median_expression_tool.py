"""Tool for querying GTEx median expression across tissues."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gtex_api import extract_records, GtexApiError, request_gtex_json


class GtexGetMedianExpressionToolInput(BaseModel):
    """Arguments for GTEx median expression lookup."""

    gene: str = Field(description="Gene symbol or GENCODE identifier")
    dataset_id: str = Field(default="gtex_v8", description="GTEx dataset identifier such as gtex_v8 or gtex_v10")
    tissue_site_detail_id: str | None = Field(
        default=None,
        description="Optional GTEx tissueSiteDetailId such as Lung or Breast_Mammary_Tissue",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of tissues to summarize")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GTEx API base URL, useful for testing or mirrors.",
    )


class GtexGetMedianExpressionTool(BaseTool):
    """Return GTEx median gene expression across tissues."""

    name = "gtex_get_median_expression"
    description = "Get GTEx median gene expression across tissues for one gene."
    input_model = GtexGetMedianExpressionToolInput

    def is_read_only(self, arguments: GtexGetMedianExpressionToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GtexGetMedianExpressionToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            gene_payload = await request_gtex_json(
                "reference/gene",
                api_base_url=arguments.api_base_url,
                geneId=arguments.gene,
                gencodeVersion="v26",
                genomeBuild="GRCh38/hg38",
                page=0,
                itemsPerPage=1,
            )
        except GtexApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        gene_records = extract_records(gene_payload, "genes", "gene")
        if not gene_records:
            return ToolResult(output=f"No GTEx gene matched: {arguments.gene}", is_error=True)

        gene_record = gene_records[0]
        gencode_id = str(gene_record.get("gencodeId") or gene_record.get("geneId") or arguments.gene)
        gene_symbol = str(gene_record.get("geneSymbol") or gene_record.get("symbol") or arguments.gene)

        params = {
            "datasetId": arguments.dataset_id,
            "gencodeId": gencode_id,
            "itemsPerPage": arguments.limit,
        }
        if arguments.tissue_site_detail_id:
            params["tissueSiteDetailId"] = arguments.tissue_site_detail_id

        try:
            expr_payload = await request_gtex_json(
                "expression/medianGeneExpression",
                api_base_url=arguments.api_base_url,
                **params,
            )
        except GtexApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        records = extract_records(expr_payload, "medianGeneExpression", "geneExpression")
        if not records:
            return ToolResult(
                output=f"No GTEx median expression records were returned for: {gene_symbol}",
                is_error=True,
            )

        records = sorted(
            records,
            key=lambda item: float(item.get("median", 0.0) or 0.0),
            reverse=True,
        )
        lines = [
            "GTEx median expression summary",
            f"Gene: {gene_symbol}",
            f"GENCODE ID: {gencode_id}",
            f"Dataset: {arguments.dataset_id}",
        ]
        if arguments.tissue_site_detail_id:
            lines.append(f"Tissue filter: {arguments.tissue_site_detail_id}")
        lines.extend(["", "Top tissues by median expression"])

        for index, item in enumerate(records[: arguments.limit], start=1):
            tissue_id = str(item.get("tissueSiteDetailId") or "(unknown)")
            tissue_name = str(item.get("tissueSiteDetail") or "")
            median = item.get("median")
            unit = str(item.get("unit") or "TPM")
            median_text = f"{float(median):.3g}" if isinstance(median, (int, float)) else str(median)
            lines.append(f"{index}. {tissue_id}")
            if tissue_name:
                lines.append(f"   Tissue: {tissue_name}")
            lines.append(f"   Median: {median_text} {unit}")
        lines.extend(["", "Source", "https://gtexportal.org/api/v2/expression/medianGeneExpression"])
        return ToolResult(output="\n".join(lines))
