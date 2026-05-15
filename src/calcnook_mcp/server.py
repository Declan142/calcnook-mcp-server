"""calcnook-mcp: MCP server exposing 23 calcnook financial tools over stdio."""

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
from .tools import india_deep as india_deep_tools

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
            "'future value of $5000 invested at 8% annually for 20 years compounded monthly'."
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
    ),
    types.Tool(
        name="calculate_sip_dca",
        description=(
            "Compute the future value of periodic contributions (SIP in India, DCA globally). "
            "Supports annual step-up of monthly contributions. "
            "Example queries: 'SIP ₹5000/month for 15 years at 12%', "
            "'how much SIP to reach 1 crore in 10 years', "
            "'DCA $500/month into index fund for 30 years', "
            "'step-up SIP with 10% annual increase'."
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
    ),
    types.Tool(
        name="calculate_loan_payment",
        description=(
            "Calculate monthly EMI / mortgage payment for a fixed-rate loan. "
            "Returns total interest, total payment, and optional full amortization schedule. "
            "Works for home loans, car loans, personal loans, mortgage. "
            "Example queries: 'EMI for ₹30L home loan at 8.5% for 20 years', "
            "'$300k mortgage at 6.5% for 30 years', "
            "'what if I pay $200 extra per month on my car loan'."
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
            "'safe monthly withdrawal from $1M at 4% rule'."
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
            "'TDEE for moderately active person with BMR 1700'."
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
    ),
    types.Tool(
        name="convert_currency",
        description=(
            "Convert an amount between any two currencies using a caller-supplied USD-based rate dict. "
            "The caller must provide current exchange rates (USD=1.0 base). "
            "Example: convert 1000 USD to INR with rates={'USD':1.0, 'INR':83.5}."
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
    ),
    types.Tool(
        name="format_currency_amount",
        description=(
            "Format a numeric amount as a human-readable currency string. "
            "For INR, optionally use Indian lakh/crore notation (₹15.00 L, ₹2.50 Cr). "
            "Example queries: 'format 83500 in INR', 'display 25000000 as crores'."
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
    ),
    # ------ Islamic Finance ------
    types.Tool(
        name="calculate_zakat",
        description=(
            "Compute Zakat al-Mal (annual 2.5% Islamic wealth obligation). "
            "Sums all zakatable assets, deducts debts, checks nisab threshold (gold or silver basis), "
            "and returns the zakat due. Cross-cutting — any Muslim, any country. "
            "Example queries: 'how much Zakat do I owe on $25000 savings and $5000 stocks', "
            "'zakat calculation with gold and silver holdings'."
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
            "'mudarabah: investor puts $100k, profit $20k split 70/30'."
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
    ),
    types.Tool(
        name="calculate_hajj_savings",
        description=(
            "Calculate the monthly savings needed to fund a Hajj pilgrimage by a target year. "
            "Accounts for existing savings and halal investment returns (sukuk/equity). "
            "Example queries: 'how much to save monthly for Hajj costing $8000 in 5 years', "
            "'hajj savings plan with ₹50000 already saved, 6% return, 3 years'."
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
    ),
    types.Tool(
        name="screen_halal_stock",
        description=(
            "Screen a stock for Sharia compliance using AAOIFI standard financial ratios. "
            "Checks: business sector (haram/halal), debt ratio, cash ratio, receivables ratio, haram revenue ratio. "
            "Returns compliance verdict, failed checks, and purification ratio. "
            "Example queries: 'is this tech stock halal?', 'AAOIFI screen for Apple with these financials'."
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
            "'UK income tax on £50000 salary', 'India income tax ₹12L new regime'."
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
    ),
    types.Tool(
        name="calculate_us_retirement_account",
        description=(
            "Analyse US retirement account contributions for 2026. "
            "account_type='traditional_401k': employee deferral, employer match, §415 cap, tax savings. "
            "account_type='roth_ira': eligibility check and MAGI phase-out calculation. "
            "Example queries: 'how much do I save in taxes with 401k contribution', "
            "'am I eligible for Roth IRA at $155k income'."
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
    ),
    types.Tool(
        name="calculate_eosg",
        description=(
            "Calculate End of Service Gratuity (EOSG) for UAE or Saudi Arabia. "
            "UAE: Federal Decree-Law 33/2021 — 21 days/year for first 5 years, 30 days/year after. "
            "Saudi: Saudi Labour Law Articles 84-87 — ½ month/year first 5 years, 1 month/year after; "
            "resignation factor applies. "
            "Example queries: 'UAE gratuity for 7 years service at AED 8000 basic salary', "
            "'Saudi EOSG if I resign after 6 years on SAR 5000 salary'."
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
    ),
    types.Tool(
        name="calculate_vat",
        description=(
            "Calculate VAT for UAE (5%) or Saudi Arabia (15%). "
            "Works for both ex-VAT and VAT-inclusive amounts. "
            "Example queries: 'UAE VAT on AED 1000 product', "
            "'what is the VAT-exclusive price of SAR 1150 including 15% VAT'."
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
    ),
    types.Tool(
        name="calculate_saudi_zakat_citizen",
        description=(
            "Estimate ZATCA-collected Zakat for Saudi / GCC nationals (simplified 2.5% estimator). "
            "Caller supplies the pre-computed zakat base. Returns zakat due with a disclaimer that "
            "actual ZATCA computation requires full financial statements. "
            "Example query: 'estimate Saudi corporate zakat on SAR 1M zakat base'."
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
    ),
    types.Tool(
        name="calculate_india_electricity_bill",
        description=(
            "Calculate an Indian electricity bill using progressive slab tariffs. "
            "Use a built-in DISCOM preset ('BESCOM' for Karnataka, 'MSEB' for Maharashtra, 'BSES' for Delhi) "
            "or supply custom slabs. The constants BESCOM_RESIDENTIAL, MSEB_RESIDENTIAL, BSES_RESIDENTIAL "
            "are importable from calcnook.countries.india.electricity_bill for custom use. "
            "Example queries: 'electricity bill for 250 units in Bangalore (BESCOM)', "
            "'Delhi BSES bill for 400 units with ₹100 fixed charge'."
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
    ),
    # ------ India deep (v0.2.0) ------
    types.Tool(
        name="calculate_india_pf_epf",
        description=(
            "Compute India PF/EPF monthly contributions and projected retirement corpus. "
            "Splits employer's 12% per EPFO rules: 8.33% to EPS (capped at ₹15K basic), 3.67% to EPF. "
            "Future-value projects EPF portion at the supplied annual return (default 8%). "
            "Example queries: 'EPF corpus on ₹50K basic over 30 years', "
            "'PF contribution split for ₹25K basic salary', "
            "'how much EPF will I have at retirement with ₹40K basic and 8.25% return'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "monthly_basic": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monthly basic salary (incl. DA) in INR.",
                },
                "years": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Years until withdrawal / retirement.",
                },
                "employee_pct": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.12,
                    "description": "Employee contribution as decimal of basic. Default 0.12 (12%).",
                },
                "employer_pct": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.12,
                    "description": "Employer contribution as decimal of basic. Default 0.12 (12%).",
                },
                "annual_return": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.08,
                    "description": "Decimal annual EPF return, e.g. 0.0825 for 8.25%. Default 0.08.",
                },
                "basic_cap": {
                    "type": "number",
                    "minimum": 0,
                    "default": 15000.0,
                    "description": "Wage ceiling for employer EPS share in INR. Default ₹15,000 (EPFO 2014).",
                },
            },
            "required": ["monthly_basic", "years"],
        },
    ),
    types.Tool(
        name="calculate_india_gratuity",
        description=(
            "Compute India statutory gratuity under the Payment of Gratuity Act, 1972. "
            "Formula: (15 × (basic + DA) × floor(years_of_service)) / 26. "
            "Tax-exempt cap ₹20L per Section 10(10)(ii). "
            "Example queries: 'gratuity for 10 years service at ₹50K basic', "
            "'how much gratuity if I leave after 8.5 years with ₹40K basic + ₹5K DA', "
            "'tax-exempt gratuity for 30-year service at ₹2L basic'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "monthly_basic_salary": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Last-drawn monthly basic salary in INR.",
                },
                "years_of_service": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total years of continuous service (floored to whole years per Sec 4).",
                },
                "dearness_allowance": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Last-drawn monthly dearness allowance in INR (added to basic).",
                },
            },
            "required": ["monthly_basic_salary", "years_of_service"],
        },
    ),
    types.Tool(
        name="calculate_india_capital_gains",
        description=(
            "Compute India capital-gains tax under Budget 2024 framework (FY 2024-25 onwards). "
            "Asset types: equity_listed (LTCG 12.5% above ₹1.25L exemption / STCG 20%), "
            "debt_mf (slab rate, Sec 50AA), property (LTCG 12.5% no-index OR 20% with-index), "
            "unlisted_equity (LTCG 12.5%), gold (LTCG 12.5%/20%), crypto (flat 30%, Sec 115BBH). "
            "Example queries: 'LTCG tax on equity sold after 2 years for ₹3.5L (purchased ₹2L)', "
            "'capital gains on flat sold for ₹80L purchased ₹50L 5 years ago', "
            "'crypto gains tax on ₹2L profit'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_type": {
                    "type": "string",
                    "enum": ["equity_listed", "debt_mf", "property", "unlisted_equity", "gold", "crypto"],
                    "description": "Asset class — determines holding-period thresholds and applicable rate.",
                },
                "purchase_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Acquisition cost in INR.",
                },
                "sale_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Realised sale consideration in INR.",
                },
                "purchase_date": {
                    "type": "string",
                    "description": "Date of acquisition in ISO YYYY-MM-DD format.",
                },
                "sale_date": {
                    "type": "string",
                    "description": "Date of sale in ISO YYYY-MM-DD format.",
                },
                "indexation": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True and asset is property/gold, apply 20% LTCG with indexation (taxpayer choice for assets acquired before 23 Jul 2024).",
                },
                "asset_subtype": {
                    "type": "string",
                    "description": "Optional informational tag (e.g. 'house', 'land', 'physical_gold', 'sgb').",
                },
            },
            "required": ["asset_type", "purchase_price", "sale_price", "purchase_date", "sale_date"],
        },
    ),
    types.Tool(
        name="calculate_india_advance_tax",
        description=(
            "Compute India advance-tax instalment due under Section 211 (FY 2024-25 schedule). "
            "Returns next due date and amount based on cumulative percentages: "
            "15% by Jun 15 (Q1), 45% by Sep 15 (Q2), 75% by Dec 15 (Q3), 100% by Mar 15 (Q4). "
            "Total tax computed via India income_tax (new/old regime) unless ``total_tax_for_year`` overrides. "
            "Example queries: 'next advance tax instalment due on income ₹25L', "
            "'how much advance tax to pay by Sep 15 on ₹40L income', "
            "'advance tax schedule for FY 2025-26 with ₹15L income already paid ₹50K'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "annual_income": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Estimated gross annual income for the FY in INR.",
                },
                "regime": {
                    "type": "string",
                    "enum": ["new", "old"],
                    "default": "new",
                    "description": "Tax regime: 'new' (default) or 'old'.",
                },
                "paid_so_far": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0.0,
                    "description": "Total advance tax already paid this FY in INR.",
                },
                "as_of_date": {
                    "type": "string",
                    "description": "Reference date in ISO YYYY-MM-DD. Defaults to today if omitted.",
                },
                "total_tax_for_year": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Optional caller-precomputed total annual tax (overrides income_tax engine call).",
                },
            },
            "required": ["annual_income"],
        },
    ),
    types.Tool(
        name="calculate_india_gst",
        description=(
            "Compute India GST (CGST/SGST/IGST) on a transaction. Permitted slabs: 0/5/12/18/28%. "
            "Rate accepted as decimal (0.18) or percent (18.0); auto-detected. "
            "Use breakup='cgst_sgst' for intra-state (split half-half) or 'igst' for inter-state (full). "
            "Set is_inclusive=true if amount already includes GST (extracts the base). "
            "Example queries: 'GST on ₹1000 product at 18% intra-state', "
            "'extract base price from ₹1180 inclusive of 18% GST', "
            "'IGST on ₹50000 inter-state invoice at 28%'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monetary amount in INR (ex-tax if is_inclusive=false; gross if true).",
                },
                "rate": {
                    "type": "number",
                    "minimum": 0,
                    "description": "GST rate. Decimal (0.18) or percent (18.0). Must equal one of {0, 5, 12, 18, 28}%.",
                },
                "is_inclusive": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, amount already includes GST and base is extracted. Default false.",
                },
                "breakup": {
                    "type": "string",
                    "enum": ["cgst_sgst", "igst"],
                    "default": "cgst_sgst",
                    "description": "'cgst_sgst' for intra-state (half-half) or 'igst' for inter-state (full).",
                },
            },
            "required": ["amount", "rate"],
        },
    ),
    types.Tool(
        name="calculate_india_hra_exemption",
        description=(
            "Compute India HRA exemption under Section 10(13A) / Rule 2A. "
            "Exempt monthly = MIN of (actual HRA, rent − 10% basic, 50% basic if metro else 40% basic). "
            "Available only under the OLD regime — Sec 115BAC disallows HRA in the new regime. "
            "Example queries: 'HRA exemption for ₹50K basic, ₹20K HRA, ₹18K rent in Mumbai', "
            "'taxable HRA for ₹40K basic, ₹15K HRA, ₹10K rent in Pune', "
            "'HRA exemption for ₹1L basic, ₹40K HRA, ₹35K rent Bangalore non-metro'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "basic_monthly": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monthly basic salary in INR (incl. DA forming part of retirement benefits).",
                },
                "hra_received_monthly": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Monthly HRA received from employer in INR.",
                },
                "rent_paid_monthly": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Actual monthly rent paid in INR.",
                },
                "is_metro": {
                    "type": "boolean",
                    "description": "True if residence is in Mumbai/Delhi/Kolkata/Chennai (Sec 10(13A) classical metros), false otherwise.",
                },
            },
            "required": ["basic_monthly", "hra_received_monthly", "rent_paid_monthly", "is_metro"],
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
    # India deep (v0.2.0)
    "calculate_india_pf_epf": india_deep_tools.tool_india_pf_epf,
    "calculate_india_gratuity": india_deep_tools.tool_india_gratuity,
    "calculate_india_capital_gains": india_deep_tools.tool_india_capital_gains,
    "calculate_india_advance_tax": india_deep_tools.tool_india_advance_tax,
    "calculate_india_gst": india_deep_tools.tool_india_gst,
    "calculate_india_hra_exemption": india_deep_tools.tool_india_hra_exemption,
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
