"""Read-layer tests (S-expr backend) — run everywhere; no kicad-cli needed."""

from __future__ import annotations

import pytest

from kicad_mcp.tools import board, schematic_read


def test_list_components(fixture_ctx, sample_pro):
    comps = schematic_read.list_components_impl(fixture_ctx, sample_pro)
    refs = [c["reference"] for c in comps]
    assert refs == ["R1", "R2"]  # natural-sorted
    r1 = comps[0]
    assert r1["value"] == "10k"
    assert r1["lib_id"] == "Device:R"
    assert r1["footprint"] == "Resistor_SMD:R_0603_1608Metric"


def test_board_info(fixture_ctx, sample_pro):
    info = board.get_board_info_impl(fixture_ctx, sample_pro)
    assert info["layer_count"] == 2
    assert info["copper_layers"] == ["F.Cu", "B.Cu"]
    assert info["board_thickness_mm"] == 1.6
    assert info["footprint_count"] == 2
    assert info["footprints"] == ["R1", "R2"]
    assert info["extents_mm"]["width"] == 20.0
    assert info["extents_mm"]["height"] == 10.0
    # Only the 2 top-level net declarations, not pad net references (regression:
    # recursive find_all previously counted pad refs and reported 6).
    assert info["net_count"] == 2
    assert {n["name"] for n in info["nets"]} == {"", "GND"}


def test_trace_net_matching_offline(fixture_ctx, sample_pro, monkeypatch):
    """trace_net's name/code matching, exercised without kicad-cli."""
    parsed = {
        "nets": [
            {
                "code": "1",
                "name": "/N1",
                "node_count": 2,
                "nodes": [{"reference": "R1", "pin": "2"}, {"reference": "R2", "pin": "2"}],
            },
            {
                "code": "2",
                "name": "unconnected-(R1-Pad1)",
                "node_count": 1,
                "nodes": [{"reference": "R1", "pin": "1"}],
            },
        ]
    }
    monkeypatch.setattr(schematic_read, "_netlist", lambda ctx, project: parsed)

    # Bare name, full sheet-path name, and numeric code all resolve to the net.
    assert schematic_read.trace_net_impl(fixture_ctx, sample_pro, "N1")["node_count"] == 2
    assert schematic_read.trace_net_impl(fixture_ctx, sample_pro, "/N1")["code"] == "1"
    assert schematic_read.trace_net_impl(fixture_ctx, sample_pro, "1")["name"] == "/N1"
    with pytest.raises(ValueError, match="not found"):
        schematic_read.trace_net_impl(fixture_ctx, sample_pro, "MISSING")

    names = {n["name"] for n in schematic_read.list_nets_impl(fixture_ctx, sample_pro)}
    assert names == {"/N1", "unconnected-(R1-Pad1)"}


def test_board_stackup(fixture_ctx, sample_pro):
    stackup = board.get_board_stackup_impl(fixture_ctx, sample_pro)["stackup"]
    names = [layer["name"] for layer in stackup]
    assert "F.Cu" in names and "B.Cu" in names
    core = next(layer for layer in stackup if layer["type"] == "core")
    assert core["material"] == "FR4"
    assert core["epsilon_r"] == 4.5
    fcu = next(layer for layer in stackup if layer["name"] == "F.Cu")
    assert fcu["type"] == "copper"
    assert fcu["thickness_mm"] == 0.035


@pytest.mark.requires_kicad
def test_list_nets_and_trace(fixture_ctx, sample_pro):
    nets = schematic_read.list_nets_impl(fixture_ctx, sample_pro)
    names = {n["name"] for n in nets}
    assert any(n.endswith("N1") for n in names)

    # Bare name resolves despite the "/N1" sheet-path prefix.
    traced = schematic_read.trace_net_impl(fixture_ctx, sample_pro, "N1")
    assert traced["node_count"] == 2
    refs = sorted(node["reference"] for node in traced["nodes"])
    assert refs == ["R1", "R2"]


@pytest.mark.requires_kicad
def test_trace_missing_net_raises(fixture_ctx, sample_pro):
    with pytest.raises(ValueError, match="not found"):
        schematic_read.trace_net_impl(fixture_ctx, sample_pro, "NONEXISTENT")
