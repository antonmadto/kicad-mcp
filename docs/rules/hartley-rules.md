# Rick Hartley Rule Catalog (machine-checkable)

Rule IDs use prefix `HARTLEY-`. Severity suggestions: E = error, W = warning, I = info.

**Primary sources**

- S1: AltiumLive 2018 slides, "The Extreme Importance of PC Board Stack-Up" — https://files.resources.altium.com/sites/default/files/uberflip_docs/file_537.pdf
- S2: AltiumLive keynote, "What Your Differential Pairs Wish You Knew" — https://www.youtube.com/watch?v=QG0Apol-oj0 — **auto-transcript watched end-to-end 2026-07-04; timestamps below are from the video.**
- S3: "How to Achieve Proper Grounding" (AltiumLive, streamed 2019-11-11, 2:19:51) — https://www.youtube.com/watch?v=ySuUZEjARPY — **auto-transcript watched end-to-end 2026-07-04; timestamps below are from the video** (supersedes the earlier third-party summary at startingelectronics.org/articles/proper-grounding/).
- S4: Sierra Circuits interviews — https://www.protoexpress.com/blog/rick-hartley-pcb-design-recommendations-to-minimize-emi/ · https://www.protoexpress.com/blog/how-grounding-controls-noise-and-emi-by-rick-hartley/ · https://www.protoexpress.com/blog/7-pcb-design-tips-by-rick-hartley/
- S5: EMA "5 PCB Design Myths Debunked by Rick Hartley" — https://www.ema-eda.com/about/blog/5-pcb-design-myths-debunked-rick-hartley
- S6: Altium "Ground in PCB Layout — Separate or Not Separate?" — https://www.youtube.com/watch?v=vALt6Sd9vlY
- S7: Rick Hartley × Robert Feranec, "How to Decide on Your PCB Layer Ordering, Pouring and Stackup" (2021, 1:16:30) — https://www.youtube.com/watch?v=52fxuRGifLU — **auto-transcript watched 2026-07-04.**

Fidelity note (updated 2026-07-04): S2 and S3 have now been verified against Hartley's **own words in the videos** (timestamps inline), not paraphrases — grounding rules G1–G4 are no longer "third-party paraphrase" confidence. Where the earlier third-party summaries and his own words differed, **his words win** (see CHANGES.md). His actual position on mixed-signal grounds: **one continuous ground plane, partition by placement; if you must isolate domains, split the POWER plane only and leave ground continuous** [S3 1:15:04–1:18:22]. Numbers that appear only on his slides (not spoken in S2/S3/S7) are marked "(slide, S1)".

## Key constants for the engine

```
v_inner ≈ 150 mm/ns (6 in/ns) ≈ 6.67 ps/mm; v_outer ≈ 1.15 × v_inner
  # cross-check: Phil's Lab #110 measures ~6.1 ps/mm microstrip, ~6.7 ps/mm stripline (Er≈4) — consistent
f_knee = 0.5 / t_rise
typical modern t_rise = 0.3–0.7 ns → L_crit ≈ 10–25 mm
return current localizes directly under the trace above ~20 kHz [S3 27:01]
cap effectiveness: "wonderful" < 100–200 MHz, "no help at all" > 500–600 MHz [S3 1:23]; engine proxy ≈ 250 MHz (slide, S1)
pwr–gnd cavity target ≤ 0.2 mm (8 mil) [verified S3 1:18:49]; "preferably 2–3 mil" is slide (S1)
signal may cross a split POWER plane only if pwr–gnd ≤ 8 mil; else ~20–40 dB worse EMI [S3 1:18–1:22]
crosstalk keep-out ≥ 3×H (H = height above reference plane); at 1×H ≈ 12% near / 1–2% far [S2 38:40]
diff pair linear crossing region = center 60% of edge (NOT 80%) [S2 41:00]
skew_allowed ≈ ±0.3 × t_rise × v  → ±50 mm @100 MHz, ±26 mm @250 MHz, ±1.5 mm @10 Gbps [S2 44:43–47:29]
return vias when changing reference: 1 nearby for digital, 4 around the via for sensitive analog [S3 1:30:14]
```

## A. Foundational axioms (not checks, but engine framing)

- **A1.** Energy travels in the E/H fields in the dielectric, not in the copper. Copper is a waveguide. All rules below are field-containment checks. [S1, S2]
- **A2.** Every trace is half a transmission line; the reference plane is the other half. A trace without a defined adjacent return conductor is a defect. [S1, S2]
- **A3.** Power delivery is a high-frequency event (harmonics to 0.5/t_rise); energy comes from the pwr–gnd dielectric cavity, not "the power plane." [S1, S4]
- **A4.** 85–90% of a trace's coupling is to the adjacent plane(s), not neighboring traces — including the other half of a diff pair. [S2 26:35 "85 to 90 percent of the coupling from each of these lines is to the plane below"]

## B. Return paths and plane changes

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-R1 | E | Every signal layer must be exactly one dielectric from a solid plane (ground preferred). Flag any signal layer 2+ dielectrics from its reference. | Distant reference → field spread → noise coupling | S1, S4 |
| HARTLEY-R2 | I | For each signal via, prefer transitions between the two sides of the same plane (fields couple through the antipad; no discontinuity). Pass if start/end layers share a common adjacent plane. | No return discontinuity | S1, S2 |
| HARTLEY-R3 | E | Signal via transitioning between layers referenced to two different ground planes requires a ground stitching via nearby. Ideal ≤ 0.5–1.0 mm; flag if > 2 mm. Applies to each line of a diff pair (one shared return via acceptable). **Hartley's rule of thumb: a digital signal needs one return via nearby; a sensitive analog signal gets four return vias placed around the signal via to fully contain the fields** [S3 1:30:14–1:30:50]. | Return current must jump planes locally | S1, S2, S3 |
| HARTLEY-R4 | E/W | Signal via transitioning from power-referenced to ground-referenced layer: below ~100–200 MHz a stitching/decoupling cap near the via helps; above ~500–600 MHz caps are inductive and do "nothing," so require a tight pwr–gnd plane pair (≤ 0.2 mm / 8 mil). **Verified: routing across a split power plane is acceptable only if the pwr–gnd planes are "eight mils separated or less"** [S3 1:18:42–1:19:03]; otherwise a signal referenced to a split plane measured "20 to 40 dB worse" EMI than one over continuous ground [S3 1:22:19–1:22:53]. The "displacement fields spread 20–40 mm" figure is from the stackup deck (slide, S1) — not spoken in S2/S3. | Local displacement current path | S1, S3 |
| HARTLEY-R5 | E | Return path under any trace must be continuous. Flag traces crossing splits, slots, antipad rows, or plane edges. **Above ~20 kHz all return current flows directly under the trace, driver to receiver** [S3 26:47–27:26]; a trace routed over a slot in the ground plane measured **20–30 dB worse** EMI than traces not over the slot [S3 42:59]. | Loop area and field volume balloon | S3 |
| HARTLEY-R6 | — | Via fill material is electrically irrelevant (return current on barrel outside). No check on fill; do check return vias (R3). "You can fill it with peanut butter, it doesn't matter" [S2 1:01:17]. | — | S2 1:01:17 |

## C. Stackup

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-K1 | E | No two adjacent signal layers without an intervening or common adjacent plane (e.g. flag Sig-Sig-Gnd-Sig). | Fields from layer 1 couple through layer 2 signals | S1 |
| HARTLEY-K2 | W | Flag conventional 4-layer Sig/Pwr/Gnd/Sig at 1.6 mm (planes ~40 mil apart = poor HF power + poor field containment). Recommend (A) GND/Sig+Pwr/Sig+Pwr/GND or (B) Sig+pouredPwr/GND/GND/Sig+pouredPwr with thin dielectrics to ground. **Hartley pours power on the signal layers (and overlaps the pours L2/L3) so every signal references ground and copper stays balanced** [S7 42:14, 45:45]. | HF power delivery + containment | S1, S7 |
| HARTLEY-K3 | W | 6-layer: avoid Sig/Pwr/Sig/Sig/Gnd/Sig. Good: Sig/GND/Pwr/Sig/GND/Sig-Pwr variants; best: Sig-Pwr/GND/Sig-Pwr/GND/Sig-Pwr/GND (power poured on signal layers, every signal adjacent to ground). | Every signal referenced to ground | S1 |
| HARTLEY-K4 | W | Flag signal layers whose only adjacent plane is a power plane when the pwr–gnd cavity is thick (vendor app-note 8-layer Sig/Gnd/Sig/Pwr1/Pwr2/Sig/Gnd/Sig fails EMI). | Power reference without tight gnd coupling | S1 |
| HARTLEY-K5 | E | Power and ground planes must be an adjacent pair with dielectric ≤ 0.2 mm (8 mil); the "preferably 2–3 mil" target is from the stackup deck (slide, S1). Never separate pwr and gnd planes with signal layers. Verified: the ≤ 8 mil (0.2 mm) pwr–gnd spacing is the same threshold below which a signal may cross a split power plane without an EMI penalty [S3 1:18:49]; high-end boards put GND on L2 / PWR on L3 with HDI vias "really close together" [S7 1:13:45]. | Interplane capacitance is the only HF charge source | S1, S3, S7 |
| HARTLEY-K6 | W | 2-layer boards with ns-regime rise times: bottom layer under every top-side signal route must be solid ground (or co-planar return with tight spacing). Flag routes over non-ground bottom copper. | Return path guarantee at low layer count | S1, S4 |
| HARTLEY-K7 | I | IC app-note layouts/stackups are "wrong until proven right" — never auto-import as rules. | Vendor app notes routinely violate field physics | S2, S5 |

## D. Grounding

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-G1 | E | One solid continuous ground pour/plane. Flag splits/moats/cuts in the ground plane unless no signal, power, or field path crosses the split. Verified: "split power only, **leave a continuous ground plane**" [S3 1:18:16]. | Splits divert return current | S3 1:15:04, 1:18:16; S5; S6 |
| HARTLEY-G2 | E | Mixed signal: do NOT split analog/digital grounds by default. One plane, partition by placement — digital circuitry+routing over one region, analog over another; never route digital over the analog region. **Verified: parts needing "100 dB or greater isolation" were put on the same board with a continuous ground plane and solved purely by physical separation** [S3 1:15:04]. The old "join grounds at a single point near the converter" exception is a legacy-datasheet last resort, not his recommendation. | Placement partitioning beats splits | S3 1:15:04–1:16:00; S5; S6 |
| HARTLEY-G3 | W | Star/single-point grounding valid only < ~1 MHz (audio/DC). Flag star topology when any signal f_knee > 1 MHz. **Note: "star"/"single-point" is NOT discussed in the grounding talk (S3) — this rule rests on S5 (myths article), not S3. Treat as W, cite S5 only.** | Long spokes are inductive antennas | S5 |
| HARTLEY-G4 | — | Board planes are return/reference planes, not "0 V magic"; check them as transmission-line halves. Earth, chassis, board reference are three different things. Verified: "the term ground refers to the earth; we first used the earth ~300 years ago to divert lightning" — earth is a safety/lightning concept, distinct from the board reference [S3 1:34–1:56]; a plane "is not a shield, it's a reference" [S7 47:05]. | Engine framing | S3 1:34; S4; S7 47:05 |
| HARTLEY-G5 | E/W | If two power domains must be isolated, split the POWER plane (not ground). A signal may be routed across a split power plane **only if the pwr–gnd dielectric is ≤ 8 mil (0.2 mm)** so displacement current couples across; flag any trace crossing a split power plane where the adjacent pwr–gnd spacing > 0.2 mm. Referencing a split (vs continuous ground) measured 20–40 dB worse EMI [S3 1:22:32]; bridging caps recover it only below ~100–200 MHz [S3 1:23:00]. | Displacement return path needs a tight cavity | S3 1:18:04–1:23:18 |

## E. Rise time, critical length, skew

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-F1 | I | Circuit frequency = rise time, not clock. f_knee = 0.5/t_rise. Get t_rise from IBIS/SPICE, not datasheets. (Case: 500 kHz clock failed emissions at 250–300 MHz after die shrink.) | Harmonic content | S2 |
| HARTLEY-F2 | E | L_crit ≈ (t_rise/2) × v (v_inner ≈ 150 mm/ns; outer ×1.15). Flag any unterminated/impedance-uncontrolled trace longer than L_crit. Modern logic (0.3–0.7 ns) → 10–25 mm. | Transmission-line onset | S2 |
| HARTLEY-F3 | — | Do NOT flag impedance discontinuities (neck-downs, BGA breakouts) with length ≪ L_crit — electrically invisible. | Lumped-region exception | S2 |
| HARTLEY-F4 | W | Diff pair intra-pair skew budget in TIME: skew_allowed ≈ ±0.3 × t_rise × v, crossing within the **center 60%** of the edge — Hartley explicitly rejects the "center 80% (10–90%)" figure; the *guaranteed* linear region is only the center 60% [S2 41:00–41:26]. Verified examples: 100 MHz clock ⇒ ~720 ps edge ⇒ ±360 ps ≈ **±50 mm** (John Deere study failed only after 55–70 mm mismatch); 250 MHz ⇒ **±26 mm**; 10 Gbps/10 GHz ⇒ **±1.5 mm** [S2 44:43–47:29]. "I have never in my life length-matched the two lines of a differential pair, including at 10 gigahertz" — match by time, not length (outer layers ~15% faster; glass weave varies Er). | Edge linear region | S2 |
| HARTLEY-F5 | W | If data rate > 2–3 Gbps AND laminate uses **1080/106** glass: flag. ΔEr up to **0.5** (bundle-vs-window) → up to **5 mm equivalent skew per 75 mm** of routing [S2 48:19–49:55]. Require spread/flattened ("ribbon not rope") glass or panel rotation so a trace never runs along one weave [S2 50:11–50:31]. | Glass-weave skew | S2 |

## F. Decoupling and power delivery

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-D1 | E | Decoupling caps do "a wonderful job" only up to ~100–200 MHz and are "no help at all" above ~500–600 MHz [S3 1:23:00–1:23:18] (engine uses ~250 MHz as a single conservative proxy; the 250 number itself is slide-sourced, S1). If any f_knee is in/above that band and no closely spaced pwr–gnd plane pair (≤ 0.2 mm) exists → error. | Above ~½ GHz caps are inductors; only thin cavities supply charge | S1, S3 |
| HARTLEY-D2 | W | Caps as close as possible to IC power pins, minimal via/trace inductance (short wide connections, vias at pads). Metric: pad-to-via distance and connection width. Verified quote: "I solve most EMI problems by simply adding return vias to boards or changing the positions of decoupling caps" [S2 1:00:37]. | Loop inductance | S2 1:00:37; S3 1:30:14 |
| HARTLEY-D3 | I | Skin effect: HF current uses copper surface only — do not require heavy copper (1 oz) planes for HF power delivery; 0.5 oz suffices. | Skin depth | S4 |

## G. Slots, connectors, cables, crosstalk

| ID | Sev | Check | Rationale | Src |
|---|---|---|---|---|
| HARTLEY-C1 | E | Any trace crossing a plane split, slot, or large antipad void in its reference plane → error. Verified: a trace over a slot measured 20–30 dB worse EMI [S3 42:59]; residual common-mode current then radiates from attached cables. | Loop area | S3 42:59; S5 |
| HARTLEY-C2 | W | Flag dense via fields near transitions between non-adjacent cavities with widely spaced planes — displacement fields spread and couple into everything in radius. The "20–40 mm" spread figure is from the stackup deck (slide, S1); it is NOT spoken in S2/S3 (in S3 the "20–40" is a dB EMI figure, not mm). | Field spread | S1 (slide) |
| HARTLEY-C3 | W | Flag single 100 Ω differential terminations on pairs leaving the board or > ~1 Gbps. Prefer two 50 Ω with center tap through 5–20 pF to reference. Verified mechanism: an off-center crossing point "will develop common-mode current in one or the other" line → cable EMI [S2 52:11]; the two-resistor + center-tap termination detail is not spoken verbatim in S2 (design derivation). | Residual skew → common-mode → cable EMI | S2 52:11 (mechanism) |
| HARTLEY-C4 | W | Keep other signals ≥ 3×H (Hartley "two or three times height above the plane") from diff pairs; general parallel-run spacing ≥ 2–3×H. Verified: at 1×H, crosstalk ≈ 12% into the near line vs 1–2% into the far line → guaranteed imbalance; "you can't route other things terribly close to differential pairs" [S2 37:31–38:40, 55:46]. | Crosstalk asymmetry | S2 |

## H. Anti-myth guards (rules the engine must NOT fire)

| ID | The engine must NOT... | Why | Src |
|---|---|---|---|
| HARTLEY-M1 | Flag 90° corners for SI below tens of GHz | Not based in physics; manufacturability at most. (Not discussed in S2/S3 — rests on S5.) | S5 |
| HARTLEY-M2 | Enforce minimum intra-pair gap as an SI rule | Return is in the plane, not the other line. Verified: the wider/looser 0.18 mm line / 0.36 mm gap pair sits clear of the eye mask at 3 GHz while the tight 0.1 mm / 0.16 mm pair infringes it; "tight coupling doesn't lower crosstalk" [S2 33:58–34:54, 37:31] | S2 |
| HARTLEY-M3 | Suggest guard traces when a plane is one dielectric away | 85–90% coupling is to the plane [S2 26:35]; unstitched guards are resonant antennas. (The "guard trace" recommendation itself is not spoken in S2 — the coupling fact is S2, the guard framing is S5.) | S2 26:35 (fact); S5 (guard) |
| HARTLEY-M4 | Worry about via fill conductivity | "There is no current inside a via — the return current is on the outside of the via barrels... you can fill it with peanut butter, it doesn't matter" [S2 1:01:03–1:01:19] | S2 1:01:03 |
| HARTLEY-M5 | Express length-match rules in mm instead of ps | Velocity varies by layer (~15%) and local Er [S2 45:35–46:05]. (Phil's Lab agrees: "we shouldn't do length matching, we should do delay matching" — #110.) | S2 |
| HARTLEY-M6 | Discourage burying critical pairs between planes | Solid planes give 60–80 dB isolation — valid mitigation [S2 36:00]. Caveat: Hartley would still avoid routing signals *inside* a plane cavity above ~a few Gbps because you can't add stitching vias through solid planes [S7 32:33–32:52]. | S2 36:00; S7 |
| HARTLEY-M7 | Treat a plane as a "shield" | A plane "is not a shield, it's a reference" [S7 47:05]; splitting/moating it to "shield" a section removes the return path and makes EMI worse (video-controller isolation example) [S3 1:15:33–1:16:00]. The engine must not reward moats/cutouts drawn "for shielding." | S7 47:05; S3 1:15:33 |
