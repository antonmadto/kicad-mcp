"""IPC backend tests.

Everything here runs WITHOUT a KiCad GUI: layer mapping, argument validation,
commit-wrapping semantics (mocked board), and graceful-degradation errors.
Live-editing integration tests are marked ``requires_kicad_gui`` and skip
everywhere except a workstation with KiCad open.
"""

from __future__ import annotations

import kipy.board_types as bt
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


# --- rip up: delete routing (mocked board) --------------------------------------
#
# Uses real kipy board-item types (Track/Via/Pad/Net) so the ``.net.name`` access
# and the footprint isinstance paths match production behaviour exactly; the fake
# board just serves them and records what ``remove_items`` was asked to delete.


def _net(name: str) -> bt.Net:
    n = bt.Net()
    n.name = name
    return n


def _track(net_name: str) -> bt.Track:
    t = bt.Track()
    t.net = _net(net_name)
    return t


def _via(net_name: str) -> bt.Via:
    v = bt.Via()
    v.net = _net(net_name)
    return v


class _FakeFootprint:
    """Just the shape rip_up_footprint reads: a ref field and pads with nets."""

    def __init__(self, reference: str, pad_nets: list[str]):
        self.reference_field = type(
            "F", (), {"text": type("T", (), {"value": reference})()}
        )()
        pads = []
        for name in pad_nets:
            p = bt.Pad()
            p.net = _net(name)
            pads.append(p)
        self.definition = type("D", (), {"pads": pads})()


class _RipUpBoard(_FakeBoard):
    def __init__(self, net_names, tracks, vias, footprints=None):
        super().__init__()
        self._nets = [_net(n) for n in net_names]
        self._tracks = list(tracks)
        self._vias = list(vias)
        self._footprints = list(footprints or [])
        self.removed: list = []

    def get_nets(self):
        return self._nets

    def get_tracks(self):
        return list(self._tracks)

    def get_vias(self):
        return list(self._vias)

    def get_footprints(self):
        return list(self._footprints)

    def remove_items(self, items):
        assert items, "rip up must not call remove_items with an empty list"
        self.removed.extend(items)


def test_rip_up_nets_requires_a_net(ipc):
    # Empty input fails before any connection/commit is attempted.
    with pytest.raises(BackendError, match="at least one net"):
        ipc.rip_up_nets([])


def test_rip_up_nets_removes_only_matching_tracks_and_vias(ipc, monkeypatch):
    board = _RipUpBoard(
        net_names=["/ADC/F_X+", "/ADC/F_X-", "GND"],
        tracks=[_track("/ADC/F_X+"), _track("/ADC/F_X+"), _track("/ADC/F_X-"), _track("GND")],
        vias=[_via("/ADC/F_X+"), _via("GND")],
    )
    monkeypatch.setattr(ipc, "get_board", lambda: board)

    result = ipc.rip_up_nets(["/ADC/F_X+", "/ADC/F_X-"])

    assert result == {
        "nets": ["/ADC/F_X+", "/ADC/F_X-"],
        "removed_tracks": 3,
        "removed_vias": 1,
    }
    # Exactly the target-net items were removed; GND (and its via) left intact.
    assert len(board.removed) == 4
    assert all(item.net.name in {"/ADC/F_X+", "/ADC/F_X-"} for item in board.removed)
    # Single commit, pushed once — never dropped.
    assert board.events[0] == "begin"
    assert board.events[-1].startswith("push:")
    assert "drop" not in board.events


def test_rip_up_nets_deduplicates_input(ipc, monkeypatch):
    board = _RipUpBoard(net_names=["SIG"], tracks=[_track("SIG")], vias=[])
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    result = ipc.rip_up_nets(["SIG", "SIG"])
    assert result["nets"] == ["SIG"]
    assert result["removed_tracks"] == 1


def test_rip_up_nets_empty_result_is_fine(ipc, monkeypatch):
    # A valid net that simply has no copper: no error, nothing removed, one commit.
    board = _RipUpBoard(net_names=["SIG", "GND"], tracks=[_track("GND")], vias=[_via("GND")])
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    result = ipc.rip_up_nets(["SIG"])
    assert result == {"nets": ["SIG"], "removed_tracks": 0, "removed_vias": 0}
    assert board.removed == []  # remove_items never called with an empty list
    assert board.events == ["begin", "push:kicad-mcp: rip up SIG"]


def test_rip_up_nets_unknown_net_raises_and_rolls_back(ipc, monkeypatch):
    board = _RipUpBoard(net_names=["SIG"], tracks=[_track("SIG")], vias=[])
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    with pytest.raises(BackendError) as exc:
        ipc.rip_up_nets(["SIG", "NOPE", "ALSO_NOPE"])
    # Both missing names are listed, sorted; nothing was deleted.
    assert "ALSO_NOPE" in str(exc.value) and "NOPE" in str(exc.value)
    assert board.removed == []
    assert board.events == ["begin", "drop"]  # rolled back, never pushed


def test_rip_up_footprint_skips_shared_nets(ipc, monkeypatch):
    # SIG_A: U1+U2 (fanout 2 → local); SIG_B: U1+U3 (local); GND: 4 parts (shared).
    board = _RipUpBoard(
        net_names=["SIG_A", "SIG_B", "GND"],
        tracks=[_track("SIG_A"), _track("SIG_B"), _track("GND"), _track("GND")],
        vias=[_via("SIG_A"), _via("GND")],
        footprints=[
            _FakeFootprint("U1", ["SIG_A", "SIG_B", "GND"]),
            _FakeFootprint("U2", ["SIG_A", "GND"]),
            _FakeFootprint("U3", ["SIG_B", "GND"]),
            _FakeFootprint("R1", ["GND"]),
        ],
    )
    monkeypatch.setattr(ipc, "get_board", lambda: board)

    result = ipc.rip_up_footprint("U1")

    assert result["reference"] == "U1"
    assert result["nets"] == ["SIG_A", "SIG_B"]
    assert result["skipped_shared_nets"] == ["GND"]
    assert result["removed_tracks"] == 2
    assert result["removed_vias"] == 1
    assert all(item.net.name in {"SIG_A", "SIG_B"} for item in board.removed)
    assert board.events[-1].startswith("push:")


def test_rip_up_footprint_include_shared_rips_everything(ipc, monkeypatch):
    board = _RipUpBoard(
        net_names=["SIG_A", "GND"],
        tracks=[_track("SIG_A"), _track("GND"), _track("GND")],
        vias=[_via("GND")],
        footprints=[
            _FakeFootprint("U1", ["SIG_A", "GND"]),
            _FakeFootprint("U2", ["SIG_A", "GND"]),
            _FakeFootprint("R1", ["GND"]),
        ],
    )
    monkeypatch.setattr(ipc, "get_board", lambda: board)

    result = ipc.rip_up_footprint("U1", include_shared=True)

    assert result["skipped_shared_nets"] == []
    assert set(result["nets"]) == {"SIG_A", "GND"}
    assert result["removed_tracks"] == 3
    assert result["removed_vias"] == 1


def test_rip_up_footprint_unknown_reference_raises(ipc, monkeypatch):
    board = _RipUpBoard(
        net_names=["SIG"],
        tracks=[_track("SIG")],
        vias=[],
        footprints=[_FakeFootprint("U1", ["SIG"])],
    )
    monkeypatch.setattr(ipc, "get_board", lambda: board)
    with pytest.raises(BackendError, match="not found"):
        ipc.rip_up_footprint("U99")
    assert board.removed == []
    assert board.events == ["begin", "drop"]


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


@pytest.mark.requires_kicad_gui
def test_live_route_then_rip_up(ipc):
    """Route a throwaway segment on an unrouted net, then rip that net up —
    self-restoring (the net had no copper before and has none after)."""
    board = ipc.get_board()
    routed = {t.net.name for t in board.get_tracks() if t.net.name}
    net = next((n.name for n in board.get_nets() if n.name and n.name not in routed), None)
    if net is None:
        pytest.skip("no unrouted named net on the open board to route+rip")

    ipc.route_trace([(40, 40), (45, 40)], 0.25, "F.Cu", net)
    assert any(t.net.name == net for t in ipc.get_board().get_tracks())

    result = ipc.rip_up_nets([net])
    assert result["nets"] == [net]
    assert result["removed_tracks"] >= 1
    assert not any(t.net.name == net for t in ipc.get_board().get_tracks())
