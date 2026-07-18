from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from kicad_mcp.backends.cli import CliBackend, discover_cli_path
from kicad_mcp.config import Config

MAC_DEFAULT = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
WIN_DEFAULT = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


def test_override_wins_when_it_exists():
    got = discover_cli_path(
        "/opt/kicad-cli",
        platform="linux",
        which=lambda _n: None,
        exists=lambda _p: True,
    )
    assert got == Path("/opt/kicad-cli")


def test_macos_default_path():
    got = discover_cli_path(
        None,
        platform="darwin",
        which=lambda _n: None,
        exists=lambda p: Path(p) == Path(MAC_DEFAULT),
    )
    assert got == Path(MAC_DEFAULT)


def test_windows_default_path():
    got = discover_cli_path(
        None,
        platform="win32",
        which=lambda _n: None,
        exists=lambda p: Path(p) == Path(WIN_DEFAULT),
    )
    assert got == Path(WIN_DEFAULT)


def test_linux_uses_path():
    got = discover_cli_path(
        None,
        platform="linux",
        which=lambda n: "/usr/bin/kicad-cli" if n == "kicad-cli" else None,
        exists=lambda _p: True,
    )
    assert got == Path("/usr/bin/kicad-cli")


def test_nothing_found_returns_none():
    got = discover_cli_path(
        None,
        platform="linux",
        which=lambda _n: None,
        exists=lambda _p: False,
    )
    assert got is None


def test_missing_override_returned_for_error_messaging():
    # Even when it does not exist, a user-configured override is echoed back so
    # error messages can name the exact path they set.
    got = discover_cli_path(
        "/bad/kicad-cli",
        platform="linux",
        which=lambda _n: None,
        exists=lambda _p: False,
    )
    assert got == Path("/bad/kicad-cli")


def test_backend_unavailable_for_bogus_path():
    backend = CliBackend(Config.from_env({}), path=Path("/definitely/not/here/kicad-cli"))
    assert backend.is_available() is False


def test_export_gerbers_reports_files_overwritten_on_reexport(tmp_path):
    # Regression: a plain before/after set-diff on directory contents misses
    # any file that already existed (kicad-cli overwrites gerbers in place),
    # so re-exporting into the fixed default output dir reported files: []
    # even though the full set was just regenerated.
    backend = CliBackend(Config.from_env({}), path=Path("/bin/true"))
    out_dir = tmp_path / "gerbers"
    out_dir.mkdir()
    stale = out_dir / "board-F_Cu.gtl"
    stale.write_text("stale content from a prior export")
    old_mtime_ns = stale.stat().st_mtime_ns

    def fake_run_checked(args):
        stale.write_text("freshly regenerated content")
        # Force a distinct mtime regardless of filesystem clock resolution.
        os.utime(stale, ns=(old_mtime_ns + 10**9, old_mtime_ns + 10**9))

    backend._run_checked = fake_run_checked
    files = backend.export_gerbers(Path("board.kicad_pcb"), out_dir)
    assert stale in files


def test_export_drill_reports_files_overwritten_on_reexport(tmp_path):
    backend = CliBackend(Config.from_env({}), path=Path("/bin/true"))
    out_dir = tmp_path / "drill"
    out_dir.mkdir()
    stale = out_dir / "board.drl"
    stale.write_text("stale drill file")
    old_mtime_ns = stale.stat().st_mtime_ns

    def fake_run_checked(args):
        stale.write_text("freshly regenerated drill file")
        os.utime(stale, ns=(old_mtime_ns + 10**9, old_mtime_ns + 10**9))

    backend._run_checked = fake_run_checked
    files = backend.export_drill(Path("board.kicad_pcb"), out_dir)
    assert stale in files


def test_export_gerbers_still_reports_brand_new_files(tmp_path):
    # Sanity: the new mtime-based diff must still catch genuinely new outputs,
    # not just overwritten ones.
    backend = CliBackend(Config.from_env({}), path=Path("/bin/true"))
    out_dir = tmp_path / "gerbers"
    out_dir.mkdir()

    def fake_run_checked(args):
        (out_dir / "board-B_Cu.gbl").write_text("new file")

    backend._run_checked = fake_run_checked
    files = backend.export_gerbers(Path("board.kicad_pcb"), out_dir)
    assert out_dir / "board-B_Cu.gbl" in files


@pytest.mark.requires_kicad
def test_real_version_reports_kicad9():
    backend = CliBackend(Config.from_env())
    assert backend.is_available()
    version = backend.version()
    assert re.match(r"\d+\.\d+", version), f"unexpected version string: {version!r}"
