"""Dispatch handlers for country-specific calcnook tools."""

from __future__ import annotations

from typing import Any

from calcnook.countries.us import income_tax as us_tax, retirement_accounts as us_retirement
from calcnook.countries.uk import income_tax as uk_tax
from calcnook.countries.ca import income_tax as ca_tax
from calcnook.countries.au import income_tax as au_tax
from calcnook.countries.india import income_tax as in_tax, electricity_bill
from calcnook.countries.ae import end_of_service_gratuity as ae_eosg, vat as ae_vat
from calcnook.countries.sa import end_of_service_gratuity as sa_eosg, vat as sa_vat, zakat_citizen


def tool_income_tax(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate income tax for US, UK, CA, AU, or India."""
    country = str(arguments.get("country", "")).lower()
    if country not in {"us", "uk", "ca", "au", "in"}:
        raise ValueError("country must be one of: us, uk, ca, au, in")

    if country == "us":
        result = us_tax.calculate(
            income=float(arguments["income"]),
            filing_status=str(arguments.get("filing_status", "single")),
            year=int(arguments.get("year", 2026)),
        )
    elif country == "uk":
        result = uk_tax.calculate(
            income=float(arguments["income"]),
            year=int(arguments.get("year", 2026)),
        )
    elif country == "ca":
        result = ca_tax.calculate(
            income=float(arguments["income"]),
            province=arguments.get("province"),
            year=int(arguments.get("year", 2026)),
        )
    elif country == "au":
        result = au_tax.calculate(
            income=float(arguments["income"]),
            has_hecs_debt=bool(arguments.get("has_hecs_debt", False)),
            year=int(arguments.get("year", 2026)),
        )
    else:  # in
        result = in_tax.calculate(
            gross_income=float(arguments["income"]),
            regime=str(arguments.get("regime", "new")),
            year=int(arguments.get("year", 2026)),
        )

    return result.to_dict()


def tool_us_retirement_account(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate US retirement account contributions (Traditional 401k or Roth IRA)."""
    account_type = str(arguments.get("account_type", ""))
    if account_type not in {"traditional_401k", "roth_ira"}:
        raise ValueError("account_type must be one of: traditional_401k, roth_ira")

    if account_type == "traditional_401k":
        result = us_retirement.traditional_401k(
            contribution=float(arguments["contribution"]),
            salary=float(arguments["salary"]),
            employer_match_percent=float(arguments.get("employer_match_percent", 0.0)),
            employer_match_cap=float(arguments.get("employer_match_cap", 0.06)),
            age=int(arguments["age"]),
            marginal_tax_rate=float(arguments.get("marginal_tax_rate", 0.22)),
        )
    else:  # roth_ira
        result = us_retirement.roth_ira(
            contribution=float(arguments["contribution"]),
            age=int(arguments["age"]),
            magi=float(arguments["magi"]),
            filing_status=str(arguments.get("filing_status", "single")),
        )

    return result.to_dict()


def tool_eosg(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate End of Service Gratuity for UAE or Saudi Arabia."""
    country = str(arguments.get("country", "")).lower()
    if country not in {"ae", "sa"}:
        raise ValueError("country must be one of: ae, sa")

    if country == "ae":
        result = ae_eosg.calculate(
            monthly_basic_salary=float(arguments["monthly_basic_salary"]),
            years_of_service=float(arguments["years_of_service"]),
            contract_type=str(arguments.get("contract_type", "limited")),
        )
    else:  # sa
        result = sa_eosg.calculate(
            monthly_basic_salary=float(arguments["monthly_basic_salary"]),
            years_of_service=float(arguments["years_of_service"]),
            end_reason=str(arguments.get("end_reason", "termination")),
        )

    return result.to_dict()


def tool_vat(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate VAT for UAE (5%) or Saudi Arabia (15%)."""
    country = str(arguments.get("country", "")).lower()
    if country not in {"ae", "sa"}:
        raise ValueError("country must be one of: ae, sa")

    if country == "ae":
        result = ae_vat.calculate(
            amount=float(arguments["amount"]),
            is_inclusive=bool(arguments.get("is_inclusive", False)),
        )
    else:  # sa
        result = sa_vat.calculate(
            amount=float(arguments["amount"]),
            is_inclusive=bool(arguments.get("is_inclusive", False)),
        )

    return result.to_dict()


def tool_saudi_zakat_citizen(arguments: dict[str, Any]) -> dict[str, Any]:
    """Estimate ZATCA-collected Zakat for Saudi / GCC nationals (2.5% of zakat base)."""
    result = zakat_citizen.calculate(
        zakat_base=float(arguments["zakat_base"]),
    )
    return result.to_dict()


def tool_india_electricity_bill(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calculate India electricity bill using progressive slab tariffs.

    Pass a preset name ("BESCOM", "MSEB", "BSES") via the ``preset`` field,
    or supply custom ``slabs`` as a list of [upper_units, rate_per_unit] pairs.
    BESCOM_RESIDENTIAL, MSEB_RESIDENTIAL, BSES_RESIDENTIAL constants are also
    available from ``calcnook.countries.india.electricity_bill``.
    """
    from calcnook.countries.india.electricity_bill import (
        BESCOM_RESIDENTIAL,
        MSEB_RESIDENTIAL,
        BSES_RESIDENTIAL,
    )

    preset = str(arguments.get("preset", "")).upper()
    if preset == "BESCOM":
        slabs = BESCOM_RESIDENTIAL
    elif preset == "MSEB":
        slabs = MSEB_RESIDENTIAL
    elif preset == "BSES":
        slabs = BSES_RESIDENTIAL
    elif "slabs" in arguments:
        slabs = [(float(s[0]) if str(s[0]).lower() != "inf" else float("inf"), float(s[1])) for s in arguments["slabs"]]
    else:
        raise ValueError("Provide 'preset' (BESCOM / MSEB / BSES) or custom 'slabs' list")

    result = electricity_bill.calculate(
        units_consumed=float(arguments["units_consumed"]),
        slabs=slabs,
        fixed_charges=float(arguments.get("fixed_charges", 0.0)),
        fuel_surcharge_per_unit=float(arguments.get("fuel_surcharge_per_unit", 0.0)),
        electricity_duty_percent=float(arguments.get("electricity_duty_percent", 0.0)),
    )
    return result.to_dict()
