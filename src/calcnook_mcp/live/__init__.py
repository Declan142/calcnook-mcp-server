"""Live data fetchers for FX rates, metal spot prices, and Zakat nisab.

Stdlib-only (urllib + json). All network calls have a 5-second timeout, send a
calcnook-mcp User-Agent, and degrade to a hardcoded fallback on any failure —
they never raise on the happy path.

Public API:
    get_fx_rates() -> {rates: {USD: 1.0, ...}, source, base, date}
    get_gold_price_per_gram(currency='USD') -> {price_per_gram, currency, source, ...}
    get_silver_price_per_gram(currency='USD') -> {price_per_gram, currency, source, ...}
    get_nisab_thresholds(basis='silver', currency='USD') -> {gold_basis, silver_basis, ...}
"""

from .fx import get_fx_rates
from .metals import get_gold_price_per_gram, get_silver_price_per_gram
from .nisab import get_nisab_thresholds

__all__ = [
    "get_fx_rates",
    "get_gold_price_per_gram",
    "get_silver_price_per_gram",
    "get_nisab_thresholds",
]
