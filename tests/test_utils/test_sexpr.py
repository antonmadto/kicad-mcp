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
