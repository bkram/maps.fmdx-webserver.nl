"""Application-wide caching utilities backed by Redis."""

from __future__ import annotations

import json
import os
import time
from threading import Lock
from typing import Any, Protocol

try:  # pragma: no cover - optional dependency guard
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis missing
    redis = None  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[assignment]


_CACHE_PREFIX = "fmdx:"
_LOCK_PREFIX = "locks:"


class CacheBackend(Protocol):
    """Minimal interface required by the application cache helpers."""

    def get(self, name: str) -> bytes | None:
        """Return the cached value for *name* or ``None`` when missing."""

    def set(self, name: str, value: bytes) -> None:
        """Store *value* under *name*."""

    def delete(self, *names: str) -> None:
        """Remove the provided cache *names* when they exist."""

    def hget(self, name: str, field: str) -> bytes | None:
        """Return the hash *field* from the *name* bucket."""

    def hset(self, name: str, field: str, value: bytes) -> None:
        """Store *value* in the hash bucket *name* under *field*."""

    def hdel(self, name: str, *fields: str) -> None:
        """Remove *fields* from the hash bucket *name*."""

    def clear(self, prefix: str) -> None:
        """Remove cached entries that start with *prefix*."""

    def add(self, name: str, value: bytes, ttl: float) -> bool:
        """Store *value* under *name* when it does not yet exist.

        The entry should expire after *ttl* seconds. The method returns ``True``
        when the key was stored and ``False`` if it already existed or the
        backend could not honour the request.
        """

        ...


class RedisCache:
    """Redis-backed cache implementation."""

    def __init__(self, url: str):
        if redis is None:  # pragma: no cover - import guard
            raise RuntimeError("redis package is unavailable")

        self._client: Any = redis.Redis.from_url(
            url,
            decode_responses=False,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )

    def get(self, name: str) -> bytes | None:
        return self._client.get(name)

    def set(self, name: str, value: bytes) -> None:
        self._client.set(name=name, value=value)

    def delete(self, *names: str) -> None:
        if names:
            self._client.delete(*names)

    def hget(self, name: str, field: str) -> bytes | None:
        return self._client.hget(name, field)

    def hset(self, name: str, field: str, value: bytes) -> None:
        self._client.hset(name, field, value)

    def hdel(self, name: str, *fields: str) -> None:
        if fields:
            self._client.hdel(name, *fields)

    def clear(self, prefix: str) -> None:
        pattern = f"{prefix}*"
        keys = list(self._client.scan_iter(match=pattern))
        if keys:
            self._client.delete(*keys)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except RedisError:
            return False

    def add(self, name: str, value: bytes, ttl: float) -> bool:
        ttl_seconds = max(int(ttl), 1)
        try:
            return bool(
                self._client.set(name=name, value=value, nx=True, ex=ttl_seconds)
            )
        except RedisError:
            return False


class InMemoryCache:
    """Thread-safe in-memory cache used as a fallback during testing."""

    def __init__(self) -> None:
        self._values: dict[str, bytes] = {}
        self._hashes: dict[str, dict[str, bytes]] = {}
        self._expirations: dict[str, float] = {}
        self._lock = Lock()

    def _is_expired(self, name: str, now: float | None = None) -> bool:
        expires_at = self._expirations.get(name)
        if expires_at is None:
            return False
        if now is None:
            now = time.time()
        if expires_at > now:
            return False
        self._values.pop(name, None)
        self._expirations.pop(name, None)
        return True

    def get(self, name: str) -> bytes | None:
        with self._lock:
            if self._is_expired(name):
                return None
            return self._values.get(name)

    def set(self, name: str, value: bytes) -> None:
        with self._lock:
            self._values[name] = value
            self._expirations.pop(name, None)

    def delete(self, *names: str) -> None:
        if not names:
            return
        with self._lock:
            for name in names:
                self._values.pop(name, None)
                self._hashes.pop(name, None)
                self._expirations.pop(name, None)

    def hget(self, name: str, field: str) -> bytes | None:
        with self._lock:
            bucket = self._hashes.get(name)
            if bucket is None:
                return None
            return bucket.get(field)

    def hset(self, name: str, field: str, value: bytes) -> None:
        with self._lock:
            bucket = self._hashes.setdefault(name, {})
            bucket[field] = value

    def hdel(self, name: str, *fields: str) -> None:
        if not fields:
            return
        with self._lock:
            bucket = self._hashes.get(name)
            if bucket is None:
                return
            for field in fields:
                bucket.pop(field, None)
            if not bucket:
                self._hashes.pop(name, None)

    def clear(self, prefix: str) -> None:
        with self._lock:
            for name in list(self._values):
                if name.startswith(prefix):
                    self._values.pop(name, None)
                    self._expirations.pop(name, None)
            for name in list(self._hashes):
                if name.startswith(prefix):
                    self._hashes.pop(name, None)

    def add(self, name: str, value: bytes, ttl: float) -> bool:
        ttl = max(ttl, 0.0)
        expiry: float | None = None
        if ttl > 0:
            expiry = time.time() + ttl
        with self._lock:
            if not self._is_expired(name) and name in self._values:
                return False
            self._values[name] = value
            if expiry is not None:
                self._expirations[name] = expiry
            else:
                self._expirations.pop(name, None)
            return True


_BACKEND: CacheBackend | None = None
_BACKEND_LOCK = Lock()
_BACKEND_LAST_FAILURE: float | None = None
_BACKEND_RETRY_DELAY = 10.0


def _namespaced(name: str) -> str:
    return f"{_CACHE_PREFIX}{name}"


def set_backend(backend: CacheBackend | None) -> None:
    """Override the active cache backend (primarily for tests)."""

    global _BACKEND, _BACKEND_LAST_FAILURE
    with _BACKEND_LOCK:
        _BACKEND = backend
        _BACKEND_LAST_FAILURE = None


def _ensure_backend() -> CacheBackend:
    global _BACKEND, _BACKEND_LAST_FAILURE
    with _BACKEND_LOCK:
        if _BACKEND is not None and not isinstance(_BACKEND, InMemoryCache):
            return _BACKEND

        url = os.getenv("REDIS_URL", "redis://redis:6379/0").strip()

        if url.startswith("memory://") or redis is None:
            if not isinstance(_BACKEND, InMemoryCache):
                _BACKEND = InMemoryCache()
            _BACKEND_LAST_FAILURE = None
            return _BACKEND

        now = time.time()
        should_try_redis = False

        if _BACKEND is None:
            should_try_redis = True
        elif isinstance(_BACKEND, InMemoryCache):
            if _BACKEND_LAST_FAILURE is None:
                should_try_redis = True
            elif now - _BACKEND_LAST_FAILURE >= _BACKEND_RETRY_DELAY:
                should_try_redis = True

        if should_try_redis and redis is not None:
            try:
                candidate = RedisCache(url)
            except Exception:  # pragma: no cover - invalid URL
                _BACKEND_LAST_FAILURE = now
            else:
                if candidate.ping():
                    _BACKEND = candidate
                    _BACKEND_LAST_FAILURE = None
                    return _BACKEND
                _BACKEND_LAST_FAILURE = now

        if _BACKEND is None:
            _BACKEND = InMemoryCache()

        return _BACKEND


def clear_all() -> None:
    """Remove cached entries maintained by the application."""

    backend = _ensure_backend()
    backend.clear(_CACHE_PREFIX)


def get_string(name: str) -> str | None:
    """Return the cached string value for *name*."""

    raw = _ensure_backend().get(_namespaced(name))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    return str(raw)


def set_string(name: str, value: str) -> None:
    """Store *value* under *name* in the cache."""

    _ensure_backend().set(_namespaced(name), value.encode("utf-8"))


def get_json(name: str) -> Any:
    """Return the JSON-deserialised value for *name*."""

    text = get_string(name)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def set_json(name: str, value: Any) -> None:
    """Serialise *value* as JSON and store it under *name*."""

    set_string(name, json.dumps(value))


def delete(*names: str) -> None:
    """Remove cached *names* if they exist."""

    if not names:
        return
    backend = _ensure_backend()
    backend.delete(*(_namespaced(name) for name in names))


def get_hash_string(name: str, field: str) -> str | None:
    """Return the string stored in hash *name* at *field*."""

    raw = _ensure_backend().hget(_namespaced(name), field)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    return str(raw)


def set_hash_string(name: str, field: str, value: str) -> None:
    """Store *value* inside hash *name* at *field*."""

    _ensure_backend().hset(_namespaced(name), field, value.encode("utf-8"))


def delete_hash(name: str) -> None:
    """Completely remove the hash bucket *name*."""

    delete(name)


def delete_hash_fields(name: str, *fields: str) -> None:
    """Remove *fields* from hash bucket *name*."""

    if not fields:
        return
    _ensure_backend().hdel(_namespaced(name), *fields)


def get_hash_json(name: str, field: str) -> Any:
    """Return the JSON-deserialised value stored in a hash bucket."""

    text = get_hash_string(name, field)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def set_hash_json(name: str, field: str, value: Any) -> None:
    """Serialise *value* as JSON and store it within a hash bucket."""

    set_hash_string(name, field, json.dumps(value))


def acquire_lock(name: str, ttl: float) -> bool:
    """Attempt to acquire a cooperative cache lock for *name*.

    The lock is stored in the active cache backend and automatically expires
    after *ttl* seconds. The function returns ``True`` when the caller obtained
    the lock and ``False`` otherwise.
    """

    backend = _ensure_backend()
    ttl = max(float(ttl), 1.0)
    return backend.add(_namespaced(f"{_LOCK_PREFIX}{name}"), b"1", ttl)


def release_lock(name: str) -> None:
    """Release the cooperative lock identified by *name*."""

    delete(f"{_LOCK_PREFIX}{name}")
