"""Impedance tools through the resolution/project layer (run everywhere)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.tools import impedance as it
from kicad_mcp.tools import review

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"


@pytest.fixture
def imp_ctx():
    return AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": str(REVIEW_FIXTURES)}))


def _pro(name: str) -> str:
    return str(REVIEW_FIXTURES / name / f"{name}.kicad_pro")


def test_analyze_impedance_clean_board(imp_ctx):
    res = it.analyze_impedance_impl(imp_ctx, _pro("clean_4layer"))
    assert res["stackup_source"] == "board"
    assert res["configs"]
    fcu = next(c for c in res["configs"] if c["layer"] == "F.Cu")
    assert 60 <= fcu["z0_ohms"] <= 90  # ≈74.6 Ω single-ended microstrip
    assert fcu["confidence"] == "high"
    assert fcu["model"] == "microstrip"
    # No declared targets → nothing to compare.
    assert res["comparison"] == []


def test_analyze_impedance_with_targets(imp_ctx):
    review.set_design_context_impl(
        imp_ctx, _pro("highspeed_4layer"), target_impedances={"SIG1": 50.0, "NOSUCH": 50.0}
    )
    res = it.analyze_impedance_impl(imp_ctx, _pro("highspeed_4layer"))
    sig1 = next(v for v in res["comparison"] if v["key"] == "SIG1")
    assert sig1["verdict"] == "fail"  # ≈104 Ω vs 50 Ω target
    assert "NOSUCH" in res["targets_unmatched"]


def test_analyze_impedance_net_filter(imp_ctx):
    review.set_design_context_impl(
        imp_ctx, _pro("highspeed_4layer"), target_impedances={"USB_D": 90.0}
    )
    res = it.analyze_impedance_impl(imp_ctx, _pro("highspeed_4layer"), net="USB_D+")
    # Filtering to a diff leg keeps its pair.
    assert res["diff_pairs"] and res["diff_pairs"][0]["stem"] == "USB_D"
    assert all(v["key"] == "USB_D" for v in res["comparison"])


def test_calculate_impedance_microstrip(imp_ctx):
    res = it.calculate_impedance_impl(
        imp_ctx,
        width_mm=0.365,
        height_mm=0.20,
        epsilon_r=4.30,
        thickness_mm=0.035,
        mode="microstrip",
    )
    assert res["z0_ohms"] == pytest.approx(50.24, abs=2)
    assert res["kind"] == "single_ended"
    assert res["z_diff_ohms"] is None


def test_calculate_impedance_differential(imp_ctx):
    res = it.calculate_impedance_impl(
        imp_ctx,
        width_mm=0.20,
        height_mm=0.10,
        epsilon_r=4.30,
        mode="microstrip",
        spacing_mm=0.20,
    )
    assert res["z_diff_ohms"] is not None
    assert res["kind"] == "differential"


def test_calculate_impedance_stripline_requires_b(imp_ctx):
    with pytest.raises(ValueError, match="plane_spacing_mm"):
        it.calculate_impedance_impl(
            imp_ctx, width_mm=0.15, height_mm=0.20, epsilon_r=4.30, mode="stripline"
        )


def test_calculate_impedance_stripline_ok(imp_ctx):
    res = it.calculate_impedance_impl(
        imp_ctx,
        width_mm=0.15,
        height_mm=0.20,
        epsilon_r=4.30,
        mode="stripline",
        plane_spacing_mm=0.50,
    )
    assert res["z0_ohms"] == pytest.approx(52.46, abs=1.5)
    assert res["model"] == "stripline"


def test_calculate_impedance_rejects_nonpositive(imp_ctx):
    with pytest.raises(ValueError, match="width_mm"):
        it.calculate_impedance_impl(imp_ctx, width_mm=0, height_mm=0.20, epsilon_r=4.30)


def test_analyze_impedance_empty_board(imp_ctx, tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    (d / "empty.kicad_pro").write_text('{"meta": {"filename": "empty.kicad_pro"}, "sheets": []}\n')
    (d / "empty.kicad_pcb").write_text(
        "(kicad_pcb\n(version 20241229)\n(generator \"pcbnew\")\n"
        "(general (thickness 1.6))\n(paper \"A4\")\n(net 0 \"\")\n"
        '(gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts"))\n)\n'
    )
    ctx = AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": str(tmp_path)}))
    res = it.analyze_impedance_impl(ctx, str(d / "empty.kicad_pro"))
    assert res["configs"] == []
    assert "No traces to analyze." in res["summary_markdown"]
