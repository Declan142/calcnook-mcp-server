"""MCP wrapper tests for calculate_india_pf_epf."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_pf_epf


def test_pf_epf_basic_above_cap():
    r = tool_india_pf_epf({"monthly_basic": 50_000, "years": 30})
    assert r["employee_monthly"] == pytest.approx(6_000.0)
    # Employer EPS capped at 8.33% × ₹15K
    assert r["employer_eps_monthly"] == pytest.approx(1_249.5, rel=1e-3)
    assert r["corpus_at_retirement"] > 0


def test_pf_epf_below_cap():
    r = tool_india_pf_epf({"monthly_basic": 10_000, "years": 20})
    assert r["employer_monthly"] == pytest.approx(1_200.0)


def test_pf_epf_missing_required():
    with pytest.raises(ValueError, match="monthly_basic"):
        tool_india_pf_epf({"years": 10})
