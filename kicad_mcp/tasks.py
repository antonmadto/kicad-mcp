"""Async task queue (PLAN.md §3) — long operations return a task_id immediately.

Autoroute, batch export, and full reviews of large boards can exceed MCP request
timeouts, so they run on a background thread pool and are polled via
``get_task_status`` / ``list_tasks``. Pure-stdlib, thread-safe, in-process.
"""

from __future__ import annotations

import atexit
import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Task:
    id: str
    kind: str
    status: str = "pending"  # pending | running | done | error
    created_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    result: Any = None
    error: str | None = None

    def summary(self) -> dict:
        return {
            "task_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }

    def full(self) -> dict:
        d = self.summary()
        d["result"] = self.result
        return d


class TaskStore:
    """Thread-safe registry + executor for background tasks."""

    def __init__(self, max_workers: int = 4, max_finished: int = 100) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kicad-mcp")
        # Bound retained finished-task payloads (results can be large: full
        # finding lists, file manifests) so a long-lived server doesn't leak
        # memory when a client polls but never calls cleanup_tasks.
        self._max_finished = max_finished
        # Don't let an in-flight background task hang process exit.
        atexit.register(self.shutdown)

    def _evict_finished_locked(self) -> None:
        """Drop oldest-finished tasks beyond the retention cap. Caller holds ``_lock``."""
        finished = [t for t in self._tasks.values() if t.status in ("done", "error")]
        if len(finished) <= self._max_finished:
            return
        finished.sort(key=lambda t: t.finished_at or t.created_at)
        for t in finished[: len(finished) - self._max_finished]:
            del self._tasks[t.id]

    def submit(self, kind: str, fn: Callable[[], Any]) -> Task:
        task = Task(id=f"task_{uuid.uuid4().hex[:12]}", kind=kind)
        with self._lock:
            self._tasks[task.id] = task

        def run() -> None:
            with self._lock:
                task.status = "running"
            try:
                result = fn()
                with self._lock:
                    task.result = result
                    task.status = "done"
            except Exception as exc:
                with self._lock:
                    task.error = f"{type(exc).__name__}: {exc}"
                    task.status = "error"
                    task.result = {"traceback": traceback.format_exc()}
            finally:
                with self._lock:
                    task.finished_at = _now_iso()
                    self._evict_finished_locked()

        self._pool.submit(run)
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def get_summary(self, task_id: str, *, full: bool = False) -> dict | None:
        """Snapshot a task's fields to a dict INSIDE the lock (no torn reads)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.full() if full else task.summary()

    def list(self) -> list[Task]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    def list_summaries(self) -> list[dict]:
        with self._lock:
            ordered = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
            return [t.summary() for t in ordered]

    def cleanup(self) -> int:
        """Drop finished tasks; return how many were removed."""
        with self._lock:
            done = [tid for tid, t in self._tasks.items() if t.status in ("done", "error")]
            for tid in done:
                del self._tasks[tid]
            return len(done)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
