"""Routing tools (Phase 3) — traces, vias, differential pairs via IPC."""

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


def _pts(points_mm: list) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in points_mm]


def route_trace_impl(
    ctx: AppContext, points_mm: list, width_mm: float, layer: str, net: str | None = None
) -> dict:
    return _ipc(ctx).route_trace(_pts(points_mm), width_mm, layer, net)


def add_via_impl(
    ctx: AppContext,
    x_mm: float,
    y_mm: float,
    size_mm: float = 0.7,
    drill_mm: float = 0.3,
    net: str | None = None,
) -> dict:
    return _ipc(ctx).add_via(x_mm, y_mm, size_mm, drill_mm, net)


def route_differential_pair_impl(
    ctx: AppContext,
    points_mm: list,
    width_mm: float,
    gap_mm: float,
    layer: str,
    net_p: str,
    net_n: str,
) -> dict:
    return _ipc(ctx).route_differential_pair(_pts(points_mm), width_mm, gap_mm, layer, net_p, net_n)


def rip_up_nets_impl(ctx: AppContext, nets: list) -> dict:
    return _ipc(ctx).rip_up_nets([str(n) for n in nets])


def rip_up_footprint_impl(ctx: AppContext, reference: str, include_shared: bool = False) -> dict:
    return _ipc(ctx).rip_up_footprint(reference, include_shared)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def route_trace(points_mm: list, width_mm: float, layer: str, net: str | None = None) -> dict:
        """Route a trace along [x, y] mm waypoints on a layer, optionally on a
        net. Multi-segment, single undo step."""
        return route_trace_impl(ctx, points_mm, width_mm, layer, net)

    @mcp.tool()
    def add_via(
        x_mm: float,
        y_mm: float,
        size_mm: float = 0.7,
        drill_mm: float = 0.3,
        net: str | None = None,
    ) -> dict:
        """Add a via at (x, y) mm. Defaults to the standard 0.7/0.3 mm geometry."""
        return add_via_impl(ctx, x_mm, y_mm, size_mm, drill_mm, net)

    @mcp.tool()
    def route_differential_pair(
        points_mm: list,
        width_mm: float,
        gap_mm: float,
        layer: str,
        net_p: str,
        net_n: str,
    ) -> dict:
        """Route a differential pair: P and N run parallel to the centerline
        waypoints, offset by (width+gap)/2 each side. Single undo step."""
        return route_differential_pair_impl(ctx, points_mm, width_mm, gap_mm, layer, net_p, net_n)

    @mcp.tool()
    def rip_up_nets(nets: list) -> dict:
        """Delete every track segment and via on the given nets — a 'rip up' for
        re-routing. Leaves pads and zones intact. One undo step. Call before
        route_differential_pair/route_trace to clear old copper."""
        return rip_up_nets_impl(ctx, nets)

    @mcp.tool()
    def rip_up_footprint(reference: str, include_shared: bool = False) -> dict:
        """Rip up the tracks/vias on a footprint's local nets so the part can be
        moved and re-routed. Nets shared across many footprints (GND, power) are
        skipped unless include_shared=True, so a plane/pour is never torn up.
        Leaves pads and zones intact. One undo step."""
        return rip_up_footprint_impl(ctx, reference, include_shared)
