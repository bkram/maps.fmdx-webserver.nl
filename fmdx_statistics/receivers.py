from __future__ import annotations

import math
from typing import Any

Coordinates = tuple[float | None, float | None]


def _coerce_float(value: Any) -> float | None:
    """Return ``value`` as a finite float when possible."""

    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None

    return as_float if math.isfinite(as_float) else None


def parse_coordinates(item: dict) -> Coordinates:
    """Extract latitude/longitude values from *item* when present."""

    coords = item.get("coords")
    if not isinstance(coords, (list, tuple)):
        return None, None

    if len(coords) < 2:
        return None, None

    lat = _coerce_float(coords[0])
    lng = _coerce_float(coords[1])

    if lat is None or lng is None:
        return None, None

    return lat, lng


def normalize_url(value: object) -> str | None:
    """Canonicalise receiver URLs for reliable comparisons."""

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.rstrip("/")
    if not normalized:
        return None

    return normalized.lower()
