"""calcnook-mcp prompts: 5 reusable MCP prompts for slash-command discovery.

Each prompt is an `mcp.types.Prompt` definition plus a renderer function that
takes user-supplied arguments and returns a `GetPromptResult` containing a
single user message with the args templated inline. Claude Desktop surfaces
these as `/calcnook:<name>` slash commands.
"""

from __future__ import annotations

from typing import Any, Callable

import mcp.types as types


PROMPTS: list[types.Prompt] = [
    types.Prompt(
        name="plan-retirement",
        description=(
            "Build a country-specific retirement plan: corpus needed, monthly "
            "contribution required, optional US 401k/Roth IRA layer, plus "
            "explicit assumptions and 3 next actions."
        ),
        arguments=[
            types.PromptArgument(
                name="country",
                description="Country code: us, uk, ca, au, in, or other.",
                required=True,
            ),
            types.PromptArgument(
                name="monthly_expense_today",
                description="Current monthly living expense in local currency (used to derive annual_expense).",
                required=True,
            ),
            types.PromptArgument(
                name="current_age",
                description="User's current age in years.",
                required=True,
            ),
            types.PromptArgument(
                name="current_savings",
                description="Existing retirement savings in local currency.",
                required=True,
            ),
            types.PromptArgument(
                name="retirement_age",
                description="Target retirement age in years.",
                required=True,
            ),
            types.PromptArgument(
                name="expected_return",
                description="Decimal expected annual investment return. Default 0.10.",
                required=False,
            ),
            types.PromptArgument(
                name="inflation",
                description="Decimal annual inflation rate. Default 0.06.",
                required=False,
            ),
        ],
    ),
    types.Prompt(
        name="annual-zakat-sweep",
        description=(
            "Walk the user through their annual Zakat al-Mal calculation: "
            "collect cash + gold + silver + stocks + business assets + debts "
            "interactively, then compute zakat with explicit nisab check."
        ),
        arguments=[
            types.PromptArgument(
                name="currency",
                description="ISO-4217 currency code for display. Default USD.",
                required=False,
            ),
            types.PromptArgument(
                name="nisab_basis",
                description="'silver' (lower, more inclusive) or 'gold'. Default silver.",
                required=False,
            ),
            types.PromptArgument(
                name="as_of_date",
                description="ISO date the zakat year ends on (e.g. 2026-05-15). Optional.",
                required=False,
            ),
        ],
    ),
    types.Prompt(
        name="salary-offer-analysis",
        description=(
            "Analyse a salary offer: income tax owed, take-home, marginal rate, "
            "US 401k/Roth eligibility layer if applicable, and delta vs current "
            "role if provided."
        ),
        arguments=[
            types.PromptArgument(
                name="salary",
                description="Gross annual salary being offered (local currency).",
                required=True,
            ),
            types.PromptArgument(
                name="country",
                description="Country code: us, uk, ca, au, or in.",
                required=True,
            ),
            types.PromptArgument(
                name="age",
                description="Candidate age in years (drives 401k catch-up + retirement runway).",
                required=True,
            ),
            types.PromptArgument(
                name="filing_status",
                description="[us only] single, married_jointly, married_separately, head_of_household.",
                required=False,
            ),
            types.PromptArgument(
                name="current_role_salary",
                description="Optional: current gross salary for delta comparison.",
                required=False,
            ),
        ],
    ),
    types.Prompt(
        name="eosg-before-resignation",
        description=(
            "Surface the End of Service Gratuity entitlement under termination vs "
            "resignation (KSA differs; UAE same). Highlights cash delta and timing."
        ),
        arguments=[
            types.PromptArgument(
                name="country",
                description="Country code: 'ae' (UAE) or 'sa' (Saudi Arabia).",
                required=True,
            ),
            types.PromptArgument(
                name="monthly_basic_salary",
                description="Monthly basic salary in local currency (excl. allowances).",
                required=True,
            ),
            types.PromptArgument(
                name="years_of_service",
                description="Total years of completed service (fractional accepted).",
                required=True,
            ),
        ],
    ),
    types.Prompt(
        name="islamic-vs-conventional-loan",
        description=(
            "Side-by-side compare a conventional loan vs murabaha Islamic financing "
            "for the same asset: monthly outflow, total payment, effective markup."
        ),
        arguments=[
            types.PromptArgument(
                name="asset_cost",
                description="Total asset purchase price.",
                required=True,
            ),
            types.PromptArgument(
                name="conventional_rate",
                description="Decimal annual interest rate on the conventional loan, e.g. 0.085 for 8.5%.",
                required=True,
            ),
            types.PromptArgument(
                name="conventional_years",
                description="Conventional loan tenure in whole years.",
                required=True,
            ),
            types.PromptArgument(
                name="islamic_markup_percent",
                description="Total markup as percent of asset cost on the murabaha leg, e.g. 30.0 for 30%.",
                required=True,
            ),
            types.PromptArgument(
                name="islamic_years",
                description="Murabaha repayment tenure in whole years.",
                required=True,
            ),
            types.PromptArgument(
                name="down_payment",
                description="Upfront down payment (applies to both legs). Default 0.",
                required=False,
            ),
        ],
    ),
]


def _arg(args: dict, key: str, default: Any = None) -> Any:
    """Pull an arg, returning default if missing or empty."""
    val = args.get(key)
    if val is None or val == "":
        return default
    return val


def _user_msg(text: str, description: str | None = None) -> types.GetPromptResult:
    return types.GetPromptResult(
        description=description,
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=text),
            )
        ],
    )


def render_plan_retirement(args: dict) -> types.GetPromptResult:
    country = str(_arg(args, "country", "other")).lower()
    monthly_expense = _arg(args, "monthly_expense_today", "<unspecified>")
    current_age = _arg(args, "current_age", "<unspecified>")
    current_savings = _arg(args, "current_savings", 0)
    retirement_age = _arg(args, "retirement_age", "<unspecified>")
    expected_return = _arg(args, "expected_return", 0.10)
    inflation = _arg(args, "inflation", 0.06)

    annual_expense_hint = ""
    years_to_retirement_hint = ""
    try:
        annual_expense_hint = f" (≈ {float(monthly_expense) * 12:.0f} annual_expense)"
    except (TypeError, ValueError):
        pass
    try:
        years_to_retirement_hint = (
            f" (years_to_retirement = {int(retirement_age) - int(current_age)})"
        )
    except (TypeError, ValueError):
        pass

    us_step = ""
    if country == "us":
        us_step = (
            "3. Then call `calculate_us_retirement_account` with account_type=traditional_401k "
            "(use a reasonable salary assumption tied to the monthly expense, ask the user if "
            "ambiguous) AND with account_type=roth_ira to surface eligibility/phase-out.\n"
        )
        next_step_num = 4
    else:
        next_step_num = 3

    text = (
        f"Build a retirement plan for a user in country='{country}' with these inputs:\n"
        f"- monthly_expense_today: {monthly_expense}{annual_expense_hint}\n"
        f"- current_age: {current_age}\n"
        f"- current_savings: {current_savings}\n"
        f"- retirement_age: {retirement_age}{years_to_retirement_hint}\n"
        f"- expected_return: {expected_return}\n"
        f"- inflation: {inflation}\n\n"
        "Execute these steps in order — do not skip:\n\n"
        "1. Call `calculate_retirement` with mode='corpus_needed', "
        "annual_expense = monthly_expense_today × 12, "
        "years_in_retirement = 30 (assume unless user specifies otherwise), "
        f"post_retirement_return = {expected_return}, inflation = {inflation}, "
        f"current_savings = {current_savings}. "
        "Capture the corpus_needed figure.\n\n"
        "2. Call `calculate_retirement` with mode='monthly_contribution_for', "
        "target_corpus = (corpus from step 1), "
        f"years_to_retirement = retirement_age - current_age, "
        f"annual_return = {expected_return}, current_savings = {current_savings}. "
        "Capture the required monthly SIP/DCA.\n\n"
        f"{us_step}"
        f"{next_step_num}. Assemble a plan that explicitly states ALL assumptions used "
        "(years_in_retirement, expected_return, inflation, currency, country tax treatment "
        "if any), then list 3 concrete next actions the user should take this week — "
        "actions must be specific (account names, instruments, % allocations), not generic.\n\n"
        "Format the final output as: ASSUMPTIONS (bulleted) → NUMBERS (table) → NEXT 3 ACTIONS (numbered)."
    )
    return _user_msg(text, description="Country-specific retirement plan walkthrough.")


def render_annual_zakat_sweep(args: dict) -> types.GetPromptResult:
    currency = str(_arg(args, "currency", "USD"))
    nisab_basis = str(_arg(args, "nisab_basis", "silver")).lower()
    as_of_date = _arg(args, "as_of_date")

    date_clause = (
        f"This is the annual zakat sweep as of {as_of_date}. "
        if as_of_date
        else "This is the annual zakat sweep for the user's current zakat year. "
    )

    text = (
        f"{date_clause}"
        f"Currency: {currency}. Nisab basis: {nisab_basis} (silver = lower threshold, "
        "more inclusive — typically preferred unless the user is following a gold-basis school).\n\n"
        "STEP 1 — Collect inputs interactively. Ask the user, ONE GROUP AT A TIME, never all at once:\n"
        "  a) Cash & bank balances (in checking, savings, FDs, money-market).\n"
        "  b) Physical gold owned in grams (jewellery, bars, coins).\n"
        "  c) Physical silver owned in grams.\n"
        "  d) Market value of zakatable equity holdings (stocks held > 1 lunar year — "
        "exclude long-term holdings deemed non-zakatable per their school).\n"
        "  e) Business assets (inventory + receivables, NOT fixed assets like machinery).\n"
        "  f) Outstanding debts owed (mortgages, personal loans — deducted from wealth).\n"
        "Wait for an answer at each step; do not invent values.\n\n"
        "STEP 2 — Once all 6 collected, call `calculate_zakat` with the supplied amounts, "
        f"currency='{currency}', nisab_basis='{nisab_basis}'. Use the default gold/silver prices "
        "unless the user supplied current spot prices.\n\n"
        "STEP 3 — Format the output as:\n"
        "  - NISAB CHECK: explicitly state threshold value, total wealth, and whether "
        "above/below nisab. If below, no zakat is due — say so clearly.\n"
        "  - WEALTH BREAKDOWN: itemised table of each asset class + debts deduction.\n"
        "  - ZAKAT DUE: the 2.5% figure with a one-line explanation of how it was reached.\n"
        "  - DISBURSEMENT REMINDER: zakat must be paid to the 8 categories of recipients "
        "specified in Surah At-Tawbah 9:60.\n\n"
        "Be precise with currency formatting. Do not editorialise on schools of fiqh — present figures."
    )
    return _user_msg(text, description="Interactive Zakat al-Mal walkthrough.")


def render_salary_offer_analysis(args: dict) -> types.GetPromptResult:
    salary = _arg(args, "salary", "<unspecified>")
    country = str(_arg(args, "country", "<unspecified>")).lower()
    age = _arg(args, "age", "<unspecified>")
    filing_status = _arg(args, "filing_status")
    current_role_salary = _arg(args, "current_role_salary")

    us_extras = ""
    if country == "us":
        fs = filing_status or "single"
        us_extras = (
            f"3. (US-specific) Call `calculate_us_retirement_account` with account_type=traditional_401k, "
            f"contribution = min(23500, salary * 0.10) as a starting suggestion, age={age}, "
            f"salary={salary}, employer_match_percent=0.50 (50¢/$ — confirm with user later), "
            "to show 401k tax savings.\n"
            f"4. (US-specific) Call `calculate_us_retirement_account` with account_type=roth_ira, "
            f"contribution=7000, age={age}, magi={salary}, filing_status='{fs}' "
            "to flag Roth IRA eligibility / phase-out range.\n"
        )
        next_step_num = 5
    else:
        next_step_num = 3

    delta_step = ""
    if current_role_salary not in (None, "", 0):
        delta_step = (
            f"{next_step_num}. Compute take-home delta vs current_role_salary={current_role_salary}: "
            "re-run `calculate_income_tax` for current salary, then surface the absolute and percentage "
            "increase in NET take-home (not gross) — this is what the user actually feels.\n"
        )
        next_step_num += 1

    fs_clause = f", filing_status='{filing_status}'" if filing_status else ""

    text = (
        f"Analyse a salary offer with these inputs:\n"
        f"- salary: {salary} (gross annual, local currency)\n"
        f"- country: {country}\n"
        f"- age: {age}\n"
        + (f"- filing_status: {filing_status}\n" if filing_status else "")
        + (f"- current_role_salary: {current_role_salary}\n" if current_role_salary else "")
        + "\nExecute in order:\n\n"
        f"1. Call `calculate_income_tax` with country='{country}', income={salary}{fs_clause}. "
        "Capture: tax_owed, take_home, effective_rate, marginal_rate.\n\n"
        f"2. Estimate the marginal rate explicitly — the next ₹/$/£ earned is taxed at the marginal rate "
        "(NOT the effective rate). This matters for negotiating a raise or evaluating a bonus.\n\n"
        f"{us_extras}"
        f"{delta_step}"
        f"{next_step_num}. Final output format:\n"
        "  - HEADLINE: NET take-home per month (one number, bolded equivalent in plain text).\n"
        "  - TAX BREAKDOWN: table — gross, deductions, taxable, tax owed, take-home.\n"
        "  - MARGINAL CONTEXT: one line — 'next dollar earned taxed at X%'.\n"
        + ("  - 401K/ROTH NOTES: tax savings + Roth eligibility flags.\n" if country == "us" else "")
        + ("  - DELTA VS CURRENT: absolute + % NET take-home change.\n" if current_role_salary not in (None, "", 0) else "")
        + "  - CAVEATS: state-level tax (US/CA), allowances (UK/IN), local levies not included unless surfaced."
    )
    return _user_msg(text, description="Country-aware salary offer analysis.")


def render_eosg_before_resignation(args: dict) -> types.GetPromptResult:
    country = str(_arg(args, "country", "<unspecified>")).lower()
    salary = _arg(args, "monthly_basic_salary", "<unspecified>")
    yos = _arg(args, "years_of_service", "<unspecified>")

    if country == "sa":
        comparison = (
            "Saudi Labour Law treats resignation differently from termination: the entitlement "
            "factor scales by years of service when the employee resigns (Article 85), so the "
            "delta between the two scenarios can be substantial. ALWAYS compute both."
        )
    else:
        comparison = (
            "UAE Federal Decree-Law 33/2021 treats termination and resignation identically for "
            "limited contracts since 2022 — the figure should match. We still compute both to "
            "make this explicit for the user (so they aren't second-guessing on the way out)."
        )

    text = (
        f"Surface End of Service Gratuity (EOSG) entitlement BEFORE resignation. Inputs:\n"
        f"- country: {country}\n"
        f"- monthly_basic_salary: {salary}\n"
        f"- years_of_service: {yos}\n\n"
        f"{comparison}\n\n"
        "Execute:\n\n"
        f"1. Call `calculate_eosg` with country='{country}', monthly_basic_salary={salary}, "
        f"years_of_service={yos}, end_reason='termination'. Capture gratuity_amount.\n\n"
        f"2. Call `calculate_eosg` with country='{country}', monthly_basic_salary={salary}, "
        f"years_of_service={yos}, end_reason='resignation'. Capture gratuity_amount.\n\n"
        "3. Surface the delta clearly:\n"
        "  - GRATUITY IF TERMINATED: <amount> AED/SAR\n"
        "  - GRATUITY IF YOU RESIGN: <amount> AED/SAR\n"
        "  - DELTA: absolute + % difference\n\n"
        "4. Timing implications:\n"
        + (
            "  - If KSA + delta > 0: weigh the resignation cost against your reasons for leaving. "
            "Sometimes negotiating an amicable exit (mutual separation) preserves termination treatment.\n"
            if country == "sa"
            else "  - UAE: resignation timing matters less for gratuity since 2022, but completing "
            "another full year before resigning increases the figure for both legs.\n"
        )
        + "  - Always confirm your last drawn BASIC salary (excludes housing/transport allowances) — "
        "EOSG is computed on basic only, which is often 50-60% of total CTC.\n\n"
        "Be direct, no fluff. The user is about to make a financial decision."
    )
    return _user_msg(text, description="EOSG resignation-vs-termination comparison.")


def render_islamic_vs_conventional_loan(args: dict) -> types.GetPromptResult:
    asset_cost = _arg(args, "asset_cost", "<unspecified>")
    conv_rate = _arg(args, "conventional_rate", "<unspecified>")
    conv_years = _arg(args, "conventional_years", "<unspecified>")
    isl_markup = _arg(args, "islamic_markup_percent", "<unspecified>")
    isl_years = _arg(args, "islamic_years", "<unspecified>")
    down_payment = _arg(args, "down_payment", 0)

    text = (
        "Compare a conventional loan against a Sharia-compliant murabaha for the same asset.\n\n"
        f"Inputs:\n"
        f"- asset_cost: {asset_cost}\n"
        f"- conventional_rate: {conv_rate} (decimal annual interest rate)\n"
        f"- conventional_years: {conv_years}\n"
        f"- islamic_markup_percent: {isl_markup} (total markup % over the murabaha tenure)\n"
        f"- islamic_years: {isl_years}\n"
        f"- down_payment: {down_payment}\n\n"
        "Execute:\n\n"
        f"1. Call `calculate_loan_payment` with principal=({asset_cost} - {down_payment}), "
        f"annual_rate={conv_rate}, years={conv_years}. Capture monthly_payment, total_payment, "
        "total_interest.\n\n"
        f"2. Call `calculate_islamic_financing` with instrument='murabaha', "
        f"asset_cost={asset_cost}, markup_percent={isl_markup}, "
        f"tenure_years={isl_years}, down_payment={down_payment}. Capture monthly_installment, "
        "total_payment, total_markup.\n\n"
        "3. Build a side-by-side comparison table:\n\n"
        "  | Metric                | Conventional | Murabaha |\n"
        "  |-----------------------|--------------|----------|\n"
        "  | Monthly outflow       | …            | …        |\n"
        "  | Total payment         | …            | …        |\n"
        "  | Total cost over price | …            | …        |\n"
        "  | Effective annual rate | …            | …        |\n"
        "  | Tenure (years)        | …            | …        |\n\n"
        "4. To compute the murabaha effective annual rate for fair comparison:\n"
        f"   approx_eff_rate ≈ ({isl_markup}/100) / {isl_years} (simple-interest equivalent — flag "
        "this approximation explicitly; murabaha is a sale not a loan, so 'rate' is a heuristic).\n\n"
        "5. Verdict guidance:\n"
        "  - If user is Muslim and prioritises Sharia compliance: murabaha wins regardless of cost delta — "
        "frame it as the cost of compliance.\n"
        "  - If user is comparing on pure economics: surface the cheaper option and the absolute $ delta "
        "over the lifetime.\n"
        "  - If tenures differ (likely): compute total cost per year of asset use to normalise.\n\n"
        "Caveat: the murabaha price is fixed at contract — no rate-reset risk. Conventional floating-rate "
        "loans carry interest-rate risk that does not show in this snapshot. Mention this."
    )
    return _user_msg(text, description="Islamic murabaha vs conventional loan comparison.")


PROMPT_RENDERERS: dict[str, Callable[[dict], types.GetPromptResult]] = {
    "plan-retirement": render_plan_retirement,
    "annual-zakat-sweep": render_annual_zakat_sweep,
    "salary-offer-analysis": render_salary_offer_analysis,
    "eosg-before-resignation": render_eosg_before_resignation,
    "islamic-vs-conventional-loan": render_islamic_vs_conventional_loan,
}
