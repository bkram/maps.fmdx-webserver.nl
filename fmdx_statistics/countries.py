"""Country normalization helpers for receiver metadata."""

from typing import Any, Iterable, cast

import pycountry


def _get_str_attr(source: Any, attr: str) -> str | None:
    """Return ``source.attr`` when it exists and is a string."""

    value = getattr(source, attr, None)
    return value if isinstance(value, str) else None


def _lookup_country_alpha2(candidate: str) -> str | None:
    """Return an ISO alpha-2 code for *candidate* using ``pycountry``."""

    try:
        record = pycountry.countries.lookup(candidate)
    except LookupError:
        return None

    return _get_str_attr(record, "alpha_2")


_COUNTRY_RECORDS = list(cast(Iterable[Any], pycountry.countries))
_ALPHA2: set[str] = set()
_ALPHA3_TO_ALPHA2: dict[str, str] = {}
_ALPHA2_TO_NAME: dict[str, str] = {}

for _record in _COUNTRY_RECORDS:
    _alpha2 = _get_str_attr(_record, "alpha_2")
    if _alpha2:
        _ALPHA2.add(_alpha2)
        name = (
            _get_str_attr(_record, "common_name")
            or _get_str_attr(_record, "name")
            or _get_str_attr(_record, "official_name")
        )
        if name:
            _ALPHA2_TO_NAME[_alpha2] = name

    _alpha3 = _get_str_attr(_record, "alpha_3")
    if _alpha2 and _alpha3:
        _ALPHA3_TO_ALPHA2[_alpha3] = _alpha2

# Manual overrides / aliases
_ALIASES = {
    "NETHERLANDS": "NL",
    "NEDERLAND": "NL",
    "HOLLAND": "NL",
    "UK": "GB",
    "UNITED KINGDOM": "GB",
    "ENGLAND": "GB",
    "SCOTLAND": "GB",
    "WALES": "GB",
    "USA": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
}

_CONTINENT_BY_ALPHA2 = {
    "DZ": "Africa",
    "BF": "Africa",
    "BM": "North America",
    "CA": "North America",
    "CW": "North America",
    "MX": "North America",
    "US": "North America",
    "BR": "South America",
    "CL": "South America",
    "PE": "South America",
    "AU": "Oceania",
    "NZ": "Oceania",
    "AT": "Europe",
    "BA": "Europe",
    "BE": "Europe",
    "BG": "Europe",
    "CH": "Europe",
    "CZ": "Europe",
    "DE": "Europe",
    "DK": "Europe",
    "EE": "Europe",
    "ES": "Europe",
    "FI": "Europe",
    "FR": "Europe",
    "GB": "Europe",
    "GR": "Europe",
    "HR": "Europe",
    "HU": "Europe",
    "IE": "Europe",
    "IT": "Europe",
    "LT": "Europe",
    "LU": "Europe",
    "NL": "Europe",
    "NO": "Europe",
    "PL": "Europe",
    "PT": "Europe",
    "RO": "Europe",
    "RS": "Europe",
    "RU": "Europe",
    "SE": "Europe",
    "SK": "Europe",
    "UA": "Europe",
    "IN": "Asia",
    "JP": "Asia",
    "PH": "Asia",
}


def normalize_country(value) -> str:
    """
    Normalize country inputs (codes, names, aliases) into ISO alpha-2 codes.
    Returns "??" if not recognized.
    """
    if value is None:
        return "??"
    s = str(value).strip()
    if not s:
        return "??"
    u = s.upper()

    # ISO2?
    if len(u) == 2 and u.isalpha() and u in _ALPHA2:
        return u

    # ISO3?
    if len(u) == 3 and u.isalpha() and u in _ALPHA3_TO_ALPHA2:
        return _ALPHA3_TO_ALPHA2[u]

    # Aliases
    if u in _ALIASES:
        return _ALIASES[u]

    # Try pycountry name/code lookup
    alpha2_lookup = _lookup_country_alpha2(s)
    if alpha2_lookup:
        return alpha2_lookup

    if u.startswith("THE "):  # e.g. "The Netherlands"
        trimmed_lookup = _lookup_country_alpha2(s[4:].strip())
        if trimmed_lookup:
            return trimmed_lookup

    return "??"


def country_name(value: Any) -> str | None:
    """Return the human-readable name for *value* when available."""

    code = normalize_country(value)
    if code == "??":
        return None
    return _ALPHA2_TO_NAME.get(code)


def continent_name(value: Any) -> str | None:
    """Return the continent label for *value* when available."""

    code = normalize_country(value)
    if code == "??":
        return None
    return _CONTINENT_BY_ALPHA2.get(code)
