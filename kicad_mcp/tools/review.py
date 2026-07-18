"""Review-engine tools (Phase 2): review_design, review_topic, set_design_context.

The differentiator. Builds the normalized model from the board (+ schematic +
design context) and runs the cited Hartley/Phil rule catalog against it.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext
from kicad_mcp.review_engine.model import DesignContext, DesignModel, build_model
from kicad_mcp.review_engine.registry import TOPICS, run_rules
from kicad_mcp.review_engine.report import build_report
from kicad_mcp.utils.netlist import parse_netlist

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _schematic_netlist(ctx: AppContext, sch_path) -> dict | None:
    """Export + parse the schematic netlist for connectivity, if cli is available."""
    if not ctx.backends.cli.is_available():
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "netlist.xml"
            ctx.backends.cli.export_netlist(sch_path, out, fmt="kicadxml")
            return parse_netlist(out)
    except Exception:
        return None  # netlist is an enrichment; never block the board review on it


def _build_model(ctx: AppContext, project: str) -> DesignModel:
    proj = resolve(ctx, project)
    pcb = proj.require_board()
    board_info = ctx.backends.sexpr.read_board_info(pcb)
    components = []
    netlist = None
    if proj.sch and proj.sch.exists():
        components = ctx.backends.sexpr.read_components(proj.sch)
        netlist = _schematic_netlist(ctx, proj.sch)
    context = ctx.design_contexts.get(str(pcb)) or DesignContext()
    return build_model(
        pcb, context=context, components=components, board_info=board_info, netlist=netlist
    )


def review_design_impl(ctx: AppContext, project: str) -> dict:
    model = _build_model(ctx, project)
    findings = run_rules(model)
    report = build_report(findings, source=model.source).to_dict()
    from kicad_mcp import history

    history.record(
        resolve(ctx, project).directory,
        "review",
        {"total": report["total"], "counts": report["counts"]},
    )
    return report


def review_topic_impl(ctx: AppContext, project: str, topic: str) -> dict:
    if topic not in TOPICS:
        raise ValueError(f"Unknown topic '{topic}'. Choose from: {', '.join(TOPICS)}.")
    model = _build_model(ctx, project)
    findings = run_rules(model, topic)
    return build_report(findings, source=model.source, topic=topic).to_dict()


def set_design_context_impl(
    ctx: AppContext,
    project: str,
    *,
    rise_time_ns: float | None = None,
    clock_frequencies_hz: dict | None = None,
    target_impedances: dict | None = None,
    connector_nets: list | None = None,
    fab_house: str | None = None,
) -> dict:
    if rise_time_ns is not None and not (math.isfinite(rise_time_ns) and rise_time_ns > 0):
        # f_knee_hz = 0.5 / (rise_time_ns * 1e-9): zero divides by zero, and a
        # negative value silently flips HARTLEY-F2's critical length negative,
        # flooding every routed net with false-positive warnings downstream.
        raise ValueError(
            f"rise_time_ns must be a positive finite number of nanoseconds, got {rise_time_ns!r}."
        )
    proj = resolve(ctx, project)
    pcb = str(proj.require_board())
    current = ctx.design_contexts.get(pcb) or DesignContext()
    updated = DesignContext(
        default_rise_time_ns=(
            rise_time_ns if rise_time_ns is not None else current.default_rise_time_ns
        ),
        clocks_hz=clock_frequencies_hz if clock_frequencies_hz is not None else current.clocks_hz,
        target_impedances=(
            target_impedances if target_impedances is not None else current.target_impedances
        ),
        connector_nets=connector_nets if connector_nets is not None else current.connector_nets,
        fab_house=fab_house if fab_house is not None else current.fab_house,
    )
    ctx.design_contexts[pcb] = updated
    return {
        "project": proj.name,
        "context": {
            "rise_time_ns": updated.default_rise_time_ns,
            "f_knee_hz": updated.f_knee_hz,
            "clock_frequencies_hz": updated.clocks_hz,
            "target_impedances": updated.target_impedances,
            "connector_nets": updated.connector_nets,
            "fab_house": updated.fab_house,
        },
    }


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def review_design(project: str) -> dict:
        """Audit a board against the full Hartley/Phil's Lab rule catalog.

        Returns findings grouped by severity with rule IDs, one-line physics
        rationales, and citations, plus a markdown summary.
        """
        return review_design_impl(ctx, project)

    @mcp.tool()
    def review_topic(project: str, topic: str) -> dict:
        """Audit one rule family: stackup, grounding, return_path, decoupling, dfm,
        transmission, crosstalk, smps, subcircuits, connectors.
        """
        # Kept in sync with review_engine.registry.TOPICS by
        # test_review_tools::test_review_topic_docstring_lists_all_topics.
        return review_topic_impl(ctx, project, topic)

    @mcp.tool()
    def set_design_context(
        project: str,
        rise_time_ns: float | None = None,
        clock_frequencies_hz: dict | None = None,
        target_impedances: dict | None = None,
        connector_nets: list | None = None,
        fab_house: str | None = None,
    ) -> dict:
        """Provide facts the files cannot contain (rise times, clocks, target
        impedances, connector-facing nets, fab house) to sharpen the review."""
        return set_design_context_impl(
            ctx,
            project,
            rise_time_ns=rise_time_ns,
            clock_frequencies_hz=clock_frequencies_hz,
            target_impedances=target_impedances,
            connector_nets=connector_nets,
            fab_house=fab_house,
        )
