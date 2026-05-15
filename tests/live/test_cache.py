"""TTLCache behaviour: hit, expiry, env override, ttl=0 disable."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from calcnook_mcp.live import cache as live_cache
from calcnook_mcp.live.cache import TTLCache


def test_set_then_get_returns_value() -> None:
    c = TTLCache(ttl_seconds=60)
    c.set("k", {"x": 1})
    assert c.get("k") == {"x": 1}


def test_get_missing_returns_none() -> None:
    c = TTLCache(ttl_seconds=60)
    assert c.get("absent") is None


def test_expiry_via_mocked_clock() -> None:
    c = TTLCache(ttl_seconds=10)
    with mock.patch("calcnook_mcp.live.cache.time.time", side_effect=[1000.0, 1005.0, 1011.0]):
        c.set("k", "v")        # stored at t=1000, expires at 1010
        assert c.get("k") == "v"  # t=1005, still valid
        assert c.get("k") is None  # t=1011, expired & evicted


def test_ttl_zero_disables_storage() -> None:
    c = TTLCache(ttl_seconds=0)
    c.set("k", "v")
    assert c.get("k") is None


def test_env_override_default_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALCNOOK_CACHE_TTL_SECONDS", "42")
    live_cache.reset_cache()
    assert live_cache.get_cache().ttl == 42


def test_env_override_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALCNOOK_CACHE_TTL_SECONDS", "not_an_int")
    live_cache.reset_cache()
    assert live_cache.get_cache().ttl == 3600


def test_clear_drops_everything() -> None:
    c = TTLCache(ttl_seconds=60)
    c.set("a", 1)
    c.set("b", 2)
    c.clear()
    assert c.get("a") is None and c.get("b") is None


def test_singleton_helpers_round_trip() -> None:
    g = live_cache.get_cache()
    g.set("foo", 123)
    assert live_cache.get_cache().get("foo") == 123
    live_cache.reset_cache()
    assert live_cache.get_cache().get("foo") is None
