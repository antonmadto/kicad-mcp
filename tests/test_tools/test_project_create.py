from __future__ import annotations

import pytest

from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.tools import project


def _ctx(root) -> AppContext:
    return AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": str(root)}))


def test_create_project_writes_valid_skeleton(tmp_path):
    ctx = _ctx(tmp_path)
    info = project.create_project_impl(ctx, "myboard", str(tmp_path))
    assert info["name"] == "myboard"
    assert info["has_schematic"] and info["has_board"]
    assert (tmp_path / "myboard.kicad_pro").exists()
    assert (tmp_path / "myboard.kicad_sch").exists()
    assert (tmp_path / "myboard.kicad_pcb").exists()


@pytest.mark.requires_kicad
def test_create_project_schematic_passes_erc(tmp_path):
    # The Phase-1 promise: a freshly created schematic passes ERC with zero
    # violations. Marked so CI reports it as a visible skip, not a silent bypass.
    ctx = _ctx(tmp_path)
    info = project.create_project_impl(ctx, "myboard", str(tmp_path))
    assert info["erc_violations"] == 0


@pytest.mark.parametrize("bad_name", ["../evil", "a/b", "..", ".", "with space", "x\\y"])
def test_create_project_rejects_unsafe_names(tmp_path, bad_name):
    ctx = _ctx(tmp_path)
    with pytest.raises(ValueError, match="Invalid project name"):
        project.create_project_impl(ctx, bad_name, str(tmp_path))
    # Nothing was written anywhere for the rejected name.
    assert not list(tmp_path.rglob("*.kicad_pro"))


def test_create_project_refuses_overwrite(tmp_path):
    ctx = _ctx(tmp_path)
    project.create_project_impl(ctx, "dup", str(tmp_path))
    with pytest.raises(FileExistsError):
        project.create_project_impl(ctx, "dup", str(tmp_path))


def test_create_project_rejects_outside_roots(tmp_path):
    from kicad_mcp.utils.paths import PathConfinementError

    # ctx root is tmp_path/allowed, but we try to create under tmp_path/other.
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    ctx = _ctx(allowed)
    with pytest.raises(PathConfinementError):
        project.create_project_impl(ctx, "x", str(tmp_path / "other"))
