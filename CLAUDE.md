# CLAUDE.md — kicad-mcp project constitution

This file is the durable operating agreement for building `kicad-mcp`. Read it every session. It is a distilled rulebook; the full spec is in `PLAN.md`. When the two conflict, `PLAN.md` wins and you should flag the conflict.

## Read first, every session
0. `HANDOFF.md` — **START HERE.** The current goal, what's done, and what to do next (making the MCP genuinely usable on real boards). Session-to-session baton.
1. `PLAN.md` — master execution plan (architecture, pinned stack, repo layout §4, phases §8).
2. `docs/rules/hartley-rules.md`, `docs/rules/philslab-rules.md` — the rule catalogs the review engine encodes.
3. `docs/rules/CHANGES.md` — corrections verified against the source videos; severity and sourcing fixes you MUST honor.

## Current status
- Phase: **ALL PHASES 0–6 complete and green** (2026-07-04). Lint (ruff) + 179 pytest pass (2 GUI tests auto-skip without a GUI; they PASSED against live KiCad 9.0.8). 45 tools + 4 router tools, 4 prompts, 23 review rules across 10 families. **Three adversarial multi-agent reviews run** (Phase 0/1, Phase 2, Phase 4–6): 6 + 12 + 20 = 38 confirmed findings, ALL fixed. Highlights fixed: path-traversal guard, UTF-8 encoding, span-based plane detection (L-shaped boards), DEC-1 connector FP, R5 abutting-zone tolerance; and Phase 4–6: diff-pair bare-P/N mis-pairing (VIN/VIP false pair + USB_DP/DM miss), atomic schematic write (temp+os.replace — a failed edit now leaves the original byte-identical), C4 cross-segment overlap accumulation, microstrip prop delay 5.8→6.1 ps/mm, TaskStore locked snapshots + atexit shutdown, sqlite URI escaping, router double-wrap unwrap.
  - **Phase 0:** repo scaffold, `pyproject.toml` (hatchling, pinned stack), FastMCP bootstrap (`kicad_mcp/server.py`), `config.py` (`KICAD_MCP_*`), backend factory + capability router with graceful degradation (`backends/{base,cli,sexpr,ipc,factory}.py`), kicad-cli discovery (mac/win/linux + override), path confinement + `shell=False` subprocess helpers, CI (`.github/workflows/ci.yml`, 3 OSes × py3.10–3.13), `get_server_status` diagnostics tool.
  - **Phase 1:** project discovery/info/create (`tools/project.py`), S-expr read layer — components (kicad-skip), stackup + board info (sexpdata) — cli wrappers for ERC/DRC (normalized JSON), netlist, BOM, gerbers, drill, STEP, pos, SVG, 3D render, and `export_fab_package` (gerbers+drill+BOM+CPL zip). 17 tools registered. Nets via cli `kicadxml` netlist + `trace_net`.
  - **Phase 2 — review engine v1** (`kicad_mcp/review_engine/`): normalized `DesignModel` (stackup + copper-layer role inference from zones, footprints/pads with absolute positions, tracks/vias/zones, net classification, geometry helpers), `Rule`/`Finding`/registry/report framework, and **11 cited rules across 5 families** — stackup (K1/K2/K5/K6), grounding (G1/G2), return_path (R5, geometric trace-over-gap via point-in-polygon), decoupling (DEC-1 proximity), dfm (RTE-2/RTE-3/DFM-4). Tools `review_design`/`review_topic`/`set_design_context` + `review_board` prompt. 20 tools total. Golden fixtures in `tests/fixtures/review/` (generator `generate_review_fixtures.py`) with must-trigger + must-not-trigger + **anti-myth** (90° corners → 0 findings) tests. Heuristic rules (G2, DEC-1) softened to WARNING to limit false positives, documented inline.
  - **Phase 3 — live editing via IPC** (`backends/ipc.py`, `tools/board_edit.py`, `tools/routing.py`): kipy connection mgmt with **per-PID socket discovery** (each KiCad process serves its own `/tmp/kicad/api-<pid>.sock`; we probe all and prefer one with an open board), `commit()` context manager (begin→push, drop on exception = single undo step), move/rotate footprint (rotate must assign via the `orientation` **setter** — the getter returns a copy), route_trace (polyline), add_via, route_differential_pair (mitered `offset_polyline`), add_zone (PolygonWithHoles), refill_zones, save_board. 30 tools total. **Verified live against KiCad 9.0.8**: moved/rotated R2, routed traces + diff pair, via, GND zone, refill, save → re-parsed the saved file (all edits present) → rendered headless (edits visible). Graceful errors when GUI down (all non-GUI tests still pass headless). NOT yet done (deferred to Phase 6 polish): place NEW footprint from a library via IPC (needs the symbol/footprint definition pipeline), netclass management tools.
  - **Phase 4 — review engine v2**: +5 families, 23 rules total. transmission (F2 critical-length keyed off `set_design_context` rise time, F4 intra-pair skew in **picoseconds**), crosstalk (C4 aggressor-near-diff-pair via segment proximity + 3×H), smps (PWR-3 FB-near-SW), subcircuits (XTL-1, STM-1 NRST=WARNING, STM-2, STM-6, USB-2, MIX-2 — schematic-connectivity via `model.schematic` from the netlist), connectors (CON-1, ESD-1). Explicit anti-myth test (`test_antimyth.py`) asserts no rule mentions a myth term. New golden fixtures `highspeed_4layer` {F2,F4,C4}, `smps_4layer` {PWR-3}.
  - **Phase 5 — schematic edit + libraries**: transactional write pipeline in `sexpr.py` (`edit_schematic`: flag gate + lock check → mutate → re-parse rollback on corruption → ERC report with delta), `set_symbol_property`/`duplicate_symbol` (clone, not lib injection — safer). `backends/library.py`: ranked symbol/footprint search over installed KiCad libs (exact>prefix>substring), JLCPCB SQLite search (jlcparts schema, actionable error when `KICAD_MCP_JLCPCB_DB` unset).
  - **Phase 6 — advanced + polish**: async `TaskStore` (`tasks.py`, thread pool) + `get_task_status`/`list_tasks`/`cleanup_tasks`; tool router (`tools/router.py`, 14 categories, `list_tool_categories`/`get_category_tools`/`search_tools`/`execute_tool`, completeness enforced by test); review/DRC history (`history.py`, `.kicad-mcp/history.jsonl`); Freerouting (`backends/freerouting.py`, async via task queue); prompts `plan_stackup`/`debug_emi`/`prepare_fab`; `docs/architecture.md`.
  - **Rip-up / delete routing** (2026-07-24): added `rip_up_nets(nets)` and `rip_up_footprint(reference)` to `backends/ipc.py` + `tools/routing.py`. Closes the delete-copper gap: the server could create tracks/vias but never remove them, and `move_footprint` stranded old copper. `rip_up_nets` validates names against `board.get_nets()`, collects `get_tracks()`+`get_vias()` on those nets (tracks/vias ONLY — never pads/zones), `board.remove_items(victims)` inside one `commit()` (single undo, rollback on error). `rip_up_footprint` scopes to the part's *local* pad nets (fanout ≤ 2 footprints), skipping shared GND/power nets so a plane is never torn up (`include_shared=True` to override). Both use **KiCad-9-safe `get_tracks()`/`get_vias()`** — NOT `get_items_by_net`/`get_connected_items`, which are kipy 0.7 / KiCad 10.0.1+ only (verified via `versionadded` annotations). 8 new fake-board unit tests + 1 `requires_kicad_gui` route-then-rip-up test. `router.py` routing category now lists both. **49 tools** now.
  - **v1.0 release prep + deferred gaps** (2026-07-04): closed two gaps — `duplicate_footprint` (IPC proto-copy of a placed footprint; KiCad 9 IPC has NO library-instantiation API, verified) and `get_netclasses` (IPC read of netclass constraints), both **verified live against KiCad 9.0.8**. **47 tools** at that point. Release: version → 0.1.0 (pyproject + `__init__` + server.json in sync), `CHANGELOG.md`, `docs/example.md` (STM32 review→fix→export walkthrough), `.github/workflows/release.yml` (PyPI Trusted Publishing on tag), `server.json` (MCP registry manifest), `PUBLISHING.md`. **Built + twine-checked the wheel/sdist and smoke-installed the wheel in a clean venv** (version 0.1.0, 47 tools, `kicad-mcp` console entry point present). NOT published (outward-facing, needs the maintainer's PyPI/registry credentials — see PUBLISHING.md).
- Remaining honest gaps (documented, not blockers): **placing a NEW footprint/symbol from a LIBRARY** — KiCad 9 IPC exposes no library-instantiation API and there is no schematic IPC at all, so `duplicate_footprint`/`duplicate_symbol` clone existing parts instead; **DSN export is not available via kicad-cli in KiCad 9** so `autoroute_board` needs a GUI-exported `.dsn`; the tool **router does not hide routed tools** — a deliberate NON-goal (true hiding needs a FastMCP tool-visibility feature and 47 tools is manageable; forcing a dispatch-registry would add fragility for marginal benefit); JLCPCB/Freerouting exercised against a synthetic DB / interface only; cross-OS (`uvx` on Linux/Windows) only via CI so far, not a live KiCad smoke on those OSes.
- Next action: **publish** (maintainer runs `PUBLISHING.md`: tag `v0.1.0` → PyPI Trusted Publishing, then `mcp-publisher` for the registry) and do a live `uvx kicad-mcp` + KiCad 9 smoke on Linux and Windows. The project is feature-complete against PLAN §8 and meets the §11 v1.0 definition of done.
- Machine note: `~/Library/Preferences/kicad/9.0/kicad_common.json` had `api.enable_server` flipped to `true` for the live smoke (backup: `kicad_common.json.kicad-mcp.bak`). Leave enabled for IPC work.
- Smoke test: `KICAD_MCP_SEARCH_PATHS=$(pwd)/tests/fixtures ./.venv/bin/python -m kicad_mcp` then call `get_server_status`; or run `./.venv/bin/python -m pytest -q`.
- Keep this section current. Update it at the end of every session with the phase reached and what is left.

## Mission — two pillars
1. Automation. Claude creates projects, edits schematics (experimental), places and routes on the PCB with live UI sync, runs ERC/DRC, and exports full fab packages.
2. Review engine (the differentiator). A rule engine that audits any KiCad design against the codified Hartley and Phil's Lab catalogs. This is what makes the project worth publishing. No existing KiCad MCP does this.

Target: KiCad 9.x, Python 3.10+, cross platform, MIT license.

## Hard architectural rules (never violate — PLAN.md §3)
- PCB mutation goes through the IPC API (kipy) ONLY. Never write `.kicad_pcb` while KiCad runs. Wrap multi item mutations in `begin_commit()`/`push_commit()` for single undo steps.
- Schematic read/write goes through the S-expression layer ONLY (kicad-skip preferred, sexpdata low level). There is no schematic IPC API in KiCad 9/10. Refuse writes when the file is open (check IPC connection and `~*.lck`). Gate writes behind `KICAD_MCP_ALLOW_SCHEMATIC_WRITE`. After every write, re-parse and run `kicad-cli sch erc` as a validity gate.
- Verification and export go through `kicad-cli` subprocess ONLY. Use `--format json` for DRC/ERC. Use `--exit-code-violations` for CI.
- Graceful degradation. If the KiCad GUI is not running, editing tools return actionable errors while analysis, review, and export keep working headless.
- Design all backends behind one abstract interface so KiCad 11 (SWIG gone, IPC gains headless + export) drops in cleanly.

## Pinned stack (ask before adding anything else)
```
python >= 3.10
mcp / fastmcp >= 1.9
kicad-python == 0.7.1   # kipy
sexpdata >= 1.0.2
kicad-skip >= 0.2.5
```
Do NOT use SWIG pcbnew or kiutils (KiCad 6/7 era, silent token loss on 9). Manage with uv.

## Config and security
- All env vars namespaced `KICAD_MCP_*` (`KICAD_MCP_SEARCH_PATHS`, `KICAD_MCP_CLI_PATH`, `KICAD_MCP_FREEROUTING_JAR`, `KICAD_MCP_ALLOW_SCHEMATIC_WRITE=0|1`, timeouts).
- Confine path validation to configured project roots. No arbitrary file reads outside project dirs.
- `shlex.quote` every subprocess arg.
- kicad-cli discovery: macOS `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`, Windows `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`, Linux `kicad-cli` on PATH. Allow `KICAD_MCP_CLI_PATH` override.

## Review engine guardrails (bake these into the data model from day one)
- Every rule is a class with `id`, `severity` (error/warning/info), `check(model) -> list[Finding]`, one line physics `rationale`, and a `citation`. Findings carry location (footprint ref, net, coordinates).
- Rules read a normalized design model, never raw files (PLAN.md §6).
- **Anti-myth guards must NEVER fire.** The engine must not warn on 90° corners, guard traces when a plane is one dielectric away, via fill, tight diff-pair coupling, or moats/cutouts drawn "for shielding". See `HARTLEY-M1..M7`. Hartley's credibility comes from removing superstition as much as adding rules. Add golden-file tests that a board full of 90° corners produces zero corner findings.
- **Length-match rules are in picoseconds, not millimeters.** Convert with ~6.1 ps/mm microstrip, ~6.7 ps/mm stripline (≈150 mm/ns). Intra-pair skew target ~0 ps, DDR3 example ≤ 5 ps.
- **Honor the corrections in `CHANGES.md`.** Do not regress them. Key ones: NRST 100 nF is a WARNING not error; split POWER not ground; cap effectiveness band ~100–200 MHz good / ~500–600 MHz useless; a signal may cross a split power plane only if pwr–gnd ≤ 8 mil; the "20–40 mm spread" and "2–3 mil cavity" and "250 MHz" are slide-sourced proxies, not spoken numbers.
- Overlapping Hartley/Phil rules are intentional. Implement once, cite both (e.g. `PHIL-MIX-1 ≈ HARTLEY-G2`, `PHIL-STK-6 ≈ HARTLEY-R5/C1`, `PHIL-USB-4 ≈ HARTLEY-M5`).
- False positives destroy trust. Use severity tiers, a `set_design_context` tool for rise times / clocks / target impedances, and a citation on every finding.

## Conventions and working agreement
- Small, reviewable commits. Tests for every module (golden-file rule tests with must-trigger and must-not-trigger fixtures).
- Green lint + pytest before any phase is called done. CI runs on Linux, macOS, Windows.
- Long operations (autoroute, batch export, full review of large boards) return a `task_id` immediately, then `get_task_status`/`list_tasks` (avoids MCP timeouts).
- Once tool count exceeds ~40, activate the router pattern (`list_tool_categories`, `get_category_tools`, `search_tools`, `execute_tool`).
- Borrow ideas from the four reference repos (PLAN.md §2) but only copy code from MIT-licensed ones with attribution. Never copy from bunnyf/pcb-mcp (license ambiguous).
- At the end of a session, update "Current status" above and hand back a short summary plus a smoke test.

## Phase map (PLAN.md §8) — stop for review at each boundary
0. Skeleton — repo scaffold, pyproject (uv), FastMCP bootstrap, config, backend factory, cli discovery, CI.
1. Headless foundation — project discovery/info, S-expr read layer, cli ERC/DRC/netlist/BOM/gerbers/renders, `export_fab_package`.
2. Review engine v1 — normalized model, registry/report, stackup + return-path + grounding + decoupling + DFM rules, golden-file tests.
3. Live editing via IPC — footprint/track/via/zone edits, commit wrapping, graceful errors, visual loop.
4. Review engine v2 — transmission-line/critical-length, crosstalk 3H, SMPS hot-loop, subcircuits, connector/ESD, anti-myth guards, review→fix loop.
5. Schematic editing (experimental) + libraries — feature-flagged write pipeline, JLCPCB parts DB.
6. Advanced + polish — Freerouting, router activation, history tracking, docs, PyPI + MCP registry.

Definition of done for v1.0: `uvx kicad-mcp` on all 3 OSes with KiCad 9; headless analyze/ERC/DRC/review/export; live place/route/zone with undo; review engine covers all 10 families with ≥ 60 cited rules tested against fixtures; anti-myth tests pass.
