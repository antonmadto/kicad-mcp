# kicad-mcp architecture

One Python process, FastMCP over stdio. Three backends behind one capability
interface, plus a rule engine. See [`PLAN.md`](../PLAN.md) for the full spec.

## Backends (`kicad_mcp/backends/`)

| Backend | Library | Capabilities | Needs |
|---|---|---|---|
| `cli.py` | `kicad-cli` subprocess | VERIFY, EXPORT | KiCad 9 installed |
| `sexpr.py` | kicad-skip + sexpdata | READ_SCHEMATIC, READ_BOARD, WRITE_SCHEMATIC* | file closed in GUI |
| `ipc.py` | kicad-python (kipy) | READ_BOARD, EDIT_BOARD | running KiCad + IPC API |
| `library.py` | filesystem + SQLite | symbol/footprint/JLCPCB search | KiCad libs installed |
| `freerouting.py` | Java subprocess | autoroute | JAR + Java |

`*` gated behind `KICAD_MCP_ALLOW_SCHEMATIC_WRITE`.

`factory.py` builds all backends and routes each tool to one by **capability**
(`Backends.require(Capability.X)`), degrading with an actionable error when no
backend can serve it — so headless analysis/review/export keep working when the
GUI is down.

## Hard division of labor (PLAN.md §3)

- **PCB mutation → IPC only.** Never write `.kicad_pcb` while KiCad runs. Every
  multi-item edit is wrapped in `begin_commit()`/`push_commit()` (one undo step);
  `IpcBackend.commit()` drops the commit on any exception.
- **Schematic read/write → S-expr only.** No schematic IPC API exists in KiCad
  9/10. Writes are feature-flagged, refused when the file is locked, and gated by
  a re-parse (rollback on corruption) + `kicad-cli sch erc`.
- **Verify/export → kicad-cli only** (`--format json`).

## Review engine (`kicad_mcp/review_engine/`) — the differentiator

```
build_model(.kicad_pcb [+ netlist + design context]) → DesignModel
                                                          │
     rules/*.py  (10 families, one Rule class each) ──────┤ read the model,
                                                          │ never raw files
                     registry.run_rules(model) → [Finding]
                                                          │
                       report.build_report → JSON + markdown
```

- `model.py` normalizes the board: stackup with copper-layer **role inference**
  (plane vs signal from zone coverage + span), footprints/pads (absolute
  positions), tracks/vias/zones, net classification, and — when a netlist is
  available — a schematic connectivity graph.
- `geometry.py` is pure 2D math (point-in-polygon, segment proximity, arc sweeps,
  diff-pair offset).
- Each `Rule` has an `id`, `severity`, one-line physics `rationale`, a `citation`,
  and `check(model) -> [Finding]`. Findings carry a location.
- **Families:** stackup, grounding, return_path, decoupling, dfm, transmission,
  crosstalk, smps, subcircuits, connectors.
- **Anti-myth is enforced by test:** no rule may mention 90° corners, guard
  traces, via fill, "shield", or length-in-mm (`test_antimyth.py`).

## Tool surface

45 tools + 4 router tools across 14 categories (`tools/router.py`), 4 prompts.
Long operations (autoroute, async fab export) return a `task_id` and run on the
background `TaskStore` (`tasks.py`); review/DRC runs append to a per-project
history log (`history.py`).

## Configuration

All env vars are `KICAD_MCP_*`: `SEARCH_PATHS` (also the file-access confinement
boundary), `CLI_PATH`, `ALLOW_SCHEMATIC_WRITE`, `FREEROUTING_JAR`, `JLCPCB_DB`,
`SYMBOL_PATHS`, `FOOTPRINT_PATHS`, `CLI_TIMEOUT`, `IPC_TIMEOUT`.
