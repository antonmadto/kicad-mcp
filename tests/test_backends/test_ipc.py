"""IPC backend tests.

Everything here runs WITHOUT a KiCad GUI: layer mapping, argument validation,
commit-wrapping semantics (mocked board), and graceful-degradation errors.
Live-editing integration tests are marked ``requires_kicad_gui`` and skip
everywhere except a workstation with KiCad open.
"""

from __future__ import annotations

import pytest

from kicad_mcp.backends.base import BackendError, BackendUnavailableError
from kicad_mcp.backends.ipc import IpcBackend, layer_id
from kicad_mcp.config import Config


@pytest.fixture
def ipc() -> IpcBackend:
    return IpcBackend(Config.from_env({}))


# --- layer mapping -----------------------------------------------------------


def test_layer_id_canonical_names():
    assert layer_id("F.Cu") == 3  # kipy BoardLayer BL_F_Cu
    assert layer_id("In1.Cu") == 4
    assert layer_id("B.Cu") == 34


def test_layer_id_rejects_unknown():
    with pytest.raises(BackendError, match="Unknown board layer"):
        layer_id("Middle.Copper")


# --- argument validation (fails before any connection attempt) ---------------


def test_route_trace_needs_two_points(ipc):
    with pytest.raises(BackendError, match="at least 2 points"):
        ipc.route_trace([(0, 0)], 0.3, "F.Cu")


def test_route_trace_rejects_nonpositive_width(ipc):
    with pytest.raises(BackendError, match="width must be positive"):
        ipc.route_trace([(0, 0), (1, 0)], 0.0, "F.Cu")


def test_add_via_rejects_drill_ge_size(ipc):
    with pytest.raises(BackendError, match="drill must be smaller"):
        ipc.add_via(0, 0, size_mm=0.3, drill_mm=0.3)


def test_add_zone_needs_three_points(ipc):
    with pytest.raises(BackendError, match="at least 3 points"):
        ipc.add_zone("F.Cu", [(0, 0), (1, 0)])


# --- graceful degradation ------------------------------------------------------


def test_connect_without_gui_is_actionable(ipc):
    if ipc.is_available():
        pytest.skip("a live KiCad is running in this environment")
    with pytest.raises(BackendUnavailableError) as exc:
        ipc.get_version()
    assert "Enable KiCad API" in str(exc.value)


# --- commit wrapping (mocked board) ---------------------------------------------


class _FakeBoard:
    def __init__(self):
        self.events: list[str] = []

    def begin_commit(self):
        self.events.append("begin")
        return "commit-token"

    def push_commit(self, commit, message=""):
        assert commit == "commit-token"
        self.events.append(f"push:{message}")

    def drop_commit(self, commit):
        assert commit == "commit-token"
        self.events.append("drop")


def test_commit_pushes_on_success(ipc, monkeypatch):
    fake = _FakeBoard()
    monkeypatch.setattr(ipc, "get_board", lambda: fake)
    with ipc.commit("test edit") as board:
        assert board is fake
    assert fake.events == ["begin", "push:test edit"]


def test_commit_drops_on_exception(ipc, monkeypatch):
    fake = _FakeBoard()
    monkeypatch.setattr(ipc, "get_board", lambda: fake)
    with pytest.raises(RuntimeError, match="boom"):
        with ipc.commit("failing edit"):
            raise RuntimeError("boom")
    assert fake.events == ["begin", "drop"]  # rolled back, never pushed


# --- live integration (needs a running KiCad GUI with a board open) -------------


@pytest.mark.requires_kicad_gui
def test_live_board_status(ipc):
    status = ipc.board_status()
    assert "copper_layers" in status


@pytest.mark.requires_kicad_gui
def test_live_roundtrip_track(ipc):
    before = ipc.board_status()["tracks"]
    ipc.route_trace([(50, 50), (60, 50)], 0.3, "F.Cu")
    assert ipc.board_status()["tracks"] == before + 2 - 1  # 1 segment added


@pytest.mark.requires_kicad_gui
def test_live_netclasses(ipc):
    classes = ipc.get_netclasses()
    assert classes and all("track_width_mm" in c and "nets" in c for c in classes)
