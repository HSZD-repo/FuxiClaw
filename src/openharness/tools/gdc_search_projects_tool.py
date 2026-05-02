"""Tool for querying GDC projects, including TCGA cohorts."""

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


class GdcSearchProjectsToolInput(BaseModel):
    """Arguments for GDC project search."""

    program: str | None = Field(default=None, description="Program name such as TCGA, TARGET, or CPTAC")
    project_id: str | None = Field(default=None, description="Specific project ID such as TCGA-BRCA")
    primary_site: str | None = Field(default=None, description="Primary disease site such as Breast or Lung")
    disease_type: str | None = Field(default=None, description="Disease type such as Adenomas and Adenocarcinomas")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of projects to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GDC API base URL, useful for testing or mirrors.",
    )


class GdcSearchProjectsTool(BaseTool):
    """Return a compact summary of matching GDC projects."""

    name = "gdc_search_projects"
    description = "Search GDC projects such as TCGA cohorts and summarize matching studies."
    input_model = GdcSearchProjectsToolInput

    def is_read_only(self, arguments: GdcSearchProjectsToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdcSearchProjectsToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        filters = combine_filters(
            [
                exact_filter("program.name", arguments.program),
                exact_filter("project_id", arguments.project_id),
                exact_filter("primary_site", arguments.primary_site),
                exact_filter("disease_type", arguments.disease_type),
            ]
        )
        params = {
            "size": arguments.limit,
            "format": "JSON",
            "fields": ",".join(
                [
                    "project_id",
                    "name",
                    "program.name",
                    "primary_site",
                    "disease_type",
                    "summary.case_count",
                    "summary.file_count",
                ]
            ),
        }
        if filters is not None:
            params["filters"] = json.dumps(filters)

        try:
            payload = await request_gdc_json("projects", api_base_url=arguments.api_base_url, **params)
        except GdcApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        hits = payload.get("data", {}).get("hits", [])
        if not isinstance(hits, list) or not hits:
            return ToolResult(output="No GDC projects matched the query.", is_error=True)

        total = format_total(payload)
        lines = ["GDC project search results"]
        if arguments.program:
            lines.append(f"Program: {arguments.program}")
        if arguments.project_id:
            lines.append(f"Project ID filter: {arguments.project_id}")
        if arguments.primary_site:
            lines.append(f"Primary site: {arguments.primary_site}")
        if arguments.disease_type:
            lines.append(f"Disease type: {arguments.disease_type}")
        if total is not None:
            lines.append(f"Matched projects: {total}")
        lines.extend(["", "Top projects"])

        for index, project in enumerate(hits, start=1):
            project_id = str(project.get("project_id") or "(unknown)")
            name = str(project.get("name") or "")
            lines.append(f"{index}. {project_id}")
            if name:
                lines.append(f"   Name: {name}")
            program = project.get("program", {})
            if isinstance(program, dict) and program.get("name"):
                lines.append(f"   Program: {program['name']}")
            if project.get("primary_site"):
                lines.append(f"   Primary site: {project['primary_site']}")
            if project.get("disease_type"):
                lines.append(f"   Disease type: {project['disease_type']}")
            summary = project.get("summary", {})
            if isinstance(summary, dict):
                if summary.get("case_count") is not None:
                    lines.append(f"   Cases: {summary['case_count']}")
                if summary.get("file_count") is not None:
                    lines.append(f"   Files: {summary['file_count']}")
        lines.extend(["", "Source", "https://api.gdc.cancer.gov/projects"])
        return ToolResult(output="\n".join(lines))
