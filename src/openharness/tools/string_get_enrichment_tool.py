"""Tool for running STRING enrichment on a gene list."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.string_api import (
    build_identifiers_param,
    build_string_result_url,
    parse_gene_terms,
    request_string_json,
    StringApiError,
)


class StringGetEnrichmentToolInput(BaseModel):
    """Arguments for a STRING enrichment query."""

    genes: list[str] = Field(description="Gene/protein symbols for enrichment analysis")
    species: int = Field(default=9606, description="NCBI taxonomy identifier. Use 9606 for human")
    category: str | None = Field(
        default=None,
        description="Optional category filter, such as Process, Function, Component, KEGG, or WikiPathways.",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of enriched terms to summarize")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the STRING API base URL, useful for testing or mirrors.",
    )
    include_link: bool = Field(default=True, description="Whether to include a STRING results link")


class StringGetEnrichmentTool(BaseTool):
    """Run STRING enrichment and summarize the top terms."""

    name = "string_get_enrichment"
    description = "Run STRING functional enrichment for a gene/protein list and summarize top terms."
    input_model = StringGetEnrichmentToolInput

    def is_read_only(self, arguments: StringGetEnrichmentToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: StringGetEnrichmentToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        genes = parse_gene_terms(arguments.genes)
        if len(genes) < 2:
            return ToolResult(
                output="At least two genes are required for STRING enrichment.",
                is_error=True,
            )

        try:
            payload = await request_string_json(
                "enrichment",
                api_base_url=arguments.api_base_url,
                identifiers=build_identifiers_param(genes),
                species=arguments.species,
            )
        except StringApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        rows = _filter_rows(payload, arguments.category)
        if not rows:
            category_msg = f" in category '{arguments.category}'" if arguments.category else ""
            return ToolResult(
                output=f"No STRING enrichment terms were found{category_msg}.",
                is_error=True,
            )

        lines = [
            "STRING enrichment summary",
            f"Input genes: {', '.join(genes)}",
            f"Mapped genes: {len(genes)} / {len(genes)}",
            f"Species: {arguments.species}",
            "",
            "Top enriched terms",
        ]
        for index, item in enumerate(rows[: arguments.limit], start=1):
            term = str(item.get("description") or item.get("term") or "(unknown term)")
            category = str(item.get("category") or item.get("termCategory") or "(unknown category)")
            fdr = item.get("fdr")
            fdr_text = f"{float(fdr):.3g}" if isinstance(fdr, (int, float)) else str(fdr)
            input_genes = item.get("inputGenes")
            genes_text = ", ".join(input_genes) if isinstance(input_genes, list) else str(input_genes or "")
            lines.append(f"{index}. {term}")
            lines.append(f"   Category: {category}")
            if fdr is not None:
                lines.append(f"   FDR: {fdr_text}")
            if genes_text:
                lines.append(f"   Genes: {genes_text}")

        lines.extend(
            [
                "",
                "Summary",
                f"STRING returned {len(rows)} enriched terms for this gene set.",
            ]
        )
        if arguments.include_link:
            lines.extend(
                [
                    "",
                    "STRING link",
                    build_string_result_url(genes, species=arguments.species),
                ]
            )
        return ToolResult(output="\n".join(lines))


def _filter_rows(payload: list[dict], category: str | None) -> list[dict]:
    if not category:
        return payload
    lowered = category.strip().lower()
    rows: list[dict] = []
    for item in payload:
        item_category = str(item.get("category") or item.get("termCategory") or "").strip().lower()
        if item_category == lowered:
            rows.append(item)
    return rows
