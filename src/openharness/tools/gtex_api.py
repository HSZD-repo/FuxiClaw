"""Helpers for querying the public GTEx API."""

from __future__ import annotations

from typing import Any

import httpx


DEFAULT_GTEX_API_BASE_URL = "https://gtexportal.org/api/v2"


class GtexApiError(RuntimeError):
    """Raised when the GTEx API request fails or returns invalid data."""


async def request_gtex_json(
    endpoint: str,
    *,
    api_base_url: str | None = None,
    timeout: float = 20.0,
    **params: object,
) -> dict[str, Any]:
    """Call one JSON endpoint from the GTEx API."""
    base_url = (api_base_url or DEFAULT_GTEX_API_BASE_URL).rstrip("/")
    url = f"{base_url}/{endpoint.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers={"User-Agent": "OpenHarness/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GtexApiError(f"GTEx API request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise GtexApiError("GTEx API returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise GtexApiError("GTEx API returned an unexpected response shape")
    return payload


def extract_records(payload: dict[str, Any], *candidate_keys: str) -> list[dict[str, Any]]:
    """Extract a list of records from a GTEx payload with flexible key handling."""
    for key in candidate_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in candidate_keys:
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []
