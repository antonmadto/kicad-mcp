"""Library / parts tools (Phase 5): symbol + footprint + JLCPCB search."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.backends import library as lib
from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _env(ctx: AppContext) -> dict:
    import os

    return dict(os.environ)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def search_symbols(query: str, limit: int = 40) -> list[dict]:
        """Search installed KiCad symbol libraries; returns Lib:Symbol ids."""
        return lib.search_symbols(query, env=_env(ctx), limit=limit)

    @mcp.tool()
    def search_footprints(query: str, limit: int = 40) -> list[dict]:
        """Search installed KiCad footprint libraries; returns Lib:Footprint ids."""
        return lib.search_footprints(query, env=_env(ctx), limit=limit)

    @mcp.tool()
    def search_jlcpcb_parts(query: str, basic_only: bool = False, limit: int = 20) -> list[dict]:
        """Search a local JLCPCB parts DB by MPN/description. Needs
        KICAD_MCP_JLCPCB_DB set to a jlcparts-style SQLite database."""
        return lib.search_jlcpcb_parts(query, env=_env(ctx), basic_only=basic_only, limit=limit)
