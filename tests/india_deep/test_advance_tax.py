"""MCP wrapper tests for calculate_india_advance_tax."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_advance_tax


def test_q1_due():
    r = tool_india_advance_tax({
        "annual_income": 2_500_000,
        "regime": "new",
        "as_of_date": "2025-04-01",
    })
    assert r["current_quarter"] == "Q1"
    assert r["next_due_date"] == "2025-06-15"


def test_q2_with_paid_so_far():
    r = tool_india_advance_tax({
        "annual_income": 2_500_000,
        "paid_so_far": 50_000,
        "as_of_date": "2025-08-01",
    })
    assert r["current_quarter"] == "Q2"
    cumulative_required = 0.45 * r["total_tax_estimated"]
    assert r["next_installment_due_now"] == pytest.approx(max(0, cumulative_required - 50_000), rel=1e-3)


def test_total_tax_for_year_override():
    """Caller-supplied total_tax_for_year should bypass income_tax engine."""
    r = tool_india_advance_tax({
        "annual_income": 1_000_000,
        "total_tax_for_year": 200_000,
        "as_of_date": "2025-04-01",
    })
    assert r["total_tax_estimated"] == pytest.approx(200_000.0)
    assert r["next_installment_required_cumulative"] == pytest.approx(0.15 * 200_000)
