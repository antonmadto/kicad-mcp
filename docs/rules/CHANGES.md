# Rule catalog CHANGES — video verification pass

Date: 2026-07-04
Method: watched the source videos on YouTube via the auto-generated transcript (YouTube's own caption track, timestamps are the video's). Cross-checked slides at key sections. Where a third-party summary and Hartley's own words differed, **his words win**. Numbers are kept in machine-checkable form; length-match rules are in picoseconds. Every change below carries a timestamp as evidence.

Videos watched end-to-end this pass:
- Hartley — "How to Achieve Proper Grounding" (ySuUZEjARPY, 2:19:51)
- Hartley — "What Your Differential Pairs Wish You Knew" (QG0Apol-oj0, 1:03:20)
- Hartley × Feranec — "PCB Layer Ordering, Pouring and Stackup" (52fxuRGifLU, 1:16:30)
- Phil's Lab #65 — "KiCad STM32 PCB Design Full Tutorial" (aVUqaB0IMh4, 1:40:03)
- Phil's Lab #60 — "Switching Regulator PCB Design" (AmfLhT5SntE, 25:04)
- Phil's Lab #110 — "PCB High-Speed Delay Matching" (xdUR3NzXUkc, 19:14) — substitute for #67
- Phil's Lab #152 — "Ceramic Capacitor DC Bias Effects" (Tfatk7wmnhs)
- Phil's Lab #88 — "Mixed-Signal Hardware/PCB Design Tips" (v6fTa6LRJLI, 18:17)

Not verified this pass (auto-transcript unavailable / lower priority): #67 USB HS (wQ37NxSeP48 — "Could Not Get Transcript"), #59 FPGA/DDR, #131 final-touches checklist. Their catalog entries are unchanged and flagged in-file.

---

## A. Hartley — grounding video promoted from paraphrase to verbatim

The grounding rules G1–G4 were previously based on third-party paraphrases (startingelectronics.org summary). They have now been checked against Hartley's own words in ySuUZEjARPY. Fidelity note in `hartley-rules.md` updated accordingly.

### Verified (confirmed correct, timestamp added)
| Rule | Evidence |
|---|---|
| A4 (85–90% coupling to plane) | S2 26:35 "85 to 90 percent of the coupling from each of these lines is to the plane below" |
| F4 (skew ±50/±26/±1.5 mm @100 MHz/250 MHz/10 Gbps; center **60%** not 80%) | S2 41:00–41:26, 44:43–47:29; "I have never in my life length-matched… including at 10 gigahertz" |
| F5 (1080/106 glass, ΔEr 0.5, 5 mm per 75 mm) | S2 48:19–49:55 |
| M2 (looser 0.18/0.36 pair beats tight 0.1/0.16 on a 3 GHz eye) | S2 33:58–34:54 |
| M4/R6 (via fill irrelevant) | S2 1:01:03–1:01:19 "you can fill it with peanut butter" |
| M6 (planes give 60–80 dB isolation) | S2 36:00 |
| C4 (12% near / 1–2% far at 1×H; keep 2–3×H away) | S2 37:31–38:40, 55:46 |
| D2 (solve most EMI with return vias / moving caps) | S2 1:00:37 verbatim |
| R5 (return current under the trace) | S3 27:01 "above 20 kilohertz all of the return current will travel directly below the trace" |
| G4 (earth = safety/lightning, distinct from board reference) | S3 1:34–1:56; S7 47:05 "it's not a shield, it's a reference" |
| K2/K5 (pour power on signal layers; tight pwr–gnd) | S7 42:14, 45:45, 1:13:45 |

### Corrected
1. **G2 — split POWER, not ground.** Was "do not split analog/digital grounds by default… grounds join at single point." His actual instruction: keep ground continuous; if domains must be isolated, split the **power** plane only. Evidence S3 1:18:04–1:18:22 "split power only, leave a continuous ground plane"; 1:15:04 parts needing "100 dB or greater isolation" solved by placement on a continuous ground plane.
2. **G3 — star grounding is NOT in the grounding talk.** "Star"/"single-point" has zero matches in S3. Rule kept but recited to S5 (myths article) only; note added so it is not attributed to the video.
3. **D1 — cap effectiveness band.** Was a flat "~200–300 MHz." His spoken numbers: caps do "a wonderful job" below ~100–200 MHz and are "no help at all" above ~500–600 MHz (S3 1:23:00). The single "250 MHz" proxy is retained but recited to the slide deck (S1).
4. **R4 / C2 — the "20–40 mm field spread" is a slide number, not spoken.** In S3 the "20–40" figure is **dB** of EMI (referencing a split vs continuous ground, 1:22:32), not millimetres. The mm-spread figure lives on the S1 stackup slides; C2 re-sourced to S1, and the S2/S3 co-citation removed.
5. **K5 — "2–3 mil" cavity is a slide target;** the spoken, verified threshold is ≤ 8 mil (0.2 mm) (S3 1:18:49). Both retained, sourced correctly.
6. **M1 / M3 — recited to S5.** 90° corners and guard traces are not discussed in S2/S3; M3's *coupling* rationale (85–90%) is S2-verbatim, but the guard-trace framing is S5.

### Added (new machine-checkable rules)
- **HARTLEY-G5 (E/W):** if two power domains must be isolated, split the POWER plane; a signal may cross a split power plane **only if the pwr–gnd dielectric ≤ 8 mil (0.2 mm)**; else flag. Referencing a split measured 20–40 dB worse EMI (S3 1:22:32); bridging caps recover it only < ~100–200 MHz (S3 1:23:00). Evidence S3 1:18:04–1:23:18.
- **R3 extension — return-via count:** digital signal → one return via nearby; sensitive analog → **four return vias around the via**. Evidence S3 1:30:14–1:30:50.
- **R5 extension — 20 kHz localization + 20–30 dB slot penalty.** Above ~20 kHz return current is directly under the trace (S3 27:01); a trace over a slot measured 20–30 dB worse EMI (S3 42:59).
- Engine "Key constants" block updated with all of the above plus a cross-check against Phil's Lab #110 (6.1–6.7 ps/mm ≈ Hartley's 150 mm/ns).

### Anti-myth section — kept intact and extended
All six original myths retained with verbatim evidence added (M2, M4, M6 timestamps above; M1/M3 re-sourced to S5). M5 now notes Phil's Lab independently says "we shouldn't do length matching, we should do delay matching" (#110). M6 gains Hartley's own caveat that he'd avoid routing signals *inside* a plane cavity above ~a few Gbps (S7 32:33). **New myth HARTLEY-M7 added:** the engine must not treat a plane as a "shield" — "it's not a shield, it's a reference" (S7 47:05), and moating to "shield" a section removes the return path and worsens EMI (S3 1:15:33). No myth was softened toward internet consensus.

---

## B. Phil's Lab — [MED] transcriptions promoted to [HIGH] verbatim

### Verified (timestamp added)
| Rule | Evidence |
|---|---|
| DEC-1 (100 nF per VDD/VBAT pin) | #65 11:15 |
| XTL-1 (C_each = 2×(C_L−C_stray); 10 pF crystal, C_stray 5 pF → 10 pF each) | #65 30:10–30:30 |
| XTL-2 (series feed resistor optional — Phil omits it) | #65 29:46 |
| XTL-3 (16 MHz; GND on package pins 2 & 4) | #65 29:17–29:38 |
| USB-2 (1.5 kΩ D+ → 3.3 V for USB 2.0 FS detection) | #65 33:01–33:51 |
| MIX-2 (VSS + VSSA tied together) | #65 8:54–9:15 |
| MIX-3 structure (ferrite bead + 1 µF + parallel caps, split gnd) | #65 13:20–14:06 |
| PWR-4 (LDO input+output caps; AMS1117 22 µF/22 µF) | #65 36:27–36:53 |
| RTE-2 (0.3 mm signal / 0.5 mm power) | #65 55:23, 1:20:06 |
| PWR-2 (keep switching + rectifier loops small and tight) | #60 5:21–6:05 |
| PWR-3 (SW-node copper small; FB away from inductor) | #60 8:22, 16:44 |
| MIX-1 ("for 99% of mixed-signal designs, do not split your ground") | #88 3:35–4:32 |
| MIX-4 (solid uncut reference under every trace; avoid via/anti-pad voids) | #88 4:40–5:13 |
| SCH-1, SCH-4 (functional sections; DNC flags) | #65 43:29, 31:22 |

### Corrected
1. **STM-1 severity E → W.** NRST has an internal pull-up (can float); Phil frames the 100 nF as "what I typically like to do," i.e. recommended, not mandatory. Evidence #65 15:20–15:44.
2. **USB-1 re-sourced.** #67's auto-transcript was unavailable, so the 90 Ω figure is cited to the USB 2.0 spec (ST AN4879) + the FS 0.3/0.3 mm example from #65, not to #67.
3. **STM-6 sourcing.** #65 does not implement I2C; the 2.2 kΩ pull-up value is not from #65 — note added.
4. **MIX-3 bead value** ("120 Ω @ 100 MHz") marked slide-sourced — the ferrite+cap *structure* is spoken, the exact bead value is on the schematic.
5. **RTE-3 via 0.7/0.3 mm** marked slide-sourced (design-rules screen), not spoken.

### Added (new machine-checkable rules)
- **PHIL-DEC-7 (W) — MLCC DC-bias derating:** size class-2 ceramics by *effective* capacitance, not nominal; **voltage rating ≥ 2× max applied DC** (3 V rail → 6.3 V part, absolute minimum). Evidence #152 8:33–9:22.
- **PHIL-USB-4 rewritten — delay match in picoseconds:** match by delay not length; prop delay ≈ **6.1 ps/mm microstrip, 6.7 ps/mm stripline** (Er≈4); **intra-pair (P/N) skew ≤ 5 ps** for DDR3, target ~0 ps for any pair (USB/PCIe); inter-pair budget spec-driven in ps. Evidence #110 3:31, 5:10, 8:14, 12:18, 14:30.
- **PHIL-PWR-3 extension — sense feedback at the output capacitor** (remote sense), not near the SW node. Evidence #60 24:19.

---

## C. Cross-authority convergence (both authors watched)
- **Don't split ground; one plane, partition by placement:** Hartley G2 (S3 1:15–1:18) and Phil MIX-1 (#88 3:35, "99% of designs"). Implement once, cite both.
- **Match by delay/time, not length:** Hartley M5/F4 (S2 45–47) and Phil #110 (3:31, 12:18); the ps/mm constants agree.
- **Solid uncut reference under every trace:** Hartley R5/C1 and Phil STK-6/MIX-4.
