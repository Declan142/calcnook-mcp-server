"""Tiny in-process TTL cache for live API responses."""

from __future__ import annotations

import os
import time
from threading import Lock
from typing import Any


def _default_ttl() -> int:
    raw = os.environ.get("CALCNOOK_CACHE_TTL_SECONDS", "3600")
    try:
        ttl = int(raw)
    except ValueError:
        return 3600
    return max(0, ttl)


class TTLCache:
    """Thread-safe TTL cache. ttl=0 disables caching."""

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = _default_ttl() if ttl_seconds is None else max(0, int(ttl_seconds))
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    @property
    def ttl(self) -> int:
        return self._ttl

    def get(self, key: str) -> Any | None:
        if self._ttl == 0:
            return None
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if now >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        if self._ttl == 0:
            return
        with self._lock:
            self._store[key] = (time.time() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_GLOBAL = TTLCache()


def get_cache() -> TTLCache:
    return _GLOBAL


def reset_cache() -> None:
    """Test helper — drop the singleton and reread TTL from env."""
    global _GLOBAL
    _GLOBAL = TTLCache()
