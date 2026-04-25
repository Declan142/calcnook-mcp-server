# RESUME — calcnook-mcp-server

**30-second pickup:** Model Context Protocol server wrapping the [calcnook](https://pypi.org/project/calcnook/) personal finance engine. Lets any MCP-compatible AI agent (Claude Code, Cursor, Goose, Continue, …) call 17 financial calculations as native tools. **v0.1.0 SHIPPED to PyPI 2026-04-25** as `pip install calcnook-mcp` / `uvx calcnook-mcp`.

## Live status

- **PyPI:** https://pypi.org/project/calcnook-mcp/0.1.0/
- **GitHub:** https://github.com/Declan142/calcnook-mcp-server — public, MIT
- **GitHub release:** https://github.com/Declan142/calcnook-mcp-server/releases/tag/v0.1.0
- **Trusted publisher:** *NOT yet configured* — first push used account-wide PyPI token. To set up: pypi.org/manage/project/calcnook-mcp/settings/publishing → Owner `Declan142`, Repo `calcnook-mcp-server`, Workflow `publish.yml`, Env `pypi`
- **Tests:** 44 passing on Python 3.10-3.13
- **Dependencies:** `mcp>=1.0`, `calcnook>=0.1.0` only

## How an end user installs

Add to Claude Desktop / Cursor / Goose config:

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

Restart the MCP host. 17 tools available immediately.

## 17 tools exposed

| Tool | Wraps |
|---|---|
| `calculate_compound_interest` | `core.compound_interest` |
| `calculate_sip_dca` | `core.periodic_investment` |
| `calculate_loan_payment` | `core.loan_payment` |
| `calculate_retirement` | `core.retirement` (mode = corpus_needed / monthly_contribution_for / safe_withdrawal) |
| `calculate_bmi_bmr_tdee` | `core.bmi` (mode = bmi / bmr / tdee) |
| `convert_currency` | `core.currency.convert` |
| `format_currency_amount` | `core.currency.format_amount` (+ lakh/crore for INR) |
| `calculate_zakat` | `core.islamic.zakat` |
| `calculate_islamic_financing` | `core.islamic.{murabaha,ijarah,mudarabah}` (instrument param) |
| `calculate_hajj_savings` | `core.islamic.hajj_savings` |
| `screen_halal_stock` | `core.islamic.halal_screen` |
| `calculate_income_tax` | `countries.{us,uk,ca,au,india}.income_tax` (country param) |
| `calculate_us_retirement_account` | `countries.us.retirement_accounts` (account_type param) |
| `calculate_eosg` | `countries.{ae,sa}.end_of_service_gratuity` (country param) |
| `calculate_vat` | `countries.{ae,sa}.vat` (country param) |
| `calculate_saudi_zakat_citizen` | `countries.sa.zakat_citizen` |
| `calculate_india_electricity_bill` | `countries.india.electricity_bill` (BESCOM/MSEB/BSES presets) |

## Quick smoke test

```bash
pip install calcnook-mcp
python -c "
from calcnook_mcp.server import TOOLS, DISPATCH
print(f'tools: {len(TOOLS)}')
r = DISPATCH['calculate_zakat']({'cash': 10000, 'stocks_value': 15000, 'debts': 2000})
print(r)
# {'total_zakatable_assets': 23000.0, 'nisab_threshold_used': 535.5, 'nisab_basis': 'silver', 'is_above_nisab': True, 'zakat_due': 575.0, 'currency': 'USD'}
"
```

## How to run tests

```bash
cd ~/repos/calcnook-mcp-server
pip install --break-system-packages -e ".[dev]"
python3 -m pytest -q
# 44 passed
```

## Open threads

- **Trusted publisher** — set up once (4 fields), then v0.2.0+ auto-publishes
- **Distribution amplification** (each ~2-5 min):
  - PR to https://github.com/punkpeye/awesome-mcp-servers under Finance category
  - Submit to https://claudemcp.com community directory
  - Submit to https://mcp-server.fastn.ai (if active)
  - Tweet from @Declan142 announcing
- **Documentation** — README has install + tool list. Could add tool-by-tool natural-language query examples (the "Talk to me about X" prompt cookbook for AI agents)
- **Engine docstring fixes** — three engine docstrings have stale example outputs (BMR, US tax, CA tax) — caught during MCP test fixture sourcing. Fix in calcnook v0.1.1 (won't affect MCP server)

## Future versions

```bash
# bump version in src/calcnook_mcp/__init__.py + pyproject.toml
git tag vX.Y.Z
git push --tags
gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
# Trusted-publish workflow auto-fires on release (after publisher is configured)
```

## Repos sister to this one

- **Engine** — `~/repos/calcnook-engine` → https://github.com/Declan142/calcnook-engine (`calcnook` v0.1.0 on PyPI)
- **Web app** — `Declan142/calcnook` (Next.js, current — pending W3 rebuild)

## Project context

Full project doc: `~/.claude/atlas/projects/active/calcnook-v2-global-relaunch.md`

Atlas memory pointer: `~/.claude/projects/-home-aditya/memory/project_calcnook_v2_global_relaunch.md`

PyPI vault: `~/.claude/vault/pypi.md` (chmod 600)
