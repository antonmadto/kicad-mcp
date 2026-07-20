"""Pure-math golden tests for the impedance core (run everywhere; only ``math``).

The 15 GOLDEN_VECTORS are carried verbatim from the build spec; each was verified
to reproduce the Hammerstad-Jensen / IPC-2141 / NatSemi reference values to 2 dp.
"""

from __future__ import annotations

import math

import pytest

from kicad_mcp.review_engine import impedance as imp

# Carried verbatim from the build spec's GOLDEN_VECTORS block (values unchanged;
# each entry wrapped only to keep within the line-length limit).
GOLDEN_VECTORS = [
    {"model": "microstrip_single", "inputs_mm": {"W": 0.30, "H": 0.20, "T": 0.035, "eps_r": 4.30},
     "expected_z0_ohms": 55.94, "tolerance_ohms": 2, "expected_eps_eff": 2.972},
    {"model": "microstrip_single", "inputs_mm": {"W": 0.365, "H": 0.20, "T": 0.035, "eps_r": 4.30},
     "expected_z0_ohms": 50.24, "tolerance_ohms": 2, "expected_eps_eff": 3.044},
    {"model": "microstrip_single", "inputs_mm": {"W": 0.30, "H": 0.1524, "T": 0.035, "eps_r": 4.20},
     "expected_z0_ohms": 48.30, "tolerance_ohms": 2, "expected_eps_eff": 2.964},
    {"model": "microstrip_single", "inputs_mm": {"W": 0.25, "H": 0.20, "T": 0.018, "eps_r": 4.50},
     "expected_z0_ohms": 61.18, "tolerance_ohms": 1.5, "expected_eps_eff": 3.129},
    {"model": "microstrip_single", "inputs_mm": {"W": 0.60, "H": 0.508, "T": 0.035, "eps_r": 4.60},
     "expected_z0_ohms": 62.65, "tolerance_ohms": 1.5, "expected_eps_eff": 3.202},
    {"model": "microstrip_single", "inputs_mm": {"W": 0.50, "H": 0.30, "T": 0.035, "eps_r": 4.30},
     "expected_z0_ohms": 53.31, "tolerance_ohms": 2, "expected_eps_eff": 3.070},
    {"model": "stripline_symmetric", "inputs_mm": {"W": 0.15, "b": 0.50, "T": 0.035, "eps_r": 4.30},
     "expected_z0_ohms": 52.46, "tolerance_ohms": 1.5, "expected_eps_eff": 4.30},
    {"model": "stripline_symmetric",
     "inputs_mm": {"W": 0.127, "b": 0.50, "T": 0.0175, "eps_r": 4.20},
     "expected_z0_ohms": 60.80, "tolerance_ohms": 1.5, "expected_eps_eff": 4.20},
    {"model": "stripline_symmetric", "inputs_mm": {"W": 0.20, "b": 0.70, "T": 0.035, "eps_r": 4.30},
     "expected_z0_ohms": 55.56, "tolerance_ohms": 1.5, "expected_eps_eff": 4.30},
    {"model": "stripline_symmetric", "inputs_mm": {"W": 0.18, "b": 0.60, "T": 0.035, "eps_r": 4.50},
     "expected_z0_ohms": 52.37, "tolerance_ohms": 1.5, "expected_eps_eff": 4.50},
    {"model": "diff_microstrip",
     "inputs_mm": {"W": 0.15, "H": 0.10, "T": 0.035, "eps_r": 4.30, "S": 0.20},
     "expected_z0_ohms": 101.99, "tolerance_ohms": 6, "z0_single_ended": 54.85},
    {"model": "diff_microstrip",
     "inputs_mm": {"W": 0.20, "H": 0.10, "T": 0.035, "eps_r": 4.30, "S": 0.20},
     "expected_z0_ohms": 87.19, "tolerance_ohms": 6, "z0_single_ended": 46.90},
    {"model": "diff_microstrip",
     "inputs_mm": {"W": 0.25, "H": 0.127, "T": 0.035, "eps_r": 4.20, "S": 0.25},
     "expected_z0_ohms": 89.20, "tolerance_ohms": 6, "z0_single_ended": 48.09},
    {"model": "diff_stripline",
     "inputs_mm": {"W": 0.10, "b": 0.40, "T": 0.035, "eps_r": 4.30, "S": 0.20},
     "expected_z0_ohms": 100.39, "tolerance_ohms": 7, "z0_single_ended": 54.65},
    {"model": "diff_stripline",
     "inputs_mm": {"W": 0.15, "b": 0.50, "T": 0.035, "eps_r": 4.30, "S": 0.20},
     "expected_z0_ohms": 93.52, "tolerance_ohms": 7, "z0_single_ended": 52.46},
]


def _id(v: dict) -> str:
    return f"{v['model']}_{'_'.join(f'{k}{x}' for k, x in v['inputs_mm'].items())}"


@pytest.mark.parametrize("v", GOLDEN_VECTORS, ids=[_id(v) for v in GOLDEN_VECTORS])
def test_golden_vector(v):
    i = v["inputs_mm"]
    tol = v["tolerance_ohms"]
    if v["model"] == "microstrip_single":
        z0, eps = imp.microstrip_z0_eps(i["W"], i["H"], i["eps_r"], i["T"])
        assert abs(z0 - v["expected_z0_ohms"]) <= tol
        assert abs(eps - v["expected_eps_eff"]) < 0.01
    elif v["model"] == "stripline_symmetric":
        z0 = imp.stripline_z0(i["W"], i["b"], i["eps_r"], i["T"])
        assert abs(z0 - v["expected_z0_ohms"]) <= tol
    elif v["model"] == "diff_microstrip":
        z0 = imp.microstrip_z0(i["W"], i["H"], i["eps_r"], i["T"])
        assert abs(z0 - v["z0_single_ended"]) < 1.0
        zd = imp.diff_z0_microstrip(z0, i["S"], i["H"])
        assert abs(zd - v["expected_z0_ohms"]) <= tol
    elif v["model"] == "diff_stripline":
        z0 = imp.stripline_z0(i["W"], i["b"], i["eps_r"], i["T"])
        assert abs(z0 - v["z0_single_ended"]) < 1.0
        zd = imp.diff_z0_stripline(z0, i["S"], i["b"])
        assert abs(zd - v["expected_z0_ohms"]) <= tol
    else:  # pragma: no cover - guards a mistyped fixture
        raise AssertionError(v["model"])


def test_zero_thickness_limit():
    # T=0 removes the normalized-width correction; Z0 rises from 55.94 (T=35µm) to 58.15.
    assert imp.microstrip_z0(0.30, 0.20, 4.30, 0.0) == pytest.approx(58.15, abs=0.05)


def test_degenerate_returns_none_not_raise():
    assert imp.microstrip_z0_eps(0.0, 0.20, 4.30)[0] is None
    assert imp.microstrip_z0_eps(0.30, 0.0, 4.30)[0] is None
    # eps_eff is still a sane floor (>=1) even when Z0 is undefined.
    assert imp.microstrip_z0_eps(0.0, 0.20, 4.30)[1] >= 1.0
    assert imp.stripline_z0(0.0, 0.50, 4.30) is None
    assert imp.stripline_z0(0.15, 0.0, 4.30) is None


def test_extremes_are_finite_not_raise():
    wide = imp.microstrip_z0(10.0, 0.20, 4.30)
    narrow = imp.microstrip_z0(0.01, 0.20, 4.30)
    assert wide is not None and math.isfinite(wide)
    assert narrow is not None and math.isfinite(narrow)
    assert narrow > wide  # a narrow trace is higher impedance than a wide one


def test_prop_delay_ps_per_mm():
    assert imp.prop_delay_ps_per_mm(4.3) == pytest.approx(6.916, abs=0.01)
    assert imp.prop_delay_ps_per_mm(2.97) == pytest.approx(5.75, abs=0.01)
    # Clamps to a vacuum floor rather than returning a sub-lightspeed delay.
    assert imp.prop_delay_ps_per_mm(0.5) == pytest.approx(imp.prop_delay_ps_per_mm(1.0))


def test_model_prop_delay_backward_compatible():
    # The optional eps_eff arg must not move the no-arg default that golden fixtures use.
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
    assert m.prop_delay_ps_per_mm("In1.Cu") == pytest.approx(6.667, abs=0.02)  # unchanged default
    assert m.prop_delay_ps_per_mm("F.Cu") == pytest.approx(6.1, abs=0.02)  # unchanged default
    assert m.prop_delay_ps_per_mm("F.Cu", eps_eff=2.97) == pytest.approx(5.75, abs=0.02)
