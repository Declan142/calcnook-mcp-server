# calcnook-mcp-server - agent brief

Brief for any coding agent working in this repository. `README.md` is the public package description (also the PyPI long description); `RESUME.md` is the maintainer's pickup notes, written at the v0.1.0 release and not updated since.

## ⚠️ Read first - published is v0.1.0; this branch is an unreleased v0.2.0

- **What users have:** `calcnook-mcp` 0.1.0 on PyPI (released 2026-04-25, tag `v0.1.0`, 17 tools). People run it with `uvx calcnook-mcp`, so a new release changes the tools inside their AI agents the next time the host starts. A PyPI version can never be replaced.
- **What this branch has:** `feat/v0.2.0-agentic-upgrade` is 11 commits ahead of `main` (last commit 2026-05-15) and has never been merged, tagged or released. It carries 26 tools (the 17 published, 3 composite tools, 6 India tools), MCP prompts and resources, and live FX and metal-price fetching.
- **It is not release-ready as it stands.** The version is still `0.1.0`, the engine dependency floor is still `calcnook>=0.1.0` although the six India tools import engine modules that only exist in engine 0.2.0, and the publish workflow depends on PyPI trusted publishing that the maintainer's notes describe as not yet configured. Details under "Hard gates".
- **Do not create a release, a tag, or run the publish workflow** unless the maintainer asks for that release by version. Pushing to `main` runs tests only.
- **The working tree is live on the maintainer's machine.** The package is installed in editable mode, so the local `calcnook-mcp` command runs whichever branch is checked out here.

## What this repo is

A Model Context Protocol server (stdio transport) that exposes the `calcnook` personal-finance library as tools for MCP hosts such as Claude Code, Cursor, Goose and Continue.

- Status: published package; branch work dormant - last commit 2026-05-15.
- Remote: `github.com/Declan142/calcnook-mcp-server`, default branch `main` (at the v0.1.0 docs commit, 2026-04-25). MIT licensed, public.
- Stack: Python >= 3.10, `mcp>=1.0`, `calcnook>=0.1.0`, setuptools >= 68 build backend. Dev extras: `pytest>=7.0`, `pytest-asyncio>=0.21` (`asyncio_mode = "auto"`).
- Entry point: console script `calcnook-mcp` -> `calcnook_mcp.server:main`.
- Registries: no `server.json` or other registry manifest exists in the repo. The maintainer's notes record one directory submission (a pull request to the awesome-mcp-servers list, open on 2026-04-25); its outcome is UNKNOWN - verify before relying on this.

## Layout

| Path | What it is |
|---|---|
| `src/calcnook_mcp/server.py` | The server: `TOOLS` (26 tool definitions with input and output schemas), `DISPATCH` (name -> handler), prompt and resource handlers, `amain()` / `main()` |
| `src/calcnook_mcp/tools/` | Handlers by area: `core.py`, `islamic.py`, `countries.py`, `india_deep.py`, `composite.py` |
| `src/calcnook_mcp/live/` | Live data with fallback: `fx.py` (Frankfurter), `metals.py` (metals.live, gold-api.com), `nisab.py`, `cache.py` (in-process TTL, `CALCNOOK_CACHE_TTL_SECONDS`, default 3600), `_http.py` (stdlib `urllib`, 5 s timeout) |
| `src/calcnook_mcp/prompts.py`, `resources.py` | MCP prompts and resources |
| `tests/` | `test_server.py`, `test_tools.py`, `test_output_schemas.py`, plus `composite/`, `india_deep/`, `live/`, `prompts/`, `resources/` |
| `.github/workflows/test.yml` | pytest on Python 3.10-3.13 for pushes and PRs to `main` only; this feature branch gets no CI unless a PR is open |
| `.github/workflows/publish.yml` | Build and upload to PyPI on a published GitHub Release or manual dispatch |
| `build/`, `dist/`, `src/calcnook_mcp.egg-info/` | Generated, ignored. `dist/` holds the 0.1.0 artefacts; never upload from it |

## Build / dev / test

```
python3 -m pytest -q            # full suite; the live-data tests use fakes and make no network calls
pip install -e ".[dev]"         # what CI runs before pytest
python3 -m calcnook_mcp         # start the server on stdio (same as the calcnook-mcp script)
```

- The maintainer's notes record 44 passing at v0.1.0. The branch adds many tests; the current count was not re-run when this file was written.
- `README.md` and `RESUME.md` describe the 17-tool v0.1.0 surface. They are accurate for what is published and stale for this branch.

## Hard gates

- **Version lives in four places** and they already disagree: `pyproject.toml` (`0.1.0`), `src/calcnook_mcp/__init__.py` (`0.1.0`), `server_version` in `server.py` (`0.1.0`), and `USER_AGENT` in `live/_http.py` (`0.2.0`). A release bumps all four together.
- **Engine first.** `tools/india_deep.py` imports modules added in engine 0.2.0. Before this branch is released, `calcnook` 0.2.0 or later must be on PyPI and the floor in `pyproject.toml` raised to match (there is a TODO on that line). Otherwise a fresh `uvx calcnook-mcp` installs an older engine and the server fails at import.
- **Publish path.** v0.1.0 was uploaded by hand with a token. `publish.yml` uses trusted publishing (`id-token: write`), which the notes list as deferred. Whether it has been configured since is UNKNOWN - verify before relying on this.
- **Tool names and input schemas are a public contract.** Hosts and users' prompts refer to the 17 published names. Add tools freely; do not rename or remove a published one, or tighten a schema, without the maintainer.
- **Every tool has an output schema** and `tests/test_output_schemas.py` checks results against it. A new tool needs its schema and a fixture.
- **Live data must degrade, never fail.** Results report where rates came from (`caller`, `live`, `cached`, `fallback`). `calculate_zakat` treats its default metal prices (75.0 and 0.90) as "not supplied" and fetches live prices instead; keep that sentinel behaviour and the provenance fields intact.
- The server does no math of its own. A wrong figure is fixed in the engine repository, with a source and a test, not patched here.

## Non-negotiable safety

- No force-push, no hard reset to a remote branch, no hook-skipping commits, no destructive commands outside this repository.
- No push to `main` with failing tests. No release, tag or manual publish without the maintainer's explicit request.
- Never commit credentials, tokens or `.env` files. A PyPI token must never appear in this repo, its history or its CI logs.
- Do not read or modify credential stores, SSH or cloud configuration, or agent configuration in the home directory without permission for that exact path.
- Do not delete branches, tags or worktrees you did not create. The `agent/v02-*` branches are the merged inputs of this feature branch; leave them.
- Do not add outbound hosts beyond the three in `live/` without the maintainer; every call must keep the timeout and a fallback.
- "Done" means a command and its real output, not a file written.

## Do not touch / never commit

- `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`.
- The `v0.1.0` tag.
- `LICENSE`. The repository is public and MIT by decision.

## Commits & branches

- `main` is the released line. Feature branches are named `{purpose}/{slug}`.
- This feature branch is level with its remote copy. Merging it into `main` is a release decision for the maintainer.
- The repository is public: commit messages, this file and `RESUME.md` are world-readable. Keep private paths, hostnames and credentials out of all three.
- Stage explicit paths, never `git add -A`. Descriptive messages with a `Co-Authored-By:` trailer for the acting agent.
