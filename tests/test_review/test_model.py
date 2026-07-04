"""Model extraction + net classification + geometry unit tests (run everywhere)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.review_engine import geometry as geo
from kicad_mcp.review_engine.model import build_model, classify_net

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
