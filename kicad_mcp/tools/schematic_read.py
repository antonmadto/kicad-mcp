"""Schematic read tools: components (S-expr) and nets/tracing (cli netlist)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext
from kicad_mcp.utils.netlist import parse_netlist

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def list_components_impl(ctx: AppContext, project: str) -> list[dict]:
    sch = resolve(ctx, project).require_schematic()
    return ctx.backends.sexpr.read_components(sch)


def _netlist(ctx: AppContext, project: str) -> dict:
    """Export a kicadxml netlist to a temp file and parse it."""
    sch = resolve(ctx, project).require_schematic()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "netlist.xml"
        ctx.backends.cli.export_netlist(sch, out, fmt="kicadxml")
        return parse_netlist(out)


def list_nets_impl(ctx: AppContext, project: str) -> list[dict]:
    nets = _netlist(ctx, project)["nets"]
    # Drop the node detail for the summary listing; keep name + fan-out.
    return [{"code": n["code"], "name": n["name"], "node_count": n["node_count"]} for n in nets]


def trace_net_impl(ctx: AppContext, project: str, net: str) -> dict:
    # KiCad prefixes local labels with their sheet path (e.g. "/N1"); accept the
    # bare name too so callers don't have to know the hierarchy.
    wanted = net.lstrip("/")
    for n in _netlist(ctx, project)["nets"]:
        name = n["name"] or ""
        if name == net or name.lstrip("/") == wanted or n["code"] == net:
            return n
    raise ValueError(f"Net '{net}' not found in project.")


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def list_schematic_components(project: str) -> list[dict]:
        """List schematic components (reference, value, lib_id, footprint)."""
        return list_components_impl(ctx, project)

    @mcp.tool()
    def list_schematic_nets(project: str) -> list[dict]:
        """List nets with their fan-out (node count), from the exported netlist."""
        return list_nets_impl(ctx, project)

    @mcp.tool()
    def trace_net(project: str, net: str) -> dict:
        """Show every pin (ref + pin number/function) connected to a given net."""
        return trace_net_impl(ctx, project, net)
