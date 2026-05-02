"""Helpers for querying the public GDC API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx


DEFAULT_GDC_API_BASE_URL = "https://api.gdc.cancer.gov"


class GdcApiError(RuntimeError):
    """Raised when the GDC API request fails or returns invalid data."""


def _normalize_values(values: str | Iterable[str]) -> list[str]:
    if isinstance(values, str):
        parts = values.replace("\n", ",").replace(";", ",").split(",")
    else:
        parts = list(values)
    result: list[str] = []
    for part in parts:
        text = str(part).strip()
        if text:
            result.append(text)
    return result


def exact_filter(field: str, value: str | Iterable[str] | None) -> dict[str, Any] | None:
    """Return a GDC exact-match filter for one or more values."""
    if value is None:
        return None
    values = _normalize_values(value)
    if not values:
        return None
    op = "in" if len(values) > 1 else "="
    content: dict[str, Any] = {"field": field, "value": values if len(values) > 1 else values[0]}
    return {"op": op, "content": content}


def combine_filters(filters: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Combine non-empty filters into one AND filter."""
    items = [item for item in filters if item is not None]
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return {"op": "and", "content": items}


async def request_gdc_json(
    endpoint: str,
    *,
    api_base_url: str | None = None,
    timeout: float = 20.0,
    **params: object,
) -> dict[str, Any]:
    """Call one JSON endpoint from the GDC API."""
    base_url = (api_base_url or DEFAULT_GDC_API_BASE_URL).rstrip("/")
    url = f"{base_url}/{endpoint.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers={"User-Agent": "OpenHarness/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GdcApiError(f"GDC API request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise GdcApiError("GDC API returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise GdcApiError("GDC API returned an unexpected response shape")
    return payload


def format_total(payload: dict[str, Any]) -> int | None:
    """Extract the total hit count from a GDC API payload when present."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    pagination = data.get("pagination")
    if not isinstance(pagination, dict):
        return None
    total = pagination.get("total")
    return int(total) if isinstance(total, int) else None
