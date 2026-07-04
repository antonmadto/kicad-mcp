# kicad-mcp

[![CI](https://github.com/antonmadto/kicad-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/antonmadto/kicad-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

An MCP server that lets Claude **analyze, review, and export** KiCad 9 designs —
and (with a running KiCad) edit boards live. Its differentiator is a built-in
**design-review engine** encoding the teachings of Rick Hartley and Phil Salmony
(Phil's Lab): stackup, return paths, grounding, decoupling, crosstalk, SMPS
layout, mixed-signal partitioning, and DFM — with anti-myth guards so it never
nags about 90° corners or "shield" moats.

> Status: **All phases (0–6) implemented.** Headless analysis/verify/export, a
> **23-rule review engine** across 10 families (with anti-myth guards), **live
> board editing via IPC** (verified against KiCad 9.0.8), experimental schematic
> writes, symbol/footprint/JLCPCB search, an async task queue, a tool router, and
> review history. 45 tools + 4 router tools, 4 prompts, 173 tests. See
> [`docs/architecture.md`](docs/architecture.md), [`PLAN.md`](PLAN.md) §8, and
> [`CLAUDE.md`](CLAUDE.md).

## The review engine (the differentiator)

`review_design` audits a board against a cited rule catalog and returns findings
grouped by severity — each with a rule ID, a one-line physics rationale, a
citation, and the exact location. v1 covers five families:

| Family | Rules | Checks |
|---|---|---|
| stackup | K1, K2, K5, K6 | signal-adjacent-to-plane, bad 4-layer order, tight pwr–gnd cavity, 2-layer ground |
| grounding | G1, G2 | split ground plane, separate analog/digital grounds |
| return_path | R5 | trace crossing a gap in its reference plane (geometric) |
| decoupling | DEC-1 | 100 nF near every IC |
| dfm | RTE-2, RTE-3, DFM-4 | power track width, via annular ring, board outline / mounting holes |

**Anti-myth by construction:** no rule fires on 90° corners, guard traces, via
fill, or length-in-mm. A golden test asserts a board full of 90° corners produces
zero findings. Use `set_design_context` to supply rise times / clocks / target
impedances the files can't contain.

## Tools

Foundation: `get_server_status` · `list_projects` · `get_project_info` ·
`create_project` · `get_board_info` · `get_board_stackup` ·
`list_schematic_components` · `list_schematic_nets` · `trace_net` · `run_erc` ·
`run_drc` · `export_gerbers` · `export_bom` · `export_netlist` · `export_step` ·
`render_board` · `export_fab_package`

Review engine: `review_design` · `review_topic` · `set_design_context` (+ the
`review_board` prompt)

Live editing (needs a running KiCad with the IPC API enabled):
`get_live_board_status` · `list_live_footprints` · `move_footprint` ·
`rotate_footprint` · `route_trace` · `add_via` · `route_differential_pair` ·
`add_zone` · `refill_zones` · `save_board`

The visual loop: edit live → `save_board` → `render_board` → inspect the PNG →
edit again. Every mutation is one undo step (Cmd/Ctrl-Z reverts it in the GUI).

## Architecture

One Python process (FastMCP, stdio). Three backends behind one capability
interface, selected at runtime with graceful degradation:

| Backend | Library | Role | Needs |
|---|---|---|---|
| `kicad-cli` | subprocess | ERC/DRC, netlist, BOM, gerbers, renders, fab package | KiCad 9 installed |
| S-expr | kicad-skip + sexpdata | schematic/board **read** (writes gated, experimental) | file closed in GUI |
| IPC | kicad-python (kipy) | live PCB editing (Phase 3) | running KiCad + IPC API |

If the GUI is down, editing tools return actionable errors while
analysis/review/export keep working headless.

## Install (dev)

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest
uv run ruff check .
```

Or with stock tooling:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
```

## Run

```bash
python -m kicad_mcp        # stdio MCP server
# or the installed console script:
kicad-mcp
```

The first tool to call is **`get_server_status`**, which reports which backends
are live, what capabilities are available, and the detected KiCad version.

## Configuration (`KICAD_MCP_*`)

| Variable | Meaning | Default |
|---|---|---|
| `KICAD_MCP_SEARCH_PATHS` | `os.pathsep`-separated project roots (also the file-access confinement boundary) | `~/Documents/KiCad`, `~/KiCad` |
| `KICAD_MCP_CLI_PATH` | override for the `kicad-cli` executable | auto-discovered per platform |
| `KICAD_MCP_FREEROUTING_JAR` | Freerouting jar for autoroute (Phase 6) | unset |
| `KICAD_MCP_ALLOW_SCHEMATIC_WRITE` | `1` to enable experimental schematic writes | `0` |
| `KICAD_MCP_CLI_TIMEOUT` | seconds for kicad-cli subprocess calls | `120` |
| `KICAD_MCP_IPC_TIMEOUT` | seconds for IPC calls | `10` |

kicad-cli is discovered at the platform default
(`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` on macOS,
`C:\Program Files\KiCad\9.0\bin\kicad-cli.exe` on Windows, `kicad-cli` on PATH on
Linux), overridable via `KICAD_MCP_CLI_PATH`.

## License

MIT — see [`LICENSE`](LICENSE).
