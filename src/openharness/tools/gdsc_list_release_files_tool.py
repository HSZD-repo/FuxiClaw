"""Tool for listing official GDSC release files."""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.gdsc_release_api import (
    DEFAULT_GDSC_ARCHIVE_URL,
    DEFAULT_GDSC_FTP_DIR,
    DEFAULT_GDSC_FTP_HOST,
    GdscReleaseError,
    list_release_files,
)


class GdscListReleaseFilesToolInput(BaseModel):
    """Arguments for GDSC release file listing."""

    query: str | None = Field(
        default=None,
        description="Optional keyword such as IC50, ANOVA, compound, or cell line to filter files.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of files to summarize")
    ftp_host: str = Field(default=DEFAULT_GDSC_FTP_HOST, description="FTP host for GDSC release files")
    ftp_dir: str = Field(default=DEFAULT_GDSC_FTP_DIR, description="FTP directory for the current GDSC release")
    archive_url: str = Field(default=DEFAULT_GDSC_ARCHIVE_URL, description="Archive URL for historical GDSC releases")
    base_url: str | None = Field(
        default=None,
        description="Optional override for the GDSC website base URL, used only if FTP listing fails.",
    )


class GdscListReleaseFilesTool(BaseTool):
    """Return matching release files from official GDSC resources."""

    name = "gdsc_list_release_files"
    description = "List official GDSC release files from FTP or the bulk download page."
    input_model = GdscListReleaseFilesToolInput

    def is_read_only(self, arguments: GdscListReleaseFilesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GdscListReleaseFilesToolInput, context: ToolExecutionContext) -> ToolResult:
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

        if arguments.query:
            needle = arguments.query.strip().lower()
            files = [
                item for item in files
                if needle in item.name.lower() or needle in item.category.lower() or needle in item.url.lower()
            ]
        if not files:
            return ToolResult(output=f"No GDSC release files matched: {arguments.query}", is_error=True)

        lines = [
            "GDSC release files",
            f"Returned files: {min(len(files), arguments.limit)}",
        ]
        if arguments.query:
            lines.append(f"Query: {arguments.query}")
        lines.extend(["", "Top files"])
        for index, item in enumerate(files[: arguments.limit], start=1):
            lines.append(f"{index}. {item.name}")
            lines.append(f"   Category: {item.category}")
            lines.append(f"   Source: {item.source}")
            lines.append(f"   URL: {item.url}")
        return ToolResult(output="\n".join(lines))
