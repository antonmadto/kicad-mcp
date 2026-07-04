from __future__ import annotations

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


@pytest.mark.requires_kicad
def test_real_version_reports_kicad9():
    backend = CliBackend(Config.from_env())
    assert backend.is_available()
    version = backend.version()
    assert re.match(r"\d+\.\d+", version), f"unexpected version string: {version!r}"
