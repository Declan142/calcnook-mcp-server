"""Live gold/silver spot prices in USD/g, with FX conversion + fallback."""

from __future__ import annotations

from typing import Any

from . import _http
from .cache import get_cache
from .fx import get_fx_rates

TROY_OZ_TO_GRAM = 0.0321507466  # multiply USD/oz by this to get USD/g

# Tier 1: legacy free endpoint (often dead, kept for compliance with original brief).
METALS_LIVE_URL = "https://api.metals.live/v1/spot"
# Tier 2: gold-api.com — free, no auth, separate endpoint per metal.
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
SILVER_API_URL = "https://api.gold-api.com/price/XAG"

CACHE_KEY = "metals:usd_per_gram"

_FALLBACK_USD_PER_GRAM: dict[str, float] = {"gold": 75.0, "silver": 0.90}


def _from_metals_live() -> dict[str, float] | None:
    """Parse the legacy `[{'gold': X}, {'silver': Y}, ...]` shape (USD per troy oz)."""
    try:
        payload = _http.fetch_json(METALS_LIVE_URL)
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    flat: dict[str, float] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        for k, v in entry.items():
            try:
                flat[str(k).lower()] = float(v)
            except (TypeError, ValueError):
                continue
    gold = flat.get("gold")
    silver = flat.get("silver")
    if gold is None or silver is None:
        return None
    return {"gold": gold * TROY_OZ_TO_GRAM, "silver": silver * TROY_OZ_TO_GRAM}


def _from_gold_api() -> dict[str, float] | None:
    """Two-call path: XAU + XAG (USD per troy oz)."""
    try:
        gold_resp = _http.fetch_json(GOLD_API_URL)
        silver_resp = _http.fetch_json(SILVER_API_URL)
    except Exception:
        return None
    try:
        gold_oz = float(gold_resp["price"])
        silver_oz = float(silver_resp["price"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"gold": gold_oz * TROY_OZ_TO_GRAM, "silver": silver_oz * TROY_OZ_TO_GRAM}


def fetch_metal_prices_uncached() -> dict[str, Any]:
    """Try tier 1 then tier 2; fall back to constants. Never raises."""
    for fn, src in (
        (_from_metals_live, "metals.live"),
        (_from_gold_api, "gold-api.com"),
    ):
        prices = fn()
        if prices is not None:
            return {"prices_usd_per_gram": prices, "source": src}
    return {
        "prices_usd_per_gram": dict(_FALLBACK_USD_PER_GRAM),
        "source": "fallback",
    }


def _convert(usd_per_gram: float, currency: str) -> tuple[float, float]:
    """Return (price_in_currency, fx_rate_used). USD short-circuits to (price, 1.0)."""
    if currency == "USD":
        return usd_per_gram, 1.0
    fx = get_fx_rates()["rates"]
    rate = fx.get(currency)
    if rate is None or rate <= 0:
        return usd_per_gram, 1.0
    return usd_per_gram * float(rate), float(rate)


def _get_usd_metals() -> dict[str, Any]:
    cache = get_cache()
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return {**cached, "source": "cached"}
    fresh = fetch_metal_prices_uncached()
    if fresh["source"] != "fallback":
        cache.set(CACHE_KEY, fresh)
    return fresh


def get_gold_price_per_gram(currency: str = "USD") -> dict[str, Any]:
    """Gold spot in `currency` per gram."""
    currency = currency.upper()
    usd = _get_usd_metals()
    gold_usd = float(usd["prices_usd_per_gram"]["gold"])
    price, fx_rate = _convert(gold_usd, currency)
    return {
        "metal": "gold",
        "price_per_gram": price,
        "currency": currency,
        "source": usd["source"],
        "usd_per_gram": gold_usd,
        "fx_rate": fx_rate,
    }


def get_silver_price_per_gram(currency: str = "USD") -> dict[str, Any]:
    """Silver spot in `currency` per gram."""
    currency = currency.upper()
    usd = _get_usd_metals()
    silver_usd = float(usd["prices_usd_per_gram"]["silver"])
    price, fx_rate = _convert(silver_usd, currency)
    return {
        "metal": "silver",
        "price_per_gram": price,
        "currency": currency,
        "source": usd["source"],
        "usd_per_gram": silver_usd,
        "fx_rate": fx_rate,
    }


__all__ = [
    "get_gold_price_per_gram",
    "get_silver_price_per_gram",
    "fetch_metal_prices_uncached",
    "TROY_OZ_TO_GRAM",
    "METALS_LIVE_URL",
    "GOLD_API_URL",
    "SILVER_API_URL",
]
