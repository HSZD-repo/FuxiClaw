"""Helpers for querying GDSC release resources via FTP or download pages."""

from __future__ import annotations

import csv
import ftplib
import html
import io
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin

import httpx


DEFAULT_GDSC_BASE_URL = "https://www.cancerrxgene.org"
DEFAULT_GDSC_FTP_HOST = "ftp.sanger.ac.uk"
DEFAULT_GDSC_FTP_DIR = "/pub/project/cancerrxgene/releases/current_release"
DEFAULT_GDSC_ARCHIVE_URL = "https://ftp.sanger.ac.uk/project/cancerrxgene/releases/"


class GdscReleaseError(RuntimeError):
    """Raised when a GDSC release request fails."""


@dataclass(frozen=True)
class GdscReleaseFile:
    """One discoverable GDSC release file."""

    name: str
    path: str
    url: str
    source: str
    category: str


def classify_gdsc_file(name: str) -> str:
    """Return a coarse category inferred from the file name."""
    lowered = name.lower()
    if "compound" in lowered or "drug" in lowered:
        return "compound_annotation"
    if "anova" in lowered:
        return "association"
    if "cell" in lowered or "model" in lowered:
        return "cell_line_annotation"
    if "ic50" in lowered or "dose_response" in lowered or "fitted" in lowered:
        return "drug_response"
    if "raw" in lowered:
        return "raw_data"
    return "other"


def parse_csv_rows(text: str) -> list[dict[str, str]]:
    """Parse a CSV string into dictionaries."""
    reader = csv.DictReader(io.StringIO(text))
    return [{str(k): str(v) for k, v in row.items() if k is not None} for row in reader]


def find_first_nonempty(row: dict[str, str], *keys: str) -> str:
    """Return the first non-empty value from the provided keys."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def contains_query(row: dict[str, str], query: str, *keys: str) -> bool:
    """Case-insensitive query matching across selected columns."""
    needle = query.strip().lower()
    if not needle:
        return False
    for key in keys:
        value = row.get(key)
        if value and needle in str(value).lower():
            return True
    return False


async def list_release_files(
    *,
    ftp_host: str = DEFAULT_GDSC_FTP_HOST,
    ftp_dir: str = DEFAULT_GDSC_FTP_DIR,
    archive_url: str = DEFAULT_GDSC_ARCHIVE_URL,
    base_url: str | None = None,
) -> list[GdscReleaseFile]:
    """List files from the current GDSC release, preferring FTP and falling back to HTML."""
    try:
        return await _list_release_files_via_ftp(ftp_host=ftp_host, ftp_dir=ftp_dir)
    except Exception:
        return await _list_release_files_via_download_page(base_url=base_url, archive_url=archive_url)


async def fetch_release_text(url: str, *, timeout: float = 30.0) -> str:
    """Fetch one release resource over HTTP(S)."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "OpenHarness/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GdscReleaseError(f"GDSC request failed: {exc}") from exc
    return response.text


async def _list_release_files_via_ftp(*, ftp_host: str, ftp_dir: str) -> list[GdscReleaseFile]:
    """List GDSC release files using anonymous FTP."""
    def _list() -> list[str]:
        with ftplib.FTP(ftp_host, timeout=20) as ftp:
            ftp.login()
            ftp.cwd(ftp_dir)
            return ftp.nlst()

    entries = await __import__("asyncio").to_thread(_list)
    files: list[GdscReleaseFile] = []
    for entry in entries:
        name = PurePosixPath(entry).name
        files.append(
            GdscReleaseFile(
                name=name,
                path=f"{ftp_dir.rstrip('/')}/{name}",
                url=f"ftp://{ftp_host}{ftp_dir.rstrip('/')}/{name}",
                source="ftp",
                category=classify_gdsc_file(name),
            )
        )
    if not files:
        raise GdscReleaseError("No files were returned from the GDSC FTP release directory.")
    return files


async def _list_release_files_via_download_page(
    *,
    base_url: str | None,
    archive_url: str,
) -> list[GdscReleaseFile]:
    """List GDSC release files by scraping the official bulk download page."""
    root = (base_url or DEFAULT_GDSC_BASE_URL).rstrip("/") + "/"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                urljoin(root, "downloads/bulk_download"),
                headers={"User-Agent": "OpenHarness/0.1"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GdscReleaseError(f"GDSC request failed: {exc}") from exc

    links: list[GdscReleaseFile] = []
    for match in re.finditer(
        r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<label>.*?)</a>',
        response.text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = html.unescape(match.group("href")).strip()
        if not href:
            continue
        absolute = urljoin(root, href)
        name = PurePosixPath(absolute).name or html_to_text(match.group("label"))
        if not name:
            continue
        links.append(
            GdscReleaseFile(
                name=name,
                path=absolute,
                url=absolute,
                source="downloads_page",
                category=classify_gdsc_file(name),
            )
        )
    if not links:
        raise GdscReleaseError("No files were discovered on the GDSC bulk download page.")

    archive_stub = GdscReleaseFile(
        name="archive",
        path=archive_url,
        url=archive_url,
        source="archive_page",
        category="archive",
    )
    deduped = {item.url: item for item in links}
    deduped[archive_stub.url] = archive_stub
    return list(deduped.values())


def select_compounds_file(files: list[GdscReleaseFile]) -> GdscReleaseFile | None:
    """Pick the compounds annotation file from discovered release files."""
    for item in files:
        lowered = item.name.lower()
        if "screened_compounds" in lowered or "compounds" in lowered:
            return item
    return None


def html_to_text(raw_html: str) -> str:
    """Convert HTML to compact readable text."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
