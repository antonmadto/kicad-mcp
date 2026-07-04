"""Schematic editing tools (Phase 5, EXPERIMENTAL, feature-flagged).

Gated behind ``KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1``. Every write goes through the
S-expr layer's transactional pipeline: file must be closed in KiCad, the edit is
re-parsed (rolled back on corruption), and ``kicad-cli sch erc`` is re-run and
reported. There is no schematic IPC API in KiCad 9/10, so this is the only path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.backends import Capability
from kicad_mcp.context import AppContext

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _writable_sch(ctx: AppContext, project: str):
    """Resolve the schematic and confirm the write capability is available."""
    sch = resolve(ctx, project).require_schematic()
    ctx.backends.require(Capability.WRITE_SCHEMATIC)  # raises actionable error if off
    return sch


def set_symbol_property_impl(
    ctx: AppContext, project: str, reference: str, property: str, value: str
) -> dict:
    sch = _writable_sch(ctx, project)
    return ctx.backends.sexpr.set_symbol_property(
        sch, reference, property, value, cli_backend=ctx.backends.cli
    )


def duplicate_symbol_impl(
    ctx: AppContext,
    project: str,
    reference: str,
    new_reference: str,
    dx_mm: float = 12.7,
    dy_mm: float = 0.0,
) -> dict:
    sch = _writable_sch(ctx, project)
    return ctx.backends.sexpr.duplicate_symbol(
        sch, reference, new_reference, dx_mm, dy_mm, cli_backend=ctx.backends.cli
    )


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def set_symbol_property(project: str, reference: str, property: str, value: str) -> dict:
        """[EXPERIMENTAL] Set a property (Value, Footprint, ...) on an existing
        schematic symbol. Requires KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1 and the file
        closed in KiCad. Returns the post-edit ERC report."""
        return set_symbol_property_impl(ctx, project, reference, property, value)

    @mcp.tool()
    def duplicate_symbol(
        project: str,
        reference: str,
        new_reference: str,
        dx_mm: float = 12.7,
        dy_mm: float = 0.0,
    ) -> dict:
        """[EXPERIMENTAL] Clone a placed symbol with a new reference, offset by
        (dx, dy) mm. Fresh UUIDs; the new part's pins start unconnected. Requires
        KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1 and the file closed in KiCad."""
        return duplicate_symbol_impl(ctx, project, reference, new_reference, dx_mm, dy_mm)
