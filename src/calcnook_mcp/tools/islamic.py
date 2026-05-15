"""Dispatch handlers for Islamic finance calcnook tools."""

from __future__ import annotations

from typing import Any

from calcnook.core.islamic import zakat, murabaha, ijarah, mudarabah, hajj_savings, halal_screen

from ..live import metals as live_metals

_GOLD_DEFAULT = 75.0
_SILVER_DEFAULT = 0.90


def tool_zakat(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate Zakat al-Mal. Auto-fetches live gold/silver if caller omits or sends defaults."""
    currency = str(arguments.get("currency", "USD")).upper()
    raw_gold = arguments.get("gold_price_per_gram")
    raw_silver = arguments.get("silver_price_per_gram")

    gold_supplied = raw_gold is not None and float(raw_gold) != _GOLD_DEFAULT
    silver_supplied = raw_silver is not None and float(raw_silver) != _SILVER_DEFAULT

    sources: dict[str, str] = {}
    if gold_supplied:
        gold_price = float(raw_gold)
        sources["gold"] = "caller"
    else:
        gold_live = live_metals.get_gold_price_per_gram(currency)
        gold_price = float(gold_live["price_per_gram"])
        sources["gold"] = gold_live["source"]

    if silver_supplied:
        silver_price = float(raw_silver)
        sources["silver"] = "caller"
    else:
        silver_live = live_metals.get_silver_price_per_gram(currency)
        silver_price = float(silver_live["price_per_gram"])
        sources["silver"] = silver_live["source"]

    result = zakat.calculate(
        cash=float(arguments.get("cash", 0.0)),
        gold_grams=float(arguments.get("gold_grams", 0.0)),
        silver_grams=float(arguments.get("silver_grams", 0.0)),
        stocks_value=float(arguments.get("stocks_value", 0.0)),
        business_assets=float(arguments.get("business_assets", 0.0)),
        other_zakatable_assets=float(arguments.get("other_zakatable_assets", 0.0)),
        debts=float(arguments.get("debts", 0.0)),
        gold_price_per_gram=gold_price,
        silver_price_per_gram=silver_price,
        nisab_basis=str(arguments.get("nisab_basis", "silver")),
        currency=currency,
    )
    payload = result.to_dict()
    payload["_prices_source"] = sources
    payload["_gold_price_per_gram"] = gold_price
    payload["_silver_price_per_gram"] = silver_price
    return payload


def tool_islamic_financing(arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to Murabaha, Ijarah, or Mudarabah financing calculation."""
    instrument = arguments.get("instrument")
    if instrument not in {"murabaha", "ijarah", "mudarabah"}:
        raise ValueError("instrument must be one of: murabaha, ijarah, mudarabah")

    if instrument == "murabaha":
        result = murabaha.calculate(
            asset_cost=float(arguments["asset_cost"]),
            markup_percent=float(arguments["markup_percent"]),
            tenure_years=int(arguments["tenure_years"]),
            down_payment=float(arguments.get("down_payment", 0.0)),
        )
    elif instrument == "ijarah":
        result = ijarah.calculate(
            asset_cost=float(arguments["asset_cost"]),
            monthly_rent=float(arguments["monthly_rent"]),
            lease_years=int(arguments["lease_years"]),
            transfer_fee=float(arguments.get("transfer_fee", 1.0)),
        )
    else:  # mudarabah
        result = mudarabah.calculate(
            capital=float(arguments["capital"]),
            actual_profit_amount=float(arguments["actual_profit_amount"]),
            investor_share_ratio=float(arguments["investor_share_ratio"]),
            years=float(arguments["years"]) if "years" in arguments else None,
        )

    return result.to_dict()


def tool_hajj_savings(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate monthly savings needed to fund Hajj pilgrimage."""
    result = hajj_savings.calculate(
        hajj_cost_target=float(arguments["hajj_cost_target"]),
        years_to_hajj=int(arguments["years_to_hajj"]),
        current_savings=float(arguments.get("current_savings", 0.0)),
        expected_annual_return=float(arguments.get("expected_annual_return", 0.0)),
    )
    return result.to_dict()


def tool_screen_halal_stock(arguments: dict[str, Any]) -> dict[str, Any]:
    """Screen a stock for Sharia compliance per AAOIFI standard ratios."""
    result = halal_screen.screen(
        sector=str(arguments["sector"]),
        market_cap=float(arguments["market_cap"]),
        debt_interest_bearing=float(arguments["debt_interest_bearing"]),
        cash_and_interest_securities=float(arguments["cash_and_interest_securities"]),
        receivables=float(arguments["receivables"]),
        total_revenue=float(arguments["total_revenue"]),
        haram_revenue=float(arguments.get("haram_revenue", 0.0)),
    )
    return result.to_dict()
