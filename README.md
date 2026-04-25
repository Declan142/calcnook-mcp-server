# calcnook-mcp

[![PyPI](https://img.shields.io/pypi/v/calcnook-mcp)](https://pypi.org/project/calcnook-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/calcnook-mcp)](https://pypi.org/project/calcnook-mcp/)

MCP server wrapping the [calcnook](https://calcnook.com) financial engine. Gives any MCP-compatible AI agent (Claude Code, Cursor, Goose, Continue, etc.) native access to 17 calculation tools across compound interest, SIP/DCA, loans, retirement planning, BMI/BMR, Islamic finance, income tax (US/UK/CA/AU/India), VAT, End of Service Gratuity, and more.

## Install

**Preferred — zero setup via uvx:**

```bash
uvx calcnook-mcp
```

**Or pip:**

```bash
pip install calcnook-mcp
calcnook-mcp
```

## Configure your AI agent

### Claude Desktop / Claude Code

Add to `claude_desktop_config.json` (or your MCP settings):

```json
{
  "mcpServers": {
    "calcnook": {
      "command": "uvx",
      "args": ["calcnook-mcp"]
    }
  }
}
```

### Cursor

```json
{
  "mcpServers": {
    "calcnook": {
      "command": "uvx",
      "args": ["calcnook-mcp"]
    }
  }
}
```

### Goose / Continue

Use the same JSON block in the respective `mcp_servers` config section.

## Tools

| Tool | What it does | Example query |
|------|-------------|---------------|
| `calculate_compound_interest` | Future value of a lump-sum at compound interest | "What will ₹1L grow to in 10 years at 7%?" |
| `calculate_sip_dca` | SIP (India) / DCA (global) with optional annual step-up | "SIP ₹5000/month for 15 years at 12%" |
| `calculate_loan_payment` | EMI / mortgage amortization with optional extra payment | "EMI for ₹30L home loan at 8.5% for 20 years" |
| `calculate_retirement` | Corpus needed, monthly SIP to reach corpus, safe withdrawal (4% rule) | "How much SIP to reach 2Cr in 20 years?" |
| `calculate_bmi_bmr_tdee` | BMI + WHO category, BMR (Mifflin-St Jeor), TDEE | "BMI for 70kg 175cm" |
| `convert_currency` | Convert between any currencies using caller-supplied rates | "Convert $1000 to INR at 83.5" |
| `format_currency_amount` | Format amount as currency string; INR supports lakh/crore | "Show 25000000 as crores" |
| `calculate_zakat` | Zakat al-Mal (2.5% wealth obligation): all asset categories, nisab check | "Zakat on $25k savings + $5k stocks" |
| `calculate_islamic_financing` | Murabaha, Ijarah, or Mudarabah financing calculator | "Murabaha for $100k house at 30% markup over 5 years" |
| `calculate_hajj_savings` | Monthly savings needed to fund Hajj by target year | "Save monthly for Hajj costing $8000 in 5 years" |
| `screen_halal_stock` | AAOIFI Sharia compliance screen (debt, cash, receivables, haram revenue ratios) | "Is this tech stock halal given these financials?" |
| `calculate_income_tax` | Federal/national income tax for US, UK, CA, AU, India (2026) | "India income tax on ₹12L new regime" |
| `calculate_us_retirement_account` | Traditional 401(k) contribution analysis or Roth IRA phase-out check | "Am I eligible for Roth IRA at $155k income?" |
| `calculate_eosg` | End of Service Gratuity for UAE or Saudi Arabia | "UAE gratuity for 7 years at AED 8000 basic salary" |
| `calculate_vat` | VAT for UAE (5%) or Saudi Arabia (15%) | "UAE VAT on AED 1000 product" |
| `calculate_saudi_zakat_citizen` | ZATCA-collected Zakat estimate for Saudi/GCC nationals (2.5% of base) | "Saudi corporate zakat on SAR 1M base" |
| `calculate_india_electricity_bill` | India electricity bill with BESCOM/MSEB/BSES presets or custom slabs | "BESCOM bill for 250 units in Bangalore" |

## Built on

[calcnook engine](https://github.com/Declan142/calcnook-engine) — the open-source personal finance calculation library.

DISCOM presets (BESCOM_RESIDENTIAL, MSEB_RESIDENTIAL, BSES_RESIDENTIAL) are importable directly from `calcnook.countries.india.electricity_bill` for custom slab configuration.

## License

MIT
