"""General receiver blacklist helpers for scoped statistics views."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import cache as cache_backend
from .receivers import normalize_url, parse_coordinates

try:  # pragma: no cover - optional dependency guard
    import yaml  # type: ignore
except Exception:  # pragma: no cover - PyYAML missing
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ScopedBlacklistEntry:
    """Canonical representation of an entry ignored for a specific scope."""

    lat: float | None
    lng: float | None
    url: str | None
    tuner: str | None
    name: str | None


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CACHE_KEY = "receiver_blacklist"
_COORD_TOLERANCE = 1e-5


def _resolve_blacklist_path() -> Path:
    """Return the configured blacklist file path."""

    env_path = os.getenv("RECEIVER_BLACKLIST_PATH")
    if env_path:
        return Path(env_path)
    return _PROJECT_ROOT / "data" / "receiver_blacklist.yaml"


def _load_yaml_payload(path: Path) -> Mapping[str, Any] | None:
    """Parse the blacklist YAML file using PyYAML when available."""

    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8")

    if yaml is None:  # pragma: no cover - PyYAML missing
        return None

    data = yaml.safe_load(text) or {}
    if isinstance(data, Mapping):
        return data
    return None


def _coerce_lat_lng(source: Any) -> tuple[float | None, float | None]:
    """Normalise latitude/longitude values from YAML entries."""

    if isinstance(source, (list, tuple)) and len(source) >= 2:
        try:
            lat = float(source[0])
            lng = float(source[1])
        except (TypeError, ValueError):
            return None, None
        if math.isfinite(lat) and math.isfinite(lng):
            return lat, lng
    return None, None


def _clean_text(value: Any) -> str | None:
    """Return a lowercased trimmed string for comparisons."""

    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def _prepare_entry(raw_entry: Mapping[str, Any]) -> ScopedBlacklistEntry | None:
    """Convert a raw YAML entry into a structured representation."""

    coords = raw_entry.get("coords")
    if coords is None:
        coords = raw_entry.get("coordinates")
    lat, lng = _coerce_lat_lng(coords)

    url = normalize_url(raw_entry.get("url"))
    tuner = _clean_text(raw_entry.get("tuner"))
    name = _clean_text(raw_entry.get("name"))

    if url is None or lat is None or lng is None:
        return None

    return ScopedBlacklistEntry(lat=lat, lng=lng, url=url, tuner=tuner, name=name)


def load_blacklist() -> dict[str, tuple[ScopedBlacklistEntry, ...]]:
    """Load and cache blacklist entries grouped by scope."""

    path = _resolve_blacklist_path()

    try:
        source_mtime = path.stat().st_mtime
    except OSError:
        source_mtime = 0.0

    cached_payload = cache_backend.get_json(_CACHE_KEY)
    if isinstance(cached_payload, dict):
        cached_mtime = cached_payload.get("mtime")
        try:
            cached_mtime_value = (
                float(cached_mtime) if cached_mtime is not None else None
            )
        except (TypeError, ValueError):
            cached_mtime_value = None
        if cached_mtime_value is not None and cached_mtime_value >= source_mtime:
            cached_entries = cached_payload.get("entries")
            if isinstance(cached_entries, dict):
                result: dict[str, tuple[ScopedBlacklistEntry, ...]] = {}
                for scope, entries in cached_entries.items():
                    if not isinstance(scope, str) or not isinstance(entries, list):
                        continue
                    scoped_entries: list[ScopedBlacklistEntry] = []
                    for raw in entries:
                        if not isinstance(raw, Mapping):
                            continue
                        lat = raw.get("lat")
                        lng = raw.get("lng")
                        tuner = raw.get("tuner")
                        name = raw.get("name")
                        url = raw.get("url")
                        try:
                            lat_val = float(lat) if lat is not None else None
                            lng_val = float(lng) if lng is not None else None
                        except (TypeError, ValueError):
                            lat_val = None
                            lng_val = None
                        tuner_text = _clean_text(tuner)
                        name_text = _clean_text(name)
                        url_text = normalize_url(url)
                        scoped_entries.append(
                            ScopedBlacklistEntry(
                                lat=lat_val,
                                lng=lng_val,
                                url=url_text,
                                tuner=tuner_text,
                                name=name_text,
                            )
                        )
                    if scoped_entries:
                        result[scope] = tuple(scoped_entries)
                return result

    parsed = _load_yaml_payload(path)
    if parsed is None:
        cache_backend.set_json(_CACHE_KEY, {"mtime": source_mtime, "entries": {}})
        return {}

    scopes: dict[str, tuple[ScopedBlacklistEntry, ...]] = {}

    raw_scopes = parsed.get("blacklist") if isinstance(parsed, Mapping) else None
    if not isinstance(raw_scopes, Mapping):
        raw_scopes = parsed

    if isinstance(raw_scopes, Mapping):
        for scope, entries in raw_scopes.items():
            if not isinstance(scope, str) or not isinstance(entries, list):
                continue
            prepared: list[ScopedBlacklistEntry] = []
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                prepared_entry = _prepare_entry(entry)
                if prepared_entry is not None:
                    prepared.append(prepared_entry)
            if prepared:
                scopes[scope.lower()] = tuple(prepared)

    cache_backend.set_json(
        _CACHE_KEY,
        {
            "mtime": source_mtime,
            "entries": {
                scope: [
                    {
                        "lat": entry.lat,
                        "lng": entry.lng,
                        "url": entry.url,
                        "tuner": entry.tuner,
                        "name": entry.name,
                    }
                    for entry in entries
                ]
                for scope, entries in scopes.items()
            },
        },
    )

    return scopes


def _matches_entry(
    entry: ScopedBlacklistEntry,
    item: Mapping[str, Any],
    lat: float | None,
    lng: float | None,
) -> bool:
    """Return ``True`` when *entry* applies to *item*."""

    if entry.url is None or entry.lat is None or entry.lng is None:
        return False

    norm_url = normalize_url(item.get("url"))
    if norm_url is None or norm_url != entry.url:
        return False

    if lat is None or lng is None:
        return False

    if abs(lat - entry.lat) > _COORD_TOLERANCE:
        return False

    if abs(lng - entry.lng) > _COORD_TOLERANCE:
        return False

    tuner_value = _clean_text(item.get("tuner"))
    name_value = _clean_text(item.get("name"))

    if entry.tuner is not None and tuner_value != entry.tuner:
        return False

    if entry.name is not None and name_value != entry.name:
        return False

    return True


def is_blacklisted_for_scope(
    scope: str | None,
    item: Mapping[str, Any],
    lat: float | None = None,
    lng: float | None = None,
) -> bool:
    """Return ``True`` when *item* should be ignored for the given *scope*."""

    if not scope:
        return False

    scope_key = str(scope).strip().lower()
    if not scope_key:
        return False

    scoped_entries = load_blacklist().get(scope_key)
    if not scoped_entries:
        return False

    if lat is None or lng is None:
        parsed_lat, parsed_lng = parse_coordinates(dict(item))
        lat = lat if lat is not None else parsed_lat
        lng = lng if lng is not None else parsed_lng

    for entry in scoped_entries:
        if _matches_entry(entry, item, lat, lng):
            return True

    return False


def reset_cached_blacklist() -> None:
    """Clear cached blacklist data (primarily for tests)."""

    cache_backend.delete(_CACHE_KEY)


def serialise_blacklist(scope: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return a JSON-safe view of the scoped blacklist entries."""

    scopes: dict[str, tuple[ScopedBlacklistEntry, ...]] = load_blacklist()

    def _format_entry(entry: ScopedBlacklistEntry) -> dict[str, Any]:
        coords = None
        if entry.lat is not None and entry.lng is not None:
            coords = [entry.lat, entry.lng]
        return {
            "url": entry.url,
            "coords": coords,
            "tuner": entry.tuner,
            "name": entry.name,
        }

    if scope is not None:
        key = str(scope).strip().lower()
        if not key:
            return {}
        entries = scopes.get(key, ())
        if not entries:
            return {}
        return {key: [_format_entry(entry) for entry in entries]}

    payload: dict[str, list[dict[str, Any]]] = {}
    for key, entries in scopes.items():
        payload[key] = [_format_entry(entry) for entry in entries]
    return payload
