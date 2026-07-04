# Changelog

All notable changes to `kicad-mcp` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses
[semantic versioning](https://semver.org/).

## [0.1.0] — 2026-07-04

First public release. Implements PLAN.md phases 0–6.

### Added

- **Headless foundation** — project discovery/info/create; S-expr read layer
  (components, stackup, board info, nets via kicad-cli netlist); ERC/DRC (JSON);
  gerber/drill/BOM/netlist/STEP/pos/SVG/3D-render exports; `export_fab_package`.
- **Design-review engine** — a normalized `DesignModel` and **23 cited rules
  across 10 families** (stackup, grounding, return-path, decoupling, DFM,
  transmission line, crosstalk, SMPS, subcircuits, connectors/ESD). Each finding
  carries a rule id, severity, one-line physics rationale, citation, and
  location. Anti-myth guards are enforced by test (no 90° corner / guard-trace /
  via-fill / length-in-mm nags). `review_design`, `review_topic`,
  `set_design_context`.
- **Live board editing via IPC** (kipy) — move/rotate/duplicate footprints,
  route traces and differential pairs, add vias/zones, refill, read netclasses,
  save. Every edit is a single undo step (commit-wrapped). Verified against
  KiCad 9.0.8.
- **Experimental schematic writes** (feature-flagged) — atomic transactional
  edits with an ERC report; `set_symbol_property`, `duplicate_symbol`.
- **Libraries** — ranked symbol/footprint search; JLCPCB parts search.
- **Infrastructure** — async task queue, a 14-category tool router, review/DRC
  history, Freerouting integration, and the prompts `review_board`,
  `plan_stackup`, `debug_emi`, `prepare_fab`.

### Backends

Three backends behind one capability interface (kicad-cli, S-expr, IPC) with
graceful degradation: analysis/review/export work headless; editing tools return
actionable errors when the GUI is down.

### Known limitations

- KiCad 9's IPC API cannot instantiate a footprint from a *library* or export
  Specctra DSN; `duplicate_footprint` clones an on-board part instead, and
  `autoroute_board` needs a GUI-exported `.dsn`.
- Schematic writes are experimental and gated behind
  `KICAD_MCP_ALLOW_SCHEMATIC_WRITE`.
- JLCPCB/Freerouting require a local parts DB / JAR respectively.
