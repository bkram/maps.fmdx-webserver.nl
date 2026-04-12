"""Tests for country normalization helpers."""

from fmdx_statistics.countries import continent_name, country_name, normalize_country


def test_normalize_country_supports_aliases():
    assert normalize_country("Netherlands") == "NL"
    assert normalize_country("USA") == "US"
    assert normalize_country("GBR") == "GB"


def test_country_and_continent_names_resolve():
    assert country_name("NL") == "Netherlands"
    assert continent_name("NL") == "Europe"


def test_unknown_country_returns_placeholder():
    assert normalize_country("not-a-country") == "??"
    assert country_name("not-a-country") is None
