"""Live-edit tool wrappers (tools/board_edit.py) — the layer an MCP client calls.

These exercise the ``*_impl`` entrypoints (argument marshaling, polygon-shape
validation, graceful-degradation error shaping) with a recording backend so
they run headless (no KiCad GUI).
"""

from __future__ import annotations

import pytest

from kicad_mcp.backends import Capability, IpcBackend
from kicad_mcp.backends.base import BackendUnavailableError
from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.tools import board_edit


class _RecordingBackend(IpcBackend):
    """IpcBackend stand-in that records the args each method receives."""

    def __init__(self):
        super().__init__(Config.from_env({}))
        self.calls: list[tuple] = []
        self.requested_caps: list = []

    def _record(self, name: str, *args):
        self.calls.append((name, args))
        return {"ok": name}

    def board_status(self):
        return self._record("board_status")

    def list_footprints(self):
        return self._record("list_footprints")

    def move_footprint(self, reference, x_mm, y_mm):
        return self._record("move_footprint", reference, x_mm, y_mm)

    def rotate_footprint(self, reference, degrees):
        return self._record("rotate_footprint", reference, degrees)

    def duplicate_footprint(self, reference, new_reference, x_mm=None, y_mm=None):
        return self._record("duplicate_footprint", reference, new_reference, x_mm, y_mm)

    def get_netclasses(self):
        return self._record("get_netclasses")

    def add_zone(self, layer, polygon_mm, net_name=None):
        return self._record("add_zone", layer, polygon_mm, net_name)

    def refill_zones(self, timeout_s=60.0):
        return self._record("refill_zones", timeout_s)

    def save_board(self):
        return self._record("save_board")


@pytest.fixture
def rec_ctx(monkeypatch):
    ctx = AppContext.create(Config.from_env({}))
    backend = _RecordingBackend()

    def _require(capability):
        backend.requested_caps.append(capability)
        return backend

    monkeypatch.setattr(ctx.backends, "require", _require)
    return ctx, backend


# --- argument marshaling to the backend -----------------------------------------


def test_move_footprint_impl_forwards_args(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.move_footprint_impl(ctx, "R2", 12.5, -3.0)
    assert backend.calls[-1] == ("move_footprint", ("R2", 12.5, -3.0))
    assert backend.requested_caps == [Capability.EDIT_BOARD]


def test_rotate_footprint_impl_forwards_args(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.rotate_footprint_impl(ctx, "R2", 90)
    assert backend.calls[-1] == ("rotate_footprint", ("R2", 90))


def test_duplicate_footprint_impl_forwards_args(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.duplicate_footprint_impl(ctx, "R2", "R99", 1.0, 2.0)
    assert backend.calls[-1] == ("duplicate_footprint", ("R2", "R99", 1.0, 2.0))


def test_get_netclasses_impl_delegates(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.get_netclasses_impl(ctx)
    assert backend.calls[-1][0] == "get_netclasses"


def test_refill_zones_impl_delegates(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.refill_zones_impl(ctx)
    assert backend.calls[-1][0] == "refill_zones"


def test_save_board_impl_delegates(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.save_board_impl(ctx)
    assert backend.calls[-1][0] == "save_board"


# --- polygon-shape validation in add_zone ---------------------------------------


def test_add_zone_impl_coerces_polygon_to_float_pairs(rec_ctx):
    ctx, backend = rec_ctx
    board_edit.add_zone_impl(ctx, "F.Cu", [[0, 0], [10, 0], [10, 10]], "GND")
    name, args = backend.calls[-1]
    assert name == "add_zone"
    layer, pts, net = args
    assert (layer, net) == ("F.Cu", "GND")
    assert pts == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert all(isinstance(v, float) for p in pts for v in p)


def test_add_zone_impl_rejects_flat_polygon(rec_ctx):
    ctx, backend = rec_ctx
    with pytest.raises(ValueError, match=r"polygon vertex 0 must be \[x_mm, y_mm\]"):
        board_edit.add_zone_impl(ctx, "F.Cu", [0.0, 0.0, 10.0])
    assert backend.calls == []  # validation fires before the backend is touched


# --- graceful degradation when the GUI is down ----------------------------------


def test_move_footprint_impl_actionable_error_without_gui():
    ctx = AppContext.create(Config.from_env({}))
    if ctx.backends.ipc.is_available():
        pytest.skip("a live KiCad is running in this environment")
    with pytest.raises(BackendUnavailableError) as exc:
        board_edit.move_footprint_impl(ctx, "R1", 1.0, 2.0)
    assert "Enable KiCad API" in str(exc.value)
