"""Shared fixtures for tests/live — reset module-level cache before each test."""

from __future__ import annotations

import pytest

from calcnook_mcp.live import cache as live_cache


@pytest.fixture(autouse=True)
def _isolated_cache() -> None:
    """Drop the singleton cache before & after every live-module test."""
    live_cache.reset_cache()
    yield
    live_cache.reset_cache()
