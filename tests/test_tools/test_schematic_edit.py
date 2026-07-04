"""Schematic-edit safety machinery + edits (Phase 5)."""

from __future__ import annotations

import shutil

import pytest

from kicad_mcp.backends.base import BackendError, BackendUnavailableError
from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.tools import schematic_edit


def _project(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree("tests/fixtures/sample_project", dst)
    return str(dst / "sample.kicad_pro")


def _ctx(root, *, write: bool):
    env = {"KICAD_MCP_SEARCH_PATHS": str(root)}
    if write:
        env["KICAD_MCP_ALLOW_SCHEMATIC_WRITE"] = "1"
    return AppContext.create(Config.from_env(env))


def test_write_refused_when_flag_off(tmp_path):
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=False)
    with pytest.raises(BackendUnavailableError, match="KICAD_MCP_ALLOW_SCHEMATIC_WRITE"):
        schematic_edit.set_symbol_property_impl(ctx, pro, "R1", "Value", "22k")


def test_set_property_persists(tmp_path):
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=True)
    result = schematic_edit.set_symbol_property_impl(ctx, pro, "R1", "Value", "22k")
    assert result["value"] == "22k"
    comps = ctx.backends.sexpr.read_components(result["schematic"])
    assert next(c for c in comps if c["reference"] == "R1")["value"] == "22k"


def test_duplicate_symbol_persists(tmp_path):
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=True)
    schematic_edit.duplicate_symbol_impl(ctx, pro, "R1", "R3", dx_mm=10)
    refs = {
        c["reference"]
        for c in ctx.backends.sexpr.read_components(str(tmp_path / "proj" / "sample.kicad_sch"))
    }
    assert refs == {"R1", "R2", "R3"}


def test_lock_file_blocks_write(tmp_path):
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=True)
    sch = tmp_path / "proj" / "sample.kicad_sch"
    lock = sch.parent / f"~{sch.name}.lck"
    lock.write_text("")
    with pytest.raises(BackendError, match="open in KiCad"):
        schematic_edit.set_symbol_property_impl(ctx, pro, "R1", "Value", "1k")


def test_unknown_symbol_errors(tmp_path):
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=True)
    with pytest.raises(BackendError, match="not found"):
        schematic_edit.set_symbol_property_impl(ctx, pro, "R99", "Value", "1k")


def test_failed_edit_leaves_original_byte_identical(tmp_path):
    # Atomic-write guarantee: a mutate that raises must not touch the original
    # .kicad_sch, and must leave no temp file behind (regression: partial
    # overwrite() could truncate the file with no rollback).
    pro = _project(tmp_path)
    ctx = _ctx(tmp_path, write=True)
    sch = tmp_path / "proj" / "sample.kicad_sch"
    before = sch.read_bytes()
    with pytest.raises(BackendError):
        schematic_edit.set_symbol_property_impl(ctx, pro, "R99", "Value", "1k")
    assert sch.read_bytes() == before
    assert not list(sch.parent.glob("*.kicad-mcp.tmp"))
