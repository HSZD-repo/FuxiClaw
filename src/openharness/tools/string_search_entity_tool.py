"""Tool for resolving gene and protein names against STRING."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.string_api import parse_gene_terms, request_string_json, StringApiError


class StringSearchEntityToolInput(BaseModel):
    """Arguments for STRING entity resolution."""

    query: str = Field(description="One gene/protein name or a short comma-separated list of names")
    species: int = Field(default=9606, description="NCBI taxonomy identifier. Use 9606 for human")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of matches to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the STRING API base URL, useful for testing or mirrors.",
    )


class StringSearchEntityTool(BaseTool):
    """Resolve one or more gene names to STRING entities."""

    name = "string_search_entity"
    description = "Resolve one or more gene/protein names to STRING entities and return the best matches."
    input_model = StringSearchEntityToolInput

    def is_read_only(self, arguments: StringSearchEntityToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: StringSearchEntityToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        genes = parse_gene_terms(arguments.query)
        if not genes:
            return ToolResult(output="No gene or protein names were provided.", is_error=True)

        try:
            payload = await request_string_json(
                "get_string_ids",
                api_base_url=arguments.api_base_url,
                identifiers="\r".join(genes),
                species=arguments.species,
                limit=arguments.limit,
            )
        except StringApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        if not payload:
            return ToolResult(
                output=f"No STRING matches found for: {', '.join(genes)}",
                is_error=True,
            )

        lines = [
            "STRING entity resolution results",
            f"Query: {', '.join(genes)}",
            f"Species: {arguments.species}",
            "",
        ]
        for index, item in enumerate(payload, start=1):
            query_item = str(item.get("queryItem", "(unknown)"))
            match_name = str(item.get("preferredName") or item.get("stringId") or "(unknown)")
            lines.append(f"{index}. Input: {query_item}")
            lines.append(f"   Match: {match_name}")
            if item.get("stringId"):
                lines.append(f"   STRING ID: {item['stringId']}")
            if item.get("ncbiTaxonId") is not None:
                lines.append(f"   Taxon: {item['ncbiTaxonId']}")
            if item.get("score") is not None:
                lines.append(f"   Score: {item['score']}")
            annotation = str(item.get("annotation") or "").strip()
            if annotation:
                lines.append(f"   Annotation: {annotation}")
        return ToolResult(output="\n".join(lines))
