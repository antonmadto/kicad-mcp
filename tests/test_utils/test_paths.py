from __future__ import annotations

import os

import pytest

from kicad_mcp.utils.paths import (
    PathConfinementError,
    is_within_roots,
    validate_within_roots,
)


def test_child_path_allowed(tmp_path):
    roots = [tmp_path]
    target = tmp_path / "proj" / "board.kicad_pcb"
    resolved = validate_within_roots(target, roots)
    assert resolved == target.resolve()


def test_exact_root_allowed(tmp_path):
    assert validate_within_roots(tmp_path, [tmp_path]) == tmp_path.resolve()


def test_outside_rejected(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "secret.kicad_sch"
    with pytest.raises(PathConfinementError) as exc:
        validate_within_roots(outside, [root])
    assert "KICAD_MCP_SEARCH_PATHS" in str(exc.value)


def test_is_within_roots_bool(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    assert is_within_roots(root / "a", [root]) is True
    assert is_within_roots(tmp_path / "other", [root]) is False


def test_symlink_escape_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this platform")
    # Resolves through the symlink to a location outside the root → rejected.
    with pytest.raises(PathConfinementError):
        validate_within_roots(link / "x", [root])
