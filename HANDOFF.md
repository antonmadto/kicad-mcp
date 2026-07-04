# HANDOFF — kicad-mcp

> **For the next session (read this first, then `CLAUDE.md`).** This project is
> built, tested, published to GitHub, and CI-green on 3 OSes. The remaining job
> is **making it genuinely useful in real use** — connect it to the user's Claude
> and run it on the user's *own* KiCad boards, then fix whatever is rough. This
> doc is self-contained: goal → what's done → what's next → facts you'll need.

---

## 1. The goal (why this exists)

An MCP server that lets Claude **create, review, and export KiCad 9 PCB designs**.
Two pillars:

1. **Automation** — discover/read projects, run ERC/DRC, export gerbers/BOM/fab
   packages, and (with KiCad open) live-edit the board over the IPC API.
2. **The differentiator: a design-review engine** — audits a board against the
   codified Rick Hartley + Phil Salmony (Phil's Lab) rule catalogs (stackup,
   return paths, grounding, decoupling, crosstalk, SMPS, mixed-signal,
   transmission-line, connectors/ESD, DFM), with **anti-myth guards** so it never
   nags about debunked stuff (90° corners, guard traces, via fill).

The user's north star for next session, in their words: **"make the MCP really
working."** That means: it's connected to their Claude, and it does something
genuinely useful on *their real board* — not just on the synthetic test fixtures.

## 2. What's done (all of PLAN.md phases 0–6)

- **47 tools + 4 router tools, 4 prompts, 23 review rules across 10 families.**
- **179 tests pass, ruff-clean, CI green** on Linux/macOS/Windows × Python
  3.10–3.13. Live IPC editing **verified against real KiCad 9.0.8** (moved/rotated
  parts, routed traces + diff pairs, added vias/zones, duplicated a footprint,
  read netclasses, saved → re-parsed → rendered).
- Three adversarial multi-agent reviews were run across the phases; **38 confirmed
  findings, all fixed** (path-traversal guard, UTF-8 encoding, atomic schematic
  write, diff-pair mis-pairing, plane-detection on cut boards, etc.).
- **Published:** https://github.com/antonmadto/kicad-mcp (public, MIT, CI badge,
  topics set). Wheel/sdist build + `twine check` pass; the wheel installs in a
  clean venv with a working `kicad-mcp` console entry point.
- Docs: `CLAUDE.md` (operating rules + full status), `PLAN.md` (master spec),
  `docs/architecture.md`, `docs/example.md` (review→fix→export walkthrough),
  `PUBLISHING.md`, `CHANGELOG.md`. Rule catalogs in `docs/rules/`.

Architecture in one line: one FastMCP/stdio process; three backends behind one
capability interface — **kicad-cli** (headless verify/export), **S-expr**
(kicad-skip/sexpdata, schematic + file reads, gated writes), **IPC/kipy** (live
board editing) — selected at runtime with graceful degradation.

## 3. What's next — "make it really working" (priority order)

**① Connect it to the user's Claude and confirm the tools fire.**
The user must run this themselves (the `claude` CLI is NOT reachable from the
Bash sandbox — different PATH):
```bash
claude mcp add kicad --env KICAD_MCP_SEARCH_PATHS="<dir with their .kicad_pro files>" \
  -- "/Users/antonmadto/Documents/Claude/Projects/KiCAD MCP/.venv/bin/kicad-mcp"
```
Then restart Claude Code / `/mcp`. First tool to call: **`get_server_status`**.
Next session: verify it connects and returns the backend/capability list.

**② Run it on the user's REAL board (biggest value).**
So far it's only been exercised on synthetic fixtures + the tiny 2-resistor
sample. Point `KICAD_MCP_SEARCH_PATHS` at the user's actual projects, then:
`list_projects` → `get_board_info` → `review_design` → read the findings *with the
user* and judge whether they're correct/useful on a real design. **Expect to tune
heuristics** — real boards will surface false positives/negatives the synthetic
fixtures can't. This is the core of "really working."

**③ Do a real live-edit loop with KiCad open.**
Launch the **standalone PCB editor** (not the project manager) with a board:
`open -a "/Applications/KiCad/KiCad.app/Contents/Applications/pcbnew.app" <board>`
— IPC sockets are per-PID (`/tmp/kicad/api-<pid>.sock`); the backend probes all
and prefers the one with an open board. Then try move/route/zone/`save_board` and
the review→fix loop end to end, on something the user cares about.

**④ Publish to PyPI (pending the user's PyPI account).**
Everything is staged. Two paths in `PUBLISHING.md`: Trusted Publishing (user adds
a "pending publisher" on pypi.org → you push tag `v0.1.0` → `release.yml`
auto-publishes) or a PyPI token → `twine upload dist/*`. After that, anyone can
`uvx kicad-mcp`.

**⑤ Polish surfaced by real use.** Likely candidates: default search paths, tool
error messages, review-report readability, and any FastMCP result-shape quirks
when tools are called for real (vs. the direct-impl calls used in tests).

## 4. Known limitations (documented, not bugs — don't "fix" by breaking scope)

- **KiCad 9 IPC cannot instantiate a footprint/symbol from a library**, and has
  **no schematic IPC at all** → `duplicate_footprint`/`duplicate_symbol` clone an
  existing part instead. Verified against KiCad's own API — this is a KiCad limit.
- **No Specctra DSN export via kicad-cli in KiCad 9** → `autoroute_board`
  (Freerouting) needs a GUI-exported `.dsn`.
- Schematic **writes are experimental**, off unless `KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1`.
- JLCPCB search needs a local `KICAD_MCP_JLCPCB_DB`; Freerouting needs
  `KICAD_MCP_FREEROUTING_JAR` + Java. Both are interface-verified, not run against
  a live DB/JAR here.
- The tool router does **not hide** routed tools (all 47 exposed) — a deliberate
  non-goal; 47 is manageable and true hiding needs a FastMCP visibility feature.

## 5. Machine facts you'll need (this is the user's Mac)

- **Repo:** `/Users/antonmadto/Documents/Claude/Projects/KiCAD MCP` — git on
  `main`, remote `origin` → github.com/antonmadto/kicad-mcp, `gh` authed as
  `antonmadto`.
- **venv:** `.venv/` (Python 3.13) with all deps + the package installed editable.
  Run tests: `./.venv/bin/python -m pytest -q`. Lint: `./.venv/bin/ruff check .`.
- **KiCad:** 9.0.8 at `/Applications/KiCad/KiCad.app`. Its IPC API was **enabled**
  (`~/Library/Preferences/kicad/9.0/kicad_common.json`, `api.enable_server=true`;
  backup `kicad_common.json.kicad-mcp.bak`). Leave on for IPC work.
- **Built artifacts:** `dist/kicad_mcp-0.1.0-{whl,tar.gz}` (gitignored).
- **`claude` CLI is not on the sandbox PATH** — anything `claude mcp …` must be run
  by the user in their own terminal.
- **Ground rules live in `CLAUDE.md` §"Hard architectural rules"** — honor them:
  PCB mutation via IPC only, schematic via S-expr only (write-gated), verify/export
  via kicad-cli only, `KICAD_MCP_*` env namespace, path confinement, `shell=False`.

## 6. Definition of "done" for next session

The user can open Claude, say *"review my board at `<path>`"* (or *"route this net"*
with KiCad open), and get a **correct, useful** result on a **real** design — and
`pip install kicad-mcp` works if they chose to publish. Everything else is polish.
