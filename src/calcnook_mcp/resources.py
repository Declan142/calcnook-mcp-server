"""calcnook-mcp resources: 4 readable URIs the LLM can fetch as context.

Resources expose static reference data — tax brackets, nisab thresholds,
DISCOM tariffs, AAOIFI screening caps — so the LLM can ground answers
without re-deriving constants from training data. URIs follow the
`calcnook://<category>/<key>...` convention.
"""

from __future__ import annotations

import json
import math
from typing import Any

import mcp.types as types
from mcp.server.lowlevel.helper_types import ReadResourceContents

from calcnook.countries.us.income_tax import (
    _BRACKETS as _US_BRACKETS,
    _STANDARD_DEDUCTION as _US_STANDARD_DEDUCTION,
)
from calcnook.countries.uk.income_tax import (
    PERSONAL_ALLOWANCE as _UK_PERSONAL_ALLOWANCE,
    BASIC_RATE_BAND as _UK_BASIC_RATE_BAND,
    BASIC_RATE as _UK_BASIC_RATE,
    HIGHER_RATE as _UK_HIGHER_RATE,
    ADDITIONAL_RATE as _UK_ADDITIONAL_RATE,
    ADDITIONAL_RATE_THRESHOLD as _UK_ADDITIONAL_RATE_THRESHOLD,
    NI_LOWER as _UK_NI_LOWER,
    NI_UPPER as _UK_NI_UPPER,
    NI_RATE_MAIN as _UK_NI_RATE_MAIN,
    NI_RATE_UPPER as _UK_NI_RATE_UPPER,
)
from calcnook.countries.ca.income_tax import (
    _FEDERAL_BRACKETS as _CA_BRACKETS,
    BASIC_PERSONAL_AMOUNT as _CA_BPA,
    BASIC_PERSONAL_CREDIT_RATE as _CA_BPA_RATE,
)
from calcnook.countries.au.income_tax import (
    _BRACKETS as _AU_BRACKETS,
    MEDICARE_RATE as _AU_MEDICARE_RATE,
    MEDICARE_PHASE_IN_LOWER as _AU_MEDICARE_LOWER,
    MEDICARE_PHASE_IN_UPPER as _AU_MEDICARE_UPPER,
)
from calcnook.countries.india.income_tax import (
    _NEW_REGIME_BRACKETS as _IN_BRACKETS,
    STANDARD_DEDUCTION_NEW as _IN_STANDARD_DEDUCTION,
    REBATE_87A_MAX as _IN_REBATE_MAX,
    REBATE_87A_INCOME_LIMIT as _IN_REBATE_LIMIT,
    CESS_RATE as _IN_CESS,
)
from calcnook.countries.india.electricity_bill import (
    BESCOM_RESIDENTIAL,
    MSEB_RESIDENTIAL,
    BSES_RESIDENTIAL,
)


SUPPORTED_TAX_COUNTRIES: tuple[str, ...] = ("us", "uk", "ca", "au", "in")
SUPPORTED_TAX_YEARS: tuple[int, ...] = (2026,)
SUPPORTED_DISCOMS: tuple[str, ...] = ("BESCOM", "MSEB", "BSES")


RESOURCES: list[types.Resource] = [
    types.Resource(
        uri="calcnook://tax-brackets/us/2026",
        name="Income Tax Brackets",
        description=(
            "Tax brackets for a country/year — supported countries: us, uk, ca, au, in. "
            "Year 2026 only. Default URI fetches US 2026; substitute country/year segments "
            "to fetch other jurisdictions (e.g. calcnook://tax-brackets/in/2026)."
        ),
        mimeType="application/json",
    ),
    types.Resource(
        uri="calcnook://nisab/current",
        name="Current Nisab Thresholds",
        description=(
            "Static gold (87.48g AAOIFI) and silver (612.36g AAOIFI) nisab thresholds for "
            "Zakat al-Mal, with default per-gram prices. Live spot data integration pending."
        ),
        mimeType="application/json",
    ),
    types.Resource(
        uri="calcnook://discom-rates/BESCOM",
        name="India DISCOM Residential Tariff Slabs",
        description=(
            "Indian DISCOM residential slab tariff — supported: BESCOM (Karnataka), "
            "MSEB (Maharashtra), BSES (Delhi). Default URI fetches BESCOM; substitute the "
            "discom segment for the other two."
        ),
        mimeType="application/json",
    ),
    types.Resource(
        uri="calcnook://aaoifi-thresholds",
        name="AAOIFI Sharia-Screening Ratio Caps",
        description=(
            "AAOIFI standard ratio caps for Sharia stock screening: max debt %, max cash %, "
            "max receivables %, max haram revenue %."
        ),
        mimeType="application/json",
    ),
]


RESOURCE_TEMPLATES: list[types.ResourceTemplate] = [
    types.ResourceTemplate(
        uriTemplate="calcnook://tax-brackets/{country}/{year}",
        name="Income Tax Brackets (parameterised)",
        description=(
            "Fetch tax brackets for any supported country/year. country in "
            "{us, uk, ca, au, in}; year in {2026}."
        ),
        mimeType="application/json",
    ),
    types.ResourceTemplate(
        uriTemplate="calcnook://discom-rates/{discom}",
        name="India DISCOM Residential Slabs (parameterised)",
        description="Fetch slab tariff for an Indian DISCOM. discom in {BESCOM, MSEB, BSES}.",
        mimeType="application/json",
    ),
]


def _slabs_to_json(slabs: list) -> list[dict[str, Any]]:
    """Render slab tuples [(upper_units, rate), …] as JSON-friendly dicts.

    `inf` upper bound becomes the string 'inf' (math.inf is not JSON-serialisable).
    """
    out: list[dict[str, Any]] = []
    for upper, rate in slabs:
        upper_val: Any = "inf" if isinstance(upper, float) and math.isinf(upper) else upper
        out.append({"upto_units": upper_val, "rate_per_unit": rate})
    return out


def _brackets_to_json(brackets: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Render (upper_bound, rate) bracket tuples as JSON-friendly dicts."""
    out: list[dict[str, Any]] = []
    for upper, rate in brackets:
        upper_val: Any = "inf" if isinstance(upper, float) and math.isinf(upper) else upper
        out.append({"upto": upper_val, "rate": rate})
    return out


def _au_brackets_to_json(brackets: list[tuple]) -> list[dict[str, Any]]:
    """AU brackets: (lower, upper, base_tax, rate)."""
    out: list[dict[str, Any]] = []
    for lower, upper, base, rate in brackets:
        upper_val: Any = "inf" if isinstance(upper, float) and math.isinf(upper) else upper
        out.append({"lower": lower, "upper": upper_val, "base_tax": base, "rate": rate})
    return out


def _tax_brackets_payload(country: str, year: int) -> dict[str, Any]:
    if country == "us":
        return {
            "country": "us",
            "year": year,
            "currency": "USD",
            "source": "IRS Rev. Proc. 2025 (projected 2026)",
            "filing_status_brackets": {
                fs: _brackets_to_json(b) for fs, b in _US_BRACKETS.items()
            },
            "standard_deduction": dict(_US_STANDARD_DEDUCTION),
        }
    if country == "uk":
        return {
            "country": "uk",
            "year": year,
            "currency": "GBP",
            "source": "HMRC 2025/26",
            "personal_allowance": _UK_PERSONAL_ALLOWANCE,
            "income_tax_bands": [
                {
                    "name": "basic",
                    "rate": _UK_BASIC_RATE,
                    "band_above_pa": _UK_BASIC_RATE_BAND,
                    "upto_total_income": _UK_PERSONAL_ALLOWANCE + _UK_BASIC_RATE_BAND,
                },
                {
                    "name": "higher",
                    "rate": _UK_HIGHER_RATE,
                    "upto_total_income": _UK_ADDITIONAL_RATE_THRESHOLD,
                },
                {
                    "name": "additional",
                    "rate": _UK_ADDITIONAL_RATE,
                    "above_total_income": _UK_ADDITIONAL_RATE_THRESHOLD,
                },
            ],
            "national_insurance": {
                "lower_threshold": _UK_NI_LOWER,
                "upper_threshold": _UK_NI_UPPER,
                "rate_main": _UK_NI_RATE_MAIN,
                "rate_above_upper": _UK_NI_RATE_UPPER,
            },
        }
    if country == "ca":
        return {
            "country": "ca",
            "year": year,
            "currency": "CAD",
            "source": "CRA T4012 (projected 2026)",
            "federal_brackets": _brackets_to_json(_CA_BRACKETS),
            "basic_personal_amount": _CA_BPA,
            "basic_personal_credit_rate": _CA_BPA_RATE,
            "provincial_tax": "not_implemented",
        }
    if country == "au":
        return {
            "country": "au",
            "year": year,
            "currency": "AUD",
            "source": "ATO 2025-26",
            "income_tax_brackets": _au_brackets_to_json(_AU_BRACKETS),
            "medicare_levy": {
                "rate": _AU_MEDICARE_RATE,
                "phase_in_lower": _AU_MEDICARE_LOWER,
                "phase_in_upper": _AU_MEDICARE_UPPER,
            },
        }
    if country == "in":
        return {
            "country": "in",
            "year": year,
            "currency": "INR",
            "source": "Finance Act 2025 / Union Budget 2025",
            "regime": "new",
            "new_regime_brackets": _brackets_to_json(_IN_BRACKETS),
            "standard_deduction": _IN_STANDARD_DEDUCTION,
            "section_87a_rebate": {
                "max": _IN_REBATE_MAX,
                "income_limit": _IN_REBATE_LIMIT,
            },
            "health_education_cess": _IN_CESS,
            "old_regime": "supported_via_tool_param_but_not_optimised",
        }
    raise ValueError(
        f"unsupported country '{country}' — supported: {', '.join(SUPPORTED_TAX_COUNTRIES)}"
    )


def _nisab_payload() -> dict[str, Any]:
    gold_grams = 87.48
    silver_grams = 612.36
    gold_price_per_gram = 75.0
    silver_price_per_gram = 0.90
    return {
        "source": "AAOIFI standard nisab weights; default per-gram prices are placeholders",
        "live_data": False,
        "gold": {
            "nisab_grams": gold_grams,
            "default_price_per_gram_usd": gold_price_per_gram,
            "implied_threshold_usd": round(gold_grams * gold_price_per_gram, 2),
        },
        "silver": {
            "nisab_grams": silver_grams,
            "default_price_per_gram_usd": silver_price_per_gram,
            "implied_threshold_usd": round(silver_grams * silver_price_per_gram, 2),
        },
        "recommendation": (
            "silver basis is lower and more inclusive — preferred unless following a school "
            "that mandates gold basis"
        ),
        "note": (
            "Replace default per-gram prices with current spot prices when computing zakat. "
            "Live spot integration is on the roadmap."
        ),
    }


def _discom_payload(discom: str) -> dict[str, Any]:
    discom_upper = discom.upper()
    if discom_upper == "BESCOM":
        slabs = BESCOM_RESIDENTIAL
        operator = "Bangalore Electricity Supply Company Ltd. (Karnataka)"
    elif discom_upper == "MSEB":
        slabs = MSEB_RESIDENTIAL
        operator = "Maharashtra State Electricity Distribution Co. Ltd."
    elif discom_upper == "BSES":
        slabs = BSES_RESIDENTIAL
        operator = "BSES Rajdhani / Yamuna (Delhi)"
    else:
        raise ValueError(
            f"unsupported discom '{discom}' — supported: {', '.join(SUPPORTED_DISCOMS)}"
        )
    return {
        "discom": discom_upper,
        "operator": operator,
        "category": "residential",
        "currency": "INR",
        "unit": "kWh",
        "slabs": _slabs_to_json(slabs),
        "note": (
            "Slabs are progressive: rate applies only to units in that slab range. "
            "Add fixed charges, fuel surcharge, and electricity duty separately via the tool."
        ),
    }


def _aaoifi_payload() -> dict[str, Any]:
    return {
        "source": "AAOIFI Sharia Standard No. 21 (Financial Papers — Shares & Bonds)",
        "ratios": {
            "debt_max_pct": 33,
            "cash_max_pct": 33,
            "receivables_max_pct": 49,
            "haram_max_pct": 5,
        },
        "denominator": (
            "ratios are computed against trailing-12-month average market capitalisation "
            "(or total assets per some interpretations)"
        ),
        "purification_required_when": "haram_revenue_pct > 0",
        "note": (
            "These caps are AAOIFI-standard; some indices (Dow Jones Islamic, S&P Sharia) "
            "use slightly different thresholds"
        ),
    }


def _parse_uri(uri: str) -> tuple[str, list[str]]:
    """Strip 'calcnook://' and split path into segments.

    `calcnook://tax-brackets/us/2026` → ('tax-brackets', ['us', '2026']).
    `calcnook://nisab/current`        → ('nisab', ['current']).
    """
    prefix = "calcnook://"
    if not uri.startswith(prefix):
        raise ValueError(f"resource URI must start with '{prefix}': got '{uri}'")
    rest = uri[len(prefix):].rstrip("/")
    parts = [p for p in rest.split("/") if p]
    if not parts:
        raise ValueError(f"empty resource path: '{uri}'")
    return parts[0], parts[1:]


async def read_resource(uri: Any) -> list[ReadResourceContents]:
    """Dispatch a `calcnook://...` URI to the right payload builder.

    Returns a single TextResourceContents wrapping JSON. The handler accepts
    `pydantic.AnyUrl` (passed by mcp SDK) or plain `str` (called directly in tests).
    """
    uri_str = str(uri)
    category, segments = _parse_uri(uri_str)

    if category == "tax-brackets":
        if len(segments) != 2:
            raise ValueError(
                f"tax-brackets URI requires '/<country>/<year>': got '{uri_str}'"
            )
        country = segments[0].lower()
        try:
            year = int(segments[1])
        except ValueError as exc:
            raise ValueError(f"year must be an integer: '{segments[1]}'") from exc
        if country not in SUPPORTED_TAX_COUNTRIES:
            raise ValueError(
                f"unsupported country '{country}' — supported: {', '.join(SUPPORTED_TAX_COUNTRIES)}"
            )
        if year not in SUPPORTED_TAX_YEARS:
            raise ValueError(
                f"unsupported year {year} — supported: {SUPPORTED_TAX_YEARS}"
            )
        payload = _tax_brackets_payload(country, year)

    elif category == "nisab":
        if segments != ["current"]:
            raise ValueError(
                f"nisab URI must be 'calcnook://nisab/current': got '{uri_str}'"
            )
        payload = _nisab_payload()

    elif category == "discom-rates":
        if len(segments) != 1:
            raise ValueError(
                f"discom-rates URI requires '/<discom>': got '{uri_str}'"
            )
        payload = _discom_payload(segments[0])

    elif category == "aaoifi-thresholds":
        if segments:
            raise ValueError(
                f"aaoifi-thresholds URI takes no path segments: got '{uri_str}'"
            )
        payload = _aaoifi_payload()

    else:
        raise ValueError(f"unknown resource category '{category}' in URI '{uri_str}'")

    return [
        ReadResourceContents(
            content=json.dumps(payload, indent=2, default=str),
            mime_type="application/json",
        )
    ]
