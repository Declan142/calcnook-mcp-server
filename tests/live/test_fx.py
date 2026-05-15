"""FX fetcher: success, caching, fallback, normalisation."""

from __future__ import annotations

from urllib.error import URLError

import pytest

from calcnook_mcp.live import fx as live_fx
from tests.live._fakes import Queue, make_url_router


_FRANKFURTER_PAYLOAD = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-05-15",
    "rates": {"INR": 83.5, "EUR": 0.92, "GBP": 0.78, "JPY": 155.0},
}


def test_live_fetch_returns_normalised_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FRANKFURTER_PAYLOAD})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = live_fx.get_fx_rates()

    assert result["source"] == "live"
    assert result["base"] == "USD"
    assert result["date"] == "2026-05-15"
    assert result["rates"]["USD"] == 1.0
    assert result["rates"]["INR"] == 83.5
    assert result["rates"]["EUR"] == 0.92
    # Pegged Gulf currencies that Frankfurter omits must come from the merge.
    assert result["rates"]["AED"] == pytest.approx(3.6725)
    assert result["rates"]["SAR"] == pytest.approx(3.75)


def test_cached_second_call_does_not_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FRANKFURTER_PAYLOAD})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    first = live_fx.get_fx_rates()
    second = live_fx.get_fx_rates()

    assert first["source"] == "live"
    assert second["source"] == "cached"
    assert second["rates"] == first["rates"]
    assert len(fake.calls) == 1


def test_network_failure_returns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: URLError("dns fail")})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = live_fx.get_fx_rates()

    assert result["source"] == "fallback"
    for code in ("USD", "EUR", "GBP", "INR", "AED", "SAR", "CAD", "AUD", "JPY"):
        assert code in result["rates"]


def test_fallback_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: Queue([URLError("x"), _FRANKFURTER_PAYLOAD])})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    first = live_fx.get_fx_rates()
    second = live_fx.get_fx_rates()

    assert first["source"] == "fallback"
    assert second["source"] == "live"


def test_malformed_payload_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: {"unexpected": "shape"}})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = live_fx.get_fx_rates()
    assert result["source"] == "fallback"


def test_uncached_helper_skips_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FRANKFURTER_PAYLOAD})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    a = live_fx.fetch_fx_rates_uncached()
    b = live_fx.fetch_fx_rates_uncached()
    assert a["source"] == "live"
    assert b["source"] == "live"
    assert len(fake.calls) == 2
