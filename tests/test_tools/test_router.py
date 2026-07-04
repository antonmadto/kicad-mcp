"""Tool router: categorization completeness + dispatch (Phase 6)."""

from __future__ import annotations

import asyncio

from kicad_mcp.server import create_server
from kicad_mcp.tools.router import CATEGORIES, _category_of


def _tool_names():
    srv = create_server()
    return {t.name for t in asyncio.run(srv.list_tools())}


def test_every_tool_is_categorized_exactly_once():
    """The router's category map must cover every registered tool, with no
    duplicates and no phantom entries. This keeps the map honest as tools change."""
    registered = _tool_names()
    categorized: list[str] = []
    for _desc, names in CATEGORIES.values():
        categorized.extend(names)

    # No duplicates across categories.
    assert len(categorized) == len(set(categorized)), "a tool appears in two categories"
    categorized_set = set(categorized)
    missing = registered - categorized_set
    phantom = categorized_set - registered
    assert not missing, f"tools not in any category: {sorted(missing)}"
    assert not phantom, f"category lists a non-existent tool: {sorted(phantom)}"


def test_category_of_lookup():
    assert _category_of("review_design") == "review"
    assert _category_of("route_trace") == "routing"
    assert _category_of("nonexistent") is None


def test_execute_tool_dispatches():
    srv = create_server()

    async def go():
        res = await srv.call_tool("execute_tool", {"name": "list_tool_categories", "arguments": {}})
        return res

    result = asyncio.run(go())
    assert result is not None  # dispatched without error


def test_more_than_forty_tools():
    # The router pattern activates past ~40 tools (PLAN.md §3).
    assert len(_tool_names()) > 40
