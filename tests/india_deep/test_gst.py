"""MCP wrapper tests for calculate_india_gst."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_gst


def test_18_pct_intra_state():
    r = tool_india_gst({"amount": 1000, "rate": 18})
    assert r["gst_total"] == pytest.approx(180.0)
    assert r["cgst"] == pytest.approx(90.0)
    assert r["sgst"] == pytest.approx(90.0)
    assert r["igst"] == 0.0


def test_28_pct_igst():
    r = tool_india_gst({"amount": 50_000, "rate": 28, "breakup": "igst"})
    assert r["igst"] == pytest.approx(14_000.0)
    assert r["cgst"] == 0.0


def test_18_pct_inclusive_extracts_base():
    r = tool_india_gst({"amount": 1180, "rate": 18, "is_inclusive": True})
    assert r["base"] == pytest.approx(1000.0, rel=1e-4)
    assert r["gst_total"] == pytest.approx(180.0, rel=1e-4)
