"""Board read tools: layer/stackup/net summary (S-expr backend, Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def get_board_info_impl(ctx: AppContext, project: str) -> dict:
    pcb = resolve(ctx, project).require_board()
    info = ctx.backends.sexpr.read_board_info(pcb)
    info["board"] = str(pcb)
    return info


def get_board_stackup_impl(ctx: AppContext, project: str) -> dict:
    pcb = resolve(ctx, project).require_board()
    return {"board": str(pcb), "stackup": ctx.backends.sexpr.read_stackup(pcb)}


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def get_board_info(project: str) -> dict:
        """Summarize a board: copper layers, thickness, nets, footprints, extents."""
        return get_board_info_impl(ctx, project)

    @mcp.tool()
    def get_board_stackup(project: str) -> dict:
        """Ordered physical stackup (dielectric + copper layers with thickness)."""
        return get_board_stackup_impl(ctx, project)
