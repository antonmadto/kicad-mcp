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


def coerce_points(points_mm: list, item: str = "point") -> list[tuple[float, float]]:
    """Coerce caller-supplied waypoints to float ``(x, y)`` pairs, shape-checked.

    LLM callers commonly flatten to ``[x0, y0, x1, y1]`` or pass ``{"x", "y"}``
    objects instead of ``[[x0, y0], ...]``; without a check those surface as a
    bare IndexError/KeyError/TypeError with no hint of the expected shape. Raise
    one actionable ValueError naming the offending index instead.
    """
    pts: list[tuple[float, float]] = []
    for i, p in enumerate(points_mm):
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, KeyError, IndexError, ValueError):
            raise ValueError(f"{item} {i} must be [x_mm, y_mm], got {p!r}") from None
        pts.append((x, y))
    return pts


def route_trace_impl(
    ctx: AppContext, points_mm: list, width_mm: float, layer: str, net: str | None = None
) -> dict:
    return _ipc(ctx).route_trace(coerce_points(points_mm), width_mm, layer, net)


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
    return _ipc(ctx).route_differential_pair(
        coerce_points(points_mm), width_mm, gap_mm, layer, net_p, net_n
    )


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
