"""Composite agentic tools — multi-step calculations chained inside one call.

Each composite tool internally invokes several engine functions and returns an
integrated, LLM-ready dict. Sub-call failures are captured in ``_errors`` so
the caller still receives partial results instead of a hard crash.
"""

from __future__ import annotations

from typing import Any

from calcnook.core import loan_payment
from calcnook.core.currency import format_amount, lakh_crore_format
from calcnook.countries.au import income_tax as au_tax
from calcnook.countries.ca import income_tax as ca_tax
from calcnook.countries.india import income_tax as in_tax
from calcnook.countries.uk import income_tax as uk_tax
from calcnook.countries.us import income_tax as us_tax, retirement_accounts as us_retirement


_COUNTRY_CURRENCY: dict[str, str] = {
    "us": "USD",
    "uk": "GBP",
    "ca": "CAD",
    "au": "AUD",
    "in": "INR",
}

# 2026 statutory caps used by the salary-offer composite.
# US: §402(g) elective deferral limit (under-50 / 50+).
_US_401K_LIMIT_UNDER_50 = 24_000.0
_US_401K_LIMIT_50_PLUS = 32_000.0
# India: 12% of basic up to the EPF wage ceiling. We approximate basic = 50% of CTC
# and then cap at the ₹2.5 L/yr tax-free EPF contribution ceiling (Finance Act 2021).
_IN_EPF_RATE = 0.12
_IN_EPF_BASIC_FRACTION = 0.50
_IN_EPF_TAX_FREE_CEILING = 250_000.0


def _format_money(amount: float, currency: str, *, lakh_crore: bool = False) -> str:
    """Pre-format a numeric amount using the engine's formatter."""
    if currency == "INR" and lakh_crore:
        return lakh_crore_format(amount)
    return format_amount(amount, currency)


# ---------------------------------------------------------------------------
# 1. Salary-offer analyzer
# ---------------------------------------------------------------------------

def tool_analyze_salary_offer(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a tax + take-home + retirement analysis on a single job offer."""
    errors: list[str] = []

    if "salary" not in arguments:
        raise KeyError("salary")
    if "country" not in arguments:
        raise KeyError("country")
    if "age" not in arguments:
        raise KeyError("age")

    salary = float(arguments["salary"])
    country = str(arguments["country"]).lower()
    age = int(arguments["age"])

    if country not in _COUNTRY_CURRENCY:
        raise ValueError(
            f"country must be one of {sorted(_COUNTRY_CURRENCY)}, got {country!r}"
        )
    if salary < 0:
        raise ValueError("salary must be >= 0")
    if age < 0:
        raise ValueError("age must be >= 0")

    currency = _COUNTRY_CURRENCY[country]
    use_lakh_crore = country == "in"

    filing_status = str(arguments.get("filing_status", "single"))
    regime = str(arguments.get("regime", "new"))
    monthly_expenses_raw = arguments.get("monthly_expenses")
    monthly_expenses = float(monthly_expenses_raw) if monthly_expenses_raw is not None else None

    total_tax = 0.0
    marginal_rate = 0.0
    try:
        if country == "us":
            tax_res = us_tax.calculate(income=salary, filing_status=filing_status)
            total_tax = tax_res.tax_owed
            marginal_rate = tax_res.marginal_rate
        elif country == "uk":
            tax_res = uk_tax.calculate(income=salary)
            total_tax = tax_res.total_tax
            higher_band = next(
                (b for b in tax_res.bracket_breakdown if b.income_in_band > 0),
                None,
            )
            marginal_rate = (
                tax_res.bracket_breakdown[-1].rate if tax_res.bracket_breakdown else 0.0
            )
            if higher_band is None:
                marginal_rate = 0.0
        elif country == "ca":
            tax_res = ca_tax.calculate(income=salary)
            total_tax = tax_res.tax_owed
            marginal_rate = tax_res.marginal_rate
        elif country == "au":
            tax_res = au_tax.calculate(income=salary)
            total_tax = tax_res.total_tax
            marginal_rate = (
                tax_res.bracket_breakdown[-1].rate if tax_res.bracket_breakdown else 0.0
            )
        else:  # in
            tax_res = in_tax.calculate(gross_income=salary, regime=regime)
            total_tax = tax_res.tax_owed
            marginal_rate = tax_res.marginal_rate
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"income_tax: {type(exc).__name__}: {exc}")

    take_home = salary - total_tax
    take_home_monthly = take_home / 12.0
    effective_rate_pct = (total_tax / salary * 100.0) if salary > 0 else 0.0

    retirement_max: float | None = None
    if country == "us":
        try:
            limit = _US_401K_LIMIT_50_PLUS if age >= 50 else _US_401K_LIMIT_UNDER_50
            res = us_retirement.traditional_401k(
                contribution=limit,
                salary=salary,
                employer_match_percent=0.0,
                employer_match_cap=0.06,
                age=age,
                marginal_tax_rate=max(0.0, min(marginal_rate, 0.99)),
            )
            retirement_max = res.employee_limit
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"us_retirement_401k: {type(exc).__name__}: {exc}")
    elif country == "in":
        approx_basic = salary * _IN_EPF_BASIC_FRACTION
        retirement_max = round(min(approx_basic * _IN_EPF_RATE, _IN_EPF_TAX_FREE_CEILING), 2)

    savings_room_monthly: float | None = None
    if monthly_expenses is not None:
        savings_room_monthly = round(take_home_monthly - monthly_expenses, 2)

    actions: list[str] = []
    if country == "us":
        if retirement_max is not None:
            actions.append(
                f"Max your 401(k) up to {_format_money(retirement_max, currency)} "
                f"to reduce taxable income."
            )
        if marginal_rate >= 0.32:
            actions.append("Consider HSA + backdoor Roth — your marginal bracket is high.")
        else:
            actions.append("Open a Roth IRA for tax-free growth (subject to MAGI limits).")
        if savings_room_monthly is not None and savings_room_monthly > 0:
            actions.append(
                f"Funnel {_format_money(savings_room_monthly, currency)} "
                f"per month into a low-cost index fund."
            )
    elif country == "in":
        if retirement_max:
            actions.append(
                f"Maximise EPF / VPF contributions (~{_format_money(retirement_max, currency, lakh_crore=True)} per year tax-deductible)."
            )
        if regime == "new" and salary > 1_200_000:
            actions.append("New regime is usually better above ₹12L — re-check old regime only if 80C+80D+HRA exceed ₹4.25L.")
        elif regime == "old":
            actions.append("Claim the full 80C ₹1.5L deduction (ELSS / PPF / EPF) before year-end.")
        actions.append("Build a 6-month emergency fund in a liquid mutual fund or high-rate FD.")
        if savings_room_monthly is not None and savings_room_monthly > 0:
            actions.append(
                f"Start a SIP of {_format_money(savings_room_monthly, currency, lakh_crore=True)} per month into a Nifty 50 index fund."
            )
    elif country == "uk":
        actions.append("Contribute to a workplace pension to capture the employer match and 20-45% tax relief.")
        if salary > 100_000:
            actions.append("Income above £100K tapers your personal allowance — salary-sacrifice into pension to retain it.")
        actions.append("Use your annual ISA allowance (£20,000) for tax-free investing.")
    elif country == "ca":
        actions.append("Contribute to RRSP to defer tax — 18% of earned income up to the annual cap.")
        actions.append("Top up TFSA (≈ CA$7,000/yr) for tax-free growth.")
        if marginal_rate >= 0.29:
            actions.append("Consider an FHSA (First Home Savings Account) for combined RRSP+TFSA-style benefits.")
    elif country == "au":
        actions.append("Maximise concessional super contributions ($30K cap FY 2025-26) to reduce taxable income.")
        if salary > 135_000:
            actions.append("You are in the 37% bracket — salary-sacrifice into super to lower marginal tax.")
        actions.append("Build a 3-6 month emergency fund in a high-interest savings account.")

    if not actions:
        actions = ["Build a 3-6 month emergency fund before any other investment."]
    actions = actions[:4]

    display = {
        "gross": _format_money(round(salary, 2), currency, lakh_crore=use_lakh_crore),
        "total_tax": _format_money(round(total_tax, 2), currency, lakh_crore=use_lakh_crore),
        "take_home": _format_money(round(take_home, 2), currency, lakh_crore=use_lakh_crore),
        "take_home_monthly": _format_money(round(take_home_monthly, 2), currency, lakh_crore=False),
        "effective_tax_rate": f"{effective_rate_pct:.2f}%",
    }
    if retirement_max is not None:
        display["retirement_contribution_max"] = _format_money(
            round(retirement_max, 2), currency, lakh_crore=use_lakh_crore
        )
    if savings_room_monthly is not None:
        display["savings_room_monthly"] = _format_money(
            round(savings_room_monthly, 2), currency, lakh_crore=False
        )

    result: dict[str, Any] = {
        "gross_annual": round(salary, 2),
        "total_tax": round(total_tax, 2),
        "take_home_annual": round(take_home, 2),
        "take_home_monthly": round(take_home_monthly, 2),
        "effective_tax_rate_pct": round(effective_rate_pct, 2),
        "marginal_bracket_estimate_pct": round(marginal_rate * 100.0, 2),
        "currency": currency,
        "retirement_contribution_max": (
            round(retirement_max, 2) if retirement_max is not None else None
        ),
        "savings_room_monthly": savings_room_monthly,
        "recommended_actions": actions,
        "display": display,
    }
    if errors:
        result["_errors"] = errors
    return result


# ---------------------------------------------------------------------------
# 2. Financial-health snapshot
# ---------------------------------------------------------------------------

# Fidelity-style age → multiple-of-annual-income corpus benchmarks.
_RETIREMENT_BENCHMARKS: list[tuple[int, float]] = [
    (30, 1.0),
    (40, 3.0),
    (50, 6.0),
    (60, 8.0),
    (67, 10.0),
]


def _required_corpus_multiplier(age: int) -> float:
    if age <= _RETIREMENT_BENCHMARKS[0][0]:
        return _RETIREMENT_BENCHMARKS[0][1]
    if age >= _RETIREMENT_BENCHMARKS[-1][0]:
        return _RETIREMENT_BENCHMARKS[-1][1]
    for (lo_age, lo_mult), (hi_age, hi_mult) in zip(
        _RETIREMENT_BENCHMARKS, _RETIREMENT_BENCHMARKS[1:]
    ):
        if lo_age <= age <= hi_age:
            span = hi_age - lo_age
            t = (age - lo_age) / span if span > 0 else 0.0
            return lo_mult + (hi_mult - lo_mult) * t
    return _RETIREMENT_BENCHMARKS[-1][1]


def _retirement_track_label(savings: float, required: float) -> str:
    if required <= 0:
        return "ahead"
    ratio = savings / required
    if ratio >= 1.10:
        return "ahead"
    if ratio >= 0.80:
        return "on_track"
    return "behind"


def tool_financial_health_snapshot(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute a 0-100 financial-health score from five everyday inputs."""
    errors: list[str] = []
    for required in ("monthly_income", "monthly_expenses", "total_debts", "total_savings", "age"):
        if required not in arguments:
            raise KeyError(required)

    monthly_income = float(arguments["monthly_income"])
    monthly_expenses = float(arguments["monthly_expenses"])
    total_debts = float(arguments["total_debts"])
    total_savings = float(arguments["total_savings"])
    age = int(arguments["age"])
    monthly_emi = float(arguments.get("monthly_emi", 0.0))
    country = str(arguments.get("country", "in")).lower()

    if monthly_income <= 0:
        raise ValueError("monthly_income must be > 0")
    if monthly_expenses < 0 or total_debts < 0 or total_savings < 0 or monthly_emi < 0:
        raise ValueError("monetary inputs must be >= 0")
    if age < 0:
        raise ValueError("age must be >= 0")

    currency = _COUNTRY_CURRENCY.get(country, "INR")
    use_lakh_crore = country == "in"

    savings_rate_pct = (monthly_income - monthly_expenses) / monthly_income * 100.0
    debt_to_income_ratio = monthly_emi / monthly_income if monthly_income > 0 else 0.0
    emergency_fund_months = (
        total_savings / monthly_expenses if monthly_expenses > 0 else float("inf")
    )

    annual_income = monthly_income * 12.0
    multiplier = _required_corpus_multiplier(age)
    required_corpus = annual_income * multiplier
    track = _retirement_track_label(total_savings, required_corpus)

    sr_score = max(0.0, min(savings_rate_pct / 30.0, 1.0)) * 30.0
    if debt_to_income_ratio <= 0.10:
        dti_score = 25.0
    elif debt_to_income_ratio >= 0.50:
        dti_score = 0.0
    else:
        dti_score = (1.0 - (debt_to_income_ratio - 0.10) / 0.40) * 25.0
    if emergency_fund_months == float("inf"):
        ef_score = 25.0
    else:
        ef_score = max(0.0, min(emergency_fund_months / 6.0, 1.0)) * 25.0
    rt_score = {"ahead": 20.0, "on_track": 14.0, "behind": 5.0}[track]

    score = round(sr_score + dti_score + ef_score + rt_score, 2)

    if score >= 85:
        verdict = "Excellent"
    elif score >= 70:
        verdict = "Healthy"
    elif score >= 50:
        verdict = "Needs work"
    else:
        verdict = "Critical"

    actions: list[tuple[float, str]] = []
    if debt_to_income_ratio > 0.40:
        actions.append((0.0, "Top priority: prepay high-interest debt — your DTI is above 40%."))
    if emergency_fund_months < 3:
        actions.append((1.0, "Build an emergency fund covering at least 6 months of expenses before any other investing."))
    if savings_rate_pct < 20:
        actions.append((2.0, "Lift your savings rate to 20%+ by cutting discretionary spending."))
    if track == "behind":
        gap = required_corpus - total_savings
        actions.append((
            3.0,
            f"You are behind on retirement — close the {_format_money(round(gap, 2), currency, lakh_crore=use_lakh_crore)} gap with a step-up SIP or extra 401(k)/EPF.",
        ))
    if track == "on_track" and savings_rate_pct >= 25:
        actions.append((4.0, "Keep stepping up SIP / 401(k) by 10% each year to compound the lead."))
    if total_debts > annual_income * 2:
        actions.append((0.5, "Total debt exceeds 2x annual income — consolidate or refinance high-rate balances."))
    if not actions:
        actions.append((9.0, "Maintain current savings rate and rebalance portfolio annually."))

    actions.sort(key=lambda x: x[0])
    recommended_actions = [a[1] for a in actions[:3]]

    return {
        "savings_rate_pct": round(savings_rate_pct, 2),
        "debt_to_income_ratio": round(debt_to_income_ratio, 4),
        "emergency_fund_months": (
            round(emergency_fund_months, 2)
            if emergency_fund_months != float("inf")
            else None
        ),
        "retirement_track": track,
        "required_corpus_at_age": round(required_corpus, 2),
        "actual_savings": round(total_savings, 2),
        "score": score,
        "verdict": verdict,
        "recommended_actions": recommended_actions,
        "currency": currency,
        "display": {
            "score": f"{score:.0f}/100",
            "savings_rate": f"{savings_rate_pct:.2f}%",
            "dti": f"{debt_to_income_ratio * 100:.2f}%",
            "emergency_fund": (
                f"{emergency_fund_months:.1f} months"
                if emergency_fund_months != float("inf")
                else "n/a"
            ),
            "required_corpus": _format_money(
                round(required_corpus, 2), currency, lakh_crore=use_lakh_crore
            ),
            "actual_savings": _format_money(
                round(total_savings, 2), currency, lakh_crore=use_lakh_crore
            ),
            "verdict": verdict,
        },
        **({"_errors": errors} if errors else {}),
    }


# ---------------------------------------------------------------------------
# 3. Loan-options comparator
# ---------------------------------------------------------------------------

def tool_compare_loan_options(arguments: dict[str, Any]) -> dict[str, Any]:
    """Side-by-side EMI / total-interest comparison across loan options."""
    options = arguments.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise ValueError("options must be a list with at least 2 entries")

    include_schedules = bool(arguments.get("include_schedules", False))
    errors: list[str] = []
    comparison: list[dict[str, Any]] = []

    for idx, raw in enumerate(options):
        label = str(raw.get("label", f"Option {idx + 1}"))
        try:
            principal = float(raw["principal"])
            annual_rate = float(raw["annual_rate"])
            years = int(raw["years"])
            extra = float(raw.get("extra_monthly", 0.0))
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"{label}: bad inputs — {type(exc).__name__}: {exc}")
            continue

        try:
            res = loan_payment.calculate(
                principal=principal,
                annual_rate=annual_rate,
                years=years,
                extra_monthly_payment=extra,
                include_schedule=True,
            )
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            continue

        effective_months = len(res.amortization) if res.amortization else years * 12
        effective_years = effective_months / 12.0

        entry: dict[str, Any] = {
            "label": label,
            "principal": round(principal, 2),
            "annual_rate": annual_rate,
            "years": years,
            "extra_monthly": round(extra, 2),
            "monthly_emi": round(res.monthly_payment, 2),
            "total_interest": round(res.total_interest, 2),
            "total_payment": round(res.total_payment, 2),
            "effective_years": round(effective_years, 2),
        }
        if include_schedules:
            entry["amortization"] = res.amortization
        comparison.append(entry)

    if not comparison:
        return {
            "comparison": [],
            "winner_by_total_payment": None,
            "winner_by_emi": None,
            "savings_vs_worst": 0.0,
            "display_table": "No valid options.",
            "_errors": errors,
        }

    cheapest = min(comparison, key=lambda x: x["total_payment"])
    lowest_emi = min(comparison, key=lambda x: x["monthly_emi"])
    worst = max(comparison, key=lambda x: x["total_payment"])
    savings_vs_worst = round(worst["total_payment"] - cheapest["total_payment"], 2)

    header = "| Option | EMI | Total interest | Total payment | Effective years |"
    sep = "| --- | ---: | ---: | ---: | ---: |"
    rows = [
        f"| {e['label']} | {e['monthly_emi']:,.2f} | {e['total_interest']:,.2f} | "
        f"{e['total_payment']:,.2f} | {e['effective_years']:.2f} |"
        for e in comparison
    ]
    display_table = "\n".join([header, sep, *rows])

    result: dict[str, Any] = {
        "comparison": comparison,
        "winner_by_total_payment": cheapest["label"],
        "winner_by_emi": lowest_emi["label"],
        "savings_vs_worst": savings_vs_worst,
        "display_table": display_table,
    }
    if errors:
        result["_errors"] = errors
    return result
