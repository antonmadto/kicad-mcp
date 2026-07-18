"""Async task queue + history tracking (Phase 6)."""

from __future__ import annotations

import threading
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


def _wait_no_pending_or_running(store, *, exclude=(), timeout=5.0):
    """Wait until every currently-tracked task (other than ``exclude`` ids) is
    finished. A task can vanish from ``store.list()`` because it finished AND
    was evicted for exceeding the retention cap — that is still "finished" for
    this purpose, so we poll the *live* view rather than a fixed id list.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        live = [t for t in store.list() if t.id not in exclude]
        if not any(t.status in ("pending", "running") for t in live):
            return
        time.sleep(0.01)
    raise AssertionError("tasks did not finish")


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


def test_finished_tasks_are_bounded_beyond_the_retention_cap():
    # Regression: TaskStore._tasks was unbounded — every submit() added an
    # entry never evicted automatically, so a long-lived server leaked result
    # payloads (findings lists, file manifests) for every completed task.
    # max_workers=1 makes completion order deterministic (single worker
    # consumes the queue FIFO), so the survivors are exactly the newest 100.
    store = TaskStore(max_workers=1, max_finished=100)
    for i in range(105):
        store.submit("demo", lambda i=i: i)
    _wait_no_pending_or_running(store)

    remaining = store.list()
    assert len(remaining) == 100
    kept_results = {t.result for t in remaining}
    assert kept_results == set(range(5, 105))  # oldest 5 (0-4) evicted


def test_running_tasks_are_never_evicted():
    store = TaskStore(max_workers=2, max_finished=3)
    gate = threading.Event()

    def blocked():
        gate.wait(5.0)
        return "unblocked"

    long_task = store.submit("long", blocked)
    deadline = time.monotonic() + 2.0
    while store.get(long_task.id).status != "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert store.get(long_task.id).status == "running"

    # Push well past max_finished with quick tasks on the other worker slot
    # while the long task keeps occupying its slot, still unfinished.
    for i in range(10):
        store.submit("quick", lambda i=i: i)
    _wait_no_pending_or_running(store, exclude={long_task.id})

    # The still-running task must never have been evicted, despite far more
    # than max_finished completed tasks having been submitted meanwhile —
    # eviction only ever considers status in (done, error). The quick tasks
    # are capped to max_finished (3); the running task is exempt and additive.
    assert store.get(long_task.id) is not None
    assert store.get(long_task.id).status == "running"
    assert len(store.list()) == 3 + 1

    gate.set()  # let the background thread finish so it doesn't outlive the test


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
