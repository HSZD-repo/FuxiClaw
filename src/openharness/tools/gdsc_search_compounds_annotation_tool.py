"""Tool for searching official GDSC compounds annotation files."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gdsc_release_api import (
    contains_query,
    DEFAULT_GDSC_ARCHIVE_URL,
    DEFAULT_GDSC_FTP_DIR,
    DEFAULT_GDSC_FTP_HOST,
    fetch_release_text,
    find_first_nonempty,
    GdscReleaseError,
    list_release_files,
    parse_csv_rows,
    select_compounds_file,
)


class GdscSearchCompoundsAnnotationToolInput(BaseModel):
    """Arguments for GDSC compound annotation search."""

    query: str = Field(description="Compound name, target, or pathway keyword such as Erlotinib or EGFR")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of matching compounds to return")
    ftp_host: str = Field(default=DEFAULT_GDSC_FTP_HOST, description="FTP host for GDSC release files")
    ftp_dir: str = Field(default=DEFAULT_GDSC_FTP_DIR, description="FTP directory for the current GDSC release")
    archive_url: str = Field(default=DEFAULT_GDSC_ARCHIVE_URL, description="Archive URL for historical GDSC releases")
    base_url: str | None = Field(
        default=None,
        description="Optional override for the GDSC website base URL, used only if FTP listing fails.",
    )


class GdscSearchCompoundsAnnotationTool(BaseTool):
    """Return matching compounds from the official GDSC compounds annotation file."""

    name = "gdsc_search_compounds_annotation"
    description = "Search official GDSC compounds annotation files by drug name, target, or pathway."
    input_model = GdscSearchCompoundsAnnotationToolInput

    def is_read_only(self, arguments: GdscSearchCompoundsAnnotationToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdscSearchCompoundsAnnotationToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            files = await list_release_files(
                ftp_host=arguments.ftp_host,
                ftp_dir=arguments.ftp_dir,
                archive_url=arguments.archive_url,
                base_url=arguments.base_url,
            )
        except GdscReleaseError as exc:
            return ToolResult(output=str(exc), is_error=True)

        compounds_file = select_compounds_file(files)
        if compounds_file is None:
            return ToolResult(output="Could not locate a GDSC compounds annotation file.", is_error=True)

        if compounds_file.url.startswith("ftp://"):
            return ToolResult(
                output=(
                    "Found the GDSC compounds annotation file on FTP, but direct FTP file download "
                    "is not enabled in this tool yet. Use gdsc_list_release_files to inspect the file path."
                ),
                is_error=True,
            )

        try:
            csv_text = await fetch_release_text(compounds_file.url)
            rows = parse_csv_rows(csv_text)
        except GdscReleaseError as exc:
            return ToolResult(output=str(exc), is_error=True)
        except Exception:
            return ToolResult(output="GDSC compounds annotation did not parse as CSV.", is_error=True)

        matches = [
            row for row in rows
            if contains_query(
                row,
                arguments.query,
                "Drug Name",
                "drug_name",
                "Name",
                "PUTATIVE_TARGET",
                "Target pathway",
                "target_pathway",
                "Synonyms",
            )
        ]
        if not matches:
            return ToolResult(output=f"No GDSC compounds matched: {arguments.query}", is_error=True)

        lines = [
            "GDSC compounds annotation results",
            f"Query: {arguments.query}",
            f"Annotation file: {compounds_file.url}",
            "",
            "Top compound matches",
        ]
        for index, row in enumerate(matches[: arguments.limit], start=1):
            name = find_first_nonempty(row, "Drug Name", "drug_name", "Name")
            target = find_first_nonempty(row, "PUTATIVE_TARGET", "Target", "target")
            pathway = find_first_nonempty(row, "Target pathway", "target_pathway", "Pathway")
            identifier = find_first_nonempty(row, "Drug Id", "drug_id", "ID")
            lines.append(f"{index}. {name or '(unknown compound)'}")
            if identifier:
                lines.append(f"   ID: {identifier}")
            if target:
                lines.append(f"   Putative target: {target}")
            if pathway:
                lines.append(f"   Target pathway: {pathway}")
        return ToolResult(output="\n".join(lines))
