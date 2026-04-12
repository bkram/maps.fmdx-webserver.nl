"""Utilities for enriching receivers with reverse geocoded locations."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Iterable, Mapping

import requests
import reverse_geocoder as rg

from . import cache as cache_backend
from .receivers import parse_coordinates

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA_FILENAME = "rg_cities1000.csv"
_DEFAULT_DATA_ARCHIVE_URL = "https://download.geonames.org/export/dump/cities1000.zip"
_DEFAULT_ADMIN1_CODES_URL = (
    "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
)
_DEFAULT_ADMIN2_CODES_URL = "https://download.geonames.org/export/dump/admin2Codes.txt"


@dataclass(frozen=True)
class CityResult:
    """Normalised details returned by the reverse geocoder."""

    name: str | None
    admin1: str | None
    admin2: str | None
    country_code: str | None


_GEOCODER: rg.RGeocoder | None = None
_GEOCODER_LOCK = Lock()
_DATA_LOCK = Lock()
_CACHE_PRECISION = 4
_CACHE_BUCKET = "geocoding"
_EXCLUDED_FEATURE_CODES = {"PPLX"}


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_data_path() -> Path:
    """Return the filesystem path for the reverse geocoder dataset."""

    env_path = os.getenv("RG_CITIES_DATA_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_dir():
            return candidate / _DEFAULT_DATA_FILENAME
        return candidate
    return PROJECT_ROOT / "data" / _DEFAULT_DATA_FILENAME


def ensure_dataset() -> Path | None:
    """Ensure the reverse geocoder dataset is available locally."""

    path = _resolve_data_path()

    if path.exists():
        return path

    with _DATA_LOCK:
        if path.exists():
            return path
        data_url = os.getenv("RG_CITIES_DATA_URL", _DEFAULT_DATA_ARCHIVE_URL)
        try:
            if _looks_like_archive(data_url):
                admin1_url = os.getenv("RG_ADMIN1_CODES_URL", _DEFAULT_ADMIN1_CODES_URL)
                admin2_url = os.getenv("RG_ADMIN2_CODES_URL", _DEFAULT_ADMIN2_CODES_URL)
                _download_archive_dataset(path, data_url, admin1_url, admin2_url)
            else:
                _download_plain_dataset(path, data_url)
        except Exception:
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            return None

    return path if path.exists() else None


def _looks_like_archive(url: str) -> bool:
    return url.lower().endswith(".zip")


def _download_plain_dataset(path: Path, url: str) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_bytes(response.content)
    temp_path.replace(path)


def _fetch_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _parse_admin_map(payload: bytes) -> dict[str, str]:
    mapping: dict[str, str] = {}
    stream = io.StringIO(payload.decode("utf-8", errors="ignore"))
    reader = csv.reader(stream, delimiter="\t")
    for row in reader:
        if not row:
            continue
        key = row[0].strip()
        if not key or key.startswith("#"):
            continue
        name = ""
        if len(row) > 2:
            name = row[2].strip()
        if not name and len(row) > 1:
            name = row[1].strip()
        if name:
            mapping[key] = name
    return mapping


def _format_field(value: object) -> str:
    text = _clean_text(value)
    return text if text is not None else ""


def _download_archive_dataset(
    path: Path,
    archive_url: str,
    admin1_url: str,
    admin2_url: str,
) -> None:
    archive_bytes = _fetch_bytes(archive_url)
    admin1_bytes = _fetch_bytes(admin1_url)
    admin2_bytes = _fetch_bytes(admin2_url)

    admin1_map = _parse_admin_map(admin1_bytes)
    admin2_map = _parse_admin_map(admin2_bytes)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        member_name = _select_archive_member(archive)
        with archive.open(member_name) as raw_file:
            text_stream = io.TextIOWrapper(raw_file, encoding="utf-8", errors="ignore")
            reader = csv.reader(text_stream, delimiter="\t")
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + ".tmp")
            _write_geonames_csv(temp_path, reader, admin1_map, admin2_map)
            temp_path.replace(path)


def _select_archive_member(archive: zipfile.ZipFile) -> str:
    for name in archive.namelist():
        if name.endswith("cities1000.txt"):
            return name
    raise KeyError("cities1000.txt not found in archive")


def _write_geonames_csv(
    output_path: Path,
    rows: Iterable[list[str]],
    admin1_map: dict[str, str],
    admin2_map: dict[str, str],
) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["lat", "lon", "name", "admin1", "admin2", "cc"])
        for row in rows:
            if len(row) < 12:
                continue

            lat_raw = row[4].strip()
            lng_raw = row[5].strip()
            cc = _clean_text(row[8])

            if not lat_raw or not lng_raw or cc is None:
                continue

            try:
                float(lat_raw)
                float(lng_raw)
            except (TypeError, ValueError):
                continue

            feature_class = _clean_text(row[6])
            feature_code = _clean_text(row[7])

            if feature_class and feature_class != "P":
                continue
            if feature_code and feature_code in _EXCLUDED_FEATURE_CODES:
                continue

            name = _clean_text(row[2]) or _clean_text(row[1])
            if name is None:
                continue

            admin1_code = _clean_text(row[10])
            admin2_code = _clean_text(row[11])

            admin1_name = ""
            if admin1_code:
                admin1_name = _format_field(admin1_map.get(f"{cc}.{admin1_code}"))

            admin2_name = ""
            if admin1_code and admin2_code:
                key = f"{cc}.{admin1_code}.{admin2_code}"
                admin2_name = _format_field(admin2_map.get(key))

            if cc == "NL":
                municipality_name = _normalise_netherlands_municipality(admin2_name)
                normalised_city = _normalise_netherlands_name(name)
                if municipality_name == "Den Haag" and normalised_city != "Den Haag":
                    continue

            writer.writerow(
                [
                    lat_raw,
                    lng_raw,
                    name,
                    admin1_name,
                    admin2_name,
                    cc,
                ]
            )


def _build_geocoder() -> rg.RGeocoder | None:
    data_path = ensure_dataset()
    if data_path is None or not data_path.exists():
        return None

    with data_path.open("r", encoding="utf-8") as handle:
        stream = io.StringIO(handle.read())
    try:
        return rg.RGeocoder(mode=1, verbose=False, stream=stream)
    except Exception:
        return None


def _get_geocoder() -> rg.RGeocoder | None:
    global _GEOCODER

    if _GEOCODER is not None:
        return _GEOCODER

    with _GEOCODER_LOCK:
        if _GEOCODER is None:
            _GEOCODER = _build_geocoder()
    return _GEOCODER


def _cache_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, _CACHE_PRECISION), round(lng, _CACHE_PRECISION))


def _cache_field(key: tuple[float, float]) -> str:
    return f"{key[0]:.{_CACHE_PRECISION}f}:{key[1]:.{_CACHE_PRECISION}f}"


def _serialise_city(city: CityResult) -> str:
    return json.dumps(
        {
            "name": city.name,
            "admin1": city.admin1,
            "admin2": city.admin2,
            "country_code": city.country_code,
        }
    )


def lookup_city(lat: float, lng: float) -> CityResult | None:
    """Reverse geocode *lat* and *lng*, caching repeated lookups."""

    try:
        lat_value = float(lat)
        lng_value = float(lng)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(lat_value) or not math.isfinite(lng_value):
        return None

    key = _cache_key(lat_value, lng_value)
    field = _cache_field(key)

    cached_text = cache_backend.get_hash_string(_CACHE_BUCKET, field)
    if cached_text is not None:
        if cached_text == "null":
            return None
        try:
            cached_payload = json.loads(cached_text)
        except json.JSONDecodeError:
            cached_payload = None
        if isinstance(cached_payload, dict):
            cached_city = CityResult(
                name=_clean_text(cached_payload.get("name")),
                admin1=_clean_text(cached_payload.get("admin1")),
                admin2=_clean_text(cached_payload.get("admin2")),
                country_code=_clean_text(cached_payload.get("country_code")),
            )
            normalised_city = _apply_netherlands_municipality_override(cached_city)
            if normalised_city != cached_city:
                cache_backend.set_hash_string(
                    _CACHE_BUCKET, field, _serialise_city(normalised_city)
                )
            return normalised_city

    geocoder = _get_geocoder()
    if geocoder is None:
        cache_backend.set_hash_string(_CACHE_BUCKET, field, "null")
        return None

    try:
        result = geocoder.query([(lat_value, lng_value)])[0]
    except Exception:
        cache_backend.set_hash_string(_CACHE_BUCKET, field, "null")
        return None

    city = CityResult(
        name=_clean_text(result.get("name")),
        admin1=_clean_text(result.get("admin1")),
        admin2=_clean_text(result.get("admin2")),
        country_code=_clean_text(result.get("cc")),
    )
    city = _apply_netherlands_municipality_override(city)

    cache_backend.set_hash_string(_CACHE_BUCKET, field, _serialise_city(city))
    return city


def _city_from_mapping(payload: Mapping[str, object]) -> CityResult:
    """Construct a :class:`CityResult` from a mapping payload."""

    return CityResult(
        name=_clean_text(payload.get("city") or payload.get("name")),
        admin1=_clean_text(payload.get("admin1") or payload.get("state")),
        admin2=_clean_text(payload.get("admin2") or payload.get("county")),
        country_code=_clean_text(payload.get("countryCode") or payload.get("cc")),
    )


def annotate_geocode_locations(items: Iterable[dict]) -> None:
    """Add reverse-geocoded metadata to *items* when coordinates exist."""

    for item in items:
        if not isinstance(item, dict):
            continue

        lat, lng = parse_coordinates(item)
        if lat is None or lng is None:
            continue

        city = lookup_city(lat, lng)
        if city is None:
            continue

        payload = {
            "countryCode": city.country_code.upper() if city.country_code else None,
            "admin1": city.admin1,
            "admin2": city.admin2,
            "city": city.name,
        }

        cleaned = {key: value for key, value in payload.items() if value}
        if not cleaned:
            continue

        existing = item.get("geocode")
        if isinstance(existing, Mapping):
            merged = dict(existing)
            for key, value in cleaned.items():
                merged.setdefault(key, value)
            item["geocode"] = merged
        else:
            item["geocode"] = cleaned


_NL_BOUNDS = {
    "min_lat": 50.5,
    "max_lat": 53.7,
    "min_lng": 3.2,
    "max_lng": 7.3,
}


def _is_in_netherlands(lat: float, lng: float) -> bool:
    return (
        _NL_BOUNDS["min_lat"] <= lat <= _NL_BOUNDS["max_lat"]
        and _NL_BOUNDS["min_lng"] <= lng <= _NL_BOUNDS["max_lng"]
    )


_NL_NAME_REWRITES = {
    "'s-gravenhage": "Den Haag",
    "the hague": "Den Haag",
}

_NL_MUNICIPALITY_DEFAULTS = {
    "den haag": "Den Haag",
}

_NL_NEIGHBOURHOOD_KEYWORDS = ("buurt", "kwartier", "stadsdeel")


def _normalise_netherlands_name(value: str | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    rewrite = _NL_NAME_REWRITES.get(text.lower())
    return rewrite if rewrite is not None else text


def _normalise_netherlands_municipality(value: str | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    stripped = text.strip()
    lowered = stripped.lower()

    prefix = "gemeente "
    if lowered.startswith(prefix):
        stripped = stripped[len(prefix) :].lstrip()
        lowered = stripped.lower()

    suffix = " (gemeente)"
    if lowered.endswith(suffix):
        stripped = stripped[: -len(suffix)].rstrip()

    stripped = stripped.strip()
    return _normalise_netherlands_name(stripped)


def _looks_like_netherlands_neighbourhood(name: str) -> bool:
    lowered = name.lower()

    if any(keyword in lowered for keyword in _NL_NEIGHBOURHOOD_KEYWORDS):
        return True

    simplified = lowered.replace("-", " ").replace("/", " ")
    tokens = [token for token in simplified.split() if token]
    if tokens and tokens[-1].endswith("wijk"):
        return True

    return lowered.endswith("wijk")


def _apply_netherlands_municipality_override(city: CityResult) -> CityResult:
    if city.country_code not in {"NL", None}:
        return city

    preferred = _normalise_netherlands_municipality(city.admin2)
    if preferred == "Den Haag" and city.admin2 != "Den Haag":
        return CityResult(
            name=city.name,
            admin1=city.admin1,
            admin2=preferred,
            country_code=city.country_code,
        )

    return city


def _select_netherlands_city_name(city: CityResult) -> str | None:
    candidate = _normalise_netherlands_name(city.name)
    municipality = _normalise_netherlands_municipality(city.admin2)

    if municipality:
        municipality_lower = municipality.lower()

        if candidate:
            candidate_lower = candidate.lower()

            if candidate_lower == municipality_lower:
                return municipality

            if candidate_lower in municipality_lower:
                return candidate

            if _looks_like_netherlands_neighbourhood(candidate):
                return municipality
        else:
            candidate_lower = None

        default_city = _NL_MUNICIPALITY_DEFAULTS.get(municipality_lower)
        if default_city:
            default_lower = default_city.lower()
            if not candidate or candidate_lower != default_lower:
                return default_city

        if candidate:
            return candidate

        return municipality

    return candidate


def annotate_netherlands_locations(items: Iterable[dict]) -> None:
    """Add Netherlands city metadata to *items* when coordinates allow."""

    for item in items:
        if not isinstance(item, dict):
            continue

        lat, lng = parse_coordinates(item)
        if lat is None or lng is None:
            continue
        if not _is_in_netherlands(lat, lng):
            continue

        city_payload = item.get("geocode")
        city: CityResult | None = None
        if isinstance(city_payload, Mapping):
            city = _city_from_mapping(city_payload)
        if city is None:
            city = lookup_city(lat, lng)
        if city is None or city.country_code not in {"NL", None}:
            continue

        preferred_city = _select_netherlands_city_name(city)
        if preferred_city:
            if not _clean_text(item.get("nlCity")):
                item["nlCity"] = preferred_city
            if not _clean_text(item.get("city")):
                item["city"] = preferred_city
        if city.admin1 and not _clean_text(item.get("nlProvince")):
            item["nlProvince"] = city.admin1
        if city.admin2 and not _clean_text(item.get("nlMunicipality")):
            item["nlMunicipality"] = city.admin2


def reset_cached_geocoder() -> None:
    """Clear cached reverse geocoder state (primarily for tests)."""

    global _GEOCODER
    with _GEOCODER_LOCK:
        _GEOCODER = None
    cache_backend.delete_hash(_CACHE_BUCKET)
