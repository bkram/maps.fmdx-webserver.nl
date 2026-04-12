"""Country population lookups used for per-capita statistics."""

from __future__ import annotations

from typing import Any

from .countries import normalize_country


# Current population values for countries present in the live FMDX feed.
# Source used when assembling this table: REST Countries API, 2026-04-09.
_POPULATION_BY_COUNTRY: dict[str, int] = {
    "AT": 9200931,
    "AU": 27536874,
    "BA": 3422000,
    "BE": 11825551,
    "BF": 24070553,
    "BG": 6437360,
    "BM": 64055,
    "BR": 213421037,
    "CA": 41651653,
    "CH": 9082848,
    "CL": 20206953,
    "CW": 156115,
    "CZ": 10882341,
    "DE": 83491249,
    "DK": 6011488,
    "DZ": 47400000,
    "EE": 1369995,
    "ES": 49315949,
    "FI": 5650325,
    "FR": 66351959,
    "GB": 69281437,
    "GR": 10400720,
    "HR": 3866233,
    "HU": 9539502,
    "IE": 5458600,
    "IN": 1417492000,
    "IT": 58927633,
    "JP": 123210000,
    "LT": 2894886,
    "LU": 681973,
    "MX": 130575786,
    "NL": 18100436,
    "NO": 5606944,
    "NZ": 5324700,
    "PE": 34350244,
    "PH": 114123600,
    "PL": 37392000,
    "PT": 10749635,
    "RO": 19036031,
    "RS": 6567783,
    "RU": 146028325,
    "SE": 10605098,
    "SK": 5413813,
    "UA": 32862000,
    "US": 340110988,
}


def population_for_country(value: Any) -> int | None:
    """Return the population for *value* when a lookup is available."""

    code = normalize_country(value)
    if code == "??":
        return None
    return _POPULATION_BY_COUNTRY.get(code)


def receivers_per_million(count: int | float, population: int | None) -> float | None:
    """Return receivers per one million inhabitants."""

    if population is None or population <= 0:
        return None
    return (float(count) * 1_000_000.0) / float(population)
