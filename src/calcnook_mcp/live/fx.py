"""Live FX rates (USD-base) via Frankfurter, with hardcoded fallback."""

from __future__ import annotations

from typing import Any

from . import _http
from .cache import get_cache

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?from=USD"
CACHE_KEY = "fx:usd"

# Pegged / commonly-needed rates Frankfurter omits (AED, SAR are USD-pegged).
_FALLBACK_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.78,
    "INR": 83.5,
    "AED": 3.6725,
    "SAR": 3.75,
    "CAD": 1.36,
    "AUD": 1.51,
    "JPY": 155.0,
}


def _normalise(rates: dict[str, Any]) -> dict[str, float]:
    out = {"USD": 1.0}
    for code, val in rates.items():
        try:
            out[str(code).upper()] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def fetch_fx_rates_uncached() -> dict[str, Any]:
    """Hit Frankfurter directly. Returns the result dict; never raises."""
    try:
        payload = _http.fetch_json(FRANKFURTER_URL)
    except Exception:
        return {
            "rates": dict(_FALLBACK_RATES),
            "source": "fallback",
            "base": "USD",
            "date": None,
        }

    rates = payload.get("rates") if isinstance(payload, dict) else None
    if not isinstance(rates, dict) or not rates:
        return {
            "rates": dict(_FALLBACK_RATES),
            "source": "fallback",
            "base": "USD",
            "date": None,
        }

    merged = dict(_FALLBACK_RATES)
    merged.update(_normalise(rates))
    return {
        "rates": merged,
        "source": "live",
        "base": str(payload.get("base", "USD")).upper(),
        "date": payload.get("date"),
    }


def get_fx_rates() -> dict[str, Any]:
    """Cached USD-base FX rates. Result has keys: rates, source, base, date."""
    cache = get_cache()
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return {**cached, "source": "cached"}
    fresh = fetch_fx_rates_uncached()
    if fresh["source"] != "fallback":
        cache.set(CACHE_KEY, fresh)
    return fresh


__all__ = ["get_fx_rates", "fetch_fx_rates_uncached", "FRANKFURTER_URL"]
