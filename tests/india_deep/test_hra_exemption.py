"""MCP wrapper tests for calculate_india_hra_exemption."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_hra_exemption


def test_metro_normal():
    r = tool_india_hra_exemption({
        "basic_monthly": 50_000,
        "hra_received_monthly": 20_000,
        "rent_paid_monthly": 18_000,
        "is_metro": True,
    })
    assert r["exempt_monthly"] == pytest.approx(13_000.0)
    assert r["exempt_annual"] == pytest.approx(156_000.0)


def test_non_metro_actual_hra_bound():
    r = tool_india_hra_exemption({
        "basic_monthly": 50_000,
        "hra_received_monthly": 5_000,
        "rent_paid_monthly": 20_000,
        "is_metro": False,
    })
    # Actual HRA = 5000 is the smallest of three
    assert r["exempt_monthly"] == pytest.approx(5_000.0)
    assert r["breakdown"]["applied_min"] == "actual_hra"


def test_zero_rent_no_exemption():
    r = tool_india_hra_exemption({
        "basic_monthly": 50_000,
        "hra_received_monthly": 20_000,
        "rent_paid_monthly": 0,
        "is_metro": True,
    })
    assert r["exempt_monthly"] == 0.0
    assert r["taxable_hra_annual"] == pytest.approx(240_000.0)
