"""Root pytest configuration.

Ensures the repo root is importable (so ``kicad_mcp`` resolves even without an
editable install) and wires the ``requires_kicad`` / ``requires_kicad_gui``
markers to auto-skip when the environment lacks KiCad.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures"


def _kicad_cli_available() -> bool:
    from kicad_mcp.backends.cli import CliBackend
    from kicad_mcp.config import Config

    return CliBackend(Config.from_env()).is_available()


def _kicad_gui_available() -> bool:
    """True only when a live KiCad with the IPC API AND an open board exists."""
    try:
        from kicad_mcp.backends.ipc import IpcBackend
        from kicad_mcp.config import Config

        ipc = IpcBackend(Config.from_env())
        if not ipc.is_available():
            return False
        ipc.get_board()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    cli_ok = _kicad_cli_available()
    gui_needed = any("requires_kicad_gui" in item.keywords for item in items)
    gui_ok = _kicad_gui_available() if gui_needed else False
    skip_cli = pytest.mark.skip(reason="kicad-cli not available")
    skip_gui = pytest.mark.skip(reason="no running KiCad GUI with IPC + open board")
    for item in items:
        if "requires_kicad" in item.keywords and not cli_ok:
            item.add_marker(skip_cli)
        if "requires_kicad_gui" in item.keywords and not gui_ok:
            item.add_marker(skip_gui)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_pro() -> str:
    return str(FIXTURES / "sample_project" / "sample.kicad_pro")


@pytest.fixture
def fixture_ctx():
    """AppContext with search paths scoped to tests/fixtures."""
    from kicad_mcp.config import Config
    from kicad_mcp.context import AppContext

    return AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": str(FIXTURES)}))


@pytest.fixture
def ctx_with_output(tmp_path):
    """Factory for an AppContext whose roots include tests/fixtures AND tmp_path,
    so export tests can write outside the read-only fixture tree."""
    import os

    from kicad_mcp.config import Config
    from kicad_mcp.context import AppContext

    roots = os.pathsep.join([str(FIXTURES), str(tmp_path)])
    return AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": roots}))
