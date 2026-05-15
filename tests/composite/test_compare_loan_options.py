"""Tests for tool_compare_loan_options composite."""

from __future__ import annotations

import pytest

from calcnook_mcp.tools.composite import tool_compare_loan_options


def test_two_option_home_loan() -> None:
    result = tool_compare_loan_options({
        "options": [
            {"label": "HDFC 8.5% 20y", "principal": 5_000_000, "annual_rate": 0.085, "years": 20},
            {"label": "SBI 8.4% 15y", "principal": 5_000_000, "annual_rate": 0.084, "years": 15},
        ],
    })
    assert len(result["comparison"]) == 2
    # Shorter tenure (15y) → lower total payment despite same principal
    assert result["winner_by_total_payment"] == "SBI 8.4% 15y"
    # Lower EMI → 20-year option (longer tenure spreads payment)
    assert result["winner_by_emi"] == "HDFC 8.5% 20y"
    assert result["savings_vs_worst"] > 0
    assert result["display_table"].startswith("| Option |")
    assert "8,5" in result["display_table"] or "5,000,000" in result["display_table"] or "EMI" in result["display_table"]


def test_three_option_with_extra_monthly() -> None:
    result = tool_compare_loan_options({
        "options": [
            {"label": "A: 8.5% 20y", "principal": 5_000_000, "annual_rate": 0.085, "years": 20},
            {"label": "B: 8.5% 20y +10k", "principal": 5_000_000, "annual_rate": 0.085, "years": 20, "extra_monthly": 10_000},
            {"label": "C: 9.0% 25y", "principal": 5_000_000, "annual_rate": 0.09, "years": 25},
        ],
    })
    assert len(result["comparison"]) == 3
    # Extra-payment option should win on total payment.
    assert result["winner_by_total_payment"] == "B: 8.5% 20y +10k"
    # Effective tenure with extra ₹10k should be ~12-13y, much less than nominal 20.
    b = next(e for e in result["comparison"] if e["label"] == "B: 8.5% 20y +10k")
    assert 11.0 < b["effective_years"] < 14.0
    # Lowest-EMI is the longest-tenure option (25y at 9%).
    assert result["winner_by_emi"] == "C: 9.0% 25y"


def test_single_option_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        tool_compare_loan_options({
            "options": [
                {"label": "Solo", "principal": 1_000_000, "annual_rate": 0.08, "years": 10},
            ],
        })
