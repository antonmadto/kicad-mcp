"""HARTLEY-Z1 controlled-impedance rule (model-injected DesignContext).

Precedent: test_golden.py::test_f2_critical_length_respects_design_context — the
rule keys strictly off set_design_context targets, never an invented number.
"""

from __future__ import annotations

from pathlib import Path

from kicad_mcp.review_engine import impedance as imp
from kicad_mcp.review_engine.model import (
    CopperLayer,
    DesignContext,
    DesignModel,
    Net,
    Track,
    build_model,
)
from kicad_mcp.review_engine.registry import run_rules

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"
HIGHSPEED = REVIEW_FIXTURES / "highspeed_4layer" / "highspeed_4layer.kicad_pcb"


def _z1(model: DesignModel):
    return [f for f in run_rules(model) if f.rule_id == "HARTLEY-Z1"]


def _computed(pcb, key: str) -> float:
    """The routed Z0/Z_diff the rule will see for ``key`` (target value is irrelevant)."""
    m = build_model(pcb, context=DesignContext(target_impedances={key: 1.0}))
    a = imp.analyze_model(m)
    v = next(v for v in a.verdicts if v.key == key)
    return v.computed_ohms


def test_z1_absent_without_targets():
    # Anti-myth invariant: no declared targets → the rule invents nothing.
    assert _z1(build_model(HIGHSPEED)) == []


def test_z1_warns_when_far_off_target():
    model = build_model(HIGHSPEED, context=DesignContext(target_impedances={"SIG1": 50.0}))
    findings = _z1(model)
    assert len(findings) == 1
    assert findings[0].severity.value == "warning"  # SIG1 ≈104 Ω, >10% off 50 Ω
    assert findings[0].location is not None and findings[0].location.net == "SIG1"


def test_z1_silent_on_target():
    # Set the target to the net's own computed Z0 → within ±5% → pass → silent.
    z0 = _computed(HIGHSPEED, "SIG1")
    model = build_model(HIGHSPEED, context=DesignContext(target_impedances={"SIG1": z0}))
    assert _z1(model) == []


def test_z1_info_tier_when_slightly_off():
    # A target ~7% below the computed Z0 → 5–10% band → INFO, not WARNING.
    z0 = _computed(HIGHSPEED, "SIG1")
    target = z0 / 1.07
    model = build_model(HIGHSPEED, context=DesignContext(target_impedances={"SIG1": target}))
    findings = _z1(model)
    assert len(findings) == 1
    assert findings[0].severity.value == "info"


def test_z1_fires_on_differential():
    model = build_model(HIGHSPEED, context=DesignContext(target_impedances={"USB_D": 90.0}))
    findings = _z1(model)
    assert len(findings) == 1  # Z_diff ≈136 Ω, >10% off 90 Ω
    assert "differential" in findings[0].message
    assert findings[0].severity.value == "warning"


def test_z1_silent_on_low_confidence_no_plane():
    # A signal with no reference plane → Z0 undefined → 'unknown' → never a FAIL,
    # even with a declared target (a guessed number must not produce a failure).
    layers = [CopperLayer("F.Cu", 0, "signal"), CopperLayer("B.Cu", 1, "signal")]
    model = DesignModel(
        source="t",
        stackup=[],
        copper_layers=layers,
        nets={3: Net(3, "SIG1", "signal")},
        footprints=[],
        tracks=[Track((0, 0), (30, 0), 0.2, "F.Cu", 3)],
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=DesignContext(target_impedances={"SIG1": 50.0}),
    )
    assert _z1(model) == []


def test_z1_matches_target_key_with_leading_slash():
    # '/SIG1' and 'SIG1' must compare equal (net-name normalization).
    model = build_model(HIGHSPEED, context=DesignContext(target_impedances={"/SIG1": 50.0}))
    findings = _z1(model)
    assert len(findings) == 1
    assert findings[0].location.net == "SIG1"
