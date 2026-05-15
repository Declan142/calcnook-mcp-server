"""Shared stdlib HTTP helper — single User-Agent, single timeout."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

USER_AGENT = "calcnook-mcp/0.2.0 (+https://github.com/Declan142/calcnook-mcp-server)"
TIMEOUT_SECONDS = 5.0


def fetch_json(url: str) -> Any:
    """GET url, return decoded JSON. Raises URLError/HTTPError/ValueError on failure."""
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310 — fixed scheme
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


__all__ = ["fetch_json", "USER_AGENT", "TIMEOUT_SECONDS", "URLError", "HTTPError"]
