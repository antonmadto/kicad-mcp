"""Golden-file rule tests: each fixture board must produce exactly its expected
set of rule IDs — must-trigger AND must-not-trigger (PLAN.md §9).

Runs everywhere (pure parser + rules; no kicad-cli).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.review_engine.model import build_model
from kicad_mcp.review_engine.registry import run_rules

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"

# Board -> exact set of rule IDs it must produce.
EXPECTED: dict[str, set[str]] = {
    "clean_4layer": set(),  # must-not-trigger: a good stackup is silent
    "antimyth_2layer": set(),  # anti-myth: 90° corners produce ZERO findings
    # Continuous plane drawn as two ABUTTING same-net zones + a track over the
    # seam: electrically continuous copper must NOT read as a gap (R5 silent).
    "abutting_zones_4layer": set(),
    "faults_4layer": {"HARTLEY-K2", "PHIL-DEC-1", "PHIL-DFM-4", "PHIL-RTE-2", "PHIL-RTE-3"},
    "split_ground_4layer": {"HARTLEY-G1", "HARTLEY-R5"},
    "thick_cavity_4layer": {"HARTLEY-K5"},
    # Phase 4: transmission + crosstalk on a clean-stackup high-speed board.
    "highspeed_4layer": {"HARTLEY-F2", "HARTLEY-F4", "HARTLEY-C4"},
    "smps_4layer": {"PHIL-PWR-3"},
}


def _rule_ids(board: str) -> set[str]:
    pcb = REVIEW_FIXTURES / board / f"{board}.kicad_pcb"
    model = build_model(pcb)
    return {f.rule_id for f in run_rules(model)}


@pytest.mark.parametrize("board,expected", EXPECTED.items())
def test_board_findings_exact(board, expected):
    assert _rule_ids(board) == expected


def test_clean_board_is_silent():
    # The single most important trust test: a good design produces nothing.
    assert _rule_ids("clean_4layer") == set()


def test_ninety_degree_corners_produce_no_findings():
    # Anti-myth guard: the antimyth board is full of 90° track corners and must
    # yield zero findings — no corner rule may ever fire (HARTLEY-M1).
    assert _rule_ids("antimyth_2layer") == set()


def test_r5_locates_the_crossing():
    pcb = REVIEW_FIXTURES / "split_ground_4layer" / "split_ground_4layer.kicad_pcb"
    findings = run_rules(build_model(pcb))
    r5 = next(f for f in findings if f.rule_id == "HARTLEY-R5")
    assert r5.location is not None and r5.location.at is not None
    # The gap is at x≈120 (between the left zone ending at 119 and right at 121).
    assert 118 <= r5.location.at["x"] <= 122


def test_f2_critical_length_respects_design_context():
    """A slow rise time raises L_crit above the SIG1 length → F2 must go silent.
    Proves the review keys off set_design_context, not a fixed number."""
    from kicad_mcp.review_engine.model import DesignContext

    pcb = REVIEW_FIXTURES / "highspeed_4layer" / "highspeed_4layer.kicad_pcb"
    fast = {f.rule_id for f in run_rules(build_model(pcb))}
    assert "HARTLEY-F2" in fast  # 0.5 ns default → L_crit 43 mm < 59 mm

    slow = build_model(pcb, context=DesignContext(default_rise_time_ns=5.0))
    ids = {f.rule_id for f in run_rules(slow)}
    assert "HARTLEY-F2" not in ids  # 5 ns → L_crit 431 mm > 59 mm
