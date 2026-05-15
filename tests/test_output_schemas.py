"""Validate every tool's runtime output against its declared outputSchema.

One representative happy-path case per tool. If `jsonschema` is importable
we use full draft validation; otherwise we fall back to a minimal stdlib
validator that checks required keys and JSON-Schema primitive types.
"""

from __future__ import annotations

from typing import Any

import pytest

from calcnook_mcp.server import TOOLS, DISPATCH


try:
    import jsonschema as _jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - jsonschema is a dev convenience only
    _HAS_JSONSCHEMA = False


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}


def _accepts(value: Any, type_decl: Any) -> bool:
    if type_decl is None:
        return True
    if isinstance(type_decl, list):
        return any(_accepts(value, t) for t in type_decl)
    expected = _TYPE_MAP.get(type_decl)
    if expected is None:
        return True
    if type_decl == "number" and isinstance(value, bool):
        return False
    if type_decl == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _stdlib_validate(payload: dict[str, Any], schema: dict[str, Any], path: str = "$") -> None:
    """Minimal JSON-Schema check: required keys + per-property type."""
    assert isinstance(payload, dict), f"{path}: expected object, got {type(payload).__name__}"
    for req in schema.get("required", []):
        assert req in payload, f"{path}: missing required key '{req}'"
    properties = schema.get("properties", {})
    for key, value in payload.items():
        if key not in properties:
            continue
        prop_schema = properties[key]
        type_decl = prop_schema.get("type")
        if type_decl is not None:
            assert _accepts(value, type_decl), (
                f"{path}.{key}: type mismatch — declared {type_decl}, got {type(value).__name__}"
            )
        if value is not None and isinstance(value, dict) and prop_schema.get("type") == "object":
            _stdlib_validate(value, prop_schema, f"{path}.{key}")
        if value is not None and isinstance(value, list) and prop_schema.get("type") == "array":
            item_schema = prop_schema.get("items")
            if isinstance(item_schema, dict):
                for i, item in enumerate(value):
                    if item_schema.get("type") == "object" and isinstance(item, dict):
                        _stdlib_validate(item, item_schema, f"{path}.{key}[{i}]")
                    elif item_schema.get("type") is not None:
                        assert _accepts(item, item_schema["type"]), (
                            f"{path}.{key}[{i}]: type mismatch — declared "
                            f"{item_schema['type']}, got {type(item).__name__}"
                        )


def _validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    if _HAS_JSONSCHEMA:
        _jsonschema.validate(instance=payload, schema=schema)
    else:
        _stdlib_validate(payload, schema)


# Happy-path inputs for every tool — keyed by tool name.
TOOL_INPUTS: dict[str, dict[str, Any]] = {
    "calculate_compound_interest": {
        "principal": 1000, "annual_rate": 0.07, "years": 10,
    },
    "calculate_sip_dca": {
        "monthly_amount": 5000, "annual_return": 0.12, "years": 15,
    },
    "calculate_loan_payment": {
        "principal": 300000, "annual_rate": 0.065, "years": 30,
    },
    "calculate_retirement": {
        "mode": "corpus_needed",
        "annual_expense": 600000,
        "years_in_retirement": 30,
        "post_retirement_return": 0.07,
        "inflation": 0.05,
    },
    "calculate_bmi_bmr_tdee": {
        "mode": "bmi", "weight_kg": 70, "height_cm": 175,
    },
    "convert_currency": {
        "amount": 1000, "from_currency": "USD", "to_currency": "INR",
        "rates": {"USD": 1.0, "INR": 83.5},
    },
    "format_currency_amount": {
        "amount": 25000000, "currency": "INR", "lakh_crore_format": True,
    },
    "calculate_zakat": {
        "cash": 25000, "stocks_value": 5000,
        "gold_price_per_gram": 75.0, "silver_price_per_gram": 0.90,
    },
    "calculate_islamic_financing": {
        "instrument": "murabaha", "asset_cost": 100000,
        "markup_percent": 30, "tenure_years": 5,
    },
    "calculate_hajj_savings": {
        "hajj_cost_target": 8000, "years_to_hajj": 5, "expected_annual_return": 0.06,
    },
    "screen_halal_stock": {
        "sector": "technology", "market_cap": 1000000000,
        "debt_interest_bearing": 100000000,
        "cash_and_interest_securities": 50000000,
        "receivables": 20000000, "total_revenue": 500000000,
        "haram_revenue": 1000000,
    },
    "calculate_income_tax": {
        "country": "us", "income": 85000, "filing_status": "married_jointly",
    },
    "calculate_us_retirement_account": {
        "account_type": "traditional_401k", "contribution": 15000,
        "salary": 100000, "age": 30,
        "employer_match_percent": 0.5, "employer_match_cap": 0.06,
        "marginal_tax_rate": 0.22,
    },
    "calculate_eosg": {
        "country": "ae", "monthly_basic_salary": 8000, "years_of_service": 7,
    },
    "calculate_vat": {
        "country": "ae", "amount": 1000,
    },
    "calculate_saudi_zakat_citizen": {
        "zakat_base": 1000000,
    },
    "calculate_india_electricity_bill": {
        "units_consumed": 250, "preset": "BESCOM",
        "fixed_charges": 50, "fuel_surcharge_per_unit": 0.5,
        "electricity_duty_percent": 6,
    },
}


def test_every_tool_has_output_schema() -> None:
    """Every registered tool must declare an outputSchema."""
    missing = [t.name for t in TOOLS if not getattr(t, "outputSchema", None)]
    assert missing == [], f"Tools without outputSchema: {missing}"


def test_every_tool_has_input_fixture() -> None:
    """The TOOL_INPUTS fixture must cover every registered tool."""
    tool_names = {t.name for t in TOOLS}
    missing = tool_names - TOOL_INPUTS.keys()
    extra = TOOL_INPUTS.keys() - tool_names
    assert not missing, f"Missing fixtures: {missing}"
    assert not extra, f"Extra fixtures: {extra}"


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.name)
def test_tool_output_matches_schema(tool: Any) -> None:
    """Run each tool with its happy-path input and validate the output shape."""
    arguments = TOOL_INPUTS[tool.name]
    handler = DISPATCH[tool.name]
    payload = handler(arguments)
    schema = tool.outputSchema
    assert schema is not None, f"{tool.name}: outputSchema is None"
    _validate(payload, schema)


# ---------------------------------------------------------------------------
# Mode / instrument coverage — exercise alternate code paths
# ---------------------------------------------------------------------------

_ALT_CASES: list[tuple[str, dict[str, Any]]] = [
    ("calculate_retirement", {
        "mode": "monthly_contribution_for",
        "target_corpus": 20000000, "years_to_retirement": 20, "annual_return": 0.10,
    }),
    ("calculate_retirement", {
        "mode": "safe_withdrawal", "corpus": 1000000,
    }),
    ("calculate_bmi_bmr_tdee", {
        "mode": "bmr", "weight_kg": 80, "height_cm": 180,
        "age_years": 30, "sex": "male",
    }),
    ("calculate_bmi_bmr_tdee", {
        "mode": "tdee", "bmr_kcal": 1700, "activity_level": "moderate",
    }),
    ("calculate_islamic_financing", {
        "instrument": "ijarah", "asset_cost": 30000,
        "monthly_rent": 600, "lease_years": 5,
    }),
    ("calculate_islamic_financing", {
        "instrument": "mudarabah", "capital": 100000,
        "actual_profit_amount": 20000, "investor_share_ratio": 0.7, "years": 2,
    }),
    ("calculate_income_tax", {"country": "uk", "income": 50000}),
    ("calculate_income_tax", {"country": "ca", "income": 80000, "province": "ON"}),
    ("calculate_income_tax", {"country": "au", "income": 70000, "has_hecs_debt": True}),
    ("calculate_income_tax", {"country": "in", "income": 1500000, "regime": "new"}),
    ("calculate_us_retirement_account", {
        "account_type": "roth_ira", "contribution": 7000,
        "age": 30, "magi": 155000, "filing_status": "single",
    }),
    ("calculate_eosg", {
        "country": "sa", "monthly_basic_salary": 5000,
        "years_of_service": 6, "end_reason": "resignation",
    }),
    ("calculate_vat", {"country": "sa", "amount": 1150, "is_inclusive": True}),
    ("calculate_loan_payment", {
        "principal": 100000, "annual_rate": 0.06, "years": 5, "include_schedule": True,
    }),
]


@pytest.mark.parametrize("name,arguments", _ALT_CASES, ids=lambda v: v if isinstance(v, str) else "")
def test_alt_paths_match_schema(name: str, arguments: dict[str, Any]) -> None:
    """Exercise alternate modes / countries / instruments against the same schema."""
    tool = next(t for t in TOOLS if t.name == name)
    payload = DISPATCH[name](arguments)
    _validate(payload, tool.outputSchema)
