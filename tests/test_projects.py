from __future__ import annotations

import pytest

from kicad_mcp.projects import find_projects, resolve_project
from kicad_mcp.utils.paths import PathConfinementError


def test_find_projects_discovers_sample(fixtures_dir):
    projects = find_projects([fixtures_dir])
    names = {p.name for p in projects}
    assert "sample" in names
    sample = next(p for p in projects if p.name == "sample")
    assert sample.sch is not None and sample.sch.exists()
    assert sample.pcb is not None and sample.pcb.exists()


def test_resolve_project_from_pro(fixtures_dir, sample_pro):
    proj = resolve_project(sample_pro, [fixtures_dir])
    assert proj.name == "sample"
    info = proj.describe()
    assert info["has_schematic"] and info["has_board"]


def test_resolve_project_from_directory(fixtures_dir):
    proj = resolve_project(fixtures_dir / "sample_project", [fixtures_dir])
    assert proj.name == "sample"


def test_resolve_rejects_outside_roots(tmp_path, fixtures_dir):
    outside = tmp_path / "evil.kicad_pro"
    outside.write_text("{}")
    with pytest.raises(PathConfinementError):
        resolve_project(outside, [fixtures_dir])


def test_require_board_and_schematic(fixtures_dir, sample_pro):
    proj = resolve_project(sample_pro, [fixtures_dir])
    assert proj.require_board().suffix == ".kicad_pcb"
    assert proj.require_schematic().suffix == ".kicad_sch"
