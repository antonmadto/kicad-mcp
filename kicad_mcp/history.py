"""Review / DRC history tracking (PLAN.md §6, lamaalrajih pattern).

Each analysis run appends a compact timestamped summary to
``.kicad-mcp/history.jsonl`` beside the project, so progress (fewer findings over
time) can be tracked. Full reports are not stored — only counts + top rule ids.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_HISTORY_DIR = ".kicad-mcp"
_HISTORY_FILE = "history.jsonl"


def _history_path(project_dir: Path) -> Path:
    return project_dir / _HISTORY_DIR / _HISTORY_FILE


def record(project_dir: Path | str, kind: str, summary: dict) -> None:
    """Append one entry (best-effort; never raises into the caller)."""
    try:
        path = _history_path(Path(project_dir))
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            **summary,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: S110 - history is a convenience; never break a review over it
        pass


def read(project_dir: Path | str, kind: str | None = None, limit: int = 50) -> list[dict]:
    """Best-effort read, mirroring :func:`record`'s never-break-the-caller contract.

    A stray non-UTF-8 byte (disk fault, interrupted write) or a line that is
    valid JSON but not an object (partial/interleaved writes) is skipped
    rather than raised — the still-readable entries are returned.
    """
    path = _history_path(Path(project_dir))
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if kind is None or entry.get("kind") == kind:
            entries.append(entry)
    return entries[-limit:]
