"""Tiny fakes for monkeypatching urllib.request.urlopen."""

from __future__ import annotations

import io
import json
from typing import Any, Callable
from urllib.error import URLError


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.getvalue()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        self._buf.close()


class Queue:
    """Wrap a list of payloads so the router treats it as a queue, not a JSON array."""

    def __init__(self, items: list[Any]) -> None:
        self.items = list(items)


def make_url_router(routes: dict[str, Any]) -> Callable[..., FakeResponse]:
    """Return a urlopen replacement that picks payload by URL prefix.

    Routes value is either:
      - a JSON-serialisable payload (returned every call),
      - an Exception instance (raised every call), or
      - a Queue([...]) wrapper to consume a sequence over multiple calls.
    """
    consumed: dict[str, Any] = {}
    for k, v in routes.items():
        if isinstance(v, Queue):
            consumed[k] = ("queue", v.items)
        elif isinstance(v, BaseException):
            consumed[k] = ("constant", v)
        else:
            consumed[k] = ("constant", v)

    call_log: list[str] = []

    def fake_urlopen(req, timeout: float | None = None):
        url = getattr(req, "full_url", str(req))
        call_log.append(url)
        for prefix, (mode, payload) in consumed.items():
            if url.startswith(prefix):
                if mode == "queue":
                    if not payload:
                        raise URLError(f"queue exhausted for {prefix}")
                    item = payload.pop(0)
                else:
                    item = payload
                if isinstance(item, BaseException):
                    raise item
                return FakeResponse(item)
        raise URLError(f"no route for {url}")

    fake_urlopen.calls = call_log  # type: ignore[attr-defined]
    return fake_urlopen
