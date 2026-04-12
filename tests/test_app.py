"""Tests for Flask routes and remote dataset loading."""

from __future__ import annotations

from typing import Any

from fmdx_statistics import app as app_module
from fmdx_statistics.cache import InMemoryCache, set_backend


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _fake_get_factory(payload: dict[str, Any]):
    def _fake_get(url, **kwargs):
        del url, kwargs
        return _FakeResponse(payload)

    return _fake_get


def test_api_servers_uses_remote_dataset(monkeypatch):
    dataset = [
        {
            "name": "Test Receiver",
            "url": "https://example.test/rx",
            "coords": [52.0, 4.0],
            "country": "NL",
        }
    ]

    set_backend(InMemoryCache())
    monkeypatch.setattr(app_module, "annotate_geocode_locations", lambda items: None)
    monkeypatch.setattr(
        app_module, "annotate_netherlands_locations", lambda items: None
    )
    monkeypatch.setattr(
        app_module.requests,
        "get",
        _fake_get_factory({"dataset": dataset}),
    )

    client = app_module.create_app().test_client()
    response = client.get("/api/servers")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["dataset"] == dataset
    assert "blacklist" in payload


def test_api_stats_passes_scope_to_aggregator(monkeypatch):
    dataset = [{"name": "Scoped Receiver", "url": "https://example.test/rx"}]

    set_backend(InMemoryCache())
    monkeypatch.setattr(app_module, "annotate_geocode_locations", lambda items: None)
    monkeypatch.setattr(
        app_module, "annotate_netherlands_locations", lambda items: None
    )
    monkeypatch.setattr(
        app_module.requests,
        "get",
        _fake_get_factory({"dataset": dataset}),
    )
    monkeypatch.setattr(
        app_module,
        "aggregate_stats",
        lambda items, scope=None: {
            "summary": {"total": len(items), "scope": {"id": scope or "world"}}
        },
    )

    client = app_module.create_app().test_client()
    response = client.get("/api/stats?scope=nl")

    assert response.status_code == 200
    assert response.get_json() == {
        "summary": {"total": 1, "scope": {"id": "nl"}}
    }


def test_api_servers_returns_503_when_remote_dataset_unavailable(monkeypatch):
    set_backend(InMemoryCache())
    monkeypatch.setattr(
        app_module.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = app_module.create_app().test_client()
    response = client.get("/api/servers")

    assert response.status_code == 503
    assert "error" in response.get_json()


def test_index_still_renders_when_remote_dataset_unavailable(monkeypatch):
    set_backend(InMemoryCache())
    monkeypatch.setattr(
        app_module.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = app_module.create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Live Dataset Unavailable" in response.data


def test_statistics_page_shows_dataset_error_banner(monkeypatch):
    set_backend(InMemoryCache())
    monkeypatch.setattr(
        app_module.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = app_module.create_app().test_client()
    response = client.get("/statistics")

    assert response.status_code == 200
    assert b"Live Dataset Unavailable" in response.data


def test_healthz_returns_ok():
    client = app_module.create_app().test_client()
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
