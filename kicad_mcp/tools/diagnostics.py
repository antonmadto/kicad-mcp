"""Diagnostics tool — the Phase-0 smoke surface and graceful-degradation view.

``get_server_status`` reports which backends are live, what capabilities are
available, and the detected KiCad version — so a user can immediately see why an
editing tool is unavailable (GUI down) while analysis/export still work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp import __version__
from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def build_status(ctx: AppContext) -> dict:
    """Pure, testable status payload (no MCP dependency)."""
    backends = ctx.backends
    summary = backends.summary()

    if backends.cli.is_available():
        try:
            summary["kicad-cli"]["version"] = backends.cli.version()
        except Exception as exc:  # surface, don't crash the status call
            summary["kicad-cli"]["version_error"] = str(exc)

    return {
        "server": "kicad-mcp",
        "version": __version__,
        "backends": summary,
        "capabilities": sorted(c.value for c in backends.available_capabilities()),
        "config": ctx.config.describe(),
    }


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def get_server_status() -> dict:
        """Report kicad-mcp backend availability, capabilities, and KiCad version.

        Use this first to see what is possible in the current environment:
        headless analysis/export (kicad-cli), schematic reads (S-expr), and live
        board editing (IPC, needs a running KiCad).
        """
        return build_status(ctx)
