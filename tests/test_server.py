"""Tests for MCP server registration and tool schema validity."""

from __future__ import annotations

import pytest

from calcnook_mcp.server import TOOLS, DISPATCH


EXPECTED_TOOL_COUNT = 26


def test_tool_count() -> None:
    """Server must expose exactly 26 tools (17 atomic + 3 composite + 6 India deep)."""
    assert len(TOOLS) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(TOOLS)}: "
        f"{[t.name for t in TOOLS]}"
    )


def test_all_tools_have_dispatch_entry() -> None:
    """Every registered tool name must have a dispatch handler."""
    for tool in TOOLS:
        assert tool.name in DISPATCH, f"No dispatch handler for tool '{tool.name}'"


def test_no_extra_dispatch_entries() -> None:
    """Dispatch table must not have entries beyond the registered tools."""
    tool_names = {t.name for t in TOOLS}
    for name in DISPATCH:
        assert name in tool_names, f"Dispatch entry '{name}' has no matching Tool registration"


def test_all_tools_have_valid_input_schema() -> None:
    """Every tool's inputSchema must be a JSON-Schema object dict with required keys."""
    for tool in TOOLS:
        schema = tool.inputSchema
        assert isinstance(schema, dict), f"Tool '{tool.name}': inputSchema must be a dict"
        assert schema.get("type") == "object", f"Tool '{tool.name}': inputSchema type must be 'object'"
        assert isinstance(schema.get("properties"), dict), (
            f"Tool '{tool.name}': inputSchema must have 'properties' dict"
        )
        assert isinstance(schema.get("required"), list), (
            f"Tool '{tool.name}': inputSchema must have 'required' list"
        )


def test_all_tools_have_description() -> None:
    """Every tool must have a non-empty description."""
    for tool in TOOLS:
        assert tool.description and len(tool.description) > 10, (
            f"Tool '{tool.name}' has missing or trivial description"
        )


def test_tool_names_follow_convention() -> None:
    """Tool names should be snake_case and start with a verb."""
    valid_prefixes = ("calculate_", "convert_", "screen_", "format_", "analyze_", "compare_", "financial_")
    for tool in TOOLS:
        assert tool.name.islower(), f"Tool '{tool.name}' must be snake_case"
        assert any(tool.name.startswith(p) for p in valid_prefixes), (
            f"Tool '{tool.name}' must start with one of {valid_prefixes}"
        )
