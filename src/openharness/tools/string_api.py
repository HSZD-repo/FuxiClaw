"""Helpers for querying the public STRING API."""

from __future__ import annotations

from collections.abc import Iterable

import httpx


DEFAULT_STRING_API_BASE_URL = "https://string-db.org/api"
DEFAULT_CALLER_IDENTITY = "openharness"


class StringApiError(RuntimeError):
    """Raised when the STRING API request fails or returns invalid data."""


def parse_gene_terms(raw: str | Iterable[str]) -> list[str]:
    """Parse one string or iterable of strings into a normalized gene list."""
    if isinstance(raw, str):
        candidates = raw.replace("\n", ",").replace(";", ",").split(",")
    else:
        candidates = list(raw)
    terms: list[str] = []
    for candidate in candidates:
        for piece in str(candidate).split():
            normalized = piece.strip()
            if normalized:
                terms.append(normalized)
    return terms


async def request_string_json(
    endpoint: str,
    *,
    api_base_url: str | None = None,
    timeout: float = 20.0,
    **params: object,
) -> list[dict]:
    """Call one JSON endpoint from the STRING API."""
    base_url = (api_base_url or DEFAULT_STRING_API_BASE_URL).rstrip("/")
    url = f"{base_url}/json/{endpoint}"
    payload = {
        "caller_identity": DEFAULT_CALLER_IDENTITY,
        **params,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=payload, headers={"User-Agent": "OpenHarness/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StringApiError(f"STRING API request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise StringApiError("STRING API returned invalid JSON") from exc

    if not isinstance(data, list):
        raise StringApiError("STRING API returned an unexpected response shape")
    return data


def build_identifiers_param(genes: list[str]) -> str:
    """Encode a gene list in the newline-separated format expected by STRING."""
    return "\r".join(genes)


def build_string_result_url(genes: list[str], *, species: int) -> str:
    """Return a human-friendly STRING network page for the provided genes."""
    identifiers = "%0d".join(genes)
    return (
        "https://string-db.org/cgi/network?"
        f"identifiers={identifiers}&species={species}"
    )
