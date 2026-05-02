"""Tool for querying STRING interaction-network summaries."""

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


class StringGetNetworkToolInput(BaseModel):
    """Arguments for a STRING network query."""

    genes: list[str] = Field(description="One or more gene/protein symbols")
    species: int = Field(default=9606, description="NCBI taxonomy identifier. Use 9606 for human")
    required_score: int = Field(
        default=700,
        ge=0,
        le=1000,
        description="Minimum STRING confidence score. Typical values are 400 or 700.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of interactions to summarize")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the STRING API base URL, useful for testing or mirrors.",
    )
    include_link: bool = Field(default=True, description="Whether to include a STRING results link")


class StringGetNetworkTool(BaseTool):
    """Return a compact interaction-network summary from STRING."""

    name = "string_get_network"
    description = "Fetch a STRING interaction-network summary for one or more genes/proteins."
    input_model = StringGetNetworkToolInput

    def is_read_only(self, arguments: StringGetNetworkToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: StringGetNetworkToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        genes = parse_gene_terms(arguments.genes)
        if not genes:
            return ToolResult(output="No genes were provided.", is_error=True)

        try:
            payload = await request_string_json(
                "network",
                api_base_url=arguments.api_base_url,
                identifiers=build_identifiers_param(genes),
                species=arguments.species,
                required_score=arguments.required_score,
            )
        except StringApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        if not payload:
            return ToolResult(
                output=(
                    "STRING returned no qualifying interactions for: "
                    f"{', '.join(genes)}"
                ),
                is_error=True,
            )

        seen_nodes: set[str] = set()
        lines = [
            "STRING network summary",
            f"Input genes: {', '.join(genes)}",
            f"Species: {arguments.species}",
            f"Required score: {arguments.required_score}",
            "",
            f"Nodes: {len(_collect_nodes(payload))}",
            f"Edges: {len(payload)}",
            "",
            "Top interactions",
        ]

        for index, item in enumerate(payload[: arguments.limit], start=1):
            node_a = str(item.get("preferredName_A") or item.get("stringId_A") or "(unknown)")
            node_b = str(item.get("preferredName_B") or item.get("stringId_B") or "(unknown)")
            score = item.get("score")
            score_text = f"{float(score):.3f}" if isinstance(score, (int, float)) else str(score)
            lines.append(f"{index}. {node_a} - {node_b} | score: {score_text}")
            seen_nodes.add(node_a)
            seen_nodes.add(node_b)

        lines.extend(
            [
                "",
                "Summary",
                (
                    f"STRING returned {len(payload)} qualifying interactions across "
                    f"{len(_collect_nodes(payload))} nodes for this query."
                ),
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


def _collect_nodes(payload: list[dict]) -> set[str]:
    nodes: set[str] = set()
    for item in payload:
        for key in ("preferredName_A", "preferredName_B", "stringId_A", "stringId_B"):
            value = item.get(key)
            if value:
                nodes.add(str(value))
    return nodes
