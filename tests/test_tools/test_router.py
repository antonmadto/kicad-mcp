"""Tool router: categorization completeness + dispatch (Phase 6)."""

from __future__ import annotations

import asyncio
import json

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


def test_execute_tool_unwraps_dict_returning_tool():
    # get_server_status returns a bare `-> dict`, which FastMCP ships as a
    # single JSON-encoded TextContent (no structured content). execute_tool's
    # own promise is to hand back "the tool's actual value" — a dict here,
    # not a JSON string the caller has to parse a second time. execute_tool
    # is itself `-> dict`, so the server's own outer dispatch wraps its reply
    # the same way; we parse that one layer (real for every caller) and then
    # assert the inner "result" field wasn't left double-encoded.
    srv = create_server()

    async def go():
        return await srv.call_tool("execute_tool", {"name": "get_server_status", "arguments": {}})

    content = asyncio.run(go())
    outer = json.loads(content[0].text)
    assert outer["tool"] == "get_server_status"
    assert isinstance(outer["result"], dict), f"expected a dict, got {type(outer['result'])}"
    assert outer["result"]["server"] == "kicad-mcp"
