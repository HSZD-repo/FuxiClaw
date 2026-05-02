"""Tool for querying GDC file metadata."""

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


class GdcSearchFilesToolInput(BaseModel):
    """Arguments for GDC file search."""

    project_id: str = Field(description="Project ID such as TCGA-BRCA")
    data_category: str | None = Field(default=None, description="Data category such as Transcriptome Profiling")
    data_type: str | None = Field(default=None, description="Data type such as Gene Expression Quantification")
    experimental_strategy: str | None = Field(default=None, description="Experimental strategy such as RNA-Seq")
    workflow_type: str | None = Field(default=None, description="Analysis workflow type such as STAR - Counts")
    access: str | None = Field(default=None, description="Access level such as open or controlled")
    sample_type: str | None = Field(default=None, description="Sample type such as Primary Tumor")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of files to return")
    api_base_url: str | None = Field(
        default=None,
        description="Optional override for the GDC API base URL, useful for testing or mirrors.",
    )


class GdcSearchFilesTool(BaseTool):
    """Return a compact summary of matching GDC files."""

    name = "gdc_search_files"
    description = "Search GDC file metadata such as TCGA RNA-seq files and summarize matching records."
    input_model = GdcSearchFilesToolInput

    def is_read_only(self, arguments: GdcSearchFilesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdcSearchFilesToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        filters = combine_filters(
            [
                exact_filter("cases.project.project_id", arguments.project_id),
                exact_filter("data_category", arguments.data_category),
                exact_filter("data_type", arguments.data_type),
                exact_filter("experimental_strategy", arguments.experimental_strategy),
                exact_filter("analysis.workflow_type", arguments.workflow_type),
                exact_filter("access", arguments.access),
                exact_filter("cases.samples.sample_type", arguments.sample_type),
            ]
        )
        params = {
            "size": arguments.limit,
            "format": "JSON",
            "fields": ",".join(
                [
                    "file_id",
                    "file_name",
                    "access",
                    "data_category",
                    "data_type",
                    "experimental_strategy",
                    "analysis.workflow_type",
                    "cases.project.project_id",
                    "cases.submitter_id",
                ]
            ),
        }
        if filters is not None:
            params["filters"] = json.dumps(filters)

        try:
            payload = await request_gdc_json("files", api_base_url=arguments.api_base_url, **params)
        except GdcApiError as exc:
            return ToolResult(output=str(exc), is_error=True)

        hits = payload.get("data", {}).get("hits", [])
        if not isinstance(hits, list) or not hits:
            return ToolResult(output="No GDC files matched the query.", is_error=True)

        total = format_total(payload)
        lines = [
            "GDC file search results",
            f"Project ID: {arguments.project_id}",
        ]
        if arguments.data_category:
            lines.append(f"Data category: {arguments.data_category}")
        if arguments.data_type:
            lines.append(f"Data type: {arguments.data_type}")
        if arguments.experimental_strategy:
            lines.append(f"Experimental strategy: {arguments.experimental_strategy}")
        if arguments.workflow_type:
            lines.append(f"Workflow type: {arguments.workflow_type}")
        if arguments.access:
            lines.append(f"Access: {arguments.access}")
        if total is not None:
            lines.append(f"Matched files: {total}")
        lines.extend(["", "Top files"])

        for index, file_item in enumerate(hits, start=1):
            file_name = str(file_item.get("file_name") or file_item.get("file_id") or "(unknown)")
            lines.append(f"{index}. {file_name}")
            if file_item.get("file_id"):
                lines.append(f"   File ID: {file_item['file_id']}")
            if file_item.get("access"):
                lines.append(f"   Access: {file_item['access']}")
            if file_item.get("data_category"):
                lines.append(f"   Category: {file_item['data_category']}")
            if file_item.get("data_type"):
                lines.append(f"   Type: {file_item['data_type']}")
            if file_item.get("experimental_strategy"):
                lines.append(f"   Strategy: {file_item['experimental_strategy']}")
            analysis = file_item.get("analysis", {})
            if isinstance(analysis, dict) and analysis.get("workflow_type"):
                lines.append(f"   Workflow: {analysis['workflow_type']}")
            cases = file_item.get("cases")
            if isinstance(cases, list) and cases:
                case_ids = [
                    str(case.get("submitter_id"))
                    for case in cases
                    if isinstance(case, dict) and case.get("submitter_id")
                ]
                if case_ids:
                    lines.append(f"   Cases: {', '.join(case_ids[:3])}")
                projects = []
                for case in cases:
                    if not isinstance(case, dict):
                        continue
                    project = case.get("project", {})
                    if isinstance(project, dict) and project.get("project_id"):
                        projects.append(str(project["project_id"]))
                if projects:
                    lines.append(f"   Project refs: {', '.join(sorted(set(projects))[:3])}")
        lines.extend(["", "Source", "https://api.gdc.cancer.gov/files"])
        return ToolResult(output="\n".join(lines))
