"""MCP wrapper tests for calculate_india_gratuity."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_gratuity


def test_gratuity_standard_10y():
    r = tool_india_gratuity({"monthly_basic_salary": 50_000, "years_of_service": 10})
    assert r["years_of_service_used"] == 10
    assert r["gratuity_gross"] == pytest.approx(288_461.54, rel=1e-3)


def test_gratuity_floors_fractional_years():
    r = tool_india_gratuity({"monthly_basic_salary": 40_000, "years_of_service": 7.5})
    assert r["years_of_service_used"] == 7


def test_gratuity_with_da():
    r = tool_india_gratuity({
        "monthly_basic_salary": 40_000,
        "years_of_service": 10,
        "dearness_allowance": 10_000,
    })
    expected = (15 * 50_000 * 10) / 26.0
    assert r["gratuity_gross"] == pytest.approx(expected, rel=1e-6)
