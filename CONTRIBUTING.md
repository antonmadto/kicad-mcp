# Contributing to kicad-mcp

## Ground rules

Read [`CLAUDE.md`](CLAUDE.md) and [`PLAN.md`](PLAN.md) first — they are the
project constitution. The non-negotiables:

- **PCB mutation → IPC (kipy) only.** Never write `.kicad_pcb` while KiCad runs.
  Wrap multi-item edits in `begin_commit()`/`push_commit()`.
- **Schematic read/write → S-expr layer only** (kicad-skip + sexpdata). Writes
  are feature-flagged (`KICAD_MCP_ALLOW_SCHEMATIC_WRITE`) and refused while the
  file is open; every write is followed by a re-parse + `kicad-cli sch erc` gate.
- **Verify/export → kicad-cli subprocess only** (`--format json`).
- **Path confinement + `shell=False`** on every external call.
- Do **not** add SWIG pcbnew or kiutils. Ask before adding any dependency beyond
  the pinned stack.

## Dev setup

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Green ruff + pytest are required before any phase is called done. CI runs on
Linux, macOS, and Windows across Python 3.10–3.13.

## Testing conventions

- Pure logic (config, path confinement, subprocess, backend capability routing)
  must be importable and testable **without** KiCad, MCP, or kipy installed.
- Tests that need a real `kicad-cli` are marked `@pytest.mark.requires_kicad`
  and auto-skip when it is absent. Tests that need a running GUI are marked
  `@pytest.mark.requires_kicad_gui` (skipped in CI).
- Review-engine rules (Phase 2+) use golden-file fixtures with both
  **must-trigger** and **must-not-trigger** cases, including anti-myth tests
  (a board full of 90° corners must produce zero corner findings).

## Commits

Small, reviewable commits. One logical change per commit. Keep the "Current
status" block in `CLAUDE.md` up to date at the end of a working session.
