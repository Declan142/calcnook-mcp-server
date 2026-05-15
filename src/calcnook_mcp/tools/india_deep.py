"""Dispatch handlers for the 6 India-deep calcnook tools (v0.2.0).

Each handler accepts a flat ``args: dict`` (as MCP supplies) and forwards to
the corresponding engine function in ``calcnook.countries.india``. Returns the
engine's ``.to_dict()`` payload.
"""

from __future__ import annotations

from typing import Any

from calcnook.countries.india import (
    pf_epf,
    gratuity,
    capital_gains,
    advance_tax,
    gst,
    hra_exemption,
)


def tool_india_pf_epf(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India PF/EPF monthly contributions and projected corpus."""
    if "monthly_basic" not in arguments:
        raise ValueError("monthly_basic is required")
    if "years" not in arguments:
        raise ValueError("years is required")

    result = pf_epf.calculate(
        monthly_basic=float(arguments["monthly_basic"]),
        years=float(arguments["years"]),
        employee_pct=float(arguments.get("employee_pct", pf_epf.DEFAULT_EMPLOYEE_PCT)),
        employer_pct=float(arguments.get("employer_pct", pf_epf.DEFAULT_EMPLOYER_PCT)),
        annual_return=float(arguments.get("annual_return", pf_epf.DEFAULT_ANNUAL_RETURN)),
        basic_cap=float(arguments.get("basic_cap", pf_epf.DEFAULT_BASIC_CAP)),
    )
    return result.to_dict()


def tool_india_gratuity(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India statutory gratuity under the Payment of Gratuity Act, 1972."""
    if "monthly_basic_salary" not in arguments:
        raise ValueError("monthly_basic_salary is required")
    if "years_of_service" not in arguments:
        raise ValueError("years_of_service is required")

    result = gratuity.calculate(
        monthly_basic_salary=float(arguments["monthly_basic_salary"]),
        years_of_service=float(arguments["years_of_service"]),
        dearness_allowance=float(arguments.get("dearness_allowance", 0.0)),
    )
    return result.to_dict()


def tool_india_capital_gains(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India capital-gains tax under Budget 2024 framework."""
    required = ("asset_type", "purchase_price", "sale_price", "purchase_date", "sale_date")
    for field in required:
        if field not in arguments:
            raise ValueError(f"{field} is required")

    result = capital_gains.calculate(
        asset_type=str(arguments["asset_type"]),
        purchase_price=float(arguments["purchase_price"]),
        sale_price=float(arguments["sale_price"]),
        purchase_date=arguments["purchase_date"],
        sale_date=arguments["sale_date"],
        indexation=bool(arguments.get("indexation", False)),
        asset_subtype=arguments.get("asset_subtype"),
    )
    return result.to_dict()


def tool_india_advance_tax(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India advance-tax instalment due under Section 211."""
    if "annual_income" not in arguments:
        raise ValueError("annual_income is required")

    total_tax = arguments.get("total_tax_for_year")
    result = advance_tax.calculate(
        annual_income=float(arguments["annual_income"]),
        regime=str(arguments.get("regime", "new")),
        paid_so_far=float(arguments.get("paid_so_far", 0.0)),
        as_of_date=arguments.get("as_of_date"),
        total_tax_for_year=float(total_tax) if total_tax is not None else None,
    )
    return result.to_dict()


def tool_india_gst(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India GST (CGST + SGST or IGST) on a transaction."""
    if "amount" not in arguments:
        raise ValueError("amount is required")
    if "rate" not in arguments:
        raise ValueError("rate is required")

    result = gst.calculate(
        amount=float(arguments["amount"]),
        rate=float(arguments["rate"]),
        is_inclusive=bool(arguments.get("is_inclusive", False)),
        breakup=str(arguments.get("breakup", "cgst_sgst")),
    )
    return result.to_dict()


def tool_india_hra_exemption(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute India HRA exemption under Section 10(13A)."""
    required = ("basic_monthly", "hra_received_monthly", "rent_paid_monthly", "is_metro")
    for field in required:
        if field not in arguments:
            raise ValueError(f"{field} is required")

    result = hra_exemption.calculate(
        basic_monthly=float(arguments["basic_monthly"]),
        hra_received_monthly=float(arguments["hra_received_monthly"]),
        rent_paid_monthly=float(arguments["rent_paid_monthly"]),
        is_metro=bool(arguments["is_metro"]),
    )
    return result.to_dict()
