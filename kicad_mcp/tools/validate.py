"""ERC / DRC tools (kicad-cli backend, Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.backends import Capability
from kicad_mcp.context import AppContext

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def run_erc_impl(ctx: AppContext, project: str) -> dict:
    sch = resolve(ctx, project).require_schematic()
    cli = ctx.backends.require(Capability.VERIFY)
    return cli.run_erc(sch)


def run_drc_impl(ctx: AppContext, project: str) -> dict:
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    cli = ctx.backends.require(Capability.VERIFY)
    report = cli.run_drc(pcb)
    from kicad_mcp import history

    history.record(proj.directory, "drc", {"total": report["total"], "counts": report["counts"]})
    return report


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def run_erc(project: str) -> dict:
        """Run Electrical Rules Check on the schematic; return normalized findings."""
        return run_erc_impl(ctx, project)

    @mcp.tool()
    def run_drc(project: str) -> dict:
        """Run Design Rules Check on the board; return normalized findings."""
        return run_drc_impl(ctx, project)
