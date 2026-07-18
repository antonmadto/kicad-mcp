"""Crosstalk C4 anti-myth regressions (Phase-4-6 correctness review).

A grounded guard/return trace deliberately run beside a differential pair must
NEVER be reported as a crosstalk aggressor (CLAUDE.md anti-myth guarantee), and a
real signal aggressor must yield ONE finding per pair, not one per leg.
"""

from __future__ import annotations

from kicad_mcp.review_engine.model import (
    CopperLayer,
    DesignContext,
    DesignModel,
    Net,
    Track,
    classify_net,
)
from kicad_mcp.review_engine.registry import run_rules


def _model(tracks: list[Track], names_by_code: dict[int, str]) -> DesignModel:
    nets = {code: Net(code, name, classify_net(name)) for code, name in names_by_code.items()}
    return DesignModel(
        source="t",
        stackup=[],
        # F.Cu 0.2 mm above the reference → 3×H keepout = 0.6 mm.
        copper_layers=[
            CopperLayer("F.Cu", 0, "signal", dielectric_to_next_mm=0.2),
            CopperLayer("In1.Cu", 1, "ground_plane"),
        ],
        nets=nets,
        footprints=[],
        tracks=tracks,
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=DesignContext(),
    )


# Diff pair USB_DP/USB_DM on F.Cu, 1 mm apart, 30 mm long.
_PAIR = [
    Track((0, 10), (30, 10), 0.2, "F.Cu", 1),  # USB_DP
    Track((0, 11), (30, 11), 0.2, "F.Cu", 2),  # USB_DM
]
_NAMES = {1: "USB_DP", 2: "USB_DM", 3: "GND", 4: "AGGR"}


def _c4(model: DesignModel):
    return [f for f in run_rules(model, "crosstalk") if f.rule_id == "HARTLEY-C4"]


def test_grounded_guard_trace_is_not_a_c4_aggressor():
    # GND guard 0.5 mm from the pair (< 0.6 mm keepout) — must not fire (anti-myth).
    guard = Track((0, 9.5), (30, 9.5), 0.2, "F.Cu", 3)
    assert _c4(_model(_PAIR + [guard], _NAMES)) == []


def test_signal_aggressor_fires_exactly_once():
    # AGGR (signal) between the legs, 0.5 mm from each; GND guard also present.
    # One finding per (aggressor, pair) — not one per leg — and never for GND.
    guard = Track((0, 9.5), (30, 9.5), 0.2, "F.Cu", 3)
    aggr = Track((0, 10.5), (30, 10.5), 0.2, "F.Cu", 4)
    findings = _c4(_model(_PAIR + [guard, aggr], _NAMES))
    assert len(findings) == 1
    assert "AGGR" in findings[0].message and "GND" not in findings[0].message
