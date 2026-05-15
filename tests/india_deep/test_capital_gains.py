"""MCP wrapper tests for calculate_india_capital_gains."""

import pytest

from calcnook_mcp.tools.india_deep import tool_india_capital_gains


def test_equity_listed_ltcg():
    r = tool_india_capital_gains({
        "asset_type": "equity_listed",
        "purchase_price": 200_000,
        "sale_price": 350_000,
        "purchase_date": "2022-04-01",
        "sale_date": "2024-09-01",
    })
    assert r["classification"] == "LTCG"
    assert r["tax_payable"] == pytest.approx(3_125.0)


def test_crypto_flat_30():
    r = tool_india_capital_gains({
        "asset_type": "crypto",
        "purchase_price": 100_000,
        "sale_price": 200_000,
        "purchase_date": "2024-01-01",
        "sale_date": "2024-12-01",
    })
    assert r["classification"] == "FLAT_30"
    assert r["tax_payable"] == pytest.approx(30_000.0)


def test_property_with_indexation():
    r = tool_india_capital_gains({
        "asset_type": "property",
        "purchase_price": 5_000_000,
        "sale_price": 8_000_000,
        "purchase_date": "2020-01-01",
        "sale_date": "2025-01-01",
        "indexation": True,
    })
    assert r["indexation_used"] is True
    assert r["tax_payable"] == pytest.approx(600_000.0)
