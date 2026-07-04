"""Live board editing tools (Phase 3) — footprints, zones, save, status.

All mutation goes through the IPC backend (kipy) with commit wrapping; when the
GUI is down every tool returns the actionable graceful-degradation error from
``Backends.require`` instead of touching files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.backends import Capability, IpcBackend
from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _ipc(ctx: AppContext) -> IpcBackend:
    backend = ctx.backends.require(Capability.EDIT_BOARD)
    assert isinstance(backend, IpcBackend)  # noqa: S101 - factory routing invariant
    return backend


def get_live_board_status_impl(ctx: AppContext) -> dict:
    return _ipc(ctx).board_status()


def list_live_footprints_impl(ctx: AppContext) -> list[dict]:
    return _ipc(ctx).list_footprints()


def move_footprint_impl(ctx: AppContext, reference: str, x_mm: float, y_mm: float) -> dict:
    return _ipc(ctx).move_footprint(reference, x_mm, y_mm)


def rotate_footprint_impl(ctx: AppContext, reference: str, degrees: float) -> dict:
    return _ipc(ctx).rotate_footprint(reference, degrees)


def duplicate_footprint_impl(
    ctx: AppContext,
    reference: str,
    new_reference: str,
    x_mm: float | None = None,
    y_mm: float | None = None,
) -> dict:
    return _ipc(ctx).duplicate_footprint(reference, new_reference, x_mm, y_mm)


def get_netclasses_impl(ctx: AppContext) -> list[dict]:
    return _ipc(ctx).get_netclasses()


def add_zone_impl(ctx: AppContext, layer: str, polygon_mm: list, net: str | None = None) -> dict:
    pts = [(float(p[0]), float(p[1])) for p in polygon_mm]
    return _ipc(ctx).add_zone(layer, pts, net)


def refill_zones_impl(ctx: AppContext) -> dict:
    return _ipc(ctx).refill_zones()


def save_board_impl(ctx: AppContext) -> dict:
    return _ipc(ctx).save_board()


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def get_live_board_status() -> dict:
        """Status of the board open in the running KiCad (via IPC): item counts,
        layers, KiCad version. Requires the GUI with the API enabled."""
        return get_live_board_status_impl(ctx)

    @mcp.tool()
    def list_live_footprints() -> list[dict]:
        """List footprints on the live board with position/rotation/layer."""
        return list_live_footprints_impl(ctx)

    @mcp.tool()
    def move_footprint(reference: str, x_mm: float, y_mm: float) -> dict:
        """Move a footprint to (x, y) in mm on the live board. Single undo step."""
        return move_footprint_impl(ctx, reference, x_mm, y_mm)

    @mcp.tool()
    def rotate_footprint(reference: str, degrees: float) -> dict:
        """Set a footprint's rotation in degrees on the live board. Single undo step."""
        return rotate_footprint_impl(ctx, reference, degrees)

    @mcp.tool()
    def duplicate_footprint(
        reference: str,
        new_reference: str,
        x_mm: float | None = None,
        y_mm: float | None = None,
    ) -> dict:
        """Copy a placed footprint to a new reference + position (KiCad 9 IPC
        cannot place from a library, so cloning an on-board part is the supported
        'add a part'). Give x_mm/y_mm for an absolute spot, else it offsets."""
        return duplicate_footprint_impl(ctx, reference, new_reference, x_mm, y_mm)

    @mcp.tool()
    def get_netclasses() -> dict | list:
        """List netclasses on the live board with their track/clearance/via/diff-
        pair constraints and member nets."""
        return get_netclasses_impl(ctx)

    @mcp.tool()
    def add_zone(layer: str, polygon_mm: list, net: str | None = None) -> dict:
        """Add a copper zone on a layer from a polygon of [x, y] mm points,
        optionally assigned to a net (e.g. GND). Single undo step."""
        return add_zone_impl(ctx, layer, polygon_mm, net)

    @mcp.tool()
    def refill_zones() -> dict:
        """Refill all copper zones on the live board."""
        return refill_zones_impl(ctx)

    @mcp.tool()
    def save_board() -> dict:
        """Save the live board to disk — required before render_board / run_drc
        can see live edits (they read the file)."""
        return save_board_impl(ctx)
