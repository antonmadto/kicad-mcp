"""Normalization of ERC/DRC JSON — pure, no kicad-cli needed."""

from __future__ import annotations

from kicad_mcp.backends.cli import _normalize_drc, _normalize_erc

ERC_DATA = {
    "source": "sample.kicad_sch",
    "kicad_version": "9.0.8",
    "coordinate_units": "mm",
    "sheets": [
        {
            "path": "/",
            "violations": [
                {
                    "severity": "error",
                    "type": "pin_not_connected",
                    "description": "Pin not connected",
                    "items": [{"description": "R1 Pin 1"}],
                },
                {
                    "severity": "warning",
                    "type": "power_pin_not_driven",
                    "description": "Input power pin not driven",
                    "items": [],
                },
            ],
        }
    ],
}

DRC_DATA = {
    "source": "sample.kicad_pcb",
    "kicad_version": "9.0.8",
    "violations": [
        {"severity": "warning", "type": "lib_footprint_mismatch", "description": "d", "items": []}
    ],
    "unconnected_items": [
        {"severity": "error", "type": "unconnected_items", "description": "u", "items": []}
    ],
    "schematic_parity": [{"severity": "error"}],
}


def test_normalize_erc_flattens_sheets():
    report = _normalize_erc(ERC_DATA)
    assert report["kind"] == "erc"
    assert report["total"] == 2
    assert report["counts"]["error"] == 1
    assert report["counts"]["warning"] == 1
    assert report["violations"][0]["sheet"] == "/"
    assert report["kicad_version"] == "9.0.8"


def test_normalize_drc_merges_unconnected():
    report = _normalize_drc(DRC_DATA)
    assert report["kind"] == "drc"
    assert report["total"] == 2  # 1 violation + 1 unconnected item
    assert report["counts"]["warning"] == 1
    assert report["counts"]["error"] == 1
    assert report["schematic_parity_checked"] is True
    types = {v["type"] for v in report["violations"]}
    assert "unconnected_items" in types
