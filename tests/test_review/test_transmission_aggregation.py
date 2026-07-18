"""HARTLEY-F2 aggregation under an assumed vs declared rise time (Package E, E1).

A real board routes hundreds of signal nets past the critical length for the 0.5 ns
DEFAULT edge rate. Warning per net floods the review with false positives when the
user never declared a rise time — so F2 summarizes as ONE INFO until a real rise
time is set, then reverts to per-net WARNINGs.
"""

from __future__ import annotations

from kicad_mcp.review_engine.model import (
    DesignContext,
    DesignModel,
    Net,
    Track,
    classify_net,
)
from kicad_mcp.review_engine.registry import run_rules

# Three signal nets each routed ~60 mm on F.Cu — over the ~41 mm L_crit for 0.5 ns.
_TRACKS = [
    Track((0, 0), (60, 0), 0.2, "F.Cu", 1),
    Track((0, 5), (60, 5), 0.2, "F.Cu", 2),
    Track((0, 10), (60, 10), 0.2, "F.Cu", 3),
]
_NAMES = {1: "SIG1", 2: "SIG2", 3: "SIG3"}


def _model(context: DesignContext) -> DesignModel:
    nets = {c: Net(c, n, classify_net(n)) for c, n in _NAMES.items()}
    return DesignModel(
        source="t",
        stackup=[],
        copper_layers=[],
        nets=nets,
        footprints=[],
        tracks=_TRACKS,
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=context,
    )


def _f2(model: DesignModel):
    return [f for f in run_rules(model, "transmission") if f.rule_id == "HARTLEY-F2"]


def test_f2_default_context_aggregates_to_one_info():
    # Default context (rise time not declared): exactly one INFO naming the count.
    findings = _f2(_model(DesignContext()))
    assert len(findings) == 1
    assert findings[0].severity.value == "info"
    assert "3 signal net" in findings[0].message


def test_f2_explicit_context_is_per_net_warning():
    ctx = DesignContext(default_rise_time_ns=0.5, rise_time_explicit=True)
    findings = _f2(_model(ctx))
    assert len(findings) == 3
    assert all(f.severity.value == "warning" for f in findings)
    assert {f.location.net for f in findings} == {"SIG1", "SIG2", "SIG3"}
