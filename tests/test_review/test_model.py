"""Model extraction + net classification + geometry unit tests (run everywhere)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.review_engine import geometry as geo
from kicad_mcp.review_engine.model import build_model, classify_net
from kicad_mcp.review_engine.registry import run_rules

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"


@pytest.mark.parametrize(
    "name,kind",
    [
        ("GND", "ground"),
        ("AGND", "ground"),
        ("VSS", "ground"),
        ("VSSA", "ground"),
        ("+3V3", "power"),
        ("VCC", "power"),
        ("VDDA", "power"),
        ("3V3_A", "power"),
        ("VBUS", "power"),
        ("SCLK", "clock"),
        ("HSE", "clock"),
        ("XTAL1", "clock"),
        ("USB_D+", "diff"),
        ("USB_DP", "diff"),
        ("ETH_TX_P", "diff"),
        ("VREF", "analog"),
        ("ADC1", "analog"),
        ("SIG1", "signal"),
        ("", "unconnected"),
        # Regression: over-matching false positives (were analog/power/diff).
        ("DATA", "signal"),
        ("SDA", "signal"),
        ("GPIOA", "signal"),
        ("DEV1", "signal"),
        ("LED_A", "signal"),
        ("CAM_DATA", "signal"),
        ("RESET", "signal"),
        ("BOOT0", "signal"),
    ],
)
def test_classify_net(name, kind):
    assert classify_net(name) == kind


def test_model_roles_and_dielectric():
    pcb = REVIEW_FIXTURES / "clean_4layer" / "clean_4layer.kicad_pcb"
    m = build_model(pcb)
    roles = [(ly.name, ly.role) for ly in m.copper_layers]
    assert roles == [
        ("F.Cu", "signal"),
        ("In1.Cu", "ground_plane"),
        ("In2.Cu", "power_plane"),
        ("B.Cu", "signal"),
    ]
    # GND (In1) → PWR (In2) dielectric is the tight 0.2 mm core.
    in1 = m.copper_layer("In1.Cu")
    assert in1.dielectric_to_next_mm == pytest.approx(0.2)


def test_pad_positions_are_absolute():
    pcb = REVIEW_FIXTURES / "clean_4layer" / "clean_4layer.kicad_pcb"
    m = build_model(pcb)
    c1 = next(fp for fp in m.footprints if fp.ref == "C1")
    # C1 origin is (117, 112); pad 1 local (-0.5, 0) → absolute (116.5, 112).
    pad1 = next(p for p in c1.pads if p.number == "1")
    assert pad1.at == pytest.approx((116.5, 112.0))


def test_geometry_point_in_polygon_and_area():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert geo.polygon_area(square) == pytest.approx(100.0)
    assert geo.point_in_polygon((5, 5), square) is True
    assert geo.point_in_polygon((15, 5), square) is False


def test_geometry_sample_segment_spans_endpoints():
    pts = geo.sample_segment((0, 0), (10, 0), step=2.0)
    assert pts[0] == (0, 0)
    assert pts[-1] == (10, 0)
    assert len(pts) >= 6


# --- Regressions from the Phase-4-6 correctness review -----------------------


def test_prop_delay_constants():
    """Pin the microstrip/stripline prop-delay constants (CLAUDE.md: 5.8→6.1 fix)
    so a drift of signal_velocity fails here, not only at a golden boundary."""
    from kicad_mcp.review_engine.model import DesignContext, DesignModel

    m = DesignModel(
        source="t",
        stackup=[],
        copper_layers=[],
        nets={},
        footprints=[],
        tracks=[],
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=DesignContext(),
    )
    # Microstrip (outer) ≈ 6.1 ps/mm; stripline (inner) ≈ 6.667 ps/mm.
    assert m.prop_delay_ps_per_mm("F.Cu") == pytest.approx(6.1, abs=0.02)
    assert m.prop_delay_ps_per_mm("B.Cu") == pytest.approx(6.1, abs=0.02)
    assert m.prop_delay_ps_per_mm("In1.Cu") == pytest.approx(6.667, abs=0.02)


def test_rotate_matches_kicad_sign():
    # KiCad RotatePoint(+orientation) on Y-down coords: pad (2,0) rotated 90° lands
    # at (0,-2); the textbook CCW form would give (0,+2).
    assert geo.rotate(2.0, 0.0, 90.0) == pytest.approx((0.0, -2.0), abs=1e-9)
    assert geo.transform_pad((2.0, 0.0), (100.0, 50.0), 90.0) == pytest.approx((100.0, 48.0))


def _write_pcb(tmp_path, body: str, nets=((0, ""),), name="hand") -> Path:
    net_lines = "\n".join(f'(net {c} "{n}")' for c, n in nets)
    pcb = f"""(kicad_pcb
(version 20241229)
(general (thickness 1.6))
(setup (stackup
(layer "F.Cu" (type "copper") (thickness 0.035))
(layer "d1" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5))
(layer "In1.Cu" (type "copper") (thickness 0.035))
(layer "d2" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5))
(layer "In2.Cu" (type "copper") (thickness 0.035))
(layer "d3" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5))
(layer "B.Cu" (type "copper") (thickness 0.035))))
{net_lines}
(gr_rect (start 0 0) (end 100 100) (layer "Edge.Cuts"))
{body}
)
"""
    path = tmp_path / f"{name}.kicad_pcb"
    path.write_text(pcb, encoding="utf-8")
    return path


def test_rotated_footprint_pad_is_absolute(tmp_path):
    # U1 origin (100,50) rotated 90°, pad local (2,0) → KiCad places it at (100,48).
    body = (
        '(footprint "lib:U" (layer "F.Cu") (at 100 50 90)\n'
        '(property "Reference" "U1" (at 0 0 0) (layer "F.SilkS"))\n'
        '(pad "1" smd rect (at 2 0) (size 0.9 0.9) (layers "F.Cu") (net 0 "")))'
    )
    m = build_model(_write_pcb(tmp_path, body))
    u1 = next(fp for fp in m.footprints if fp.ref == "U1")
    pad1 = next(p for p in u1.pads if p.number == "1")
    assert pad1.at == pytest.approx((100.0, 48.0))


def test_arc_track_length(tmp_path):
    # Quarter circle, r=10: start (10,0), mid (7.071068,7.071068), end (0,10).
    # True arc length = (pi/2)*10 ≈ 15.708 mm — a chord would give 14.14.
    body = (
        "(arc (start 10 0) (mid 7.071068 7.071068) (end 0 10) "
        '(width 0.25) (layer "F.Cu") (net 4))'
    )
    m = build_model(_write_pcb(tmp_path, body, nets=((0, ""), (4, "SIG"))))
    assert m.net_length_mm(4) == pytest.approx(15.708, abs=0.05)


def test_island_count_merges_abutting_pours():
    from kicad_mcp.review_engine.model import Zone, _island_count

    def z(poly):
        return Zone(1, "GND", ("In1.Cu",), poly, "ground")

    left = z([(0, 0), (50, 0), (50, 50), (0, 50)])
    right = z([(50, 0), (100, 0), (100, 50), (50, 50)])  # shares the x=50 edge
    far = z([(60, 0), (100, 0), (100, 50), (60, 50)])  # 10 mm gap from left
    assert _island_count([left]) == 1
    assert _island_count([left, right]) == 1  # one continuous plane
    assert _island_count([left, far]) == 2  # genuinely separated islands


def test_keepout_zone_extraction(tmp_path):
    from kicad_mcp.review_engine.model import build_model as bm

    body = (
        '(zone (net 1) (net_name "GND") (layer "In1.Cu") (hatch edge 0.5)\n'
        "(polygon (pts (xy 0 0) (xy 100 0) (xy 100 100) (xy 0 100))))\n"
        '(zone (net 0) (net_name "") (layer "In1.Cu") (hatch edge 0.5)\n'
        "(keepout (tracks not_allowed) (vias not_allowed) (copperpour not_allowed))\n"
        "(polygon (pts (xy 49 0) (xy 51 0) (xy 51 100) (xy 49 100))))\n"
        '(zone (net 0) (net_name "") (layer "In1.Cu") (hatch edge 0.5)\n'
        "(keepout (tracks not_allowed) (copperpour allowed))\n"
        "(polygon (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10))))"
    )
    m = bm(_write_pcb(tmp_path, body, nets=((0, ""), (1, "GND"))))
    flags = sorted(z.keepout for z in m.zones)
    # Solid pour → False; copperpour-not_allowed keepout → True; copperpour-allowed
    # keepout (still solid copper) → False.
    assert flags == [False, False, True]


def _g1_ids(tmp_path, polys) -> set[str]:
    zones = "\n".join(
        '(zone (net 1) (net_name "GND") (layer "In1.Cu") (hatch edge 0.5)\n'
        f"(polygon (pts {' '.join(f'(xy {x} {y})' for x, y in poly)})))"
        for poly in polys
    )
    m = build_model(_write_pcb(tmp_path, zones, nets=((0, ""), (1, "GND"))))
    return {f.rule_id for f in run_rules(m, "grounding")}


def test_g1_abutting_ground_pours_not_split(tmp_path):
    # One continuous plane drawn as two abutting pours (share x=50) → NOT a split.
    left = [(0, 0), (50, 0), (50, 100), (0, 100)]
    right = [(50, 0), (100, 0), (100, 100), (50, 100)]
    assert "HARTLEY-G1" not in _g1_ids(tmp_path, [left, right])


def test_g1_separated_ground_pours_flagged(tmp_path):
    # Two GND pours with a 10 mm gap → genuinely split ground plane → G1 fires.
    left = [(0, 0), (45, 0), (45, 100), (0, 100)]
    right = [(55, 0), (100, 0), (100, 100), (55, 100)]
    assert "HARTLEY-G1" in _g1_ids(tmp_path, [left, right])
