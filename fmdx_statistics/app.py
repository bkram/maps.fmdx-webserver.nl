"""Flask application entrypoint for the FMDX statistics site."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request, url_for

from . import cache as cache_backend
from .countries import country_name, normalize_country
from .geocoding import (
    annotate_geocode_locations,
    annotate_netherlands_locations,
)
from .receiver_blacklist import serialise_blacklist
from .stats import WORLD_SCOPE_ALIASES, aggregate_stats, available_country_counts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


_RECEIVER_HINT_KEYS = {
    "coords",
    "lat",
    "lng",
    "latitude",
    "longitude",
    "name",
    "url",
    "country",
    "countrycode",
    "country_code",
    "cc",
}


class DatasetUnavailableError(RuntimeError):
    """Raised when the remote receiver dataset cannot be loaded."""


def _normalise_scope_param(value: str | None, default: str = "nl") -> str:
    """Return a normalised scope value for map/statistics views."""

    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    lowered = text.lower()
    if lowered in WORLD_SCOPE_ALIASES:
        return "world"

    country_code = normalize_country(text)
    if country_code != "??":
        return country_code.lower()

    return default


def _resolve_scope_label(scope: str) -> str:
    """Return a human-friendly label for *scope*."""

    if scope == "world":
        return "Worldwide"

    name = country_name(scope)
    if name:
        return name

    code = normalize_country(scope)
    if code != "??":
        return code

    return scope.upper()


def _looks_like_receiver(candidate: Any) -> bool:
    """Return ``True`` when *candidate* resembles a receiver record."""

    if not isinstance(candidate, Mapping):
        return False

    normalised_keys = {
        str(key).strip().lower() for key in candidate.keys() if str(key).strip()
    }
    return bool(normalised_keys & _RECEIVER_HINT_KEYS)


def normalise_dataset(payload: Any) -> list[dict[str, Any]]:
    """Extract the receiver list from nested API responses."""

    visited: set[int] = set()

    def _search(obj: Any, depth: int = 0) -> list[Any] | None:
        if depth > 8:
            return None

        obj_id = id(obj)
        if obj_id in visited:
            return None
        visited.add(obj_id)

        if isinstance(obj, list):
            if not obj:
                return []
            if any(_looks_like_receiver(entry) for entry in obj):
                return obj
            for entry in obj:
                result = _search(entry, depth + 1)
                if result is not None:
                    return result
            return []

        if isinstance(obj, tuple):
            return _search(list(obj), depth + 1)

        if isinstance(obj, Mapping):
            for key in (
                "dataset",
                "data",
                "items",
                "receivers",
                "stations",
                "results",
                "result",
                "list",
                "payload",
            ):
                if key in obj:
                    result = _search(obj[key], depth + 1)
                    if result is not None:
                        return result
            for value in obj.values():
                result = _search(value, depth + 1)
                if result is not None:
                    return result

        return None

    found = _search(payload)
    if isinstance(found, list):
        return [dict(entry) for entry in found if isinstance(entry, Mapping)]
    return []


def create_app():
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )

    # Config via env
    app.config["REMOTE_API_URL"] = os.getenv(
        "REMOTE_API_URL", "https://servers.fmdx.org/api/"
    )
    app.config["CACHE_TTL"] = int(os.getenv("CACHE_TTL", "60"))  # seconds

    dataset_cache_lock = Lock()

    # ---------------- Dataset loading ----------------
    def _load_remote_dataset() -> list[dict[str, Any]]:
        """Fetch and normalise the remote dataset payload."""

        response = requests.get(app.config["REMOTE_API_URL"], timeout=10)
        response.raise_for_status()
        dataset = normalise_dataset(response.json())
        annotate_geocode_locations(dataset)
        annotate_netherlands_locations(dataset)
        return dataset

    def _get_dataset() -> list[dict[str, Any]]:
        ttl = app.config["CACHE_TTL"]

        def _cached_payload() -> list[dict[str, Any]]:
            payload = cache_backend.get_json("dataset:data")
            if not isinstance(payload, list):
                return []
            return [entry for entry in payload if isinstance(entry, dict)]

        def _cached_timestamp() -> float:
            timestamp_text = cache_backend.get_string("dataset:timestamp")
            if not timestamp_text:
                return 0.0
            try:
                return float(timestamp_text)
            except (TypeError, ValueError):
                return 0.0

        now = time.time()
        cached_payload = _cached_payload()
        if now - _cached_timestamp() < ttl:
            return cached_payload

        lock_ttl = min(max(float(ttl) * 0.25, 5.0), 10.0)
        acquired = False
        refresh_failed = False
        refreshed_dataset: list[dict[str, Any]] | None = None

        with dataset_cache_lock:
            if now - _cached_timestamp() < ttl:
                return _cached_payload()

            acquired = cache_backend.acquire_lock("dataset:refresh", lock_ttl)
            if acquired:
                try:
                    dataset = _load_remote_dataset()
                except Exception:
                    refresh_failed = True
                else:
                    refreshed_at = time.time()
                    cache_backend.set_json("dataset:data", dataset)
                    cache_backend.set_string("dataset:timestamp", str(refreshed_at))
                    refreshed_dataset = dataset
                finally:
                    cache_backend.release_lock("dataset:refresh")

        if refreshed_dataset is not None:
            return refreshed_dataset

        if refresh_failed:
            if cached_payload:
                return cached_payload
            raise DatasetUnavailableError("Remote receiver dataset refresh failed")

        if not acquired:
            if time.time() - _cached_timestamp() < ttl:
                cached_payload = _cached_payload()
                if cached_payload:
                    return cached_payload
            deadline = time.time() + lock_ttl
            while time.time() < deadline:
                if time.time() - _cached_timestamp() < ttl:
                    cached_payload = _cached_payload()
                    if cached_payload:
                        return cached_payload
                time.sleep(0.1)
            cached_payload = _cached_payload()
            if cached_payload:
                return cached_payload
            raise DatasetUnavailableError("Remote receiver dataset is unavailable")

        return _cached_payload()

    def _fallback_scope_options(current_scope: str) -> list[dict[str, str]]:
        """Return a minimal scope selector when dataset loading is unavailable."""

        def _map_url(scope_value: str) -> str:
            if scope_value == "world":
                return url_for("index")
            return url_for("index", scope=scope_value)

        def _stats_url(scope_value: str) -> str:
            if scope_value == "world":
                return url_for("statistics_page")
            return url_for("statistics_page", scope=scope_value)

        values = ["world"]
        if current_scope not in values:
            values.append(current_scope)

        return [
            {
                "value": value,
                "label": _resolve_scope_label(value),
                "map_url": _map_url(value),
                "statistics_url": _stats_url(value),
            }
            for value in values
        ]

    def _build_scope_options(current_scope: str) -> list[dict[str, str]]:
        """Return dropdown options for available scopes."""

        items = _get_dataset()
        country_counts = available_country_counts(items)

        def _map_url(scope_value: str) -> str:
            if scope_value == "world":
                return url_for("index")
            return url_for("index", scope=scope_value)

        def _stats_url(scope_value: str) -> str:
            if scope_value == "world":
                return url_for("statistics_page")
            return url_for("statistics_page", scope=scope_value)

        options: list[dict[str, str]] = [
            {
                "value": "world",
                "label": _resolve_scope_label("world"),
                "map_url": _map_url("world"),
                "statistics_url": _stats_url("world"),
            }
        ]

        countries: list[dict[str, str]] = []
        for country_code, _total in country_counts.items():
            value = country_code.lower()
            label = _resolve_scope_label(value)
            countries.append(
                {
                    "value": value,
                    "label": label,
                    "map_url": _map_url(value),
                    "statistics_url": _stats_url(value),
                }
            )

        countries.sort(key=lambda option: (option["label"].lower(), option["value"]))
        options.extend(countries)

        seen_values = {option["value"] for option in options}
        if current_scope not in seen_values:
            options.append(
                {
                    "value": current_scope,
                    "label": _resolve_scope_label(current_scope),
                    "map_url": _map_url(current_scope),
                    "statistics_url": _stats_url(current_scope),
                }
            )

        return options

    # ---------------- Routes ----------------
    @app.route("/")
    def index():
        map_scope = _normalise_scope_param(
            request.args.get("scope", ""), default="world"
        )
        scope_label = _resolve_scope_label(map_scope)
        dataset_error = False
        try:
            scope_options = _build_scope_options(map_scope)
        except DatasetUnavailableError:
            scope_options = _fallback_scope_options(map_scope)
            dataset_error = True

        return render_template(
            "index.html",
            active_page="map",
            map_scope=map_scope,
            scope_label=scope_label,
            scope_options=scope_options,
            dataset_error=dataset_error,
        )

    @app.route("/statistics")
    @app.route("/statistics.html")
    def statistics_page():
        scope = _normalise_scope_param(request.args.get("scope", ""), default="world")
        scope_label = _resolve_scope_label(scope)
        dataset_error = False
        try:
            scope_options = _build_scope_options(scope)
        except DatasetUnavailableError:
            scope_options = _fallback_scope_options(scope)
            dataset_error = True
        return render_template(
            "statistics.html",
            active_page="statistics",
            map_scope=scope,
            scope_label=scope_label,
            scope_options=scope_options,
            dataset_error=dataset_error,
        )

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/servers")
    def api_servers():
        try:
            items = _get_dataset()
        except DatasetUnavailableError as exc:
            return jsonify({"error": str(exc)}), 503
        blacklist = serialise_blacklist()
        return jsonify({"dataset": items, "blacklist": blacklist})

    @app.route("/api/stats")
    def api_stats():
        try:
            items = _get_dataset()
        except DatasetUnavailableError as exc:
            return jsonify({"error": str(exc)}), 503
        scope = _normalise_scope_param(request.args.get("scope", ""), default="world")
        stats = aggregate_stats(items, scope=scope)
        return jsonify(stats)

    @app.after_request
    def add_cache_headers(response):
        if request.path in ("/api/servers", "/api/stats"):
            ttl = app.config["CACHE_TTL"]
            response.headers["Cache-Control"] = (
                f"public, max-age={ttl}, must-revalidate"
            )
        return response

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "9090")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
