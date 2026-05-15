"""Tests for the 4 MCP Resource definitions, URI dispatch, and JSON shape."""

from __future__ import annotations

import asyncio
import json

import pytest
import mcp.types as types

from calcnook_mcp.resources import (
    RESOURCES,
    RESOURCE_TEMPLATES,
    SUPPORTED_TAX_COUNTRIES,
    SUPPORTED_DISCOMS,
    read_resource,
)


def _read_sync(uri: str) -> dict:
    """Run the async read_resource and return the parsed JSON dict."""
    contents = asyncio.run(read_resource(uri))
    assert len(contents) == 1, "read_resource must return exactly 1 contents entry"
    item = contents[0]
    assert item.mime_type == "application/json"
    assert isinstance(item.content, str)
    return json.loads(item.content)


# ---------------------------------------------------------------------------
# Static resource list
# ---------------------------------------------------------------------------


def test_resource_count() -> None:
    assert len(RESOURCES) == 4, (
        f"Expected 4 resources, got {len(RESOURCES)}: {[str(r.uri) for r in RESOURCES]}"
    )


def test_all_expected_resource_uris_present() -> None:
    actual = {str(r.uri) for r in RESOURCES}
    expected = {
        "calcnook://tax-brackets/us/2026",
        "calcnook://nisab/current",
        "calcnook://discom-rates/BESCOM",
        "calcnook://aaoifi-thresholds",
    }
    assert actual == expected, (
        f"Missing: {expected - actual}; Extra: {actual - expected}"
    )


def test_every_resource_has_metadata() -> None:
    for r in RESOURCES:
        assert r.name and len(r.name) > 3, f"Resource {r.uri} has trivial name"
        assert r.description and len(r.description) > 10, (
            f"Resource {r.uri} has trivial description"
        )
        assert r.mimeType == "application/json", (
            f"Resource {r.uri} should advertise application/json mimeType"
        )


def test_resource_templates_present() -> None:
    assert len(RESOURCE_TEMPLATES) == 2
    templates = {t.uriTemplate for t in RESOURCE_TEMPLATES}
    assert "calcnook://tax-brackets/{country}/{year}" in templates
    assert "calcnook://discom-rates/{discom}" in templates


# ---------------------------------------------------------------------------
# Tax brackets — every supported country round-trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("country", SUPPORTED_TAX_COUNTRIES)
def test_tax_brackets_dispatch(country: str) -> None:
    payload = _read_sync(f"calcnook://tax-brackets/{country}/2026")
    assert payload["country"] == country
    assert payload["year"] == 2026
    assert "currency" in payload
    assert "source" in payload


def test_us_tax_brackets_have_all_filing_statuses() -> None:
    payload = _read_sync("calcnook://tax-brackets/us/2026")
    fs = payload["filing_status_brackets"]
    for status in ("single", "married_jointly", "married_separately", "head_of_household"):
        assert status in fs
        first = fs[status][0]
        assert "upto" in first and "rate" in first
    assert "standard_deduction" in payload
    assert payload["standard_deduction"]["single"] == 15000


def test_india_tax_brackets_shape() -> None:
    payload = _read_sync("calcnook://tax-brackets/in/2026")
    assert payload["regime"] == "new"
    brackets = payload["new_regime_brackets"]
    assert brackets[0]["upto"] == 400000
    assert brackets[0]["rate"] == 0.0
    assert brackets[-1]["upto"] == "inf"
    assert payload["standard_deduction"] == 75000.0
    assert payload["health_education_cess"] == 0.04


def test_uk_tax_brackets_shape() -> None:
    payload = _read_sync("calcnook://tax-brackets/uk/2026")
    assert payload["personal_allowance"] == 12570.0
    assert "income_tax_bands" in payload
    assert "national_insurance" in payload


def test_au_tax_brackets_shape() -> None:
    payload = _read_sync("calcnook://tax-brackets/au/2026")
    assert "income_tax_brackets" in payload
    assert "medicare_levy" in payload
    last = payload["income_tax_brackets"][-1]
    assert last["upper"] == "inf"
    assert last["rate"] == 0.45


def test_ca_tax_brackets_shape() -> None:
    payload = _read_sync("calcnook://tax-brackets/ca/2026")
    assert payload["basic_personal_amount"] == 16500.0
    assert payload["basic_personal_credit_rate"] == 0.15


def test_unsupported_country_raises() -> None:
    with pytest.raises(ValueError, match="unsupported country"):
        _read_sync("calcnook://tax-brackets/de/2026")


def test_unsupported_year_raises() -> None:
    with pytest.raises(ValueError, match="unsupported year"):
        _read_sync("calcnook://tax-brackets/us/2024")


def test_malformed_tax_brackets_uri_raises() -> None:
    with pytest.raises(ValueError, match="requires"):
        _read_sync("calcnook://tax-brackets/us")


# ---------------------------------------------------------------------------
# Nisab
# ---------------------------------------------------------------------------


def test_nisab_current_shape() -> None:
    payload = _read_sync("calcnook://nisab/current")
    assert "gold" in payload
    assert "silver" in payload
    assert payload["gold"]["nisab_grams"] == 87.48
    assert payload["silver"]["nisab_grams"] == 612.36
    assert payload["gold"]["default_price_per_gram_usd"] == 75.0
    assert payload["silver"]["default_price_per_gram_usd"] == 0.90
    assert "implied_threshold_usd" in payload["gold"]
    assert "implied_threshold_usd" in payload["silver"]
    assert payload["live_data"] is False


def test_nisab_wrong_path_raises() -> None:
    with pytest.raises(ValueError, match="nisab URI must be"):
        _read_sync("calcnook://nisab/historical")


# ---------------------------------------------------------------------------
# DISCOM rates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("discom", SUPPORTED_DISCOMS)
def test_discom_dispatch(discom: str) -> None:
    payload = _read_sync(f"calcnook://discom-rates/{discom}")
    assert payload["discom"] == discom
    assert payload["currency"] == "INR"
    assert payload["unit"] == "kWh"
    assert isinstance(payload["slabs"], list) and len(payload["slabs"]) >= 1
    for slab in payload["slabs"]:
        assert "upto_units" in slab
        assert "rate_per_unit" in slab
    assert payload["slabs"][-1]["upto_units"] == "inf"


def test_unsupported_discom_raises() -> None:
    with pytest.raises(ValueError, match="unsupported discom"):
        _read_sync("calcnook://discom-rates/TANGEDCO")


def test_bescom_first_slab_matches_engine() -> None:
    payload = _read_sync("calcnook://discom-rates/BESCOM")
    first = payload["slabs"][0]
    assert first["upto_units"] == 30
    assert first["rate_per_unit"] == 0.0


# ---------------------------------------------------------------------------
# AAOIFI
# ---------------------------------------------------------------------------


def test_aaoifi_thresholds_shape() -> None:
    payload = _read_sync("calcnook://aaoifi-thresholds")
    ratios = payload["ratios"]
    assert ratios["debt_max_pct"] == 33
    assert ratios["cash_max_pct"] == 33
    assert ratios["receivables_max_pct"] == 49
    assert ratios["haram_max_pct"] == 5


def test_aaoifi_extra_path_raises() -> None:
    with pytest.raises(ValueError, match="takes no path segments"):
        _read_sync("calcnook://aaoifi-thresholds/v2")


# ---------------------------------------------------------------------------
# URI parser edge cases
# ---------------------------------------------------------------------------


def test_unknown_category_raises() -> None:
    with pytest.raises(ValueError, match="unknown resource category"):
        _read_sync("calcnook://gibberish/foo")


def test_wrong_scheme_raises() -> None:
    with pytest.raises(ValueError, match="must start with"):
        _read_sync("https://example.com/x")


def test_accepts_anyurl_input() -> None:
    """SDK passes pydantic.AnyUrl, not str — the handler must accept it."""
    from pydantic import AnyUrl
    contents = asyncio.run(read_resource(AnyUrl("calcnook://aaoifi-thresholds")))
    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    assert payload["ratios"]["debt_max_pct"] == 33
