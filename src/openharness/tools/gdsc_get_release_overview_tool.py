"""Tool for summarizing the current official GDSC release."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gdsc_release_api import (
    DEFAULT_GDSC_ARCHIVE_URL,
    DEFAULT_GDSC_FTP_DIR,
    DEFAULT_GDSC_FTP_HOST,
    GdscReleaseError,
    list_release_files,
)


class GdscGetReleaseOverviewToolInput(BaseModel):
    """Arguments for GDSC release overview."""

    ftp_host: str = Field(default=DEFAULT_GDSC_FTP_HOST, description="FTP host for GDSC release files")
    ftp_dir: str = Field(default=DEFAULT_GDSC_FTP_DIR, description="FTP directory for the current GDSC release")
    archive_url: str = Field(default=DEFAULT_GDSC_ARCHIVE_URL, description="Archive URL for historical GDSC releases")
    base_url: str | None = Field(
        default=None,
        description="Optional override for the GDSC website base URL, used only if FTP listing fails.",
    )


class GdscGetReleaseOverviewTool(BaseTool):
    """Return a compact overview derived from current GDSC release files."""

    name = "gdsc_get_release_overview"
    description = "Summarize the current GDSC release using official release files."
    input_model = GdscGetReleaseOverviewToolInput

    def is_read_only(self, arguments: GdscGetReleaseOverviewToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdscGetReleaseOverviewToolInput, context: ToolExecutionContext) -> ToolResult:
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

        counts = Counter(item.category for item in files)
        lines = [
            "GDSC release overview",
            f"Discovered files: {len(files)}",
            "",
            "File categories",
        ]
        for category, count in sorted(counts.items()):
            lines.append(f"- {category}: {count}")

        highlighted = [
            item for item in files
            if item.category in {"drug_response", "association", "compound_annotation", "cell_line_annotation"}
        ]
        lines.extend(["", "Highlighted files"])
        for item in highlighted[:10]:
            lines.append(f"- {item.name} [{item.category}]")
        lines.extend(
            [
                "",
                "Notes",
                "This overview is derived from the current official GDSC release files, not from scraped homepage text.",
                f"Archive: {arguments.archive_url}",
            ]
        )
        return ToolResult(output="\n".join(lines))
