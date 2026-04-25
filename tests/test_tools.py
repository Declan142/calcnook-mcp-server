"""Functional dispatch tests — one per tool group with known inputs."""

from __future__ import annotations

import pytest

from calcnook_mcp.tools.core import (
    tool_compound_interest,
    tool_sip_dca,
    tool_loan_payment,
    tool_retirement,
    tool_bmi_bmr_tdee,
    tool_convert_currency,
    tool_format_currency_amount,
)
from calcnook_mcp.tools.islamic import (
    tool_zakat,
    tool_islamic_financing,
    tool_hajj_savings,
    tool_screen_halal_stock,
)
from calcnook_mcp.tools.countries import (
    tool_income_tax,
    tool_us_retirement_account,
    tool_eosg,
    tool_vat,
    tool_saudi_zakat_citizen,
    tool_india_electricity_bill,
)


# ---------------------------------------------------------------------------
# Core tools
# ---------------------------------------------------------------------------

def test_compound_interest_basic() -> None:
    result = tool_compound_interest({"principal": 10_000, "annual_rate": 0.07, "years": 10})
    assert "future_value" in result
    assert result["future_value"] == pytest.approx(20096.61, rel=1e-4)
    assert "interest_earned" in result


def test_sip_dca_basic() -> None:
    result = tool_sip_dca({"monthly_amount": 5000, "annual_return": 0.12, "years": 10})
    assert "future_value" in result
    assert result["future_value"] > 0
    assert "total_invested" in result
    assert "wealth_gained" in result


def test_sip_dca_with_stepup() -> None:
    result = tool_sip_dca({"monthly_amount": 5000, "annual_return": 0.12, "years": 10, "step_up_percent": 10.0})
    assert result["step_up_percent"] == 10.0
    # Step-up should produce a higher future value than flat
    flat = tool_sip_dca({"monthly_amount": 5000, "annual_return": 0.12, "years": 10})
    assert result["future_value"] > flat["future_value"]


def test_loan_payment_basic() -> None:
    result = tool_loan_payment({"principal": 300_000, "annual_rate": 0.065, "years": 30})
    assert "monthly_payment" in result
    assert result["monthly_payment"] == pytest.approx(1896.20, rel=1e-4)
    assert "total_interest" in result
    assert "amortization" not in result  # not requested


def test_loan_payment_with_schedule() -> None:
    result = tool_loan_payment({
        "principal": 100_000, "annual_rate": 0.06, "years": 5, "include_schedule": True
    })
    assert "amortization" in result
    assert len(result["amortization"]) > 0


def test_retirement_corpus_needed() -> None:
    result = tool_retirement({
        "mode": "corpus_needed",
        "annual_expense": 50_000,
        "years_in_retirement": 30,
        "post_retirement_return": 0.07,
        "inflation": 0.06,
    })
    assert "corpus_needed" in result
    assert result["corpus_needed"] > 0


def test_retirement_monthly_contribution() -> None:
    result = tool_retirement({
        "mode": "monthly_contribution_for",
        "target_corpus": 10_000_000,
        "years_to_retirement": 20,
        "annual_return": 0.12,
    })
    assert "monthly_contribution" in result
    assert result["monthly_contribution"] == pytest.approx(10008.53, rel=1e-3)


def test_retirement_safe_withdrawal() -> None:
    result = tool_retirement({"mode": "safe_withdrawal", "corpus": 1_000_000})
    assert result["annual_withdrawal"] == pytest.approx(40_000.0)
    assert result["monthly_withdrawal"] == pytest.approx(3333.33, rel=1e-4)


def test_retirement_bad_mode() -> None:
    with pytest.raises(ValueError, match="mode must be one of"):
        tool_retirement({"mode": "bad_mode"})


def test_bmi_mode() -> None:
    result = tool_bmi_bmr_tdee({"mode": "bmi", "weight_kg": 70, "height_cm": 175})
    assert result["bmi"] == pytest.approx(22.86, rel=1e-3)
    assert result["category"] == "normal"


def test_bmr_mode() -> None:
    result = tool_bmi_bmr_tdee({"mode": "bmr", "weight_kg": 70, "height_cm": 175, "age_years": 30, "sex": "male"})
    assert "bmr_kcal" in result
    assert result["bmr_kcal"] == pytest.approx(1648.75, rel=1e-4)


def test_tdee_mode() -> None:
    result = tool_bmi_bmr_tdee({"mode": "tdee", "bmr_kcal": 1673.75, "activity_level": "moderate"})
    assert "tdee_kcal" in result
    assert result["tdee_kcal"] == pytest.approx(2594.31, rel=1e-4)


def test_convert_currency() -> None:
    result = tool_convert_currency({
        "amount": 1000,
        "from_currency": "USD",
        "to_currency": "INR",
        "rates": {"USD": 1.0, "INR": 83.5},
    })
    assert result["converted_amount"] == pytest.approx(83500.0)


def test_format_currency_amount_inr_lakh() -> None:
    result = tool_format_currency_amount({"amount": 1_500_000, "currency": "INR", "lakh_crore_format": True})
    assert result["formatted"] == "₹15.00 L"


def test_format_currency_amount_crore() -> None:
    result = tool_format_currency_amount({"amount": 25_000_000, "currency": "INR", "lakh_crore_format": True})
    assert result["formatted"] == "₹2.50 Cr"


def test_format_currency_amount_usd() -> None:
    result = tool_format_currency_amount({"amount": 1234.56, "currency": "USD"})
    assert result["formatted"] == "$1,234.56"


# ---------------------------------------------------------------------------
# Islamic finance tools
# ---------------------------------------------------------------------------

def test_zakat_basic() -> None:
    result = tool_zakat({
        "cash": 10_000,
        "stocks_value": 15_000,
        "debts": 2_000,
        "currency": "USD",
        "gold_price_per_gram": 75,
        "silver_price_per_gram": 0.90,
        "nisab_basis": "silver",
    })
    assert "zakat_due" in result
    assert result["is_above_nisab"] is True
    assert result["zakat_due"] == pytest.approx(575.0, rel=1e-4)


def test_murabaha() -> None:
    result = tool_islamic_financing({
        "instrument": "murabaha",
        "asset_cost": 100_000,
        "markup_percent": 30.0,
        "tenure_years": 5,
    })
    assert result["total_sale_price"] == pytest.approx(130_000.0)
    assert result["monthly_installment"] == pytest.approx(2166.67, rel=1e-4)


def test_ijarah() -> None:
    result = tool_islamic_financing({
        "instrument": "ijarah",
        "asset_cost": 30_000,
        "monthly_rent": 600.0,
        "lease_years": 5,
    })
    assert result["total_rent_paid"] == pytest.approx(36_000.0)
    assert result["total_cost_of_ownership"] == pytest.approx(36_001.0)


def test_mudarabah() -> None:
    result = tool_islamic_financing({
        "instrument": "mudarabah",
        "capital": 100_000,
        "actual_profit_amount": 20_000,
        "investor_share_ratio": 0.70,
        "years": 3,
    })
    assert result["investor_profit"] == pytest.approx(14_000.0)
    assert result["manager_profit"] == pytest.approx(6_000.0)


def test_hajj_savings() -> None:
    result = tool_hajj_savings({"hajj_cost_target": 10_000, "years_to_hajj": 5})
    assert "monthly_contribution_needed" in result
    assert result["monthly_contribution_needed"] > 0


def test_screen_halal_stock_compliant() -> None:
    result = tool_screen_halal_stock({
        "sector": "technology",
        "market_cap": 1_000_000,
        "debt_interest_bearing": 100_000,
        "cash_and_interest_securities": 50_000,
        "receivables": 200_000,
        "total_revenue": 500_000,
        "haram_revenue": 10_000,
    })
    assert result["is_compliant"] is True
    assert result["failed_checks"] == []


def test_screen_halal_stock_non_compliant() -> None:
    result = tool_screen_halal_stock({
        "sector": "banking",
        "market_cap": 1_000_000,
        "debt_interest_bearing": 400_000,  # debt ratio > 33%
        "cash_and_interest_securities": 50_000,
        "receivables": 200_000,
        "total_revenue": 500_000,
        "haram_revenue": 0,
    })
    assert result["is_compliant"] is False
    assert len(result["failed_checks"]) >= 2  # banking sector + debt ratio


# ---------------------------------------------------------------------------
# Country tools
# ---------------------------------------------------------------------------

def test_income_tax_us() -> None:
    result = tool_income_tax({"country": "us", "income": 60_000, "filing_status": "single"})
    assert result["tax_owed"] == pytest.approx(5161.5, rel=1e-3)
    assert "effective_rate" in result


def test_income_tax_uk() -> None:
    result = tool_income_tax({"country": "uk", "income": 30_000})
    assert result["income_tax"] == pytest.approx(3486.0, rel=1e-3)
    assert "national_insurance" in result
    assert "take_home" in result


def test_income_tax_ca() -> None:
    result = tool_income_tax({"country": "ca", "income": 100_000})
    assert result["tax_owed"] == pytest.approx(14869.32, rel=1e-3)


def test_income_tax_au() -> None:
    result = tool_income_tax({"country": "au", "income": 80_000})
    assert result["income_tax"] == pytest.approx(14788.0, rel=1e-3)
    assert "medicare_levy" in result


def test_income_tax_india_new_regime() -> None:
    result = tool_income_tax({"country": "in", "income": 1_000_000, "regime": "new"})
    assert result["tax_owed"] == 0.0  # 87A rebate kicks in under ₹12L


def test_income_tax_india_above_rebate() -> None:
    result = tool_income_tax({"country": "in", "income": 1_500_000, "regime": "new"})
    assert result["tax_owed"] > 0


def test_us_retirement_401k() -> None:
    result = tool_us_retirement_account({
        "account_type": "traditional_401k",
        "contribution": 10_000,
        "salary": 80_000,
        "employer_match_percent": 0.50,
        "employer_match_cap": 0.06,
        "age": 35,
        "marginal_tax_rate": 0.22,
    })
    assert result["employer_contribution"] == pytest.approx(2400.0)
    assert "tax_savings_now" in result


def test_us_retirement_roth_ira() -> None:
    result = tool_us_retirement_account({
        "account_type": "roth_ira",
        "contribution": 7_000,
        "age": 30,
        "magi": 157_500,
        "filing_status": "single",
    })
    assert result["phase_out_factor"] == pytest.approx(0.5, rel=1e-3)


def test_eosg_uae() -> None:
    result = tool_eosg({
        "country": "ae",
        "monthly_basic_salary": 8_000,
        "years_of_service": 5,
    })
    assert result["gratuity_aed"] == pytest.approx(28_000.0)


def test_eosg_sa_termination() -> None:
    result = tool_eosg({
        "country": "sa",
        "monthly_basic_salary": 5_000,
        "years_of_service": 3,
        "end_reason": "resignation",
    })
    assert result["gratuity_sar"] == pytest.approx(2500.0, rel=1e-4)


def test_vat_uae() -> None:
    result = tool_vat({"country": "ae", "amount": 1000})
    assert result["vat_amount"] == pytest.approx(50.0)
    assert result["gross_amount"] == pytest.approx(1050.0)


def test_vat_sa() -> None:
    result = tool_vat({"country": "sa", "amount": 1000})
    assert result["vat_amount"] == pytest.approx(150.0)
    assert result["gross_amount"] == pytest.approx(1150.0)


def test_saudi_zakat_citizen() -> None:
    result = tool_saudi_zakat_citizen({"zakat_base": 1_000_000})
    assert result["zakat_due"] == pytest.approx(25_000.0)
    assert "disclaimer" in result


def test_india_electricity_bescom() -> None:
    result = tool_india_electricity_bill({"units_consumed": 150, "preset": "BESCOM", "fixed_charges": 50})
    assert result["energy_charge"] == pytest.approx(564.5, rel=1e-4)
    assert result["total_bill"] > result["energy_charge"]


def test_india_electricity_custom_slabs() -> None:
    result = tool_india_electricity_bill({
        "units_consumed": 100,
        "slabs": [[100, 3.0], ["inf", 5.0]],
    })
    assert result["energy_charge"] == pytest.approx(300.0)
