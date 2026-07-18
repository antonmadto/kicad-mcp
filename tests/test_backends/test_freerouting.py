"""Freerouting jar-path validation (Phase 6)."""

from __future__ import annotations

import pytest

from kicad_mcp.backends import freerouting as fr
from kicad_mcp.backends.base import BackendError


def test_freerouting_available_rejects_directory(tmp_path):
    # KICAD_MCP_FREEROUTING_JAR is admin-set by hand; pointing it at the
    # extracted release directory instead of the .jar inside it is a
    # plausible mistake that must not report "available".
    jar_dir = tmp_path / "freerouting-2.0.0"
    jar_dir.mkdir()
    assert fr.freerouting_available(jar_dir) is False


def test_freerouting_available_accepts_file(tmp_path):
    jar_file = tmp_path / "freerouting.jar"
    jar_file.write_bytes(b"not a real jar, existence is all that's checked")
    if fr._java() is None:
        pytest.skip("no java runtime on PATH")
    assert fr.freerouting_available(jar_file) is True


def test_route_dsn_rejects_directory_jar_with_actionable_error(tmp_path):
    dsn = tmp_path / "board.dsn"
    dsn.write_text("(pcb board)", encoding="utf-8")
    jar_dir = tmp_path / "freerouting-2.0.0"
    jar_dir.mkdir()
    with pytest.raises(BackendError, match="KICAD_MCP_FREEROUTING_JAR"):
        fr.route_dsn(dsn, jar_dir)
