"""Zakat nisab thresholds derived from current gold/silver spot.

Classical thresholds: gold = 87.48 g (≈20 mithqal), silver = 612.36 g (≈200 dirham).
Most contemporary scholars recommend the silver basis as it's the lower threshold
and therefore more obligation-protective (zakat fardh on more people).
"""

from __future__ import annotations

from typing import Any

from .metals import get_gold_price_per_gram, get_silver_price_per_gram

GOLD_NISAB_GRAMS = 87.48
SILVER_NISAB_GRAMS = 612.36


def get_nisab_thresholds(basis: str = "silver", currency: str = "USD") -> dict[str, Any]:
    """Return both nisab values plus the recommended basis."""
    basis = basis.lower()
    if basis not in {"gold", "silver"}:
        basis = "silver"
    currency = currency.upper()

    gold = get_gold_price_per_gram(currency)
    silver = get_silver_price_per_gram(currency)

    gold_nisab = gold["price_per_gram"] * GOLD_NISAB_GRAMS
    silver_nisab = silver["price_per_gram"] * SILVER_NISAB_GRAMS

    selected = silver_nisab if basis == "silver" else gold_nisab

    return {
        "gold_basis": gold_nisab,
        "silver_basis": silver_nisab,
        "selected_basis": basis,
        "selected_threshold": selected,
        "recommended": "silver",
        "currency": currency,
        "gold_price_per_gram": gold["price_per_gram"],
        "silver_price_per_gram": silver["price_per_gram"],
        "source": gold["source"],
    }


__all__ = ["get_nisab_thresholds", "GOLD_NISAB_GRAMS", "SILVER_NISAB_GRAMS"]
