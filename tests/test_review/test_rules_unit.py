"""Per-rule edge cases on hand-built models (not easily expressed as a fixture)."""

from __future__ import annotations

from kicad_mcp.review_engine.model import CopperLayer, DesignContext, DesignModel, Net
from kicad_mcp.review_engine.registry import run_rules


def mk_model(*, copper_layers=None, nets=None, extents="default", footprints=None) -> DesignModel:
    if extents == "default":
        extents = {
            "min_x": 100,
            "min_y": 100,
            "max_x": 140,
            "max_y": 130,
            "width": 40,
            "height": 30,
        }
    return DesignModel(
        source="test",
        stackup=[],
        copper_layers=copper_layers or [],
        nets=nets or {},
        footprints=footprints or [],
        tracks=[],
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=extents,
        context=DesignContext(),
    )


def _ids(model, topic=None):
    return {f.rule_id for f in run_rules(model, topic)}


def _cu(name, i, role, **kw):
    return CopperLayer(name=name, stack_index=i, role=role, **kw)


def test_dfm4_no_outline_is_error():
    model = mk_model(extents=None, footprints=[])
    findings = [f for f in run_rules(model, "dfm") if f.rule_id == "PHIL-DFM-4"]
    assert any(f.severity.value == "error" and "outline" in f.message.lower() for f in findings)


def test_k5_non_adjacent_planes_flagged():
    # power and ground planes both present but separated by a signal layer.
    layers = [
        _cu("F.Cu", 0, "signal"),
        _cu("In1.Cu", 1, "power_plane"),
        _cu("In2.Cu", 2, "signal"),
        _cu("B.Cu", 3, "ground_plane"),
    ]
    assert "HARTLEY-K5" in _ids(mk_model(copper_layers=layers), "stackup")


def test_k5_adjacent_tight_pair_passes():
    layers = [
        _cu("F.Cu", 0, "signal"),
        _cu("In1.Cu", 1, "ground_plane", dielectric_to_next_mm=0.2),
        _cu("In2.Cu", 2, "power_plane"),
        _cu("B.Cu", 3, "signal"),
    ]
    assert "HARTLEY-K5" not in _ids(mk_model(copper_layers=layers), "stackup")


def test_g2_separate_grounds_flagged():
    nets = {
        1: Net(1, "GND", "ground"),
        2: Net(2, "AGND", "ground"),
        3: Net(3, "+3V3", "power"),
    }
    findings = [f for f in run_rules(mk_model(nets=nets), "grounding") if f.rule_id == "HARTLEY-G2"]
    assert findings and findings[0].severity.value == "warning"


def test_g2_single_ground_ok():
    nets = {1: Net(1, "GND", "ground"), 2: Net(2, "+3V3", "power")}
    assert "HARTLEY-G2" not in _ids(mk_model(nets=nets), "grounding")


def test_k1_adjacent_signal_layers_flagged():
    layers = [
        _cu("F.Cu", 0, "signal"),
        _cu("In1.Cu", 1, "ground_plane"),
        _cu("In2.Cu", 2, "signal"),
        _cu("B.Cu", 3, "signal"),  # In2 & B.Cu are adjacent signals → K1
    ]
    assert "HARTLEY-K1" in _ids(mk_model(copper_layers=layers), "stackup")


# --- Regressions from the Phase-2 adversarial review -------------------------


def test_l_shaped_plane_classifies_by_span():
    """A full pour on an L-shaped board covers < 30% of the bbox but spans it —
    must classify as a plane (regression: bbox-area threshold called it signal)."""
    from kicad_mcp.review_engine.model import Zone, _classify_layer_role

    extents = {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100, "width": 100, "height": 100}
    # L-shape with 15 mm arms: bottom arm 100x15 (1500) + left arm 15x85 (1275)
    # = 2775 mm^2 = 27.75% of the 100x100 bbox — below the 30% area threshold.
    l_poly = [(0, 0), (15, 0), (15, 85), (100, 85), (100, 100), (0, 100)]
    z = Zone(net_code=1, net_name="GND", layers=("In1.Cu",), polygon=l_poly, net_kind="ground")
    assert z.area / (100 * 100) < 0.30
    role = _classify_layer_role([z], [], [z], 100 * 100, extents)
    assert role == "ground_plane"


def test_connector_is_not_an_ic():
    """8-pad connector J1 with no cap must NOT trigger DEC-1 (regression:
    pad-count heuristic treated any 6+ pad part as an IC)."""
    from kicad_mcp.review_engine.model import Footprint, Pad

    def pad(i):
        return Pad(
            footprint_ref="J1",
            number=str(i),
            net_code=3,
            net_name="SIG",
            at=(i, 0),
            layer_span="F.Cu",
        )

    j1 = Footprint(
        ref="J1",
        value="Conn_01x08",
        lib_id="Connector_PinHeader_2.54mm:PinHeader_1x08",
        at=(10, 10),
        rotation=0,
        layer="F.Cu",
        pads=[pad(i) for i in range(8)],
    )
    model = mk_model(footprints=[j1])
    assert "PHIL-DEC-1" not in _ids(model, "decoupling")


def test_usb_ref_is_not_an_ic():
    from kicad_mcp.review_engine.model import Footprint
    from kicad_mcp.review_engine.rules.decoupling import _is_ic

    usb = Footprint(ref="USB1", value="USB_C", lib_id="x", at=(0, 0), rotation=0, layer="F.Cu")
    u = Footprint(ref="U1", value="MCU", lib_id="x", at=(0, 0), rotation=0, layer="F.Cu")
    assert not _is_ic(usb)
    assert _is_ic(u)
