"""Model-extraction tests: reference-plane discovery, dielectric span, diff spacing."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.review_engine import impedance as imp
from kicad_mcp.review_engine.model import (
    CopperLayer,
    DesignContext,
    DesignModel,
    Net,
    PhysicalLayer,
    Track,
    build_model,
)

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"


def _pcb(name: str) -> Path:
    return REVIEW_FIXTURES / name / f"{name}.kicad_pcb"


def _mk(copper_layers, *, stackup=None, tracks=None, nets=None) -> DesignModel:
    return DesignModel(
        source="t",
        stackup=stackup or [],
        copper_layers=copper_layers,
        nets=nets or {},
        footprints=[],
        tracks=tracks or [],
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=DesignContext(),
    )


def test_reference_planes_top_signal_is_microstrip():
    m = build_model(_pcb("highspeed_4layer"))
    above, below = imp.reference_planes(m, "F.Cu")
    assert above is None
    assert below is not None and below.name == "In1.Cu" and below.role == "ground_plane"


def test_reference_planes_between_planes_is_stripline():
    # Signal at index 2 has a ground plane above (In1) and a power plane two down (In4).
    layers = [
        CopperLayer("F.Cu", 0, "signal"),
        CopperLayer("In1.Cu", 1, "ground_plane"),
        CopperLayer("In2.Cu", 2, "signal"),
        CopperLayer("In3.Cu", 3, "signal"),
        CopperLayer("In4.Cu", 4, "power_plane"),
        CopperLayer("B.Cu", 5, "signal"),
    ]
    above, below = imp.reference_planes(_mk(layers), "In2.Cu")
    assert above is not None and below is not None
    assert above.name == "In1.Cu" and below.name == "In4.Cu"


def test_reference_planes_no_plane():
    layers = [CopperLayer("F.Cu", 0, "signal"), CopperLayer("B.Cu", 1, "signal")]
    assert imp.reference_planes(_mk(layers), "F.Cu") == (None, None)


def test_reference_planes_on_a_plane_layer_returns_none():
    layers = [CopperLayer("F.Cu", 0, "signal"), CopperLayer("In1.Cu", 1, "ground_plane")]
    assert imp.reference_planes(_mk(layers), "In1.Cu") == (None, None)


def test_dielectric_span_clean_4layer():
    m = build_model(_pcb("clean_4layer"))
    thick, er = imp._dielectric_span(m, "F.Cu", "In1.Cu")
    assert thick == pytest.approx(0.6)
    assert er == pytest.approx(4.5)


def test_dielectric_span_full_plane_to_plane():
    m = build_model(_pcb("clean_4layer"))
    # In1(GND) → In2(PWR) is the tight 0.2 mm core.
    thick, er = imp._dielectric_span(m, "In1.Cu", "In2.Cu")
    assert thick == pytest.approx(0.2)
    assert er == pytest.approx(4.5)


def test_dielectric_span_thickness_weighted_er():
    stackup = [
        PhysicalLayer("F.Cu", "copper", 0.035, True),
        PhysicalLayer("prepreg", "prepreg", 0.1, False, epsilon_r=4.0),
        PhysicalLayer("core", "core", 0.3, False, epsilon_r=4.6),
        PhysicalLayer("In1.Cu", "copper", 0.035, True),
    ]
    thick, er = imp._dielectric_span(_mk([], stackup=stackup), "F.Cu", "In1.Cu")
    assert thick == pytest.approx(0.4)
    # (4.0*0.1 + 4.6*0.3) / 0.4 = 4.45
    assert er == pytest.approx(4.45)


def test_diff_spacing_highspeed():
    m = build_model(_pcb("highspeed_4layer"))
    # USB_D+ = net 4, USB_D- = net 5; centreline separation 0.4 mm.
    perp = imp.diff_spacing_mm(m, 4, 5, "F.Cu")
    assert perp == pytest.approx(0.4, abs=0.01)


def test_diff_spacing_none_without_sustained_run():
    # Two short crossing stubs never accumulate the 5 mm overlap gate → None.
    tracks = [
        Track((0, 0), (1, 0), 0.2, "F.Cu", 4),
        Track((0, 0.4), (1, 0.4), 0.2, "F.Cu", 5),
    ]
    m = _mk(
        [CopperLayer("F.Cu", 0, "signal")],
        tracks=tracks,
        nets={4: Net(4, "D_P", "diff"), 5: Net(5, "D_N", "diff")},
    )
    assert imp.diff_spacing_mm(m, 4, 5, "F.Cu") is None


def test_trace_configs_groups_by_layer_width():
    m = build_model(_pcb("highspeed_4layer"))
    configs = imp.trace_configs(m)
    fcu = [c for c in configs if c.layer == "F.Cu" and c.width_mm == pytest.approx(0.2)]
    assert len(fcu) == 1  # SIG1 + USB pair + AGGR all share F.Cu 0.2 mm
    assert set(fcu[0].net_codes) == {3, 4, 5, 6}


def test_analyze_config_microstrip_clean():
    m = build_model(_pcb("clean_4layer"))
    cfg = next(c for c in imp.trace_configs(m) if c.layer == "F.Cu")
    r = imp.analyze_config(m, cfg)
    assert r.model == "microstrip"
    assert r.confidence == "high"
    assert 60 <= r.z0_ohms <= 90  # realistic outer-layer Z0
    assert r.inputs["H_mm"] == pytest.approx(0.6)
    assert r.inputs["er"] == pytest.approx(4.5)
