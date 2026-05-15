"""Dispatch handlers for universal (core) calcnook tools."""

from __future__ import annotations

from typing import Any

from calcnook.core import compound_interest, periodic_investment, loan_payment, retirement
from calcnook.core import bmi as bmi_module, currency

from ..live import fx as live_fx


def tool_compound_interest(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate future value of a lump-sum investment at compound interest."""
    result = compound_interest.calculate(
        principal=float(arguments["principal"]),
        annual_rate=float(arguments["annual_rate"]),
        years=float(arguments["years"]),
        compounding_per_year=int(arguments.get("compounding_per_year", 12)),
    )
    return result.to_dict()


def tool_sip_dca(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate future value of periodic SIP/DCA contributions with optional step-up."""
    result = periodic_investment.calculate(
        monthly_amount=float(arguments["monthly_amount"]),
        annual_return=float(arguments["annual_return"]),
        years=float(arguments["years"]),
        step_up_percent=float(arguments.get("step_up_percent", 0.0)),
    )
    return result.to_dict()


def tool_loan_payment(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate EMI / mortgage payment and optional amortization schedule."""
    result = loan_payment.calculate(
        principal=float(arguments["principal"]),
        annual_rate=float(arguments["annual_rate"]),
        years=int(arguments["years"]),
        extra_monthly_payment=float(arguments.get("extra_monthly_payment", 0.0)),
        include_schedule=bool(arguments.get("include_schedule", False)),
    )
    return result.to_dict()


def tool_retirement(arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch retirement planning to the appropriate sub-function by mode."""
    mode = arguments.get("mode")
    if mode not in {"corpus_needed", "monthly_contribution_for", "safe_withdrawal"}:
        raise ValueError("mode must be one of: corpus_needed, monthly_contribution_for, safe_withdrawal")

    if mode == "corpus_needed":
        result = retirement.corpus_needed(
            annual_expense=float(arguments["annual_expense"]),
            years_in_retirement=int(arguments["years_in_retirement"]),
            post_retirement_return=float(arguments["post_retirement_return"]),
            inflation=float(arguments["inflation"]),
        )
    elif mode == "monthly_contribution_for":
        result = retirement.monthly_contribution_for(
            target_corpus=float(arguments["target_corpus"]),
            years_to_retirement=int(arguments["years_to_retirement"]),
            annual_return=float(arguments["annual_return"]),
            current_savings=float(arguments.get("current_savings", 0.0)),
        )
    else:  # safe_withdrawal
        result = retirement.safe_withdrawal(
            corpus=float(arguments["corpus"]),
            withdrawal_rate=float(arguments.get("withdrawal_rate", 0.04)),
        )

    return result.to_dict()


def tool_bmi_bmr_tdee(arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch health metrics to BMI, BMR, or TDEE calculation by mode."""
    mode = arguments.get("mode")
    if mode not in {"bmi", "bmr", "tdee"}:
        raise ValueError("mode must be one of: bmi, bmr, tdee")

    if mode == "bmi":
        result = bmi_module.bmi(
            weight_kg=float(arguments["weight_kg"]),
            height_cm=float(arguments["height_cm"]),
        )
    elif mode == "bmr":
        result = bmi_module.bmr(
            weight_kg=float(arguments["weight_kg"]),
            height_cm=float(arguments["height_cm"]),
            age_years=int(arguments["age_years"]),
            sex=str(arguments["sex"]),
        )
    else:  # tdee
        result = bmi_module.tdee(
            bmr_kcal=float(arguments["bmr_kcal"]),
            activity_level=str(arguments["activity_level"]),
        )

    return result.to_dict()


def tool_convert_currency(arguments: dict[str, Any]) -> dict[str, Any]:
    """Convert an amount between currencies. Uses caller-supplied rates if given, else live FX."""
    raw_rates = arguments.get("rates")
    from_curr = str(arguments["from_currency"]).upper()
    to_curr = str(arguments["to_currency"]).upper()

    if raw_rates:
        rates = {str(k).upper(): float(v) for k, v in raw_rates.items()}
        rates_source = "caller"
        live_meta: dict[str, Any] = {}
    else:
        live = live_fx.get_fx_rates()
        rates = {str(k).upper(): float(v) for k, v in live["rates"].items()}
        rates_source = live["source"]
        live_meta = {"_rates_date": live.get("date"), "_rates_base": live.get("base", "USD")}

    result = currency.convert(
        amount=float(arguments["amount"]),
        from_currency=from_curr,
        to_currency=to_curr,
        rates=rates,
    )
    payload = result.to_dict()
    payload["_rates_source"] = rates_source
    payload.update(live_meta)
    return payload


def tool_format_currency_amount(arguments: dict[str, Any]) -> dict[str, Any]:
    """Format a numeric amount as a currency string. INR supports lakh/crore notation."""
    amount = float(arguments["amount"])
    curr = str(arguments["currency"]).upper()
    use_lakh_crore = bool(arguments.get("lakh_crore_format", False))

    if curr == "INR" and use_lakh_crore:
        formatted = currency.lakh_crore_format(amount)
    else:
        formatted = currency.format_amount(amount, curr)

    return {"formatted": formatted, "amount": amount, "currency": curr}
