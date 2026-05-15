"""Tests for the 5 MCP Prompt definitions and their renderer functions."""

from __future__ import annotations

import pytest
import mcp.types as types

from calcnook_mcp.prompts import PROMPTS, PROMPT_RENDERERS


EXPECTED_PROMPT_NAMES = {
    "plan-retirement",
    "annual-zakat-sweep",
    "salary-offer-analysis",
    "eosg-before-resignation",
    "islamic-vs-conventional-loan",
}


def test_prompt_count() -> None:
    assert len(PROMPTS) == 5, (
        f"Expected 5 prompts, got {len(PROMPTS)}: {[p.name for p in PROMPTS]}"
    )


def test_all_expected_prompts_present() -> None:
    actual = {p.name for p in PROMPTS}
    assert actual == EXPECTED_PROMPT_NAMES, (
        f"Missing: {EXPECTED_PROMPT_NAMES - actual}; Extra: {actual - EXPECTED_PROMPT_NAMES}"
    )


def test_every_prompt_has_renderer() -> None:
    for prompt in PROMPTS:
        assert prompt.name in PROMPT_RENDERERS, (
            f"Prompt '{prompt.name}' has no renderer in PROMPT_RENDERERS"
        )


def test_no_extra_renderers() -> None:
    prompt_names = {p.name for p in PROMPTS}
    for name in PROMPT_RENDERERS:
        assert name in prompt_names, (
            f"Renderer '{name}' has no matching Prompt registration"
        )


def test_every_prompt_has_description_and_arguments() -> None:
    for prompt in PROMPTS:
        assert prompt.description and len(prompt.description) > 10, (
            f"Prompt '{prompt.name}' has missing or trivial description"
        )
        assert prompt.arguments and len(prompt.arguments) >= 1, (
            f"Prompt '{prompt.name}' must declare at least 1 argument"
        )
        for arg in prompt.arguments:
            assert isinstance(arg, types.PromptArgument), (
                f"Prompt '{prompt.name}' has non-PromptArgument entry"
            )
            assert arg.name and arg.description, (
                f"Prompt '{prompt.name}' arg '{arg.name}' missing description"
            )


def test_required_arguments_match_brief() -> None:
    by_name = {p.name: p for p in PROMPTS}

    def required_names(prompt_name: str) -> set[str]:
        return {a.name for a in by_name[prompt_name].arguments if a.required}

    assert required_names("plan-retirement") == {
        "country",
        "monthly_expense_today",
        "current_age",
        "current_savings",
        "retirement_age",
    }
    assert required_names("annual-zakat-sweep") == set()
    assert required_names("salary-offer-analysis") == {"salary", "country", "age"}
    assert required_names("eosg-before-resignation") == {
        "country",
        "monthly_basic_salary",
        "years_of_service",
    }
    assert required_names("islamic-vs-conventional-loan") == {
        "asset_cost",
        "conventional_rate",
        "conventional_years",
        "islamic_markup_percent",
        "islamic_years",
    }


# ---------------------------------------------------------------------------
# Renderer outputs
# ---------------------------------------------------------------------------


def _render(prompt_name: str, args: dict) -> types.GetPromptResult:
    return PROMPT_RENDERERS[prompt_name](args)


def _message_text(result: types.GetPromptResult) -> str:
    assert result.messages, "GetPromptResult must contain at least 1 message"
    msg = result.messages[0]
    assert msg.role == "user", "First message role must be 'user'"
    assert isinstance(msg.content, types.TextContent), (
        "Message content must be TextContent"
    )
    return msg.content.text


def test_plan_retirement_templates_args() -> None:
    result = _render(
        "plan-retirement",
        {
            "country": "in",
            "monthly_expense_today": 80000,
            "current_age": 30,
            "current_savings": 500000,
            "retirement_age": 60,
            "expected_return": 0.10,
            "inflation": 0.06,
        },
    )
    text = _message_text(result)
    assert "in" in text
    assert "80000" in text
    assert "30" in text
    assert "500000" in text
    assert "60" in text
    assert "0.1" in text or "0.10" in text
    assert "0.06" in text
    assert "calculate_retirement" in text
    assert "corpus_needed" in text
    assert "monthly_contribution_for" in text


def test_plan_retirement_us_includes_us_step() -> None:
    result = _render(
        "plan-retirement",
        {
            "country": "us",
            "monthly_expense_today": 5000,
            "current_age": 28,
            "current_savings": 10000,
            "retirement_age": 65,
        },
    )
    text = _message_text(result)
    assert "calculate_us_retirement_account" in text
    assert "traditional_401k" in text
    assert "roth_ira" in text


def test_plan_retirement_non_us_omits_us_step() -> None:
    result = _render(
        "plan-retirement",
        {
            "country": "uk",
            "monthly_expense_today": 3000,
            "current_age": 40,
            "current_savings": 50000,
            "retirement_age": 60,
        },
    )
    text = _message_text(result)
    assert "calculate_us_retirement_account" not in text


def test_annual_zakat_sweep_templates_args() -> None:
    result = _render(
        "annual-zakat-sweep",
        {"currency": "INR", "nisab_basis": "gold", "as_of_date": "2026-05-15"},
    )
    text = _message_text(result)
    assert "INR" in text
    assert "gold" in text
    assert "2026-05-15" in text
    assert "calculate_zakat" in text


def test_annual_zakat_sweep_defaults() -> None:
    result = _render("annual-zakat-sweep", {})
    text = _message_text(result)
    assert "USD" in text
    assert "silver" in text


def test_salary_offer_analysis_us_includes_401k_and_roth() -> None:
    result = _render(
        "salary-offer-analysis",
        {
            "salary": 150000,
            "country": "us",
            "age": 35,
            "filing_status": "married_jointly",
            "current_role_salary": 130000,
        },
    )
    text = _message_text(result)
    assert "150000" in text
    assert "us" in text
    assert "35" in text
    assert "married_jointly" in text
    assert "130000" in text
    assert "calculate_income_tax" in text
    assert "calculate_us_retirement_account" in text
    assert "traditional_401k" in text
    assert "roth_ira" in text
    assert "DELTA" in text or "delta" in text.lower()


def test_salary_offer_analysis_in_skips_us_extras() -> None:
    result = _render(
        "salary-offer-analysis",
        {"salary": 1500000, "country": "in", "age": 30},
    )
    text = _message_text(result)
    assert "1500000" in text
    assert "calculate_us_retirement_account" not in text


def test_eosg_sa_templates_both_modes() -> None:
    result = _render(
        "eosg-before-resignation",
        {"country": "sa", "monthly_basic_salary": 8000, "years_of_service": 6},
    )
    text = _message_text(result)
    assert "sa" in text
    assert "8000" in text
    assert "6" in text
    assert "calculate_eosg" in text
    assert "termination" in text
    assert "resignation" in text


def test_eosg_ae_templates_both_modes() -> None:
    result = _render(
        "eosg-before-resignation",
        {"country": "ae", "monthly_basic_salary": 12000, "years_of_service": 7},
    )
    text = _message_text(result)
    assert "ae" in text
    assert "12000" in text
    assert "termination" in text
    assert "resignation" in text


def test_islamic_vs_conventional_templates_args() -> None:
    result = _render(
        "islamic-vs-conventional-loan",
        {
            "asset_cost": 3000000,
            "conventional_rate": 0.085,
            "conventional_years": 20,
            "islamic_markup_percent": 60,
            "islamic_years": 15,
            "down_payment": 600000,
        },
    )
    text = _message_text(result)
    assert "3000000" in text
    assert "0.085" in text
    assert "20" in text
    assert "60" in text
    assert "15" in text
    assert "600000" in text
    assert "calculate_loan_payment" in text
    assert "calculate_islamic_financing" in text
    assert "murabaha" in text


def test_all_renderers_return_valid_result() -> None:
    """Every renderer must produce a valid GetPromptResult with ≥1 message."""
    minimal_args = {
        "plan-retirement": {
            "country": "us",
            "monthly_expense_today": 1000,
            "current_age": 25,
            "current_savings": 0,
            "retirement_age": 65,
        },
        "annual-zakat-sweep": {},
        "salary-offer-analysis": {"salary": 50000, "country": "uk", "age": 30},
        "eosg-before-resignation": {
            "country": "ae",
            "monthly_basic_salary": 5000,
            "years_of_service": 3,
        },
        "islamic-vs-conventional-loan": {
            "asset_cost": 100000,
            "conventional_rate": 0.07,
            "conventional_years": 10,
            "islamic_markup_percent": 25,
            "islamic_years": 8,
        },
    }
    for name in EXPECTED_PROMPT_NAMES:
        result = _render(name, minimal_args[name])
        assert isinstance(result, types.GetPromptResult), (
            f"Renderer '{name}' did not return a GetPromptResult"
        )
        assert len(result.messages) >= 1, (
            f"Renderer '{name}' produced no messages"
        )
        text = _message_text(result)
        assert len(text) > 100, (
            f"Renderer '{name}' produced trivially short text ({len(text)} chars)"
        )


def test_unknown_prompt_raises_via_renderers_dict() -> None:
    assert "nonexistent-prompt" not in PROMPT_RENDERERS
