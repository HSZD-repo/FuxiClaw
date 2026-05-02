"""Helpers for querying public DepMap portal exports."""

from __future__ import annotations

import csv
import io
from typing import Any

import httpx


DEFAULT_DEPMAP_PORTAL_BASE_URL = "https://depmap.org/portal/api/download"


class DepmapApiError(RuntimeError):
    """Raised when a DepMap API request fails or returns invalid content."""


async def request_depmap_text(
    path_or_url: str,
    *,
    api_base_url: str | None = None,
    timeout: float = 30.0,
) -> str:
    """Fetch one text response from a DepMap endpoint or URL."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        url = path_or_url
    else:
        base_url = (api_base_url or DEFAULT_DEPMAP_PORTAL_BASE_URL).rstrip("/")
        url = f"{base_url}/{path_or_url.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "OpenHarness/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DepmapApiError(f"DepMap request failed: {exc}") from exc
    return response.text


def parse_csv_rows(text: str) -> list[dict[str, str]]:
    """Parse a CSV string into dictionaries."""
    reader = csv.DictReader(io.StringIO(text))
    return [{str(k): str(v) for k, v in row.items() if k is not None} for row in reader]


async def fetch_depmap_csv(
    path_or_url: str,
    *,
    api_base_url: str | None = None,
) -> list[dict[str, str]]:
    """Fetch and parse one DepMap CSV export."""
    text = await request_depmap_text(path_or_url, api_base_url=api_base_url)
    try:
        rows = parse_csv_rows(text)
    except Exception as exc:  # pragma: no cover - defensive
        raise DepmapApiError("DepMap returned invalid CSV") from exc
    if not rows:
        raise DepmapApiError("DepMap returned no rows")
    return rows


def find_first_nonempty(row: dict[str, str], *keys: str) -> str:
    """Return the first non-empty string found in the provided keys."""
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


def choose_model_metadata_file(rows: list[dict[str, str]]) -> dict[str, str] | None:
    """Pick the most likely model metadata CSV from the files listing."""
    for row in rows:
        name = find_first_nonempty(row, "filename", "name", "display_name")
        lowered = name.lower()
        if lowered == "model.csv" or lowered.endswith("/model.csv"):
            return row
    for row in rows:
        name = find_first_nonempty(row, "filename", "name", "display_name")
        lowered = name.lower()
        if lowered == "sample_info.csv" or lowered.endswith("/sample_info.csv"):
            return row
    return None
