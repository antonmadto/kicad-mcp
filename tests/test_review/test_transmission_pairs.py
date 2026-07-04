"""Diff-pair recognition regressions (Phase 4-6 review findings)."""

from __future__ import annotations

from kicad_mcp.review_engine.model import DesignContext, DesignModel, Net
from kicad_mcp.review_engine.rules.transmission import _diff_pairs, _split_polarity


def _model(names_by_code) -> DesignModel:
    from kicad_mcp.review_engine.model import classify_net

    nets = {code: Net(code, name, classify_net(name)) for code, name in names_by_code.items()}
    return DesignModel(
        source="t",
        stackup=[],
        copper_layers=[],
        nets=nets,
        footprints=[],
        tracks=[],
        vias=[],
        zones=[],
        board_thickness_mm=1.6,
        extents=None,
        context=DesignContext(),
    )


def test_bare_pn_letters_do_not_pair():
    # VIP/VIN, OP/ON, EN, SPIN must NOT be recognized as differential pairs.
    for name in ("VIN", "VIP", "OP", "ON", "EN", "SPIN", "MAIN", "VP", "VN"):
        assert _split_polarity(name)[1] is None, f"{name} wrongly split"


def test_vip_vin_not_a_pair():
    model = _model({1: "VIP", 2: "VIN", 3: "OP", 4: "ON"})
    assert list(_diff_pairs(model)) == []


def test_usb_dp_dm_pairs():
    model = _model({1: "USB_DP", 2: "USB_DM"})
    pairs = list(_diff_pairs(model))
    assert len(pairs) == 1
    p_code, n_code, stem = pairs[0]
    assert {p_code, n_code} == {1, 2}
    assert stem in ("USB", "USB_D")


def test_delimited_and_signed_pairs_still_recognized():
    for pos, neg in (("CLK_P", "CLK_N"), ("HDMI0+", "HDMI0-"), ("LVDS0P", "LVDS0N")):
        model = _model({1: pos, 2: neg})
        assert len(list(_diff_pairs(model))) == 1, f"{pos}/{neg} not paired"


def test_power_nets_never_pair():
    # Even if names split, a power/ground kind net is excluded from pairing.
    model = _model({1: "3V3_P", 2: "3V3_N"})  # classify as power
    assert list(_diff_pairs(model)) == []
