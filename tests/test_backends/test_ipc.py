"""IPC backend tests.

Everything here runs WITHOUT a KiCad GUI: layer mapping, argument validation,
commit-wrapping semantics (mocked board), and graceful-degradation errors.
Live-editing integration tests are marked ``requires_kicad_gui`` and skip
everywhere except a workstation with KiCad open.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kicad_mcp.backends import ipc as ipc_module
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


# --- diff-pair width/gap validation (fails before any connection) ---------------


def test_route_diff_pair_rejects_nonpositive_width(ipc):
    with pytest.raises(BackendError, match="width must be positive"):
        ipc.route_differential_pair([(0, 0), (1, 0)], 0.0, 0.2, "F.Cu", "P", "N")


def test_route_diff_pair_rejects_nonpositive_gap(ipc):
    # A zero/negative gap collapses half = (w+g)/2 and crosses P/N — reject it,
    # matching route_trace's positive-width guard.
    with pytest.raises(BackendError, match="gap must be positive"):
        ipc.route_differential_pair([(0, 0), (1, 0)], 0.2, -0.3, "F.Cu", "P", "N")


# --- rotate normalization (mocked board) ----------------------------------------


class _FakeAngle:
    """Minimal kipy Angle stand-in: normalize180 mutates in place to [-180, 180)."""

    def __init__(self, degrees: float):
        self.degrees = degrees

    def normalize180(self) -> None:
        self.degrees = (self.degrees + 180.0) % 360.0 - 180.0


class _FakeFootprint:
    def __init__(self, reference: str, degrees: float = 0.0):
        self.reference_field = SimpleNamespace(text=SimpleNamespace(value=reference))
        self._deg = degrees

    @property
    def orientation(self) -> _FakeAngle:
        return _FakeAngle(self._deg)  # a fresh copy, like kipy's getter

    @orientation.setter
    def orientation(self, angle: _FakeAngle) -> None:
        angle.normalize180()  # kipy normalizes the passed angle in place
        self._deg = angle.degrees


class _FakeEditableBoard(_FakeBoard):
    def __init__(self, footprints):
        super().__init__()
        self._fps = footprints

    def get_footprints(self):
        return self._fps

    def update_items(self, item):
        self.events.append("update")


def test_rotate_footprint_returns_stored_normalized_angle(ipc, monkeypatch):
    fp = _FakeFootprint("R2", degrees=0.0)
    board = _FakeEditableBoard([fp])
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    result = ipc.rotate_footprint("R2", 450)
    # KiCad stores 450° as 90° (normalize180); the result must report what landed
    # on the board, not echo the raw request (or a follow-up read looks like a
    # second, unrequested rotation).
    assert result["rotation_deg"] == 90.0
    assert fp.orientation.degrees == 90.0


# --- get_board() re-probe after a boardless fallback ----------------------------


class _FakeClient:
    def __init__(self, board=None, raises=False):
        self._board = board
        self._raises = raises

    def get_board(self):
        if self._raises:
            raise RuntimeError("no board open")
        return self._board


def test_get_board_reprobes_after_boardless_fallback(ipc, monkeypatch):
    board = object()
    # First connect yields a boardless client; get_board must drop it and re-probe,
    # discovering the board that opened later in a sibling KiCad process.
    clients = iter([_FakeClient(raises=True), _FakeClient(board=board)])
    monkeypatch.setattr(ipc, "_connect", lambda: next(clients))
    assert ipc.get_board() is board


def test_get_board_reprobe_still_none_raises_guidance(ipc, monkeypatch):
    monkeypatch.setattr(ipc, "_connect", lambda: _FakeClient(raises=True))
    with pytest.raises(BackendError, match="no board is open"):
        ipc.get_board()


# --- refill_zones() bounded polling (mocked board + client) ---------------------


def _busy_error() -> Exception:
    """A kipy AS_BUSY ApiError — the exact type/code refill_zones() checks for."""
    return ipc_module._kerr.ApiError("busy", code=ipc_module.ApiStatusCode.AS_BUSY)


class _FakeRefillBoard:
    def __init__(self):
        self.refill_calls: list[bool] = []

    def refill_zones(self, block=True):
        self.refill_calls.append(block)


class _BusyThenDoneClient:
    """Reports AS_BUSY for the first ``busy_times`` pings, then completes."""

    def __init__(self, busy_times: int):
        self.busy_times = busy_times
        self.pings = 0

    def ping(self):
        self.pings += 1
        if self.pings <= self.busy_times:
            raise _busy_error()


class _AlwaysBusyClient:
    def ping(self):
        raise _busy_error()


class _DeadClient:
    def ping(self):
        raise OSError("broken pipe")  # transport-layer loss (KiCad closed/crashed)


def test_refill_zones_polls_until_done(ipc, monkeypatch):
    monkeypatch.setattr("kicad_mcp.backends.ipc.time.sleep", lambda _s: None)
    board = _FakeRefillBoard()
    client = _BusyThenDoneClient(busy_times=3)
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    ipc._kicad = client
    result = ipc.refill_zones(timeout_s=5.0)
    assert result == {"refilled": True}
    assert board.refill_calls == [False]  # drove the NON-blocking variant
    assert client.pings == 4  # 3× AS_BUSY, then the completion ping


def test_refill_zones_times_out_when_never_ready(ipc, monkeypatch):
    monkeypatch.setattr("kicad_mcp.backends.ipc.time.sleep", lambda _s: None)
    board = _FakeRefillBoard()
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    ipc._kicad = _AlwaysBusyClient()
    with pytest.raises(BackendError, match="did not complete within"):
        ipc.refill_zones(timeout_s=0.01)


def test_refill_zones_fails_fast_on_lost_connection(ipc, monkeypatch):
    # kipy's own loop swallows IOError and retries forever; ours must fail fast so
    # a KiCad crash mid-fill cannot wedge the single-threaded MCP event loop.
    monkeypatch.setattr("kicad_mcp.backends.ipc.time.sleep", lambda _s: None)
    board = _FakeRefillBoard()
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    ipc._kicad = _DeadClient()
    with pytest.raises(BackendError, match="Lost connection"):
        ipc.refill_zones(timeout_s=5.0)


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
