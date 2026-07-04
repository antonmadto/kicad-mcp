"""Async task queue + history tracking (Phase 6)."""

from __future__ import annotations

import time

from kicad_mcp import history
from kicad_mcp.tasks import TaskStore


def _wait(store, task_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        t = store.get(task_id)
        if t.status in ("done", "error"):
            return t
        time.sleep(0.01)
    raise AssertionError("task did not finish")


def test_task_runs_and_returns_result():
    store = TaskStore()
    task = store.submit("demo", lambda: {"answer": 42})
    finished = _wait(store, task.id)
    assert finished.status == "done"
    assert finished.result == {"answer": 42}
    assert finished.finished_at is not None


def test_task_captures_error():
    store = TaskStore()

    def boom():
        raise ValueError("nope")

    task = store.submit("demo", boom)
    finished = _wait(store, task.id)
    assert finished.status == "error"
    assert "nope" in finished.error


def test_list_and_cleanup():
    store = TaskStore()
    t1 = store.submit("a", lambda: 1)
    t2 = store.submit("b", lambda: 2)
    _wait(store, t1.id)
    _wait(store, t2.id)
    assert len(store.list()) == 2
    assert store.cleanup() == 2
    assert store.list() == []


# --- history -----------------------------------------------------------------


def test_history_roundtrip(tmp_path):
    history.record(tmp_path, "review", {"total": 3, "counts": {"error": 1}})
    history.record(tmp_path, "drc", {"total": 0, "counts": {}})
    history.record(tmp_path, "review", {"total": 1, "counts": {"error": 0}})

    reviews = history.read(tmp_path, kind="review")
    assert [e["total"] for e in reviews] == [3, 1]  # chronological
    assert all("timestamp" in e for e in reviews)
    assert len(history.read(tmp_path)) == 3  # all kinds


def test_history_missing_file_is_empty(tmp_path):
    assert history.read(tmp_path) == []
