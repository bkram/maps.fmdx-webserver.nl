"""Utilities for aggregating FMDX receiver statistics."""

from urllib.parse import urlparse
from collections import Counter, defaultdict

from .geocoding import CityResult, lookup_city
from .population import population_for_country, receivers_per_million
from .receiver_blacklist import is_blacklisted_for_scope

from .countries import continent_name, normalize_country
from .detectors import os_family
from .receivers import parse_coordinates
from .tuners import tuner_family

COUNTRY_FIELD_KEYS = ("countryCode", "country_code", "cc", "countryName", "country")

SUBDIVISION_SCOPES = {
    "nl": {
        "label": "Provinces",
        "country_codes": {"NL"},
        "fields": ("nlProvince", "province", "state", "region"),
        "geocode": True,
    },
    "us": {
        "label": "States",
        "country_codes": {"US"},
        "fields": ("usState", "state", "province", "region"),
        "geocode": True,
    },
    "jp": {
        "label": "Prefectures",
        "country_codes": {"JP"},
        "fields": ("jpPrefecture", "prefecture", "province", "region"),
        "geocode": True,
    },
}

WORLD_SCOPE_ALIASES = {"world", "global", "all", "worldwide"}


def available_country_counts(items: list[dict]) -> dict[str, int]:
    """Return receiver totals per country excluding blacklisted entries."""

    counts: Counter[str] = Counter()

    for item in items:
        lat, lng = parse_coordinates(item)
        city: CityResult | None = None
        if lat is not None and lng is not None:
            city = lookup_city(lat, lng)

        country_code = _resolve_country_code(item, lat, lng, city)
        if country_code == "??":
            continue

        scope_id = country_code.lower()
        if is_blacklisted_for_scope(scope_id, item, lat, lng):
            continue

        counts[country_code] += 1

    return dict(counts)


def _normalise_scope(scope: str | None) -> tuple[str, str | None]:
    """Return a lower-cased scope identifier and ISO country code when available."""

    if scope is None:
        return "world", None

    text = str(scope).strip()
    if not text:
        return "world", None

    lowered = text.lower()
    if lowered in WORLD_SCOPE_ALIASES:
        return "world", None

    country_code = normalize_country(text)
    if country_code == "??":
        return "world", None

    return country_code.lower(), country_code


def _resolve_country_code(
    item: dict,
    lat: float | None,
    lng: float | None,
    city: CityResult | None = None,
) -> str:
    """Map the raw country fields to an ISO2 code, mirroring the map heuristics."""

    if city is None and lat is not None and lng is not None:
        city = lookup_city(lat, lng)

    if city is not None and city.country_code:
        return city.country_code.upper()

    for key in COUNTRY_FIELD_KEYS:
        code = normalize_country(item.get(key))
        if code != "??":
            return code

    return "??"


def _normalise_stat_field(value: object, default: str = "Unknown") -> str:
    """Return a trimmed string for counters with a sensible fallback."""

    if value is None:
        return default

    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    text = str(value).strip()
    return text if text else default


def _is_supporter_url(value: object) -> bool:
    """Return ``True`` when the URL points at fmtuner.org."""

    if value is None:
        return False

    text = str(value).strip().lower()
    if not text:
        return False

    try:
        hostname = (urlparse(text).hostname or "").strip(".").lower()
    except ValueError:
        hostname = ""

    if hostname:
        return hostname == "fmtuner.org" or hostname.endswith(".fmtuner.org")

    return "fmtuner.org" in text


def _clean_label(value: object) -> str | None:
    """Return a normalised label for subdivision counters."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_subdivision(
    scope: str,
    item: dict,
    lat: float | None,
    lng: float | None,
    country_code: str,
    city: CityResult | None = None,
) -> str | None:
    """Determine the subdivision label for the configured *scope*."""

    config = SUBDIVISION_SCOPES.get(scope)
    if not config:
        return None

    if config["country_codes"] and country_code not in config["country_codes"]:
        return None

    for field in config.get("fields", ()):  # pragma: no cover - defensive loop
        label = _clean_label(item.get(field))
        if label:
            return label

    if not config.get("geocode"):
        return None

    if city is None:
        if lat is None or lng is None:
            return None
        city = lookup_city(lat, lng)
    if city is None:
        return None

    if city.country_code and config["country_codes"]:
        if city.country_code.upper() not in config["country_codes"]:
            return None

    return _clean_label(city.admin1)


def aggregate_stats(items: list[dict], scope: str | None = None) -> dict:
    """Aggregate statistics from a dataset of receivers."""

    normalized_scope, restrict_to_scope = _normalise_scope(scope)

    total = 0

    countries_counter = Counter()
    continents_counter = Counter()
    os_family_counter = Counter()
    tuner_counter = Counter()
    tuner_arch_counter = Counter()
    version_counter = Counter()
    status_counter = Counter()
    audio_quality_counter = Counter()
    audio_channels_counter = Counter()
    supporters_total = 0
    os_by_country = defaultdict(Counter)
    os_by_subdivision = defaultdict(Counter)
    subdivisions_counter = Counter()

    for it in items:
        lat, lng = parse_coordinates(it)
        city: CityResult | None = None
        if lat is not None and lng is not None:
            city = lookup_city(lat, lng)

        resolved_country = _resolve_country_code(it, lat, lng, city)

        if restrict_to_scope and resolved_country != restrict_to_scope:
            continue

        if normalized_scope != "world" and is_blacklisted_for_scope(
            normalized_scope, it, lat, lng
        ):
            continue

        total += 1
        country_code = resolved_country
        countries_counter[country_code] += 1
        continent = continent_name(country_code)
        if continent:
            continents_counter[continent] += 1

        fam = os_family(it.get("os"))
        os_family_counter[fam] += 1
        os_by_country[country_code][fam] += 1

        subdivision_label = _resolve_subdivision(
            normalized_scope, it, lat, lng, country_code, city
        )
        if subdivision_label:
            subdivisions_counter[subdivision_label] += 1
            os_by_subdivision[subdivision_label][fam] += 1

        tuner_str = (it.get("tuner") or "Unknown").strip()
        tuner_counter[tuner_str] += 1
        tuner_arch_counter[tuner_family(tuner_str)] += 1

        version_counter[_normalise_stat_field(it.get("version"))] += 1

        audio_quality_counter[_normalise_stat_field(it.get("audioQuality"))] += 1
        audio_channels_counter[_normalise_stat_field(it.get("audioChannels"))] += 1
        if _is_supporter_url(it.get("url")):
            supporters_total += 1

        status = it.get("status")
        if status == 2:
            status_counter["locked"] += 1
        elif status == 1:
            status_counter["public"] += 1
        else:
            status_counter["unknown"] += 1

    countries_covered = len([c for c in countries_counter if c != "??"])
    by_country_population: dict[str, int] = {}
    by_country_per_million: dict[str, float] = {}
    continent_population_counter = Counter()

    for country_code, count in countries_counter.items():
        if country_code == "??":
            continue
        continent = continent_name(country_code)
        population = population_for_country(country_code)
        if population is None:
            continue
        by_country_population[country_code] = population
        per_million = receivers_per_million(count, population)
        if per_million is not None:
            by_country_per_million[country_code] = per_million
        if continent:
            continent_population_counter[continent] += population

    by_continent_per_million: dict[str, float] = {}
    for continent, count in continents_counter.items():
        population = continent_population_counter.get(continent)
        per_million = receivers_per_million(count, population)
        if per_million is not None:
            by_continent_per_million[continent] = per_million

    scope_summary: dict[str, object] = {"id": normalized_scope}
    if restrict_to_scope:
        scope_population = population_for_country(restrict_to_scope)
        scope_per_million = receivers_per_million(
            countries_counter.get(restrict_to_scope, 0), scope_population
        )
        scope_summary["countryCode"] = restrict_to_scope
        scope_summary["matchCount"] = int(countries_counter.get(restrict_to_scope, 0))
        if scope_population is not None:
            scope_summary["population"] = scope_population
        if scope_per_million is not None:
            scope_summary["receiversPerMillion"] = scope_per_million

    return {
        "summary": {
            "total": total,
            "countriesCovered": countries_covered,
            "supporters": supporters_total,
            "status": dict(status_counter),
            "scope": scope_summary,
        },
        "byCountry": dict(countries_counter),
        "byCountryPopulation": by_country_population,
        "byCountryPerMillion": by_country_per_million,
        "byContinent": dict(continents_counter),
        "byContinentPerMillion": by_continent_per_million,
        "byOsFamily": dict(os_family_counter),
        "osByCountry": {
            country: dict(counter) for country, counter in os_by_country.items()
        },
        "osBySubdivision": {
            name: dict(counter) for name, counter in os_by_subdivision.items()
        },
        "subdivisions": {
            "label": SUBDIVISION_SCOPES.get(normalized_scope, {}).get("label"),
            "counts": dict(subdivisions_counter),
        },
        "byTuner": dict(tuner_counter),
        "byTunerArch": dict(tuner_arch_counter),
        "byVersion": dict(version_counter),
        "byAudioQuality": dict(audio_quality_counter),
        "byAudioChannels": dict(audio_channels_counter),
    }
