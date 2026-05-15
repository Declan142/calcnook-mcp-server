"""Metal spot fetcher: tier-1, tier-2 fallback, USD->currency conversion, defaults."""

from __future__ import annotations

from urllib.error import URLError

import pytest

from calcnook_mcp.live import metals as live_metals
from calcnook_mcp.live import fx as live_fx
from calcnook_mcp.live.metals import TROY_OZ_TO_GRAM
from tests.live._fakes import make_url_router


_METALS_LIVE_PAYLOAD = [
    {"gold": 2400.0},   # USD per troy oz
    {"silver": 28.0},
    {"platinum": 950.0},
]

_GOLD_API_PAYLOAD = {"price": 2400.0, "currency": "USD", "symbol": "XAU"}
_SILVER_API_PAYLOAD = {"price": 28.0, "currency": "USD", "symbol": "XAG"}

_FX_PAYLOAD = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-05-15",
    "rates": {"INR": 83.5, "EUR": 0.92},
}


def test_tier1_metals_live_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_metals.METALS_LIVE_URL: _METALS_LIVE_PAYLOAD})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    gold = live_metals.get_gold_price_per_gram("USD")
    silver = live_metals.get_silver_price_per_gram("USD")

    assert gold["source"] in ("metals.live", "cached")
    assert gold["price_per_gram"] == pytest.approx(2400.0 * TROY_OZ_TO_GRAM)
    assert silver["price_per_gram"] == pytest.approx(28.0 * TROY_OZ_TO_GRAM)


def test_tier2_gold_api_used_when_tier1_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: URLError("tls sni fail"),
        live_metals.GOLD_API_URL: _GOLD_API_PAYLOAD,
        live_metals.SILVER_API_URL: _SILVER_API_PAYLOAD,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    gold = live_metals.get_gold_price_per_gram("USD")
    assert gold["source"] in ("gold-api.com", "cached")
    assert gold["price_per_gram"] == pytest.approx(2400.0 * TROY_OZ_TO_GRAM)


def test_full_failure_returns_fallback_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: URLError("a"),
        live_metals.GOLD_API_URL: URLError("b"),
        live_metals.SILVER_API_URL: URLError("c"),
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    gold = live_metals.get_gold_price_per_gram("USD")
    silver = live_metals.get_silver_price_per_gram("USD")

    assert gold["source"] == "fallback"
    assert gold["price_per_gram"] == pytest.approx(75.0)
    assert silver["source"] == "fallback"
    assert silver["price_per_gram"] == pytest.approx(0.90)


def test_currency_conversion_uses_fx(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS_LIVE_PAYLOAD,
        live_fx.FRANKFURTER_URL: _FX_PAYLOAD,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    inr = live_metals.get_gold_price_per_gram("INR")
    expected_usd_per_g = 2400.0 * TROY_OZ_TO_GRAM
    assert inr["currency"] == "INR"
    assert inr["fx_rate"] == pytest.approx(83.5)
    assert inr["price_per_gram"] == pytest.approx(expected_usd_per_g * 83.5)
    assert inr["usd_per_gram"] == pytest.approx(expected_usd_per_g)


def test_caching_prevents_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_metals.METALS_LIVE_URL: _METALS_LIVE_PAYLOAD})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    a = live_metals.get_gold_price_per_gram("USD")
    b = live_metals.get_silver_price_per_gram("USD")
    c = live_metals.get_gold_price_per_gram("USD")

    assert a["source"] == "metals.live"
    assert b["source"] == "cached"
    assert c["source"] == "cached"
    assert len(fake.calls) == 1


def test_unknown_currency_falls_back_to_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS_LIVE_PAYLOAD,
        live_fx.FRANKFURTER_URL: _FX_PAYLOAD,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    res = live_metals.get_gold_price_per_gram("ZZZ")
    assert res["currency"] == "ZZZ"
    assert res["fx_rate"] == 1.0
    assert res["price_per_gram"] == pytest.approx(res["usd_per_gram"])


def test_nisab_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    from calcnook_mcp.live.nisab import (
        get_nisab_thresholds,
        GOLD_NISAB_GRAMS,
        SILVER_NISAB_GRAMS,
    )

    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS_LIVE_PAYLOAD,
        live_fx.FRANKFURTER_URL: _FX_PAYLOAD,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    n = get_nisab_thresholds(basis="silver", currency="USD")
    expected_gold = 2400.0 * TROY_OZ_TO_GRAM * GOLD_NISAB_GRAMS
    expected_silver = 28.0 * TROY_OZ_TO_GRAM * SILVER_NISAB_GRAMS
    assert n["gold_basis"] == pytest.approx(expected_gold)
    assert n["silver_basis"] == pytest.approx(expected_silver)
    assert n["recommended"] == "silver"
    assert n["selected_basis"] == "silver"
    assert n["selected_threshold"] == pytest.approx(expected_silver)
    assert n["currency"] == "USD"
