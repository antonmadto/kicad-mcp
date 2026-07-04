"""Export tools: gerbers, drill, BOM, netlist, STEP, render, and fab package.

All outputs are confined to the project roots. ``export_fab_package`` bundles a
JLCPCB-style set (gerbers + drill + BOM + CPL) into a single zip.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_mcp.backends import Capability
from kicad_mcp.context import AppContext

from ._common import confine_output, resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _default_output(ctx: AppContext, project: str, leaf: str) -> Path:
    proj = resolve(ctx, project)
    return confine_output(ctx, proj.directory / leaf)


def export_gerbers_impl(ctx: AppContext, project: str, output_dir: str | None = None) -> dict:
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    cli = ctx.backends.require(Capability.EXPORT)
    out_dir = confine_output(ctx, output_dir or proj.directory / "gerbers")
    files = cli.export_gerbers(pcb, out_dir)
    files += cli.export_drill(pcb, out_dir)
    return {"output_dir": str(out_dir), "files": [str(f) for f in sorted(files)]}


def export_bom_impl(ctx: AppContext, project: str, output: str | None = None) -> dict:
    proj = resolve(ctx, project)
    sch = proj.require_schematic()
    cli = ctx.backends.require(Capability.EXPORT)
    out = confine_output(ctx, output or proj.directory / f"{proj.name}_BOM.csv")
    return {"output": str(cli.export_bom(sch, out))}


def export_netlist_impl(ctx: AppContext, project: str, output: str | None = None) -> dict:
    proj = resolve(ctx, project)
    sch = proj.require_schematic()
    cli = ctx.backends.require(Capability.EXPORT)
    out = confine_output(ctx, output or proj.directory / f"{proj.name}.net")
    return {"output": str(cli.export_netlist(sch, out))}


def export_step_impl(ctx: AppContext, project: str, output: str | None = None) -> dict:
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    cli = ctx.backends.require(Capability.EXPORT)
    out = confine_output(ctx, output or proj.directory / f"{proj.name}.step")
    return {"output": str(cli.export_step(pcb, out))}


def render_board_impl(
    ctx: AppContext, project: str, output: str | None = None, side: str = "top"
) -> dict:
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    cli = ctx.backends.require(Capability.EXPORT)
    out = confine_output(ctx, output or proj.directory / f"{proj.name}_{side}.png")
    return {"output": str(cli.render_board(pcb, out, side=side))}


def export_fab_package_impl(ctx: AppContext, project: str, output: str | None = None) -> dict:
    """Bundle gerbers + drill + BOM + CPL into a single fab zip."""
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    cli = ctx.backends.require(Capability.EXPORT)
    out_zip = confine_output(ctx, output or proj.directory / f"{proj.name}_fab.zip")

    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        gerber_dir = stage / "gerbers"
        cli.export_gerbers(pcb, gerber_dir)
        cli.export_drill(pcb, gerber_dir)
        cli.export_pos(pcb, stage / f"{proj.name}_CPL.csv")
        if proj.sch and proj.sch.exists():
            cli.export_bom(proj.sch, stage / f"{proj.name}_BOM.csv")

        members = sorted(p for p in stage.rglob("*") if p.is_file())
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for member in members:
                zf.write(member, member.relative_to(stage))
        manifest = [str(member.relative_to(stage)) for member in members]

    return {"output": str(out_zip), "file_count": len(manifest), "files": manifest}


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def export_gerbers(project: str, output_dir: str | None = None) -> dict:
        """Plot gerbers + drill files for the board into a directory."""
        return export_gerbers_impl(ctx, project, output_dir)

    @mcp.tool()
    def export_bom(project: str, output: str | None = None) -> dict:
        """Export the schematic Bill of Materials as CSV."""
        return export_bom_impl(ctx, project, output)

    @mcp.tool()
    def export_netlist(project: str, output: str | None = None) -> dict:
        """Export the schematic netlist (KiCad s-expression format)."""
        return export_netlist_impl(ctx, project, output)

    @mcp.tool()
    def export_step(project: str, output: str | None = None) -> dict:
        """Export a STEP 3D model of the board."""
        return export_step_impl(ctx, project, output)

    @mcp.tool()
    def render_board(project: str, output: str | None = None, side: str = "top") -> dict:
        """Render a 3D PNG of the board from a side (top/bottom/left/right/front/back)."""
        return render_board_impl(ctx, project, output, side)

    @mcp.tool()
    def export_fab_package(project: str, output: str | None = None) -> dict:
        """Bundle a complete fab package (gerbers + drill + BOM + CPL) into a zip."""
        return export_fab_package_impl(ctx, project, output)
