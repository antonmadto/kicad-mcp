"""ERC/DRC/export tests — require a real kicad-cli (auto-skip otherwise)."""

from __future__ import annotations

import zipfile

import pytest

from kicad_mcp.tools import export, validate

pytestmark = pytest.mark.requires_kicad


def test_run_erc(fixture_ctx, sample_pro):
    report = validate.run_erc_impl(fixture_ctx, sample_pro)
    assert report["kind"] == "erc"
    assert report["total"] == len(report["violations"])
    assert set(report["counts"]) >= {"error", "warning"}
    # Every normalized violation has the expected shape.
    for v in report["violations"]:
        assert {"severity", "type", "description", "items"} <= set(v)


def test_run_drc(fixture_ctx, sample_pro):
    report = validate.run_drc_impl(fixture_ctx, sample_pro)
    assert report["kind"] == "drc"
    assert "schematic_parity_checked" in report
    assert report["total"] == len(report["violations"])


def test_export_gerbers(ctx_with_output, sample_pro, tmp_path):
    out_dir = tmp_path / "gerb"
    result = export.export_gerbers_impl(ctx_with_output, sample_pro, str(out_dir))
    files = result["files"]
    assert any(f.endswith(".gtl") for f in files)  # F.Cu gerber
    assert any(f.endswith(".drl") for f in files)  # drill


def test_export_fab_package(ctx_with_output, sample_pro, tmp_path):
    out_zip = tmp_path / "sample_fab.zip"
    result = export.export_fab_package_impl(ctx_with_output, sample_pro, str(out_zip))
    assert out_zip.exists()
    assert result["file_count"] >= 3
    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()
    assert any(n.endswith(".drl") for n in names)
    assert any("BOM" in n for n in names)
    assert any("CPL" in n for n in names)


def test_export_confinement_rejects_outside_root(fixture_ctx, sample_pro, tmp_path):
    # fixture_ctx roots do NOT include tmp_path → writing there is rejected.
    from kicad_mcp.utils.paths import PathConfinementError

    with pytest.raises(PathConfinementError):
        export.export_fab_package_impl(fixture_ctx, sample_pro, str(tmp_path / "x.zip"))
