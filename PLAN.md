# KiCad MCP for Claude — Master Execution Plan

Version 1.0 — 2026-07-04
Author brief. This document is the complete plan to build a Python MCP server that lets Claude create, edit, review, and export KiCad designs. Its differentiator is a built-in design review engine encoding the teachings of Rick Hartley and Phil Salmony (Phil's Lab). Hand this document plus `docs/rules/hartley-rules.md` and `docs/rules/philslab-rules.md` to the executing model.

---

## 1. Goal and positioning

Build `kicad-mcp` (working name, pick final name before GitHub push) with two pillars.

1. **Automation pillar.** Claude can create projects, edit schematics (experimental), place and route on the PCB with live UI sync, run ERC/DRC, and export full fab packages.
2. **Review pillar (the differentiator).** A rule engine that audits any KiCad design against a codified catalog of Hartley and Phil's Lab rules — stackup, return paths, grounding, decoupling, crosstalk, SMPS layout, mixed signal partitioning, DFM. No existing KiCad MCP does this. This is what makes the project worth publishing.

Target users: mixed-signal MCU boards, high-speed digital, power electronics, general purpose.
Target platform: KiCad 9.x (design forward-compatible with 10/11), Python 3.10+, cross-platform (Linux/macOS/Windows).
License: MIT.

## 2. What we learned from the four reference repos

| Repo | Take | Avoid |
|---|---|---|
| lamaalrajih/kicad-mcp (MIT, 465★, Python+FastMCP) | Package layout (`tools/ resources/ prompts/ utils/`), project discovery via `KICAD_SEARCH_PATHS`, DRC history tracking, circuit pattern recognition, MCP prompts layer | Read-only, no editing at all, stalled maintenance |
| Seeed-Studio/kicad-mcp-server (MIT, Python+FastMCP) | Graceful degradation between backends, SI/PI analysis tools, pin-level netlist tracing, `detect_pin_conflicts`, code generation ideas (DTS, pytest) | Experimental schematic S-expr hacking presented as editing; no license file in repo |
| mixelpixx/KiCAD-MCP-Server (MIT, 1.2k★, TS+Python) | Triple backend with factory (IPC/SWIG/file), tool router pattern (categories + `execute_tool` to cut context ~70%), JLCPCB SQLite parts search, Freerouting integration, resource URI scheme `kicad://...`, dynamic symbol loading pipeline | The Node+Python two-runtime bridge (accidental complexity), SWIG dependence, history of regressions |
| bunnyf/pcb-mcp (license ambiguous MIT/GPLv3) | Async task queue for long jobs (`auto_route` → task_id → `get_task_status`), one-shot `export_jlcpcb` fab package, `KICAD_MCP_*` env config, path validation + `shlex.quote` hardening | Borrow ideas only, never code (license conflict, committed secrets). No editing. |

Full analysis is in section 12 references; the executing model does not need to re-research these.

## 3. Architecture

Single Python process, FastMCP, stdio transport. No Node, no SSH requirement. Three backends behind one abstract interface, selected by capability at runtime.

```
┌─────────────────────────────────────────────────────┐
│                 FastMCP server (stdio)              │
│  tools/   resources/   prompts/   review_engine/    │
├───────────────┬───────────────────┬─────────────────┤
│ Backend A     │ Backend B         │ Backend C       │
│ IPC API (kipy)│ S-expression layer│ kicad-cli       │
│ live PCB edit │ schematic + files │ ERC/DRC/exports │
│ needs GUI up  │ file must be      │ fully headless  │
│               │ closed in GUI     │                 │
└───────────────┴───────────────────┴─────────────────┘
```

**Division of labor (hard rules).**

- PCB mutation goes through the IPC API (`kicad-python`/kipy) ONLY. Never write `.kicad_pcb` directly while KiCad runs. Wrap every multi-item mutation in `begin_commit()`/`push_commit()` for single undo steps.
- Schematic read/write goes through the S-expression layer (kicad-skip preferred, sexpdata as low-level engine). There is no schematic IPC API in KiCad 9 or 10 — this is unavoidable. Refuse writes when the file is open in a running KiCad (check IPC connection and `~*.lck` lock files). After every schematic write, re-parse and run `kicad-cli sch erc` as a validity gate.
- Verification and export go through `kicad-cli` subprocess ONLY. The IPC API cannot plot or run DRC in KiCad 9. Use `--format json` for DRC/ERC so violations are machine-readable; `--exit-code-violations` for CI.
- Graceful degradation (Seeed pattern). If KiCad GUI is not running → editing tools return actionable errors ("start KiCad and enable Preferences → Plugins → Enable KiCad API"), while analysis/review/export tools keep working headless.
- Design all backends behind an interface for KiCad 11, where SWIG disappears and IPC gains headless + export.

**Pinned stack.**

```
python >= 3.10
mcp / fastmcp (official Python SDK, >= 1.9)
kicad-python == 0.7.1   # kipy; pulls protobuf, pynng >= 0.9
sexpdata >= 1.0.2
kicad-skip >= 0.2.5
# optional: kicadcliwrapper (atopile, typed kicad-cli bindings)
# evaluate: KiCadFiles (steffen-w) if full-schema dataclasses needed
# do NOT use: SWIG pcbnew, kiutils (KiCad 6/7 era, silent token loss on 9)
```

kicad-cli discovery per platform: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (macOS), `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe` (Windows), `kicad-cli` on PATH (Linux). Allow override via `KICAD_MCP_CLI_PATH`.

**Async task pattern (bunnyf idea).** Long operations (autoroute, batch export, full review of large boards) return a `task_id` immediately; add `get_task_status`, `list_tasks`, `cleanup_tasks`. Avoids MCP timeout limits.

**Tool router (mixelpixx idea).** The full tool count will exceed 60. Expose ~20 core tools directly plus 4 router tools: `list_tool_categories`, `get_category_tools`, `search_tools`, `execute_tool`. Everything else routes through categories.

**Config.** Env vars namespaced `KICAD_MCP_*` (`KICAD_MCP_SEARCH_PATHS`, `KICAD_MCP_CLI_PATH`, `KICAD_MCP_FREEROUTING_JAR`, `KICAD_MCP_ALLOW_SCHEMATIC_WRITE=0|1`, timeouts). Security: path validation confined to configured project roots, `shlex.quote` on all subprocess args, no arbitrary `read_file` outside project dirs.

## 4. Repository structure

```
kicad-mcp/
├── pyproject.toml              # uv-managed
├── README.md, LICENSE (MIT), CONTRIBUTING.md
├── main.py                     # entry point
├── kicad_mcp/
│   ├── server.py               # create_server(), lifespan, registration
│   ├── config.py               # KICAD_MCP_* env handling
│   ├── context.py              # shared lifespan context
│   ├── backends/
│   │   ├── base.py             # abstract backend interface
│   │   ├── ipc.py              # kipy wrapper, connection mgmt, commits
│   │   ├── sexpr.py            # schematic/file layer (kicad-skip + sexpdata)
│   │   ├── cli.py              # kicad-cli discovery + typed wrappers
│   │   └── factory.py          # capability detection, degradation logic
│   ├── tools/
│   │   ├── project.py          # create/list/open/info
│   │   ├── schematic_read.py   # components, nets, pin tracing
│   │   ├── schematic_edit.py   # EXPERIMENTAL, feature-flagged
│   │   ├── board_edit.py       # place/move/rotate footprints, zones
│   │   ├── routing.py          # traces, vias, diff pairs, netclasses
│   │   ├── validate.py         # run_erc, run_drc, violations
│   │   ├── review.py           # review engine entry tools
│   │   ├── export.py           # gerbers, step, pdf, bom, pos, fab package
│   │   ├── library.py          # symbol/footprint search, JLCPCB parts
│   │   ├── render.py           # board 2D/3D renders for visual loop
│   │   └── tasks.py            # async task mgmt
│   ├── review_engine/
│   │   ├── model.py            # normalized design model (see §6)
│   │   ├── rules/              # one module per rule family
│   │   │   ├── stackup.py      # HARTLEY-K*, PHIL-STK-*
│   │   │   ├── return_path.py  # HARTLEY-R*, C1, C2
│   │   │   ├── grounding.py    # HARTLEY-G*, PHIL-MIX-*
│   │   │   ├── transmission.py # HARTLEY-F* critical length, skew
│   │   │   ├── decoupling.py   # HARTLEY-D*, PHIL-DEC-*
│   │   │   ├── crosstalk.py    # HARTLEY-C4, PHIL-RTE-1 (3H rule)
│   │   │   ├── smps.py         # PHIL-PWR-* hot loop checks
│   │   │   ├── connectors.py   # PHIL-CON/ESD-*, HARTLEY-C3
│   │   │   ├── subcircuits.py  # crystal, USB, STM32, I2C checks
│   │   │   └── dfm.py          # PHIL-RTE/DFM-*, silkscreen, testpoints
│   │   ├── registry.py         # rule metadata, severity, citations
│   │   └── report.py           # findings → structured report + markdown
│   ├── resources/              # kicad:// URI resources
│   ├── prompts/                # review_board, debug_emi, plan_stackup...
│   └── utils/
├── docs/
│   ├── rules/hartley-rules.md  # rule catalog with sources (done)
│   ├── rules/philslab-rules.md # rule catalog with sources (done)
│   └── architecture.md
└── tests/
    ├── fixtures/               # sample KiCad 9 projects (see §9)
    ├── test_backends/
    ├── test_review/            # golden-file rule tests
    └── test_tools/
```

## 5. Tool catalog

Direct tools (always exposed):

| Tool | Backend | Notes |
|---|---|---|
| `list_projects`, `get_project_info`, `create_project`, `open_project` | file/cli | discovery via search paths |
| `get_board_status`, `get_board_info` | ipc→file fallback | stackup, layers, extents |
| `list_schematic_components`, `list_schematic_nets`, `trace_net` | sexpr + cli netlist | pin-level tracing (Seeed pattern) |
| `run_erc`, `run_drc`, `get_violations` | cli | JSON reports, history tracking |
| `review_design` | review engine | full audit, returns structured findings |
| `review_topic` | review engine | audit one family (stackup, decoupling…) |
| `place_footprint`, `move_footprint`, `rotate_footprint` | ipc | commit-wrapped |
| `route_trace`, `add_via`, `route_differential_pair` | ipc | netclass-aware |
| `add_zone`, `refill_zones` | ipc | |
| `render_board` | cli | PNG/SVG top/bottom for the visual loop |
| `export_gerbers`, `export_step`, `export_bom`, `export_fab_package` | cli | fab package = gerbers+drill+BOM+CPL zip |
| `get_task_status`, `list_tasks` | internal | async pattern |
| router: `list_tool_categories`, `get_category_tools`, `search_tools`, `execute_tool` | internal | |

Routed categories (via `execute_tool`): board setup (outline, mounting holes, text, layers), component ops (arrays, align, group, replace, properties), advanced routing (modify/delete/query traces, copper pours, netclass mgmt), schematic editing (EXPERIMENTAL flag: add symbol, wire, label, annotate, sync to board), libraries (search symbols/footprints, JLCPCB parts search + alternatives, datasheet URLs), exports (pdf, svg, pos, step, 3D render, IPC-2581, ODB++), design rules (set/get rules, netclass constraints, import fab capabilities e.g. JLCPCB profile), autoroute (Freerouting via DSN/SES if JAR configured; async).

Resources: `kicad://projects`, `kicad://project/current/{info,board,components,nets,layers,design-rules,drc-report,review-report}`, `kicad://board/preview.png`.

Prompts: `review_board` (full Hartley/Phil audit walkthrough), `plan_stackup` (interview → recommended stackup per §6 rules), `debug_emi` (Hartley-style diagnostic tree), `prepare_fab` (pre-release checklist per PHIL-DFM), `design_review_mixed_signal`.

## 6. Review engine (the core differentiator)

**Normalized design model.** Rules never touch raw files. Build `model.py` extracting one normalized structure from any backend combination:

- Stackup: ordered layers with type (signal/plane), dielectric thicknesses, copper weights
- Nets with classification (power, ground, clock, diff pair, analog, high-speed guess from name + connected components)
- Footprints with position, layer, courtyard, pads, pin functions where known
- Tracks/vias/zones with geometry, net, layer
- Plane geometry per layer (zones + voids) for split/slot detection
- Schematic graph (components, pins, nets) when available
- Optional user-provided context that files cannot contain: rise times per net class, clock frequencies, target impedances, connector-facing nets, expected fab house. Ask via a `set_design_context` tool; assume conservative defaults otherwise (t_rise 0.5 ns for modern logic → f_knee 1 GHz, L_crit ≈ 15–25 mm).

**Rule anatomy.** Each rule is a class with `id` (e.g. `HARTLEY-R3`), `severity` (error/warning/info), `check(model) -> list[Finding]`, `rationale` (one-sentence physics), `citation` (source URL). Findings carry location (footprint ref, net, coordinates) so Claude can point at the exact spot and optionally fix it via editing tools.

**Rule families and the key checks** (full catalogs with numbers and citations live in `docs/rules/`):

1. **Stackup** — every signal layer adjacent to a plane (HARTLEY-K1/PHIL-STK-3); flag conventional Sig/Pwr/Gnd/Sig 4-layer, recommend Sig/GND/GND/Sig or GND/SigPwr/SigPwr/GND (K2/STK-1); pwr–gnd cavity ≤ 0.2 mm else caps must cover HF (K5); 2-layer boards need solid bottom ground under top routes (K6/STK-7).
2. **Return path** — trace crossing plane split/slot/void = error (R5/C1/STK-6); layer-change vias: same-plane transitions pass, gnd→gnd needs stitching via within ~1–2 mm (flag > 2 mm) including each diff pair line (R3); pwr-referenced transitions need nearby stitching cap below ~250 MHz (R4).
3. **Grounding** — split ground planes flagged by default; mixed signal = one plane partitioned by placement, digital never routed over analog region (G1/G2/MIX-1); star topology flagged when f_knee > 1 MHz (G3).
4. **Transmission lines** — compute L_crit ≈ (t_rise/2)×v with v_inner ≈ 150 mm/ns, v_outer ×1.15; flag uncontrolled/unterminated traces > L_crit (F2); diff pair skew budget in TIME not length, skew_allowed ≈ ±0.3×t_rise×v (F4/M6); don't flag 90° corners (M1 — myth); don't enforce tight intra-pair gap (M2).
5. **Decoupling** — 100 nF per power pin near pin (DEC-1) + bulk per domain (DEC-2); measure loop inductance proxy = pad-to-via distance, flag long/thin connections (D2/DEC-3); if f_knee > 250 MHz require close plane pair since caps are inductors above that (D1).
6. **Crosstalk** — spacing ≥ 3×H to reference plane for parallel runs, aggressors ≥ 3–4×H from diff pairs (C4/RTE-1).
7. **SMPS** — hot loop area metric (input cap → switch → diode/sync FET → back), flag large loops; SW node copper size; FB trace routed away from SW/inductor (PWR-2/3).
8. **Subcircuits** — crystal load cap formula C = 2(C_L − C_stray) with C_stray 3–5 pF, crystal proximity to MCU (XTL-1/4); USB 90 Ω diff, 1k5 pull-up rules per family (USB-1/2); STM32 NRST 100 nF, BOOT0 strap, SWD header presence, VDDA ferrite+10nF+1µF filter (STM-1/2/3, MIX-3); I2C pull-ups present (STM-6).
9. **Connectors/ESD** — TVS on connector-facing lines placed at connector (ESD-1/2); ≥1 gnd per signal on headers (CON-1); single-resistor diff termination on cable-leaving pairs flagged, prefer two 50 Ω + center-tap cap (C3).
10. **DFM** — via 0.7/0.3 mm default, trace widths by function (0.3 sig/0.5 pwr, 0.2 mm ≈ 1 A), fab capability profile imported into design rules before layout, silkscreen labels, mounting holes, fab output completeness (RTE-2/3/4, DFM-1..5).

**Anti-myth guard.** The engine must also NOT nag: no 90° corner warnings, no guard trace suggestions when a plane is one dielectric away, no via-fill concerns, no length matching demands tighter than the time budget. Hartley's credibility comes from removing superstition as much as adding rules.

**Report format.** `review_design` returns JSON findings grouped by severity + a markdown summary with rule IDs, physics one-liners, and citations. Store report history like lamaalrajih's DRC history for progress tracking.

## 7. Schematic editing policy

Feature-flagged (`KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1`), labelled experimental everywhere. Pipeline (mixelpixx pattern, rebuilt on kicad-skip/sexpdata): parse `.kicad_sym` library → inject definition into `lib_symbols` cache → instantiate with fresh UUIDs → place wires/labels using pin-location math with rotation transforms. Hazards to engineer around: UUID uniqueness, `lib_id` vs embedded cache consistency, hierarchical sheet instance paths, live-GUI clobbering. Every write is followed by re-parse + headless ERC. Read-side schematic tools are first-class and always on.

## 8. Phased execution plan

**Phase 0 — Skeleton (small).** Repo scaffold, pyproject with uv, FastMCP server bootstrap, config/env, backend factory with capability detection, kicad-cli discovery, CI (lint+pytest on 3 OSes).

**Phase 1 — Headless foundation.** Project discovery/info; S-expr read layer (components, nets, stackup extraction); cli wrappers for ERC/DRC (JSON), netlist, BOM, gerbers, renders; `export_fab_package`. Deliverable: Claude can analyze and export any project with KiCad closed.

**Phase 2 — Review engine v1.** Normalized model; rule registry/report plumbing; implement the highest-value, most machine-checkable families first: stackup, return-path/split crossing, grounding, decoupling proximity, DFM. `review_design`, `review_topic`, `set_design_context`, `review_board` prompt. Golden-file tests against fixture boards with seeded violations. Deliverable: the differentiator works headless.

**Phase 3 — Live editing via IPC.** kipy connection mgmt + version check; footprint place/move/rotate, tracks, vias, zones, netclasses, diff pair routing; commit wrapping; graceful errors when GUI down. Visual loop: render → Claude inspects → edits. Deliverable: Claude edits a live board with UI sync and undo.

**Phase 4 — Review engine v2.** Transmission-line/critical-length checks with design context; crosstalk 3H geometry checks; SMPS hot-loop metric; subcircuit checks (crystal, USB, STM32, I2C); connector/ESD; anti-myth guards. Review→fix loop: findings link to editing tools so Claude can remediate.

**Phase 5 — Schematic editing (experimental) + libraries.** Feature-flagged write pipeline; symbol/footprint search; JLCPCB parts DB (SQLite download + search + alternatives); datasheet enrichment.

**Phase 6 — Advanced + polish.** Freerouting integration (async); tool router activation once tool count > ~40; DRC/review history tracking; prompts polish; docs site; example walkthrough (design a small STM32 mixed-signal board end-to-end passing the review engine); publish to PyPI + GitHub, register in MCP registry.

Each phase ends with: tests green on Linux/macOS/Windows CI, README updated, and a manual smoke test against KiCad 9.0.x.

## 9. Test strategy

- **Fixtures.** Create small KiCad 9 projects: a clean 4-layer STM32 mixed-signal board (should pass), plus deliberately broken variants (trace over plane split, missing stitching vias, Sig/Pwr/Gnd/Sig stackup, decoupling caps far from pins, split analog ground, SMPS with huge hot loop, USB without pull-up). Also use Phil's open HadesFCS boards (github.com/pms67/HadesFCS, incl. HadesMicroJLCPCB) as real-world review targets.
- **Golden-file rule tests.** Each rule has fixtures that must trigger and must-not-trigger (anti-myth tests included: a board with 90° corners must produce zero corner findings).
- **Backend tests.** S-expr round-trip preservation on KiCad 9 files; cli JSON parsing; IPC tests marked `@requires_kicad_gui` (run locally, skipped in CI).
- **Integration.** Full pipeline: fixture project → review → export fab package → verify file set.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No schematic IPC API in KiCad 9/10 | S-expr layer, feature-flagged writes, ERC gate after every write |
| kiutils stale for KiCad 9 | Don't use it; kicad-skip + sexpdata; evaluate KiCadFiles |
| IPC needs GUI running (headless only in KiCad 11) | Degradation design; cli covers all headless needs today |
| SWIG removal in KiCad 11 | Never depend on SWIG |
| Rule engine false positives destroy trust | Severity tiers, design-context tool, anti-myth guards, citations on every finding |
| Tool count blows LLM context | Router pattern from mixelpixx |
| Long ops hit MCP timeouts | Async task queue |
| bunnyf license ambiguity | Ideas only, no code; all borrowed code from MIT repos with attribution |

## 11. Definition of done (v1.0 release)

1. `uvx kicad-mcp` (or `pip install kicad-mcp`) works on all 3 OSes with KiCad 9.
2. Headless: analyze, ERC/DRC, review, full fab export with KiCad closed.
3. Live: place/route/zone edit with UI sync and single-step undo.
4. Review engine covers all 10 families with ≥ 60 rules, each with citation, tested against fixtures.
5. Anti-myth tests pass.
6. Example end-to-end walkthrough documented.
7. Published on GitHub (MIT) with CI badges; optionally PyPI + MCP registry.

## 12. Reference materials for the executing model

- Rule catalogs (complete, with numbers and source URLs): `docs/rules/hartley-rules.md`, `docs/rules/philslab-rules.md`
- KiCad IPC API docs: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/ and https://docs.kicad.org/kicad-python-main/
- kicad-cli 9.0: https://docs.kicad.org/9.0/en/cli/cli.html
- kicad-python PyPI: https://pypi.org/project/kicad-python/
- kicad-skip: https://github.com/psychogenic/kicad-skip · sexpdata: https://pypi.org/project/sexpdata/
- Reference repos: https://github.com/lamaalrajih/kicad-mcp · https://github.com/Seeed-Studio/kicad-mcp-server · https://github.com/mixelpixx/KiCAD-MCP-Server · https://github.com/bunnyf/pcb-mcp
- Also worth a look during Phase 0: https://github.com/Kletternaut/kicad-mcp-pro (hybrid + router, closest existing analog to this plan) and https://github.com/Finerestaurant/kicad-mcp-python (pure IPC)
- Hartley primary sources: stackup slides https://files.resources.altium.com/sites/default/files/uberflip_docs/file_537.pdf · diff pairs keynote https://www.youtube.com/watch?v=QG0Apol-oj0 · grounding talk https://www.youtube.com/watch?v=ySuUZEjARPY
- Phil's Lab primary sources: https://resources.altium.com/p/pcb-stackup-basics and other Altium articles by Phil Salmony · https://github.com/pms67 · ST AN2867 (oscillators), ST AN4879 (USB)
