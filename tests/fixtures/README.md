# Test fixtures

## `sample_project/`

A minimal but **valid** KiCad 9 project used by the read/verify/export tests:

- `sample.kicad_pro` — project file
- `sample.kicad_sch` — two resistors (R1 10k, R2 1k) on an embedded `Device:R`
  symbol, wired into net `N1` (so `trace_net` has a real 2-node net)
- `sample.kicad_pcb` — 2-layer board: FR4 stackup, 20×10 mm edge cut, two
  `R_0603` footprints, a routed GND segment

**Provenance / licensing:** this project is **self-authored** for kicad-mcp (MIT).
It is *not* copied from KiCad's bundled demos/templates (which are GPL). Only the
`Device:R` symbol *geometry* is extracted from the installed KiCad symbol library
at generation time so the schematic passes `kicad-cli sch erc`; the extracted
symbol block is standard library data, not design content.

Validated against KiCad 9.0.8: ERC and DRC both run and return parseable JSON,
and a full fab package (gerbers + drill + BOM + CPL) exports cleanly.

### Regenerating

`generate_sample_project.py` reproduces the fixture. It needs KiCad installed
(to read `Device.kicad_sym`); point it at your install with
`KICAD_SYMBOL_DIR=/path/to/kicad/symbols` if auto-discovery fails.

```bash
python tests/fixtures/generate_sample_project.py
```

## `review/` — review-engine golden boards

Synthetic boards that drive the Phase-2 review engine, one per rule scenario:

| Board | Expected findings |
|---|---|
| `clean_4layer` | none (must-not-trigger) |
| `antimyth_2layer` | none — has 90° track corners; anti-myth guard |
| `faults_4layer` | K2, DEC-1, RTE-2, RTE-3, DFM-4 |
| `split_ground_4layer` | G1, R5 |
| `thick_cavity_4layer` | K5 |

These are **self-authored** (MIT) and built for the engine's *name-based* parser
(stackup/zones/tracks by layer name + net). Copper layer-ID numbering in the
`(layers)` table is not GUI-canonical, so they are not guaranteed to open in the
KiCad editor — they exist to unit-test the rules, not to be edited.

Regenerate with `python tests/fixtures/review/generate_review_fixtures.py` (no
KiCad install needed — these boards are fully synthetic).
