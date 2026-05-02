"""Tool for querying GDC cases metadata."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gdc_api import (
    combine_filters,
    exact_filter,
    format_total,
    GdcApiError,
    request_gdc_json,
)


class GdcSearchCasesToolInput(BaseModel):
    """Arguments for GDC case search."""

    project_id: str = Field(description="Project ID such as TCGA-BRCA")
    primary_site: str | None = Field(default=None, description="Primary site such as Breast or Lung")
    disease_type: str | None = Field(default=None, description="Disease type filter")
    sample_type: str | None = Field(default=None, description="Sample type such as Primary Tumor or Solid Tissue Normal")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of cases to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GDC API base URL, useful for testing or mirrors.",
    )


class GdcSearchCasesTool(BaseTool):
    """Return a compact summary of matching GDC cases."""

    name = "gdc_search_cases"
    description = "Search GDC cases within a project and summarize matching sample metadata."
    input_model = GdcSearchCasesToolInput

    def is_read_only(self, arguments: GdcSearchCasesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdcSearchCasesToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        filters = combine_filters(
            [
                exact_filter("project.project_id", arguments.project_id),
                exact_filter("primary_site", arguments.primary_site),
                exact_filter("disease_type", arguments.disease_type),
                exact_filter("samples.sample_type", arguments.sample_type),
            ]
        )
        params = {
            "size": arguments.limit,
            "format": "JSON",
            "fields": ",".join(
                [
                    "case_id",
                    "submitter_id",
                    "primary_site",
                    "disease_type",
                    "project.project_id",
                    "samples.sample_type",
                ]
            ),
        }
        if filters is not None:
            params["filters"] = json.dumps(filters)

        try:
            payload = await request_gdc_json("cases", api_base_url=arguments.api_base_url, **params)
        except GdcApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        hits = payload.get("data", {}).get("hits", [])
        if not isinstance(hits, list) or not hits:
            return ToolResult(output="No GDC cases matched the query.", is_error=True)

        total = format_total(payload)
        lines = [
            "GDC case search results",
            f"Project ID: {arguments.project_id}",
        ]
        if arguments.sample_type:
            lines.append(f"Sample type: {arguments.sample_type}")
        if total is not None:
            lines.append(f"Matched cases: {total}")
        lines.extend(["", "Top cases"])

        for index, case in enumerate(hits, start=1):
            submitter_id = str(case.get("submitter_id") or case.get("case_id") or "(unknown)")
            lines.append(f"{index}. {submitter_id}")
            if case.get("case_id"):
                lines.append(f"   Case ID: {case['case_id']}")
            if case.get("primary_site"):
                lines.append(f"   Primary site: {case['primary_site']}")
            if case.get("disease_type"):
                lines.append(f"   Disease type: {case['disease_type']}")
            project = case.get("project", {})
            if isinstance(project, dict) and project.get("project_id"):
                lines.append(f"   Project: {project['project_id']}")
            samples = case.get("samples")
            if isinstance(samples, list) and samples:
                sample_types = sorted(
                    {
                        str(sample.get("sample_type"))
                        for sample in samples
                        if isinstance(sample, dict) and sample.get("sample_type")
                    }
                )
                if sample_types:
                    lines.append(f"   Sample types: {', '.join(sample_types)}")
        lines.extend(["", "Source", "https://api.gdc.cancer.gov/cases"])
        return ToolResult(output="\n".join(lines))
