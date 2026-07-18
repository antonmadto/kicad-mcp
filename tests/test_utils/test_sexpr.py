"""S-expr walking helpers, exercised against the fixture board."""

from __future__ import annotations

from kicad_mcp.utils import sexpr as sx


def test_parse_and_walk_board(sample_pro):
    pcb = sample_pro.replace(".kicad_pro", ".kicad_pcb")
    root = sx.parse_file(pcb)

    assert sx.head(root) == "kicad_pcb"

    general = sx.find(root, "general")
    assert sx.first_value(general, "thickness") == 1.6

    footprints = sx.find_all(root, "footprint")
    assert len(footprints) == 2

    stackup = sx.find(root, "stackup")
    layers = sx.children(stackup, "layer")
    names = [layer[1] for layer in layers]
    assert "F.Cu" in names and "B.Cu" in names


def test_first_value_default():
    node = ["thing", ["a", 1]]
    assert sx.first_value(node, "a") == 1
    assert sx.first_value(node, "missing", default="fallback") == "fallback"


def test_sample_arc_public_alias():
    # Public alias wraps _sample_arc; a quarter circle (r=10) samples along its
    # true sweep, so the polyline length ≈ (pi/2)*10 = 15.708 mm, not the chord.
    import math

    pts = sx.sample_arc((10, 0), (7.071068, 7.071068), (0, 10))
    assert pts is not None
    assert math.isclose(pts[0][0], 10, abs_tol=1e-6) and math.isclose(pts[-1][1], 10, abs_tol=1e-6)
    length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False))
    assert abs(length - 15.708) < 0.05
