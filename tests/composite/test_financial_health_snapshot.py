"""Tests for tool_financial_health_snapshot composite."""

from __future__ import annotations

import pytest

from calcnook_mcp.tools.composite import tool_financial_health_snapshot


def test_healthy_35yo() -> None:
    result = tool_financial_health_snapshot({
        "monthly_income": 200_000,
        "monthly_expenses": 80_000,
        "total_debts": 500_000,
        "total_savings": 5_000_000,
        "age": 35,
        "monthly_emi": 20_000,
        "country": "in",
    })
    assert result["savings_rate_pct"] == pytest.approx(60.0, abs=0.01)
    assert result["debt_to_income_ratio"] == pytest.approx(0.10, abs=0.001)
    assert result["emergency_fund_months"] == pytest.approx(62.5, abs=0.01)
    assert result["score"] >= 70
    assert result["verdict"] in {"Healthy", "Excellent"}
    assert len(result["recommended_actions"]) <= 3
    assert result["display"]["score"].endswith("/100")


def test_over_leveraged() -> None:
    result = tool_financial_health_snapshot({
        "monthly_income": 100_000,
        "monthly_expenses": 95_000,
        "total_debts": 3_000_000,
        "total_savings": 100_000,
        "age": 35,
        "monthly_emi": 60_000,
        "country": "in",
    })
    assert result["savings_rate_pct"] == pytest.approx(5.0, abs=0.01)
    assert result["debt_to_income_ratio"] == pytest.approx(0.60, abs=0.001)
    assert result["emergency_fund_months"] < 2
    assert result["score"] < 50
    assert result["verdict"] == "Critical"
    # First action should target the dominant problem (DTI > 40%)
    assert "debt" in result["recommended_actions"][0].lower() or "DTI" in result["recommended_actions"][0]


def test_behind_on_retirement_at_50() -> None:
    result = tool_financial_health_snapshot({
        "monthly_income": 200_000,
        "monthly_expenses": 100_000,
        "total_debts": 0,
        "total_savings": 1_000_000,
        "age": 50,
        "monthly_emi": 0,
        "country": "in",
    })
    # At 50, required corpus = 200000 * 12 * 6 = ₹1.44 Cr → savings ₹10L is way behind.
    assert result["retirement_track"] == "behind"
    assert result["required_corpus_at_age"] == pytest.approx(14_400_000.0, abs=1.0)
    assert any(
        "retirement" in a.lower() or "behind" in a.lower()
        for a in result["recommended_actions"]
    )
