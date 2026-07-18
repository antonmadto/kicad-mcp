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


# --- Regressions from the Phase-4-6 correctness review -----------------------


def test_dec1_measures_from_pads_not_centroid():
    """A 100 nF cap 4 mm from a perimeter power PAD but >5 mm from the footprint
    CENTROID must NOT fire DEC-1 (regression: distance was centroid-to-cap, so a
    correctly-decoupled large package reported 'no cap within 5 mm')."""
    from kicad_mcp.review_engine.model import Footprint, Pad

    ic = Footprint(
        ref="U1",
        value="MCU",
        lib_id="x",
        at=(10, 10),
        rotation=0,
        layer="F.Cu",
        pads=[Pad("U1", "1", 2, "+3V3", (16, 10), "F.Cu")],  # power pin 6 mm off centroid
    )
    cap = Footprint(ref="C1", value="100nF", lib_id="x", at=(20, 10), rotation=0, layer="F.Cu")
    # Pad→cap = 4 mm (< 5, OK); centroid→cap = 10 mm (would have fired).
    assert "PHIL-DEC-1" not in _ids(mk_model(footprints=[ic, cap]), "decoupling")


def _r5_model(keepout_moat: bool) -> DesignModel:
    from kicad_mcp.review_engine.model import Track, Zone

    layers = [
        _cu("F.Cu", 0, "signal"),
        _cu("In1.Cu", 1, "ground_plane"),
        _cu("In2.Cu", 2, "power_plane"),
        _cu("B.Cu", 3, "signal"),
    ]
    pour = Zone(1, "GND", ("In1.Cu",), [(0, 0), (100, 0), (100, 50), (0, 50)], "ground")
    moat = Zone(
        0, "", ("In1.Cu",), [(49, 0), (51, 0), (51, 50), (49, 50)], "unconnected",
        keepout=keepout_moat,
    )
    track = Track((20, 25), (80, 25), 0.2, "F.Cu", 3)  # crosses the x≈50 strip
    extents = {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 50, "width": 100, "height": 50}
    m = mk_model(copper_layers=layers, nets={1: Net(1, "GND", "ground")}, extents=extents)
    m.tracks.append(track)
    m.zones.extend([pour, moat])
    return m


def test_r5_fires_on_keepout_moat():
    # A moat cut into the GND plane as a keepout (copperpour not_allowed) is a
    # return-path void — a trace crossing it must fire R5.
    ids = {f.rule_id for f in run_rules(_r5_model(keepout_moat=True), "return_path")}
    assert "HARTLEY-R5" in ids


def test_r5_silent_over_solid_plane():
    # Same geometry, the strip is NOT a keepout → solid reference copper → silent.
    ids = {f.rule_id for f in run_rules(_r5_model(keepout_moat=False), "return_path")}
    assert "HARTLEY-R5" not in ids


def _r5_grouping_model(n_segments: int) -> DesignModel:
    from kicad_mcp.review_engine.model import Track, Zone

    layers = [_cu("F.Cu", 0, "signal"), _cu("In1.Cu", 1, "ground_plane")]
    pour = Zone(1, "GND", ("In1.Cu",), [(0, 0), (100, 0), (100, 50), (0, 50)], "ground")
    moat = Zone(
        0, "", ("In1.Cu",), [(49, 0), (51, 0), (51, 50), (49, 50)], "unconnected", keepout=True
    )
    extents = {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 50, "width": 100, "height": 50}
    m = mk_model(
        copper_layers=layers,
        nets={1: Net(1, "GND", "ground"), 3: Net(3, "SIG", "signal")},
        extents=extents,
    )
    # n parallel F.Cu tracks of ONE net each crossing the x≈50 keepout strip.
    m.tracks.extend(
        Track((20, 10 + i * 2), (80, 10 + i * 2), 0.2, "F.Cu", 3) for i in range(n_segments)
    )
    m.zones.extend([pour, moat])
    return m


def _r5(model: DesignModel):
    return [f for f in run_rules(model, "return_path") if f.rule_id == "HARTLEY-R5"]


def test_r5_groups_segments_of_one_net_into_one_finding():
    # A net routed as 3 segments through one uncovered region is ONE root cause:
    # exactly one finding, whose message reports the crossing count (regression: R5
    # emitted one finding PER segment, flooding a real board).
    findings = _r5(_r5_grouping_model(3))
    assert len(findings) == 1
    assert "3 place" in findings[0].message


def test_r5_single_segment_crossing_still_fires():
    findings = _r5(_r5_grouping_model(1))
    assert len(findings) == 1
    assert findings[0].location is not None and findings[0].location.at is not None
