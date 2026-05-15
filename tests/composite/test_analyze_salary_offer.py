"""Tests for tool_analyze_salary_offer composite."""

from __future__ import annotations

import pytest

from calcnook_mcp.tools.composite import tool_analyze_salary_offer


def test_in_new_regime_20l_age_30() -> None:
    result = tool_analyze_salary_offer({
        "salary": 2_000_000,
        "country": "in",
        "age": 30,
        "regime": "new",
        "monthly_expenses": 50_000,
    })
    assert result["currency"] == "INR"
    assert result["gross_annual"] == 2_000_000.0
    # New regime ₹20L: brackets eat into 20% slab.
    assert result["total_tax"] > 0
    assert result["take_home_annual"] == pytest.approx(
        result["gross_annual"] - result["total_tax"], abs=0.01
    )
    assert result["take_home_monthly"] == pytest.approx(result["take_home_annual"] / 12.0, abs=0.01)
    assert result["effective_tax_rate_pct"] == pytest.approx(
        result["total_tax"] / result["gross_annual"] * 100.0, abs=0.01
    )
    assert result["marginal_bracket_estimate_pct"] == pytest.approx(20.0, abs=0.01)
    assert result["retirement_contribution_max"] is not None
    assert result["retirement_contribution_max"] > 0
    assert result["savings_room_monthly"] == pytest.approx(
        result["take_home_monthly"] - 50_000, abs=0.01
    )
    assert "₹" in result["display"]["gross"]
    assert " L" in result["display"]["gross"] or " Cr" in result["display"]["gross"]
    assert 2 <= len(result["recommended_actions"]) <= 4


def test_us_single_80k_age_28() -> None:
    result = tool_analyze_salary_offer({
        "salary": 80_000,
        "country": "us",
        "age": 28,
        "filing_status": "single",
    })
    assert result["currency"] == "USD"
    assert result["total_tax"] == pytest.approx(9214.0, rel=1e-3)
    assert result["retirement_contribution_max"] == 24_000.0
    assert result["savings_room_monthly"] is None
    assert result["display"]["gross"] == "$80,000.00"
    assert result["marginal_bracket_estimate_pct"] == pytest.approx(22.0)
    assert any("401(k)" in a for a in result["recommended_actions"])


def test_uk_55k_age_35() -> None:
    result = tool_analyze_salary_offer({
        "salary": 55_000,
        "country": "uk",
        "age": 35,
    })
    assert result["currency"] == "GBP"
    # UK total tax = income tax + NI
    assert result["total_tax"] > 0
    assert result["take_home_annual"] < 55_000
    # Marginal should be 40% at £55K (above basic-rate band)
    assert result["marginal_bracket_estimate_pct"] == pytest.approx(40.0, abs=0.01)
    assert result["retirement_contribution_max"] is None
    assert "£" in result["display"]["gross"]
    assert any("pension" in a.lower() or "isa" in a.lower() for a in result["recommended_actions"])


def test_invalid_country_raises() -> None:
    with pytest.raises(ValueError, match="country must be one of"):
        tool_analyze_salary_offer({
            "salary": 50_000,
            "country": "de",
            "age": 30,
        })
