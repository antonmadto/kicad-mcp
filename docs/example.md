# Example walkthrough — review → fix → export

An end-to-end tour of `kicad-mcp` on a small STM32 mixed-signal board. It shows
the intended loop: **analyze headless → review against the Hartley/Phil catalog →
fix (live or in the schematic) → re-review → export a fab package.** Tool calls
are shown as `tool_name(args)`; each returns JSON.

## 0. Orient

```
get_server_status()
```

Tells you which capabilities are live. With KiCad closed you still get
`verify`, `export`, `read_schematic`, `read_board`; live board editing needs a
running KiCad with the API enabled (Preferences → Plugins → Enable KiCad API).

```
list_projects()                       # discover projects under KICAD_MCP_SEARCH_PATHS
get_project_info("…/hades.kicad_pro")
get_board_info(project)               # copper layers, thickness, nets, extents
get_board_stackup(project)            # the physical stackup
```

## 1. Give the review engine context

Rule thresholds depend on rise time, clocks, target impedances, and which nets
leave the board — none of which live in the files. Provide them once:

```
set_design_context(
  project,
  rise_time_ns=0.5,                          # → f_knee ≈ 1 GHz, L_crit ≈ 43 mm
  clock_frequencies_hz={"HSE": 16e6},
  target_impedances={"USB_D+": 90, "USB_D-": 90},
  connector_nets=["USB_D+", "USB_D-", "VBUS"],
)
```

## 2. Review

```
review_design(project)
```

Returns findings grouped by severity, each with a rule id, a one-line physics
rationale, a citation, and a location — plus a markdown summary. For example:

```
🔴 HARTLEY-R5  Trace crosses a gap in its reference plane — net USB_D+, F.Cu @(41.2, 30.5)
   Return current flows directly under the trace; a gap forces it around,
   ballooning loop area and EMI.  Source: HARTLEY-R5/C1 ≈ PHIL-STK-6/MIX-4

🟡 PHIL-DEC-1  IC without a nearby 100 nF decoupling cap — U1 @(60, 42)
🟡 HARTLEY-F4  Differential pair 'USB_D' has 18 ps intra-pair skew (…) — match by delay, not length
```

Focus one family at a time with `review_topic(project, "return_path")` (families:
stackup, grounding, return_path, decoupling, dfm, transmission, crosstalk, smps,
subcircuits, connectors). The engine will **not** nag about 90° corners, guard
traces, via fill, or length-in-mm — those are debunked myths.

## 3. Fix

With KiCad open, fix on the live board (each edit is one undo step):

```
list_live_footprints()
move_footprint("C3", 60.5, 41.8)               # tuck the decoupling cap next to U1
route_trace([[41.2, 28], [41.2, 33]], 0.2, "F.Cu", "USB_D+")   # reroute off the gap
add_zone("In1.Cu", [[10,10],[70,10],[70,50],[10,50]], "GND")   # solid ground pour
refill_zones()
save_board()                                    # write to disk so cli/review see it
```

Or, experimentally, edit the schematic (needs `KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1`
and the file closed in KiCad):

```
set_symbol_property(project, "R7", "Value", "2.2k")   # I2C pull-up value
```

## 4. Re-review and verify

```
render_board(project, side="top")   # eyeball the change
review_topic(project, "return_path")# confirm R5 is gone
run_drc(project)                    # electrical/geometry rules
get_review_history(project)         # findings trending down over time
```

## 5. Export the fab package

```
run_erc(project)                    # schematic clean
export_fab_package(project)         # gerbers + drill + BOM + CPL, zipped
```

For a big board this can exceed the request timeout — use the async form:

```
task = export_fab_package_async(project)   # returns a task_id
get_task_status(task["task_id"])           # poll until status == "done"
```

## Prompts

Guided variants of the above: `review_board`, `plan_stackup`, `debug_emi`,
`prepare_fab`.
