"""Tool router (Phase 6, mixelpixx pattern, PLAN.md §3).

Once the tool count passes ~40, these four tools help navigate the surface:
categories, per-category listings, free-text search, and a dispatch passthrough.
All tools remain directly callable by name; the router is a discovery aid layered
over the live FastMCP registry (no static duplication of tool metadata).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Category → member tool names. Kept in sync with the registered tools by
# test_router::test_every_tool_is_categorized.
CATEGORIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "diagnostics": ("Server + backend status", ("get_server_status",)),
    "project": (
        "Discover, inspect, and create projects",
        ("list_projects", "get_project_info", "create_project"),
    ),
    "board": ("Read board layers, stackup", ("get_board_info", "get_board_stackup")),
    "schematic_read": (
        "Read schematic components and nets",
        ("list_schematic_components", "list_schematic_nets", "trace_net"),
    ),
    "verify": ("ERC / DRC", ("run_erc", "run_drc")),
    "export": (
        "Gerbers, BOM, netlist, STEP, renders, fab package",
        (
            "export_gerbers",
            "export_bom",
            "export_netlist",
            "export_step",
            "render_board",
            "export_fab_package",
        ),
    ),
    "review": (
        "Hartley/Phil design-review engine",
        ("review_design", "review_topic", "set_design_context"),
    ),
    "board_edit": (
        "Live footprint/zone editing via IPC",
        (
            "get_live_board_status",
            "list_live_footprints",
            "move_footprint",
            "rotate_footprint",
            "duplicate_footprint",
            "add_zone",
            "refill_zones",
            "save_board",
            "get_netclasses",
        ),
    ),
    "routing": (
        "Live trace/via/diff-pair routing + rip-up via IPC",
        ("route_trace", "add_via", "route_differential_pair", "rip_up_nets", "rip_up_footprint"),
    ),
    "schematic_edit": (
        "Experimental schematic writes",
        ("set_symbol_property", "duplicate_symbol"),
    ),
    "library": (
        "Symbol / footprint / JLCPCB search",
        ("search_symbols", "search_footprints", "search_jlcpcb_parts"),
    ),
    "tasks": (
        "Background task management",
        ("get_task_status", "list_tasks", "cleanup_tasks"),
    ),
    "advanced": (
        "Async export, autoroute, review history",
        ("export_fab_package_async", "autoroute_board", "get_review_history"),
    ),
    "router": (
        "Tool discovery + dispatch",
        ("list_tool_categories", "get_category_tools", "search_tools", "execute_tool"),
    ),
}


def _category_of(tool_name: str) -> str | None:
    for cat, (_desc, names) in CATEGORIES.items():
        if tool_name in names:
            return cat
    return None


async def _tool_index(mcp: FastMCP) -> dict[str, str]:
    """name → description for every registered tool."""
    return {t.name: (t.description or "").strip().split("\n")[0] for t in await mcp.list_tools()}


def _normalize_result(res) -> object:
    """FastMCP call_tool returns (content, structured) or a content list; prefer
    the structured payload, else fall back to text."""
    if isinstance(res, tuple) and len(res) == 2:
        _content, structured = res
        if structured is not None:
            # FastMCP wraps a non-dict return as {"result": ...}; unwrap it so the
            # caller sees the tool's actual value, not a double-nested wrapper.
            if isinstance(structured, dict) and set(structured) == {"result"}:
                return structured["result"]
            return structured
        res = _content
    if isinstance(res, list):
        texts = [getattr(c, "text", None) for c in res]
        texts = [t for t in texts if t is not None]
        return texts[0] if len(texts) == 1 else texts
    return res


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def list_tool_categories() -> list[dict]:
        """List tool categories with a description and tool count. Start here to
        navigate the tool surface."""
        return [
            {"category": cat, "description": desc, "tool_count": len(names)}
            for cat, (desc, names) in CATEGORIES.items()
        ]

    @mcp.tool()
    async def get_category_tools(category: str) -> list[dict]:
        """List the tools in a category with their one-line descriptions."""
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category '{category}'. Options: {', '.join(CATEGORIES)}.")
        index = await _tool_index(mcp)
        _desc, names = CATEGORIES[category]
        return [{"name": n, "description": index.get(n, "")} for n in names]

    @mcp.tool()
    async def search_tools(query: str) -> list[dict]:
        """Search tools by name or description substring."""
        q = query.lower()
        index = await _tool_index(mcp)
        return [
            {"name": name, "category": _category_of(name), "description": desc}
            for name, desc in index.items()
            if q in name.lower() or q in desc.lower()
        ]

    @mcp.tool()
    async def execute_tool(name: str, arguments: dict | None = None) -> dict:
        """Dispatch to any tool by name with an arguments object. Convenience for
        tools reached via the categories above."""
        index = await _tool_index(mcp)
        if name not in index:
            raise ValueError(f"Unknown tool '{name}'. Use search_tools to find one.")
        if name == "execute_tool":
            raise ValueError("Refusing to recurse execute_tool into itself.")
        res = await mcp.call_tool(name, arguments or {})
        return {"tool": name, "result": _normalize_result(res)}
