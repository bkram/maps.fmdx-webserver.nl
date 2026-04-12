"""Tests for receiver metadata helpers."""

from fmdx_statistics.receivers import normalize_url, parse_coordinates


def test_parse_coordinates_accepts_numeric_strings():
    lat, lng = parse_coordinates({"coords": ["52.1", "4.3"]})
    assert lat == 52.1
    assert lng == 4.3


def test_parse_coordinates_rejects_invalid_payloads():
    assert parse_coordinates({}) == (None, None)
    assert parse_coordinates({"coords": ["x", "4.3"]}) == (None, None)


def test_normalize_url_lowercases_and_trims_trailing_slash():
    assert normalize_url(" HTTPS://Example.COM/path/ ") == "https://example.com/path"
    assert normalize_url("") is None
