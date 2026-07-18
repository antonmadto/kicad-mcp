"""Routing tool wrappers (tools/routing.py) — the layer an MCP client calls.

These exercise the ``*_impl`` entrypoints where argument marshaling, point-shape
validation, and graceful-degradation error shaping live. A recording backend
stands in for the IPC backend so the tests run headless (no KiCad GUI).
"""

from __future__ import annotations

import pytest

from kicad_mcp.backends import Capability, IpcBackend
from kicad_mcp.backends.base import BackendUnavailableError
from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.tools import routing


class _RecordingBackend(IpcBackend):
    """IpcBackend stand-in that records the args each method receives."""

    def __init__(self):
        super().__init__(Config.from_env({}))
        self.calls: list[tuple] = []
        self.requested_caps: list = []

    def _record(self, name: str, *args):
        self.calls.append((name, args))
        return {"ok": name}

    def route_trace(self, points_mm, width_mm, layer, net_name=None):
        return self._record("route_trace", points_mm, width_mm, layer, net_name)

    def add_via(self, x_mm, y_mm, size_mm=0.7, drill_mm=0.3, net_name=None):
        return self._record("add_via", x_mm, y_mm, size_mm, drill_mm, net_name)

    def route_differential_pair(self, points_mm, width_mm, gap_mm, layer, net_p, net_n):
        return self._record(
            "route_differential_pair", points_mm, width_mm, gap_mm, layer, net_p, net_n
        )


@pytest.fixture
def rec_ctx(monkeypatch):
    ctx = AppContext.create(Config.from_env({}))
    backend = _RecordingBackend()

    def _require(capability):
        backend.requested_caps.append(capability)
        return backend

    monkeypatch.setattr(ctx.backends, "require", _require)
    return ctx, backend


# --- point-shape validation (the common LLM flattening mistake) -----------------


def test_coerce_points_rejects_flat_list():
    with pytest.raises(ValueError, match=r"point 0 must be \[x_mm, y_mm\]"):
        routing.coerce_points([1.0, 2.0, 3.0, 4.0])


def test_coerce_points_rejects_dict_points():
    with pytest.raises(ValueError, match=r"point 0 must be \[x_mm, y_mm\]"):
        routing.coerce_points([{"x": 1, "y": 2}])


def test_coerce_points_names_the_bad_index():
    with pytest.raises(ValueError, match=r"point 1 must be \[x_mm, y_mm\]"):
        routing.coerce_points([[0.0, 1.0], [2.0]])


def test_coerce_points_accepts_pairs_as_float_tuples():
    assert routing.coerce_points([[1, 2], (3, 4)]) == [(1.0, 2.0), (3.0, 4.0)]


def test_coerce_points_rejects_string_point():
    # '12' is subscriptable, so without a guard it silently coerces to (1.0, 2.0) —
    # a wrong coordinate. It must raise the same actionable shape error instead.
    with pytest.raises(ValueError, match=r"point 0 must be \[x_mm, y_mm\]"):
        routing.coerce_points(["12", "34"])


def test_coerce_points_rejects_nan():
    with pytest.raises(ValueError, match=r"point 0 coordinates must be finite"):
        routing.coerce_points([[float("nan"), 0.0], [1.0, 1.0]])


def test_coerce_points_rejects_inf():
    with pytest.raises(ValueError, match=r"point 1 coordinates must be finite"):
        routing.coerce_points([[0.0, 0.0], [float("inf"), 1.0]])


def test_route_trace_impl_rejects_flat_list(rec_ctx):
    ctx, backend = rec_ctx
    with pytest.raises(ValueError, match=r"point 0 must be \[x_mm, y_mm\]"):
        routing.route_trace_impl(ctx, [1.0, 2.0, 3.0, 4.0], 0.2, "F.Cu")
    assert backend.calls == []  # never reached the backend


# --- argument marshaling to the backend -----------------------------------------


def test_route_trace_impl_forwards_float_pairs(rec_ctx):
    ctx, backend = rec_ctx
    routing.route_trace_impl(ctx, [[1, 2], [3, 4]], 0.25, "F.Cu", "GND")
    name, args = backend.calls[-1]
    assert name == "route_trace"
    points, width, layer, net = args
    assert points == [(1.0, 2.0), (3.0, 4.0)]
    assert all(isinstance(v, float) for p in points for v in p)
    assert (width, layer, net) == (0.25, "F.Cu", "GND")
    assert backend.requested_caps == [Capability.EDIT_BOARD]


def test_route_differential_pair_impl_preserves_width_then_gap(rec_ctx):
    ctx, backend = rec_ctx
    routing.route_differential_pair_impl(
        ctx, [[0, 0], [10, 0]], 0.2, 0.15, "F.Cu", "D_P", "D_N"
    )
    name, args = backend.calls[-1]
    assert name == "route_differential_pair"
    points, width, gap, layer, net_p, net_n = args
    assert width == 0.2 and gap == 0.15  # width forwarded before gap, not swapped
    assert (layer, net_p, net_n) == ("F.Cu", "D_P", "D_N")
    assert points == [(0.0, 0.0), (10.0, 0.0)]


def test_add_via_impl_forwards_geometry(rec_ctx):
    ctx, backend = rec_ctx
    routing.add_via_impl(ctx, 5.0, 6.0, 0.8, 0.4, "GND")
    assert backend.calls[-1] == ("add_via", (5.0, 6.0, 0.8, 0.4, "GND"))


# --- graceful degradation when the GUI is down ----------------------------------


def test_route_trace_impl_actionable_error_without_gui():
    ctx = AppContext.create(Config.from_env({}))
    if ctx.backends.ipc.is_available():
        pytest.skip("a live KiCad is running in this environment")
    with pytest.raises(BackendUnavailableError) as exc:
        routing.route_trace_impl(ctx, [[0, 0], [1, 0]], 0.2, "F.Cu")
    assert "Enable KiCad API" in str(exc.value)
