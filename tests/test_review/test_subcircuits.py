"""Subcircuit + connector rules on hand-built Schematic graphs (run everywhere)."""

from __future__ import annotations

from kicad_mcp.review_engine.model import (
    DesignContext,
    DesignModel,
    Schematic,
    SchematicComponent,
    SchematicNet,
    SchematicPin,
)
from kicad_mcp.review_engine.registry import run_rules


def _model(sch: Schematic) -> DesignModel:
    return DesignModel(
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
        schematic=sch,
    )


def _net(name, pins):
    from kicad_mcp.review_engine.model import classify_net

    return SchematicNet(name=name, kind=classify_net(name), pins=[SchematicPin(*p) for p in pins])


def _ids(sch, topic="subcircuits"):
    return {f.rule_id for f in run_rules(_model(sch), topic)}


# --- crystal -----------------------------------------------------------------


def test_crystal_without_load_caps_flagged():
    sch = Schematic(
        components=[SchematicComponent("Y1", "16MHz"), SchematicComponent("U1", "STM32")],
        nets=[
            _net("/XTAL_IN", [("Y1", "1"), ("U1", "5")]),
            _net("/XTAL_OUT", [("Y1", "3"), ("U1", "6")]),
        ],
    )
    assert "PHIL-XTL-1" in _ids(sch)


def test_crystal_with_load_caps_ok():
    sch = Schematic(
        components=[
            SchematicComponent("Y1", "16MHz"),
            SchematicComponent("C1", "18pF"),
            SchematicComponent("C2", "18pF"),
        ],
        nets=[
            _net("/XTAL_IN", [("Y1", "1"), ("C1", "1")]),
            _net("/XTAL_OUT", [("Y1", "3"), ("C2", "1")]),
        ],
    )
    assert "PHIL-XTL-1" not in _ids(sch)


# --- STM32 -------------------------------------------------------------------


def test_nrst_without_cap_is_warning():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32")],
        nets=[_net("/NRST", [("U1", "7")])],
    )
    findings = [f for f in run_rules(_model(sch)) if f.rule_id == "PHIL-STM-1"]
    assert findings and findings[0].severity.value == "warning"  # E→W per CHANGES.md


def test_nrst_with_100nf_ok():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32"), SchematicComponent("C5", "100nF")],
        nets=[_net("/NRST", [("U1", "7"), ("C5", "1")])],
    )
    assert "PHIL-STM-1" not in _ids(sch)


def test_boot0_floating_flagged():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32")],
        nets=[_net("/BOOT0", [("U1", "44")])],  # only the MCU pin, nothing else
    )
    assert "PHIL-STM-2" in _ids(sch)


def test_boot0_strapped_ok():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32"), SchematicComponent("R9", "10k")],
        nets=[_net("/BOOT0", [("U1", "44"), ("R9", "1")])],
    )
    assert "PHIL-STM-2" not in _ids(sch)


def test_i2c_without_pullups_flagged():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32")],
        nets=[_net("/SCL", [("U1", "10")]), _net("/SDA", [("U1", "11")])],
    )
    ids = _ids(sch)
    assert "PHIL-STM-6" in ids


def test_i2c_with_pullups_ok():
    sch = Schematic(
        components=[
            SchematicComponent("U1", "STM32"),
            SchematicComponent("R1", "2.2k"),
            SchematicComponent("R2", "2.2k"),
        ],
        nets=[
            _net("/SCL", [("U1", "10"), ("R1", "1")]),
            _net("/SDA", [("U1", "11"), ("R2", "1")]),
        ],
    )
    assert "PHIL-STM-6" not in _ids(sch)


# --- USB + mixed-signal ------------------------------------------------------


def test_usb_dplus_without_pullup_flagged():
    sch = Schematic(
        components=[SchematicComponent("J1", "USB")],
        nets=[_net("/USB_D+", [("J1", "3")])],
    )
    assert "PHIL-USB-2" in _ids(sch)


def test_vssa_not_tied_flagged():
    sch = Schematic(
        components=[SchematicComponent("U1", "STM32")],
        nets=[_net("/VSSA", [("U1", "20")]), _net("/GND", [("U1", "8")])],
    )
    assert "PHIL-MIX-2" in _ids(sch)


# --- connectors --------------------------------------------------------------


def test_connector_without_ground_flagged():
    sch = Schematic(
        components=[SchematicComponent("J2", "Header")],
        nets=[
            _net("/SIG_A", [("J2", "1"), ("U1", "2")]),
            _net("/SIG_B", [("J2", "2"), ("U1", "3")]),
        ],
    )
    assert "PHIL-CON-1" in _ids(sch, "connectors")


def test_connector_esd_missing_flagged():
    sch = Schematic(
        components=[SchematicComponent("J3", "USB")],
        nets=[_net("/USB_DAT", [("J3", "1"), ("U1", "5")])],
    )
    assert "PHIL-ESD-1" in _ids(sch, "connectors")


def test_connector_with_tvs_ok():
    sch = Schematic(
        components=[SchematicComponent("J3", "USB"), SchematicComponent("D1", "USBLC6")],
        nets=[_net("/USB_DAT", [("J3", "1"), ("D1", "2"), ("U1", "5")])],
    )
    assert "PHIL-ESD-1" not in _ids(sch, "connectors")


def test_no_schematic_no_subcircuit_findings():
    # Board-only model (schematic=None): schematic rules stay silent, never crash.
    model = DesignModel(
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
        schematic=None,
    )
    assert run_rules(model, "subcircuits") == []
    assert run_rules(model, "connectors") == []
