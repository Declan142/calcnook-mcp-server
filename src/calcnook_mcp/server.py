"""calcnook-mcp: MCP server exposing 20 calcnook financial tools over stdio."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .tools import core as core_tools
from .tools import islamic as islamic_tools
from .tools import countries as country_tools
from .tools import composite as composite_tools
from .prompts import PROMPTS, PROMPT_RENDERERS
from .resources import RESOURCES, RESOURCE_TEMPLATES, read_resource as read_resource_impl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: list[types.Tool] = [
    # ------ Universal / Core ------
    types.Tool(
        name="calculate_compound_interest",
        description=(
            "Compute the future value of a single lump-sum investment at compound interest. "
            "Universal — no country specifics. "
            "Example queries: 'What will ₹1L grow to in 10 years at 7%?', "
            "'future value of $5000 invested at 8% annually for 20 years compounded monthly'. "
            "Input notes: annual_rate is decimal — 0.07 = 7%, NOT 7.0. "
            "Limitations: single lump-sum only — for periodic contributions use calculate_sip_dca. "
            "See also: calculate_sip_dca for monthly contributions vs lump-sum."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Initial deposit amount (any currency).",
                },
                "annual_rate": {
                    "type": "number",
                    "description": "Decimal annual interest rate, e.g. 0.07 for 7%.",
                },
                "years": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Time horizon in years.",
                },
                "compounding_per_year": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 12,
                    "description": "Compounding frequency: 12=monthly (default), 4=quarterly, 1=annual.",
                },
            },
            "required": ["principal", "annual_rate", "years"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "Echoed initial deposit."},
                "future_value": {"type": "number", "description": "Final amount after compounding."},
                "interest_earned": {"type": "number", "description": "future_value - principal."},
                "annual_rate": {"type": "number", "description": "Echoed decimal annual rate."},
                "years": {"type": "number", "description": "Echoed time horizon."},
                "compounding_per_year": {"type": "integer", "description": "Echoed compounding frequency."},
            },
            "required": ["principal", "future_value", "interest_earned", "annual_rate", "years", "compounding_per_year"],
        },
    ),
    types.Tool(
        name="calculate_sip_dca",
        description=(
            "Compute the future value of periodic contributions (SIP in India, DCA globally). "
            "Supports annual step-up of monthly contributions. "
            "Example queries: 'SIP ₹5000/month for 15 years at 12%', "
            "'how much SIP to reach 1 crore in 10 years', "
            "'DCA $500/month into index fund for 30 years', "
            "'step-up SIP with 10% annual increase'. "
            "Input notes: annual_return is decimal (0.12 = 12%) but step_up_percent is whole percent (10.0 = 10%). "
            "Limitations: monthly contributions only — for lump-sum use calculate_compound_interest. "
            "See also: calculate_retirement (mode='monthly_contribution_for') to back-solve SIP for a target corpus."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "monthly_amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Fixed monthly contribution.",
                },
                "annual_return": {
                    "type": "number",
                    "description": "Decimal expected annual return, e.g. 0.12 for 12%.",
                },
                "years": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Investment horizon in years.",
                },
                "step_up_percent": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Annual % increase in monthly contribution. E.g. 10.0 = 10% step-up each year.",
                },
            },
            "required": ["monthly_amount", "annual_return", "years"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "monthly_amount": {"type": "number", "description": "Echoed initial monthly contribution."},
                "annual_return": {"type": "number", "description": "Echoed decimal annual return."},
                "years": {"type": "number", "description": "Echoed investment horizon."},
                "step_up_percent": {"type": "number", "description": "Echoed annual step-up percent."},
                "total_invested": {"type": "number", "description": "Sum of all contributions made."},
                "future_value": {"type": "number", "description": "Final corpus including returns."},
                "wealth_gained": {"type": "number", "description": "future_value - total_invested."},
            },
            "required": ["monthly_amount", "annual_return", "years", "step_up_percent",
                         "total_invested", "future_value", "wealth_gained"],
        },
    ),
    types.Tool(
        name="calculate_loan_payment",
        description=(
            "Calculate monthly EMI / mortgage payment for a fixed-rate loan. "
            "Returns total interest, total payment, and optional full amortization schedule. "
            "Works for home loans, car loans, personal loans, mortgage. "
            "Example queries: 'EMI for ₹30L home loan at 8.5% for 20 years', "
            "'$300k mortgage at 6.5% for 30 years', "
            "'what if I pay $200 extra per month on my car loan'. "
            "Input notes: annual_rate is decimal — 0.085 = 8.5%, NOT 8.5. "
            "Limitations: fixed-rate only — variable / floating-rate loans not supported. "
            "See also: calculate_retirement for goal-based amortisation of a target corpus."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Loan principal amount.",
                },
                "annual_rate": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Decimal annual interest rate, e.g. 0.085 for 8.5%.",
                },
                "years": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Loan tenure in whole years.",
                },
                "extra_monthly_payment": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Additional monthly payment above EMI (reduces tenure).",
                },
                "include_schedule": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, include the full month-by-month amortization table.",
                },
            },
            "required": ["principal", "annual_rate", "years"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "Echoed loan principal."},
                "annual_rate": {"type": "number", "description": "Echoed decimal annual rate."},
                "years": {"type": "integer", "description": "Echoed loan tenure in years."},
                "monthly_payment": {"type": "number", "description": "Scheduled monthly EMI (excludes extra_monthly_payment)."},
                "total_payment": {"type": "number", "description": "Sum of all payments over the loan life."},
                "total_interest": {"type": "number", "description": "total_payment - principal."},
                "amortization": {
                    "type": "array",
                    "description": "Month-by-month schedule (only if include_schedule=true).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "month": {"type": "integer"},
                            "principal_paid": {"type": "number"},
                            "interest_paid": {"type": "number"},
                            "balance": {"type": "number"},
                        },
                        "required": ["month", "principal_paid", "interest_paid", "balance"],
                    },
                },
            },
            "required": ["principal", "annual_rate", "years", "monthly_payment", "total_payment", "total_interest"],
        },
    ),
    types.Tool(
        name="calculate_retirement",
        description=(
            "Retirement planning in three modes: "
            "(1) corpus_needed — how much lump-sum do I need at retirement? "
            "(2) monthly_contribution_for — how much SIP to hit a target corpus? "
            "(3) safe_withdrawal — how much can I safely withdraw (4% rule)? "
            "Example queries: 'how much corpus to retire with ₹50k/month for 30 years', "
            "'SIP needed to build 2 crore corpus in 20 years', "
            "'safe monthly withdrawal from $1M at 4% rule'. "
            "Input notes: all rates (return, inflation, withdrawal_rate) are decimal — 0.07 = 7%, NOT 7. "
            "Limitations: assumes constant returns and inflation; no Monte Carlo or sequence-of-returns modelling. "
            "See also: calculate_us_retirement_account for tax-advantaged 401k / Roth IRA contribution sizing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["corpus_needed", "monthly_contribution_for", "safe_withdrawal"],
                    "description": "Which calculation to perform.",
                },
                # corpus_needed params
                "annual_expense": {
                    "type": "number",
                    "description": "[corpus_needed] Annual expense in today's money. Required for corpus_needed.",
                },
                "years_in_retirement": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "[corpus_needed] Number of years in retirement.",
                },
                "post_retirement_return": {
                    "type": "number",
                    "description": "[corpus_needed] Decimal nominal annual return during retirement.",
                },
                "inflation": {
                    "type": "number",
                    "minimum": 0,
                    "description": "[corpus_needed] Decimal annual inflation rate.",
                },
                # monthly_contribution_for params
                "target_corpus": {
                    "type": "number",
                    "description": "[monthly_contribution_for] Target retirement corpus. Required.",
                },
                "years_to_retirement": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "[monthly_contribution_for] Years until retirement. Required.",
                },
                "annual_return": {
                    "type": "number",
                    "description": "[monthly_contribution_for] Decimal expected annual return.",
                },
                "current_savings": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "[monthly_contribution_for / corpus_needed] Existing savings that will compound.",
                },
                # safe_withdrawal params
                "corpus": {
                    "type": "number",
                    "description": "[safe_withdrawal] Retirement corpus (lump-sum). Required.",
                },
                "withdrawal_rate": {
                    "type": "number",
                    "default": 0.04,
                    "description": "[safe_withdrawal] Decimal annual withdrawal rate (default 0.04 = 4% rule).",
                },
            },
            "required": ["mode"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by mode. Common: echoes of relevant inputs.",
            "properties": {
                "annual_expense": {"type": "number", "description": "[corpus_needed] Echoed annual expense."},
                "years_in_retirement": {"type": "integer", "description": "[corpus_needed] Echoed years in retirement."},
                "post_retirement_return": {"type": "number", "description": "[corpus_needed] Echoed post-retirement return."},
                "inflation": {"type": "number", "description": "[corpus_needed] Echoed inflation rate."},
                "corpus_needed": {"type": "number", "description": "[corpus_needed] Required retirement corpus."},
                "target_corpus": {"type": "number", "description": "[monthly_contribution_for] Echoed target corpus."},
                "years_to_retirement": {"type": "integer", "description": "[monthly_contribution_for] Echoed years until retirement."},
                "annual_return": {"type": "number", "description": "[monthly_contribution_for] Echoed expected annual return."},
                "current_savings": {"type": "number", "description": "[monthly_contribution_for] Echoed existing savings."},
                "monthly_contribution": {"type": "number", "description": "[monthly_contribution_for] Required monthly SIP."},
                "corpus": {"type": "number", "description": "[safe_withdrawal] Echoed retirement corpus."},
                "withdrawal_rate": {"type": "number", "description": "[safe_withdrawal] Echoed withdrawal rate."},
                "annual_withdrawal": {"type": "number", "description": "[safe_withdrawal] Annual withdrawal amount."},
                "monthly_withdrawal": {"type": "number", "description": "[safe_withdrawal] Monthly withdrawal amount."},
            },
        },
    ),
    types.Tool(
        name="calculate_bmi_bmr_tdee",
        description=(
            "Health metrics in three modes: "
            "(1) bmi — Body Mass Index and WHO category; "
            "(2) bmr — Basal Metabolic Rate (Mifflin-St Jeor); "
            "(3) tdee — Total Daily Energy Expenditure from BMR and activity level. "
            "Example queries: 'BMI for 70kg 175cm', "
            "'BMR for 30-year-old male 80kg 180cm', "
            "'TDEE for moderately active person with BMR 1700'. "
            "Input notes: weight in kilograms, height in centimetres — never lbs/inches. Convert before calling. "
            "Limitations: Mifflin-St Jeor only — Harris-Benedict, Katch-McArdle, body-fat-aware formulas not supported. "
            "See also: chain bmr -> tdee by feeding the bmr_kcal output into tdee mode."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["bmi", "bmr", "tdee"],
                    "description": "Which health metric to compute.",
                },
                "weight_kg": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "[bmi, bmr] Body weight in kilograms.",
                },
                "height_cm": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "[bmi, bmr] Height in centimetres.",
                },
                "age_years": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "[bmr] Age in whole years.",
                },
                "sex": {
                    "type": "string",
                    "enum": ["male", "female"],
                    "description": "[bmr] Biological sex for the Mifflin-St Jeor equation.",
                },
                "bmr_kcal": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "[tdee] Basal Metabolic Rate in kcal (output of bmr mode).",
                },
                "activity_level": {
                    "type": "string",
                    "enum": ["sedentary", "light", "moderate", "active", "very_active"],
                    "description": "[tdee] Activity level: sedentary, light, moderate, active, very_active.",
                },
            },
            "required": ["mode"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by mode.",
            "properties": {
                "weight_kg": {"type": "number", "description": "[bmi/bmr] Echoed weight."},
                "height_cm": {"type": "number", "description": "[bmi/bmr] Echoed height."},
                "bmi": {"type": "number", "description": "[bmi] Body Mass Index value."},
                "category": {"type": "string", "description": "[bmi] WHO category: underweight, normal, overweight, obese."},
                "age_years": {"type": "integer", "description": "[bmr] Echoed age."},
                "sex": {"type": "string", "description": "[bmr] Echoed biological sex."},
                "bmr_kcal": {"type": "number", "description": "[bmr/tdee] Basal metabolic rate in kcal/day."},
                "activity_level": {"type": "string", "description": "[tdee] Echoed activity level."},
                "activity_multiplier": {"type": "number", "description": "[tdee] Activity multiplier applied to BMR."},
                "tdee_kcal": {"type": "number", "description": "[tdee] Total daily energy expenditure in kcal/day."},
            },
        },
    ),
    types.Tool(
        name="convert_currency",
        description=(
            "Convert an amount between any two currencies using a caller-supplied USD-based rate dict. "
            "The caller must provide current exchange rates (USD=1.0 base). "
            "Example: convert 1000 USD to INR with rates={'USD':1.0, 'INR':83.5}. "
            "Input notes: rates are units-per-USD — INR 83.5 means 1 USD = 83.5 INR. USD must be present (typically 1.0). "
            "Limitations: no live rate fetching — caller must supply rates dict each call. "
            "See also: format_currency_amount to render the converted_amount with currency symbol / lakh-crore notation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Amount to convert.",
                },
                "from_currency": {
                    "type": "string",
                    "description": "ISO-4217 source currency code, e.g. 'USD'.",
                },
                "to_currency": {
                    "type": "string",
                    "description": "ISO-4217 target currency code, e.g. 'INR'.",
                },
                "rates": {
                    "type": "object",
                    "description": "Dict mapping currency codes to units-per-USD, e.g. {'USD':1.0,'INR':83.5,'EUR':0.93}.",
                    "additionalProperties": {"type": "number"},
                },
            },
            "required": ["amount", "from_currency", "to_currency", "rates"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Echoed source amount."},
                "from_currency": {"type": "string", "description": "Echoed source currency code."},
                "to_currency": {"type": "string", "description": "Echoed target currency code."},
                "rate_used": {"type": "number", "description": "Effective conversion factor applied."},
                "converted_amount": {"type": "number", "description": "Converted amount in to_currency."},
            },
            "required": ["amount", "from_currency", "to_currency", "rate_used", "converted_amount"],
        },
    ),
    types.Tool(
        name="format_currency_amount",
        description=(
            "Format a numeric amount as a human-readable currency string. "
            "For INR, optionally use Indian lakh/crore notation (₹15.00 L, ₹2.50 Cr). "
            "Example queries: 'format 83500 in INR', 'display 25000000 as crores'. "
            "Input notes: lakh_crore_format is honoured ONLY when currency='INR' — silently ignored for other codes. "
            "Limitations: no localisation of decimal/grouping separators per locale beyond INR. "
            "See also: convert_currency to first convert between currencies, then format the result."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Numeric amount to format.",
                },
                "currency": {
                    "type": "string",
                    "description": "ISO-4217 currency code (e.g. USD, INR, GBP, AED).",
                },
                "lakh_crore_format": {
                    "type": "boolean",
                    "default": False,
                    "description": "For INR only: use lakh/crore notation (₹15.00 L / ₹2.50 Cr).",
                },
            },
            "required": ["amount", "currency"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "formatted": {"type": "string", "description": "Display string with currency symbol."},
                "amount": {"type": "number", "description": "Echoed numeric amount."},
                "currency": {"type": "string", "description": "Echoed currency code (uppercased)."},
            },
            "required": ["formatted", "amount", "currency"],
        },
    ),
    # ------ Composite agentic tools ------
    types.Tool(
        name="analyze_salary_offer",
        description=(
            "Composite analysis of a single job offer — combines income tax, take-home, "
            "marginal-bracket estimate, country-aware retirement contribution limits "
            "(401k for US, EPF cap for India), and monthly savings room into one call. "
            "Supported countries: us, uk, ca, au, in. Returns pre-formatted display "
            "strings (lakh/crore for India) plus 2-4 country-aware recommended actions. "
            "Replaces 4-5 separate tool calls. "
            "Example queries: 'should I take a ₹15L job in India at age 30 with ₹40k expenses', "
            "'analyse $80,000 single-filer offer in the US for a 28-year-old', "
            "'evaluate £55,000 UK salary for a 35-year-old'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "salary": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Gross annual salary in local currency.",
                },
                "country": {
                    "type": "string",
                    "enum": ["us", "uk", "ca", "au", "in"],
                    "description": "Country code: us, uk, ca, au, in.",
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Age in whole years (drives 401k catch-up logic for US).",
                },
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "married_separately", "head_of_household"],
                    "default": "single",
                    "description": "[us] Federal filing status.",
                },
                "regime": {
                    "type": "string",
                    "enum": ["new", "old"],
                    "default": "new",
                    "description": "[in] Indian tax regime.",
                },
                "monthly_expenses": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Optional monthly expenses — enables savings_room_monthly computation.",
                },
            },
            "required": ["salary", "country", "age"],
        },
    ),
    types.Tool(
        name="financial_health_snapshot",
        description=(
            "Composite 0-100 financial-health score derived from five inputs: monthly income, "
            "monthly expenses, total debts, total savings, age. Computes savings rate, "
            "debt-to-income, emergency-fund months, and retirement-track verdict against a "
            "Fidelity-style age multiplier (1× at 30, 3× at 40, 6× at 50, 8× at 60, 10× at 67). "
            "Returns score, verdict (Excellent / Healthy / Needs work / Critical), and 3 "
            "prioritized recommended actions. "
            "Example queries: 'snapshot my finances — income ₹2L, expenses 80k, savings 30L, age 35', "
            "'am I behind on retirement at 50 with $200k saved on $200k income', "
            "'health check: 100k income, 95k expenses, 5L debt, 1L savings, age 35'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "monthly_income": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Monthly take-home or gross income.",
                },
                "monthly_expenses": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monthly recurring expenses.",
                },
                "total_debts": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Outstanding debt principal across all loans.",
                },
                "total_savings": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Liquid + retirement savings balance.",
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Age in whole years (drives retirement benchmark).",
                },
                "monthly_emi": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Total monthly EMI / loan repayments — drives DTI ratio.",
                },
                "country": {
                    "type": "string",
                    "enum": ["us", "uk", "ca", "au", "in"],
                    "default": "in",
                    "description": "Country code (used for currency display only).",
                },
            },
            "required": ["monthly_income", "monthly_expenses", "total_debts", "total_savings", "age"],
        },
    ),
    types.Tool(
        name="compare_loan_options",
        description=(
            "Compare 2+ loan options side-by-side: monthly EMI, total interest, total "
            "payment, and effective tenure (with optional extra monthly payments). Returns "
            "winner_by_total_payment, winner_by_emi, savings_vs_worst, and a markdown table "
            "ready for direct LLM rendering. Replaces N separate calculate_loan_payment calls. "
            "Example queries: 'compare HDFC 8.5% 20y vs SBI 8.4% 15y for a ₹50L home loan', "
            "'should I add ₹10k extra monthly to my mortgage', "
            "'three lenders side-by-side for a ₹30L car loan'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "options": {
                    "type": "array",
                    "minItems": 2,
                    "description": "List of loan options to compare. Each must include principal, annual_rate, years; label and extra_monthly are optional.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "Display label (e.g. 'HDFC 8.5% 20y'). Auto-numbered if omitted.",
                            },
                            "principal": {
                                "type": "number",
                                "exclusiveMinimum": 0,
                                "description": "Loan principal.",
                            },
                            "annual_rate": {
                                "type": "number",
                                "minimum": 0,
                                "description": "Decimal annual interest rate, e.g. 0.085 for 8.5%.",
                            },
                            "years": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Loan tenure in whole years.",
                            },
                            "extra_monthly": {
                                "type": "number",
                                "minimum": 0,
                                "default": 0.0,
                                "description": "Additional monthly payment above EMI — shortens effective tenure.",
                            },
                        },
                        "required": ["principal", "annual_rate", "years"],
                    },
                },
                "include_schedules": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, attaches per-option amortization schedule.",
                },
            },
            "required": ["options"],
        },
    ),
    # ------ Islamic Finance ------
    types.Tool(
        name="calculate_zakat",
        description=(
            "Compute Zakat al-Mal (annual 2.5% Islamic wealth obligation). "
            "Sums all zakatable assets, deducts debts, checks nisab threshold (gold or silver basis), "
            "and returns the zakat due. Cross-cutting — any Muslim, any country. "
            "Example queries: 'how much Zakat do I owe on $25000 savings and $5000 stocks', "
            "'zakat calculation with gold and silver holdings'. "
            "Input notes: gold/silver prices must be in the SAME currency as the cash/stocks fields — caller-supplied, not auto-fetched. "
            "Limitations: standard Hanafi nisab rules; does not handle agricultural zakat (ushr) or livestock (zakat al-an'am). "
            "See also: calculate_saudi_zakat_citizen for ZATCA corporate zakat estimation in Saudi Arabia."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cash": {"type": "number", "minimum": 0, "default": 0.0, "description": "Cash + bank balances."},
                "gold_grams": {"type": "number", "minimum": 0, "default": 0.0, "description": "Gold owned in grams."},
                "silver_grams": {"type": "number", "minimum": 0, "default": 0.0, "description": "Silver owned in grams."},
                "stocks_value": {"type": "number", "minimum": 0, "default": 0.0, "description": "Market value of zakatable equity holdings."},
                "business_assets": {"type": "number", "minimum": 0, "default": 0.0, "description": "Business inventory + receivables."},
                "other_zakatable_assets": {"type": "number", "minimum": 0, "default": 0.0, "description": "Other qualifying assets."},
                "debts": {"type": "number", "minimum": 0, "default": 0.0, "description": "Outstanding debts owed (deducted from wealth)."},
                "gold_price_per_gram": {"type": "number", "minimum": 0, "default": 75.0, "description": "Current gold price per gram in the chosen currency."},
                "silver_price_per_gram": {"type": "number", "minimum": 0, "default": 0.90, "description": "Current silver price per gram."},
                "nisab_basis": {"type": "string", "enum": ["gold", "silver"], "default": "silver", "description": "'silver' (lower, more inclusive) or 'gold'."},
                "currency": {"type": "string", "default": "USD", "description": "ISO-4217 currency code for display."},
            },
            "required": [],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "total_zakatable_assets": {"type": "number", "description": "Sum of all assets minus debts."},
                "nisab_threshold_used": {"type": "number", "description": "Nisab threshold value in the chosen currency."},
                "nisab_basis": {"type": "string", "description": "'gold' or 'silver' basis used."},
                "is_above_nisab": {"type": "boolean", "description": "True if assets exceed nisab — zakat is due."},
                "zakat_due": {"type": "number", "description": "Zakat owed (2.5% of total when above nisab; else 0)."},
                "currency": {"type": "string", "description": "Echoed currency code."},
            },
            "required": ["total_zakatable_assets", "nisab_threshold_used", "nisab_basis",
                         "is_above_nisab", "zakat_due", "currency"],
        },
    ),
    types.Tool(
        name="calculate_islamic_financing",
        description=(
            "Calculate Islamic financing arrangements — Sharia-compliant alternatives to conventional loans. "
            "Three instruments: "
            "(1) murabaha — cost-plus sale (Sharia mortgage/asset purchase); "
            "(2) ijarah — lease-to-own (Sharia auto-loan/equipment); "
            "(3) mudarabah — profit-sharing investment (Sharia FD alternative). "
            "Example queries: 'murabaha financing for $100k house at 30% markup over 5 years', "
            "'ijarah lease for car worth $30k at $600/month for 5 years', "
            "'mudarabah: investor puts $100k, profit $20k split 70/30'. "
            "Input notes: markup_percent is whole percent (30.0 = 30%) but investor_share_ratio is decimal (0.70 = 70%) — easy to swap. "
            "Limitations: no diminishing-musharaka or sukuk modelling; murabaha assumes fixed markup, not variable. "
            "See also: calculate_loan_payment for the conventional interest-bearing equivalent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "instrument": {
                    "type": "string",
                    "enum": ["murabaha", "ijarah", "mudarabah"],
                    "description": "Which Islamic financing instrument to compute.",
                },
                # murabaha
                "asset_cost": {"type": "number", "exclusiveMinimum": 0, "description": "[murabaha/ijarah] Asset purchase price."},
                "markup_percent": {"type": "number", "minimum": 0, "description": "[murabaha] Total markup as % of asset cost, e.g. 30.0 for 30%."},
                "tenure_years": {"type": "integer", "minimum": 1, "description": "[murabaha] Repayment tenure in years."},
                "down_payment": {"type": "number", "minimum": 0, "default": 0.0, "description": "[murabaha] Upfront payment by client."},
                # ijarah
                "monthly_rent": {"type": "number", "minimum": 0, "description": "[ijarah] Agreed monthly lease payment."},
                "lease_years": {"type": "integer", "minimum": 1, "description": "[ijarah] Lease duration in years."},
                "transfer_fee": {"type": "number", "minimum": 0, "default": 1.0, "description": "[ijarah] Token ownership-transfer fee at end of lease."},
                # mudarabah
                "capital": {"type": "number", "exclusiveMinimum": 0, "description": "[mudarabah] Capital provided by investor."},
                "actual_profit_amount": {"type": "number", "description": "[mudarabah] Realised profit (positive) or loss (negative)."},
                "investor_share_ratio": {"type": "number", "exclusiveMinimum": 0, "maximum": 1, "description": "[mudarabah] Investor profit share as decimal, e.g. 0.70 = 70%."},
                "years": {"type": "number", "exclusiveMinimum": 0, "description": "[mudarabah] Optional: years to compute annualised return."},
            },
            "required": ["instrument"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by instrument.",
            "properties": {
                "asset_cost": {"type": "number", "description": "[murabaha/ijarah] Echoed asset price."},
                "markup_percent": {"type": "number", "description": "[murabaha] Echoed markup percent."},
                "tenure_years": {"type": "integer", "description": "[murabaha] Echoed tenure in years."},
                "down_payment": {"type": "number", "description": "[murabaha] Echoed down payment."},
                "total_sale_price": {"type": "number", "description": "[murabaha] asset_cost * (1 + markup)."},
                "principal_financed": {"type": "number", "description": "[murabaha] Amount financed after down payment."},
                "monthly_installment": {"type": "number", "description": "[murabaha] Equal monthly installment."},
                "total_paid": {"type": "number", "description": "[murabaha] Total paid over the tenure."},
                "total_markup": {"type": "number", "description": "[murabaha] Bank's profit (markup amount)."},
                "effective_apr_equivalent": {"type": "number", "description": "[murabaha] Equivalent conventional APR (for comparison only)."},
                "monthly_rent": {"type": "number", "description": "[ijarah] Echoed monthly lease."},
                "lease_years": {"type": "integer", "description": "[ijarah] Echoed lease duration."},
                "transfer_fee": {"type": "number", "description": "[ijarah] Echoed token transfer fee."},
                "total_rent_paid": {"type": "number", "description": "[ijarah] Total lease paid."},
                "total_cost_of_ownership": {"type": "number", "description": "[ijarah] total_rent_paid + transfer_fee."},
                "effective_cost_premium": {"type": "number", "description": "[ijarah] total_cost - asset_cost."},
                "effective_premium_percent": {"type": "number", "description": "[ijarah] Premium as percent of asset_cost."},
                "capital": {"type": "number", "description": "[mudarabah] Echoed investor capital."},
                "actual_profit_amount": {"type": "number", "description": "[mudarabah] Echoed realised profit (or loss)."},
                "investor_share_ratio": {"type": "number", "description": "[mudarabah] Echoed investor share."},
                "investor_profit": {"type": "number", "description": "[mudarabah] Investor's share of profit."},
                "manager_profit": {"type": "number", "description": "[mudarabah] Manager's (mudarib) share of profit."},
                "investor_total": {"type": "number", "description": "[mudarabah] Capital + investor_profit."},
                "years": {"type": ["number", "null"], "description": "[mudarabah] Echoed years (or null if omitted)."},
                "annualised_return": {"type": ["number", "null"], "description": "[mudarabah] Annualised return (or null when years omitted)."},
            },
        },
    ),
    types.Tool(
        name="calculate_hajj_savings",
        description=(
            "Calculate the monthly savings needed to fund a Hajj pilgrimage by a target year. "
            "Accounts for existing savings and halal investment returns (sukuk/equity). "
            "Example queries: 'how much to save monthly for Hajj costing $8000 in 5 years', "
            "'hajj savings plan with ₹50000 already saved, 6% return, 3 years'. "
            "Input notes: expected_annual_return is decimal — 0.06 = 6%, NOT 6.0. "
            "Limitations: hajj_cost_target is treated as fixed in today's money; does not auto-inflate Saudi pilgrimage costs. "
            "See also: calculate_sip_dca for general goal-based monthly investment planning."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "hajj_cost_target": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Total estimated cost of Hajj in today's currency.",
                },
                "years_to_hajj": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of years until Hajj trip.",
                },
                "current_savings": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Existing savings already set aside.",
                },
                "expected_annual_return": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Expected annual halal investment return as decimal (e.g. 0.06 for 6%).",
                },
            },
            "required": ["hajj_cost_target", "years_to_hajj"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "hajj_cost_target": {"type": "number", "description": "Echoed Hajj cost target."},
                "years_to_hajj": {"type": "integer", "description": "Echoed years until Hajj."},
                "current_savings": {"type": "number", "description": "Echoed existing savings."},
                "expected_annual_return": {"type": "number", "description": "Echoed expected return."},
                "monthly_contribution_needed": {"type": "number", "description": "Required monthly savings amount."},
                "total_contribution": {"type": "number", "description": "Sum of all monthly contributions over the period."},
                "expected_growth": {"type": "number", "description": "Investment returns earned on contributions + current savings."},
                "target_met_at_zero_contribution": {"type": "boolean", "description": "True if current_savings alone (compounded) meets the target."},
            },
            "required": ["hajj_cost_target", "years_to_hajj", "current_savings", "expected_annual_return",
                         "monthly_contribution_needed", "total_contribution", "expected_growth",
                         "target_met_at_zero_contribution"],
        },
    ),
    types.Tool(
        name="screen_halal_stock",
        description=(
            "Screen a stock for Sharia compliance using AAOIFI standard financial ratios. "
            "Checks: business sector (haram/halal), debt ratio, cash ratio, receivables ratio, haram revenue ratio. "
            "Returns compliance verdict, failed checks, and purification ratio. "
            "Example queries: 'is this tech stock halal?', 'AAOIFI screen for Apple with these financials'. "
            "Input notes: all monetary fields share the same currency (caller's choice); ratios are computed against market_cap and total_revenue. "
            "Limitations: AAOIFI thresholds only — does not apply DJIM, S&P Shariah, or MSCI Islamic alternative thresholds. "
            "See also: calculate_zakat for the purification ratio applied to actual holdings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Business sector/activity description (e.g. 'technology', 'banking', 'alcohol').",
                },
                "market_cap": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Total market capitalisation.",
                },
                "debt_interest_bearing": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total interest-bearing debt on the balance sheet.",
                },
                "cash_and_interest_securities": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Cash + conventional bonds/interest-bearing securities held.",
                },
                "receivables": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total accounts receivable.",
                },
                "total_revenue": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Total annual revenue.",
                },
                "haram_revenue": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Revenue from non-compliant activities.",
                },
            },
            "required": ["sector", "market_cap", "debt_interest_bearing",
                         "cash_and_interest_securities", "receivables", "total_revenue"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "is_compliant": {"type": "boolean", "description": "True if all AAOIFI checks pass."},
                "failed_checks": {
                    "type": "array",
                    "description": "List of human-readable reasons (empty if compliant).",
                    "items": {"type": "string"},
                },
                "ratios": {
                    "type": "object",
                    "description": "Computed AAOIFI ratios.",
                    "properties": {
                        "debt_ratio": {"type": "number", "description": "debt / market_cap."},
                        "cash_ratio": {"type": "number", "description": "cash+interest_securities / market_cap."},
                        "receivables_ratio": {"type": "number", "description": "receivables / market_cap."},
                        "haram_revenue_ratio": {"type": "number", "description": "haram_revenue / total_revenue."},
                    },
                },
                "purification_ratio": {"type": "number", "description": "Fraction of dividends to purify (give to charity)."},
            },
            "required": ["is_compliant", "failed_checks", "ratios", "purification_ratio"],
        },
    ),
    # ------ Country-specific ------
    types.Tool(
        name="calculate_income_tax",
        description=(
            "Calculate income tax for US, UK, Canada, Australia, or India (2026 / FY 2025-26). "
            "country='us': federal tax with brackets by filing_status. "
            "country='uk': income tax + National Insurance (2025/26). "
            "country='ca': federal tax with Basic Personal Amount credit. "
            "country='au': income tax + Medicare Levy + optional HECS-HELP. "
            "country='in': India new/old regime with 87A rebate + cess. "
            "Example queries: 'US tax on $85000 income married filing jointly', "
            "'UK income tax on £50000 salary', 'India income tax ₹12L new regime'. "
            "Input notes: income is gross annual in local currency; do NOT pre-deduct standard deduction. "
            "Limitations: 2026 tax year only — historical years not yet supported. CA computes federal only (no provincial). "
            "See also: calculate_us_retirement_account for tax-advantaged 401k / Roth IRA contribution analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": ["us", "uk", "ca", "au", "in"],
                    "description": "Country code: us, uk, ca, au, in.",
                },
                "income": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Gross annual income in local currency.",
                },
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "married_separately", "head_of_household"],
                    "description": "[us] Filing status. Default: single.",
                },
                "has_hecs_debt": {
                    "type": "boolean",
                    "default": False,
                    "description": "[au] Whether HECS-HELP compulsory repayment applies.",
                },
                "regime": {
                    "type": "string",
                    "enum": ["new", "old"],
                    "default": "new",
                    "description": "[in] Tax regime: 'new' (default, lower rates) or 'old' (with deductions).",
                },
                "province": {
                    "type": "string",
                    "description": "[ca] Province/territory code (e.g. 'ON'). Accepted but provincial tax not yet computed.",
                },
                "year": {
                    "type": "integer",
                    "default": 2026,
                    "description": "Tax year. Only 2026 is supported across all countries.",
                },
            },
            "required": ["country", "income"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by country. Common: gross_income, year, taxable_income, tax_owed (us/ca/in) or income_tax+take_home (uk/au).",
            "properties": {
                "gross_income": {"type": "number", "description": "Echoed gross income."},
                "year": {"type": "integer", "description": "Echoed tax year."},
                "filing_status": {"type": "string", "description": "[us] Echoed filing status."},
                "taxable_income": {"type": "number", "description": "[us/ca/uk/in] Income after deductions/allowances."},
                "tax_owed": {"type": "number", "description": "[us/ca/in] Final tax liability."},
                "income_tax": {"type": "number", "description": "[uk/au] Income tax component."},
                "national_insurance": {"type": "number", "description": "[uk] NI Class 1 contribution."},
                "medicare_levy": {"type": "number", "description": "[au] Medicare Levy."},
                "hecs_repayment": {"type": "number", "description": "[au] HECS-HELP compulsory repayment (if has_hecs_debt)."},
                "total_tax": {"type": "number", "description": "[uk/au] Sum of all taxes/levies."},
                "take_home": {"type": "number", "description": "[uk/au] Net income after all taxes."},
                "personal_allowance_used": {"type": "number", "description": "[uk] Personal allowance applied."},
                "federal_tax_before_credits": {"type": "number", "description": "[ca] Federal tax before BPA credit."},
                "basic_personal_credit": {"type": "number", "description": "[ca] Basic Personal Amount credit."},
                "provincial_tax": {"type": "number", "description": "[ca] Provincial tax (currently 0 — not yet computed)."},
                "province": {"type": "string", "description": "[ca] Echoed province."},
                "regime": {"type": "string", "description": "[in] Echoed tax regime ('new' or 'old')."},
                "standard_deduction": {"type": "number", "description": "[in] Standard deduction applied."},
                "tax_before_rebate": {"type": "number", "description": "[in] Tax before 87A rebate."},
                "rebate_87a": {"type": "number", "description": "[in] Section 87A rebate."},
                "tax_after_rebate": {"type": "number", "description": "[in] Tax after 87A rebate."},
                "health_education_cess": {"type": "number", "description": "[in] 4% cess on tax_after_rebate."},
                "has_hecs_debt": {"type": "boolean", "description": "[au] Echoed HECS flag."},
                "effective_rate": {"type": "number", "description": "Effective tax rate on gross_income (decimal)."},
                "marginal_rate": {"type": "number", "description": "[us/ca/in] Marginal bracket rate."},
                "bracket_breakdown": {
                    "type": "array",
                    "description": "Per-bracket / per-band tax breakdown. Field names vary by country.",
                    "items": {"type": "object"},
                },
            },
            "required": ["gross_income", "year"],
        },
    ),
    types.Tool(
        name="calculate_us_retirement_account",
        description=(
            "Analyse US retirement account contributions for 2026. "
            "account_type='traditional_401k': employee deferral, employer match, §415 cap, tax savings. "
            "account_type='roth_ira': eligibility check and MAGI phase-out calculation. "
            "Example queries: 'how much do I save in taxes with 401k contribution', "
            "'am I eligible for Roth IRA at $155k income'. "
            "Input notes: employer_match_percent and employer_match_cap are decimals — 0.50 = 50%, 0.06 = 6% of salary. marginal_tax_rate also decimal. "
            "Limitations: 2026 IRS limits only; no SEP-IRA, SIMPLE-IRA, 403(b), 457(b), or HSA modelling. "
            "See also: calculate_income_tax (country='us') for the full federal tax computation that the 401k deduction reduces."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account_type": {
                    "type": "string",
                    "enum": ["traditional_401k", "roth_ira"],
                    "description": "Retirement account type.",
                },
                "contribution": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Desired annual contribution amount in USD.",
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Employee/contributor age (determines catch-up limits for 50+).",
                },
                # 401k only
                "salary": {
                    "type": "number",
                    "minimum": 0,
                    "description": "[traditional_401k] Annual gross salary in USD.",
                },
                "employer_match_percent": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.0,
                    "description": "[traditional_401k] Employer match fraction, e.g. 0.50 = 50-cent per dollar.",
                },
                "employer_match_cap": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.06,
                    "description": "[traditional_401k] Match applies up to this % of salary, e.g. 0.06 = 6%.",
                },
                "marginal_tax_rate": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.22,
                    "description": "[traditional_401k] Marginal federal rate for tax savings estimate.",
                },
                # roth_ira only
                "magi": {
                    "type": "number",
                    "minimum": 0,
                    "description": "[roth_ira] Modified Adjusted Gross Income for phase-out check.",
                },
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "married_separately", "head_of_household"],
                    "default": "single",
                    "description": "[roth_ira] Filing status for MAGI phase-out range.",
                },
            },
            "required": ["account_type", "contribution", "age"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by account_type.",
            "properties": {
                "age": {"type": "integer", "description": "Echoed contributor age."},
                "employee_contribution": {"type": "number", "description": "[traditional_401k] Employee deferral after capping at limit."},
                "employer_contribution": {"type": "number", "description": "[traditional_401k] Computed employer match."},
                "total_contribution": {"type": "number", "description": "[traditional_401k] Employee + employer contributions."},
                "employee_limit": {"type": "number", "description": "[traditional_401k] 2026 employee deferral cap (incl. catch-up if 50+)."},
                "total_limit": {"type": "number", "description": "[traditional_401k] §415 total annual additions cap."},
                "is_employee_maxed": {"type": "boolean", "description": "[traditional_401k] True if employee hit the deferral cap."},
                "is_total_maxed": {"type": "boolean", "description": "[traditional_401k] True if combined hit the §415 cap."},
                "tax_savings_now": {"type": "number", "description": "[traditional_401k] employee_contribution * marginal_tax_rate."},
                "marginal_rate_used": {"type": "number", "description": "[traditional_401k] Echoed marginal tax rate."},
                "requested_contribution": {"type": "number", "description": "[roth_ira] Echoed requested contribution."},
                "effective_contribution": {"type": "number", "description": "[roth_ira] Allowed amount after MAGI phase-out."},
                "contribution_limit": {"type": "number", "description": "[roth_ira] 2026 Roth IRA contribution cap (incl. catch-up if 50+)."},
                "phase_out_factor": {"type": "number", "description": "[roth_ira] Fraction allowed (1.0 = full, 0.0 = ineligible)."},
                "magi": {"type": "number", "description": "[roth_ira] Echoed MAGI."},
                "filing_status": {"type": "string", "description": "[roth_ira] Echoed filing status."},
                "phase_out_low": {"type": "number", "description": "[roth_ira] Lower MAGI threshold for phase-out."},
                "phase_out_high": {"type": "number", "description": "[roth_ira] Upper MAGI threshold (full phase-out)."},
            },
            "required": ["age"],
        },
    ),
    types.Tool(
        name="calculate_eosg",
        description=(
            "Calculate End of Service Gratuity (EOSG) for UAE or Saudi Arabia. "
            "UAE: Federal Decree-Law 33/2021 — 21 days/year for first 5 years, 30 days/year after. "
            "Saudi: Saudi Labour Law Articles 84-87 — ½ month/year first 5 years, 1 month/year after; "
            "resignation factor applies. "
            "Example queries: 'UAE gratuity for 7 years service at AED 8000 basic salary', "
            "'Saudi EOSG if I resign after 6 years on SAR 5000 salary'. "
            "Input notes: monthly_basic_salary EXCLUDES allowances (housing, transport, etc.); years_of_service accepts fractional years (5.5). "
            "Limitations: GCC private-sector only — government, free-zone, or public-sector EOSG rules not modelled. "
            "See also: calculate_vat for tax handling on the gratuity payout (typically VAT-exempt; verify with employer)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": ["ae", "sa"],
                    "description": "Country: 'ae' (UAE) or 'sa' (Saudi Arabia).",
                },
                "monthly_basic_salary": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monthly basic salary in local currency (AED for UAE, SAR for KSA). Excludes allowances.",
                },
                "years_of_service": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total years of service (fractional years accepted, e.g. 5.5).",
                },
                "contract_type": {
                    "type": "string",
                    "enum": ["limited", "unlimited"],
                    "default": "limited",
                    "description": "[ae] Contract type — both compute identically under 2021 Decree-Law.",
                },
                "end_reason": {
                    "type": "string",
                    "enum": ["termination", "resignation"],
                    "default": "termination",
                    "description": "[sa] Reason for leaving — affects entitlement factor for resignation.",
                },
            },
            "required": ["country", "monthly_basic_salary", "years_of_service"],
        },
        outputSchema={
            "type": "object",
            "description": "Output keys vary by country.",
            "properties": {
                "monthly_basic_salary": {"type": "number", "description": "Echoed monthly basic salary."},
                "years_of_service": {"type": "number", "description": "Echoed years of service."},
                "daily_basic_wage": {"type": "number", "description": "[ae] Daily wage (basic / 30)."},
                "gratuity_before_cap": {"type": "number", "description": "[ae] Computed gratuity before 2-year-salary cap."},
                "gratuity_aed": {"type": "number", "description": "[ae] Final gratuity payable in AED."},
                "is_capped": {"type": "boolean", "description": "[ae] True if 2-year-salary cap reduced the payout."},
                "formula_used": {"type": "string", "description": "[ae] Tag describing the formula applied."},
                "end_reason": {"type": "string", "description": "[sa] Echoed reason for leaving."},
                "accrued_gratuity_full": {"type": "number", "description": "[sa] Full accrued amount before resignation factor."},
                "entitlement_factor": {"type": "number", "description": "[sa] Resignation reduction factor (1.0 for termination)."},
                "gratuity_sar": {"type": "number", "description": "[sa] Final gratuity payable in SAR."},
                "formula_note": {"type": "string", "description": "[sa] Tag describing the formula applied."},
            },
            "required": ["monthly_basic_salary", "years_of_service"],
        },
    ),
    types.Tool(
        name="calculate_vat",
        description=(
            "Calculate VAT for UAE (5%) or Saudi Arabia (15%). "
            "Works for both ex-VAT and VAT-inclusive amounts. "
            "Example queries: 'UAE VAT on AED 1000 product', "
            "'what is the VAT-exclusive price of SAR 1150 including 15% VAT'. "
            "Input notes: set is_inclusive=true when the amount already contains VAT (reverse-extract); default false. "
            "Limitations: GCC standard rates only — does not model zero-rated, exempt, or out-of-scope supplies. "
            "See also: calculate_eosg for end-of-service gratuity which is typically VAT-exempt."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": ["ae", "sa"],
                    "description": "'ae' = UAE 5% VAT, 'sa' = Saudi Arabia 15% VAT.",
                },
                "amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monetary amount in local currency (AED for UAE, SAR for KSA).",
                },
                "is_inclusive": {
                    "type": "boolean",
                    "default": False,
                    "description": "True if amount already includes VAT (to extract it). False if amount is ex-VAT.",
                },
            },
            "required": ["country", "amount"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "vat_amount": {"type": "number", "description": "VAT component of the transaction."},
                "net_amount": {"type": "number", "description": "Amount excluding VAT."},
                "gross_amount": {"type": "number", "description": "Amount including VAT."},
                "rate": {"type": "number", "description": "Decimal VAT rate applied (0.05 or 0.15)."},
                "is_inclusive": {"type": "boolean", "description": "Echoed input flag."},
            },
            "required": ["vat_amount", "net_amount", "gross_amount", "rate", "is_inclusive"],
        },
    ),
    types.Tool(
        name="calculate_saudi_zakat_citizen",
        description=(
            "Estimate ZATCA-collected Zakat for Saudi / GCC nationals (simplified 2.5% estimator). "
            "Caller supplies the pre-computed zakat base. Returns zakat due with a disclaimer that "
            "actual ZATCA computation requires full financial statements. "
            "Example query: 'estimate Saudi corporate zakat on SAR 1M zakat base'. "
            "Input notes: zakat_base is the caller-computed adjusted equity figure per ZATCA — this tool does NOT derive it from raw balance-sheet items. "
            "Limitations: 2.5% flat applied; does not model the deemed-base alternative or industry-specific ZATCA rules. "
            "See also: calculate_zakat for personal Zakat al-Mal computation from raw asset breakdown."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "zakat_base": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Caller-computed zakat-eligible base amount in SAR (adjusted equity per ZATCA).",
                },
            },
            "required": ["zakat_base"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "zakat_base": {"type": "number", "description": "Echoed zakat base."},
                "zakat_due": {"type": "number", "description": "2.5% of zakat_base."},
                "rate": {"type": "number", "description": "Applied rate (0.025)."},
                "disclaimer": {"type": "string", "description": "Required disclaimer about real ZATCA computation."},
            },
            "required": ["zakat_base", "zakat_due", "rate", "disclaimer"],
        },
    ),
    types.Tool(
        name="calculate_india_electricity_bill",
        description=(
            "Calculate an Indian electricity bill using progressive slab tariffs. "
            "Use a built-in DISCOM preset ('BESCOM' for Karnataka, 'MSEB' for Maharashtra, 'BSES' for Delhi) "
            "or supply custom slabs. The constants BESCOM_RESIDENTIAL, MSEB_RESIDENTIAL, BSES_RESIDENTIAL "
            "are importable from calcnook.countries.india.electricity_bill for custom use. "
            "Example queries: 'electricity bill for 250 units in Bangalore (BESCOM)', "
            "'Delhi BSES bill for 400 units with ₹100 fixed charge'. "
            "Input notes: electricity_duty_percent is whole percent (6 = 6%, NOT 0.06); fuel_surcharge_per_unit and rates are in ₹/kWh. "
            "Limitations: residential tariffs only — no commercial / industrial / TOD slab support. Provide preset OR slabs (one is required). "
            "See also: format_currency_amount with currency='INR' to display total_bill in lakh/crore notation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "units_consumed": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total electricity consumption in kWh for the billing period.",
                },
                "preset": {
                    "type": "string",
                    "enum": ["BESCOM", "MSEB", "BSES"],
                    "description": "Pre-built DISCOM tariff: BESCOM (Karnataka), MSEB (Maharashtra), BSES (Delhi).",
                },
                "slabs": {
                    "type": "array",
                    "description": "Custom slab list: each item is [upper_units, rate_per_unit]. Last upper_units can be 'inf'.",
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "fixed_charges": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Monthly fixed / demand charges in ₹.",
                },
                "fuel_surcharge_per_unit": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Fuel adjustment charge per unit in ₹/kWh.",
                },
                "electricity_duty_percent": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "State electricity duty as a percentage of energy + fuel charges.",
                },
            },
            "required": ["units_consumed"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "units_consumed": {"type": "number", "description": "Echoed kWh consumed."},
                "energy_charge": {"type": "number", "description": "Slab-tariff energy cost in ₹."},
                "fixed_charges": {"type": "number", "description": "Echoed monthly fixed/demand charges."},
                "fuel_surcharge": {"type": "number", "description": "Total fuel surcharge in ₹."},
                "electricity_duty": {"type": "number", "description": "Computed electricity duty in ₹."},
                "total_bill": {"type": "number", "description": "Final bill amount in ₹."},
                "slab_breakdown": {
                    "type": "array",
                    "description": "Per-slab consumption and charge breakdown.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "slab_upper": {"type": ["number", "string"]},
                            "rate_per_unit": {"type": "number"},
                            "units_in_slab": {"type": "number"},
                            "energy_charge": {"type": "number"},
                        },
                    },
                },
            },
            "required": ["units_consumed", "energy_charge", "fixed_charges", "fuel_surcharge",
                         "electricity_duty", "total_bill", "slab_breakdown"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

DISPATCH: dict[str, Any] = {
    "calculate_compound_interest": core_tools.tool_compound_interest,
    "calculate_sip_dca": core_tools.tool_sip_dca,
    "calculate_loan_payment": core_tools.tool_loan_payment,
    "calculate_retirement": core_tools.tool_retirement,
    "calculate_bmi_bmr_tdee": core_tools.tool_bmi_bmr_tdee,
    "convert_currency": core_tools.tool_convert_currency,
    "format_currency_amount": core_tools.tool_format_currency_amount,
    "analyze_salary_offer": composite_tools.tool_analyze_salary_offer,
    "financial_health_snapshot": composite_tools.tool_financial_health_snapshot,
    "compare_loan_options": composite_tools.tool_compare_loan_options,
    "calculate_zakat": islamic_tools.tool_zakat,
    "calculate_islamic_financing": islamic_tools.tool_islamic_financing,
    "calculate_hajj_savings": islamic_tools.tool_hajj_savings,
    "screen_halal_stock": islamic_tools.tool_screen_halal_stock,
    "calculate_income_tax": country_tools.tool_income_tax,
    "calculate_us_retirement_account": country_tools.tool_us_retirement_account,
    "calculate_eosg": country_tools.tool_eosg,
    "calculate_vat": country_tools.tool_vat,
    "calculate_saudi_zakat_citizen": country_tools.tool_saudi_zakat_citizen,
    "calculate_india_electricity_bill": country_tools.tool_india_electricity_bill,
}

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

server: Server = Server("calcnook")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return all registered calcnook tools."""
    return TOOLS


@server.call_tool()
async def call_tool(
    name: str,
    arguments: dict[str, Any] | None,
) -> list[types.TextContent]:
    """Dispatch a tool call to the appropriate handler."""
    if name not in DISPATCH:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"unknown tool: {name}"}),
        )]

    args = arguments or {}
    try:
        result = DISPATCH[name](args)
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug("Tool %s raised %s: %s", name, type(exc).__name__, exc)
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(exc)}),
        )]


# ---------------------------------------------------------------------------
# Prompts (5)
# ---------------------------------------------------------------------------


@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    """Return all registered calcnook prompts (slash-command discovery)."""
    return PROMPTS


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, Any] | None) -> types.GetPromptResult:
    """Render a registered prompt with caller-supplied arguments templated inline."""
    if name not in PROMPT_RENDERERS:
        raise ValueError(f"unknown prompt: {name}")
    return PROMPT_RENDERERS[name](arguments or {})


# ---------------------------------------------------------------------------
# Resources (4 + 2 templates)
# ---------------------------------------------------------------------------


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """Return all registered calcnook resources (LLM context fetch surface)."""
    return RESOURCES


@server.list_resource_templates()
async def list_resource_templates() -> list[types.ResourceTemplate]:
    """Return parameterised resource templates (tax-brackets, discom-rates)."""
    return RESOURCE_TEMPLATES


@server.read_resource()
async def read_resource(uri: Any) -> Any:
    """Dispatch a `calcnook://...` URI to the resources module."""
    return await read_resource_impl(uri)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

async def amain() -> None:
    """Run the calcnook MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="calcnook",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    """CLI entry point: ``calcnook-mcp``."""
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(amain())
