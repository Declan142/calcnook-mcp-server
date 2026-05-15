"""End-to-end: tool_convert_currency + tool_zakat with caller-supplied vs live data."""

from __future__ import annotations

from urllib.error import URLError

import pytest

from calcnook_mcp.live import fx as live_fx, metals as live_metals
from calcnook_mcp.tools.core import tool_convert_currency
from calcnook_mcp.tools.islamic import tool_zakat
from tests.live._fakes import make_url_router


_FX = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-05-15",
    "rates": {"INR": 83.5, "EUR": 0.92, "GBP": 0.78, "JPY": 155.0},
}

_METALS = [{"gold": 2400.0}, {"silver": 28.0}]


# --------------------------------------------------------------------------- #
# Currency conversion                                                         #
# --------------------------------------------------------------------------- #

def test_caller_supplied_rates_bypass_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **kw):
        raise AssertionError("network must not be touched")
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", boom)

    result = tool_convert_currency({
        "amount": 1000,
        "from_currency": "USD",
        "to_currency": "INR",
        "rates": {"USD": 1.0, "INR": 83.5},
    })

    assert result["converted_amount"] == pytest.approx(83500.0)
    assert result["_rates_source"] == "caller"
    assert "_rates_date" not in result


def test_live_path_when_rates_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FX})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_convert_currency({"amount": 100, "from_currency": "USD", "to_currency": "INR"})

    assert result["_rates_source"] == "live"
    assert result["_rates_date"] == "2026-05-15"
    assert result["converted_amount"] == pytest.approx(8350.0)


def test_live_path_when_rates_empty_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FX})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_convert_currency({
        "amount": 100, "from_currency": "USD", "to_currency": "EUR", "rates": {},
    })
    assert result["_rates_source"] == "live"
    assert result["converted_amount"] == pytest.approx(92.0)


def test_live_path_falls_back_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: URLError("offline")})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_convert_currency({"amount": 100, "from_currency": "USD", "to_currency": "INR"})

    assert result["_rates_source"] == "fallback"
    assert result["converted_amount"] == pytest.approx(8350.0)


def test_second_live_call_marked_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({live_fx.FRANKFURTER_URL: _FX})
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    tool_convert_currency({"amount": 100, "from_currency": "USD", "to_currency": "INR"})
    second = tool_convert_currency({"amount": 100, "from_currency": "USD", "to_currency": "EUR"})

    assert second["_rates_source"] == "cached"


# --------------------------------------------------------------------------- #
# Zakat                                                                       #
# --------------------------------------------------------------------------- #

def test_zakat_caller_prices_bypass_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **kw):
        raise AssertionError("network must not be touched")
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", boom)

    result = tool_zakat({
        "cash": 10_000,
        "stocks_value": 15_000,
        "debts": 2_000,
        "currency": "USD",
        "gold_price_per_gram": 80.0,    # NOT 75.0 default
        "silver_price_per_gram": 1.20,  # NOT 0.90 default
        "nisab_basis": "silver",
    })

    assert result["zakat_due"] == pytest.approx(575.0)
    assert result["_prices_source"] == {"gold": "caller", "silver": "caller"}
    assert result["_gold_price_per_gram"] == 80.0
    assert result["_silver_price_per_gram"] == 1.20


def test_zakat_default_prices_trigger_live_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS,
        live_fx.FRANKFURTER_URL: _FX,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_zakat({
        "cash": 10_000,
        "stocks_value": 15_000,
        "debts": 2_000,
        "currency": "USD",
        "gold_price_per_gram": 75.0,
        "silver_price_per_gram": 0.90,
        "nisab_basis": "silver",
    })

    assert result["zakat_due"] == pytest.approx(575.0)
    assert result["_prices_source"]["gold"] == "metals.live"
    assert result["_prices_source"]["silver"] == "cached"
    # ~28 USD/oz silver -> ~$0.90/g, so the math may coincide; check live override regardless.
    assert result["_gold_price_per_gram"] != 75.0


def test_zakat_missing_prices_use_live(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS,
        live_fx.FRANKFURTER_URL: _FX,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_zakat({
        "cash": 10_000, "stocks_value": 15_000, "debts": 2_000, "currency": "USD",
    })

    assert result["_prices_source"]["gold"] in ("metals.live", "gold-api.com")
    assert result["zakat_due"] == pytest.approx(575.0)


def test_zakat_live_fetch_in_inr(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS,
        live_fx.FRANKFURTER_URL: _FX,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    result = tool_zakat({
        "cash": 1_000_000, "currency": "INR", "nisab_basis": "silver",
    })

    assert result["currency"] == "INR"
    assert result["_prices_source"]["gold"] in ("metals.live", "gold-api.com")
    # silver USD/g ~ 28 * 0.0321507466 ≈ 0.900; INR ≈ 0.900 * 83.5 ≈ 75.16
    assert result["_silver_price_per_gram"] == pytest.approx(28.0 * 0.0321507466 * 83.5, rel=1e-4)


def test_zakat_partial_caller_override(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_url_router({
        live_metals.METALS_LIVE_URL: _METALS,
        live_fx.FRANKFURTER_URL: _FX,
    })
    monkeypatch.setattr("calcnook_mcp.live._http.urlopen", fake)

    # Caller supplies only gold; silver should be live.
    result = tool_zakat({
        "cash": 10_000, "stocks_value": 15_000, "debts": 2_000,
        "currency": "USD", "gold_price_per_gram": 100.0,
    })

    assert result["_prices_source"] == {"gold": "caller", "silver": "metals.live"}
    assert result["_gold_price_per_gram"] == 100.0
