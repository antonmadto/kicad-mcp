# Phil's Lab (Phil Salmony) Rule Catalog (machine-checkable)

Rule IDs use prefix `PHIL-`. [HIGH] = from Phil's own writing (Altium Learning Hub articles), [MED] = third-party transcriptions of his videos.

**Source index**

- S1: "PCB Stackup Basics" — https://resources.altium.com/p/pcb-stackup-basics [HIGH]
- S2: "Beginner PCB Design Mistakes" — https://resources.altium.com/p/top-5-pcb-design-mistakes-and-how-fix-them [HIGH]
- S3: "Designing Custom Hardware with Microcontrollers" — https://resources.altium.com/p/designing-custom-hardware-microcontrollers [HIGH]
- S4: "ESD Protection Basics with TVS Diodes" — https://resources.altium.com/p/esd-protection-basics-tvs-diodes [HIGH]
- S5: "Buck Converter Component Sizing" — https://resources.altium.com/p/buck-converter-component-sizing [HIGH]
- S6: Phil's Lab #65 "KiCad STM32 PCB Design Full Tutorial" (1:40:03) — https://youtu.be/aVUqaB0IMh4 — **[HIGH] auto-transcript watched end-to-end 2026-07-04; timestamps inline** (upgrades the earlier third-party notes at publish.obsidian.md/.../Phil's+Lab+65 and c-dev66.github.io).
- S8: Phil's Lab #59 "FPGA/DDR tips" — https://glasp.co/youtube/p/fpga-soc-ddr-pcb-design-tips-phil-s-lab-59 [MED] (not re-verified this pass)
- S9: Phil's Lab #88 "Mixed-Signal Hardware/PCB Design Tips" (18:17) — https://www.youtube.com/watch?v=v6fTa6LRJLI — **[HIGH] auto-transcript watched 2026-07-04** (blog mirror: fedevel.com/blog/mixed-signal-hardware-pcb-design-tips-phils-lab-88).
- S10: Video index — https://gist.github.com/JonyBepary/ed7419fec1ed115fd9aed64be34afde5 · GitHub https://github.com/pms67 (test fixture designs: HadesFCS incl. HadesMicroJLCPCB)
- S11: Phil's Lab #60 "Switching Regulator PCB Design" (25:04) — https://www.youtube.com/watch?v=AmfLhT5SntE — **[HIGH] watched 2026-07-04.**
- S12: Phil's Lab #110 "PCB High-Speed Delay Matching" (19:14) — https://www.youtube.com/watch?v=xdUR3NzXUkc — **[HIGH] watched 2026-07-04** (substitute for #67, whose auto-transcript is unavailable; #67 = https://www.youtube.com/watch?v=wQ37NxSeP48).
- S13: Phil's Lab #152 "Ceramic Capacitor DC Bias Effects & Measurement" — https://www.youtube.com/watch?v=Tfatk7wmnhs — **[HIGH] watched 2026-07-04.**
- Canonical references Phil defers to: **ST AN2867** (oscillator design), **ST AN4879** (USB hardware)

## 1. Schematic organization and review

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-SCH-1 | I | Section schematics into named functional blocks with explanatory notes. Verified: draw bounding boxes + text labels ("power supply", "microcontroller circuitry", "USB circuitry") around functional groups [S6 43:29–44:06] | — | S6 43:29 |
| PHIL-SCH-2 | W | Net-label all functionally important nets (HSE, USB_D±, SWDIO/SWCLK, BOOT0, NRST) | — | S6, S7 |
| PHIL-SCH-3 | W | Diff nets named identical stem + `+`/`-` suffix so KiCad recognizes pairs | — | S7 |
| PHIL-SCH-4 | E | Every unused pin gets explicit no-connect flag; connector signal lines paired with ≥1 GND. Verified: USB connector shield left floating with a do-not-connect flag so ERC passes [S6 31:22–31:37] | 1:1 | S6 31:22 |
| PHIL-SCH-5 | E | Pre-layout gate: re-annotate by position, ERC to zero (PWR_FLAG on regulator outputs), pinouts verified vs datasheet, parts sourceable | — | S6 |
| PHIL-SCH-6 | I | Draw decoupling caps adjacent to the pin group they serve | — | S6 |
| PHIL-SCH-7 | I | Reuse passive values where non-critical (BOM line reduction) | — | S6 |

## 2. Stackup

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-STK-1 | W | 4-layer default SIG–GND–GND–SIG with routed/poured power, not a dedicated PWR plane | — | S1 |
| PHIL-STK-2 | I | 6-layer SIG–GND–SIG–PWR–GND–SIG; 8-layer SIG–GND–SIG–PWR–GND–SIG–GND–SIG | — | S1 |
| PHIL-STK-3 | E | Golden rule: ≥1 ground reference closely adjacent to every signal AND power layer | — | S1 |
| PHIL-STK-4 | W | PWR–GND plane pairs closely spaced (interplane capacitance; SMD caps inductive at HF) | — | S1 |
| PHIL-STK-5 | I | Prefer stripline (GND–SIG–GND) for high-speed/high-energy nets when layers allow | — | S1 |
| PHIL-STK-6 | E | Never route across a split/void in the reference plane; avoid creating large plane voids | — | S2 |
| PHIL-STK-7 | W | 2-layer boards: top signal, bottom solid ground | — | S6 |
| PHIL-STK-8 | W | Stitching vias tie GND planes/pours together; pours on signal layers via'd back to plane | — | S8 |

## 3. Decoupling

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-DEC-1 | E | One 100 nF ceramic per VDD/VBAT pin, close to that pin/VSS pair. Verified: "one 100 nano farad capacitor per V-BAT and per VDD pin" [S6 11:15] | 100 nF/pin | S3, S6 11:15 |
| PHIL-DEC-2 | W | One bulk cap per IC power domain | 1 µF (STM32F1 example) | S6 |
| PHIL-DEC-3 | W | Decoupling connections short + wide; pwr/GND vias immediately adjacent to pads | — | S2 |
| PHIL-DEC-4 | W | BGA/dense ICs: caps on opposite side directly under pins, via straight up | — | S8 |
| PHIL-DEC-5 | E | Internal regulator bypass pins use datasheet value | 2.2 µF per VCAP (STM32H7) | S3 |
| PHIL-DEC-6 | W | NO ferrite bead between supply and a large high-speed digital IC's decoupling network (rail ripple). Ferrites OK for DC/low-f analog domains | — | Altium ferrite guidance |
| PHIL-DEC-7 | W | **MLCC DC-bias derating (NEW):** class-2 ceramics (X5R/X7R) lose capacitance under applied DC — size by *effective* capacitance, not nominal ("if it derates 50%, double the nominal or parallel caps"). Rule of thumb: **capacitor voltage rating ≥ 2× the max applied DC voltage** (e.g. 3 V rail → 6.3 V part) as an absolute minimum; larger package / better dielectric also reduce derating. Flag bulk/output MLCCs whose V_rating < 2× V_rail. | V_rating ≥ 2× V_applied; effective C not nominal | S13 8:33–9:22 |

## 4. Crystal and USB

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-XTL-1 | E | Load caps: C_each = 2 × (C_L − C_stray), C_stray 3–5 pF, matched pair. Verified worked example: C_L = 10 pF from datasheet, assume max C_stray 5 pF → 2 × (10 − 5) = 10 pF each, both equal [S6 30:10–30:30] | 10 pF crystal → 10 pF each | S6 30:10 (per AN2867) |
| PHIL-XTL-2 | I | Optional series resistor on OSC_OUT, tens of ohms (prevents overdrive/harmonics). Verified: Phil omits the feed resistor "because it's typically not required" [S6 29:46] — so absence is not a violation | ~10s Ω (optional) | S6 29:46 |
| PHIL-XTL-3 | W | Crystal freq within MCU limits (STM32F1 HSE 4–16 MHz); ground crystal package GND pads. Verified: 16 MHz crystal, GND on package pins 2 & 4 [S6 29:17–29:38] | 8/16 MHz typical, 3225 pkg | S6 29:17 |
| PHIL-XTL-4 | W | Crystal close to MCU, away from high-speed routing (AN2867 layout) | — | S6, S3 |
| PHIL-USB-1 | E | USB D+/D− routed as diff pair; HS USB needs 90 Ω differential controlled impedance (FS hobby 2-layer example 0.3 mm/0.3 mm). The 90 Ω figure is the USB 2.0 spec (ST AN4879); #67's auto-transcript was unavailable this pass, so cite AN4879 + the FS example from #65 rather than #67 | 90 Ω diff | S6; ST AN4879 |
| PHIL-USB-2 | E | STM32F1 (no internal pull-up): 1.5 kΩ D+ → 3.3 V; newer families check AN4879 table. Verified: datasheet footnote requires pulling D+ to 3.0–3.6 V via 1.5 kΩ to be detected as a USB 2.0 full-speed device; "without it the USB would not work" [S6 33:01–33:51] | 1k5 | S6 33:01 |
| PHIL-USB-3 | W | VBUS as own net; supply filtering on VBUS in production designs | — | S6 |
| PHIL-USB-4 | W | Match diff pairs and grouped buses by **DELAY (ps), not length** — velocity varies with Er, geometry, and loading [S12 3:31, 12:18]. Verified numbers: prop delay ≈ 6.1 ps/mm microstrip, ≈ 6.7 ps/mm stripline (Er≈4) [S12 5:10]; intra-pair (P/N) skew ≤ 5 ps for DDR3, target ~0 ps for any pair incl. USB/PCIe [S12 14:30]; inter-pair/group budget is spec-driven in ps (e.g. ±150 ps) [S12 8:14]. Include package delay. | intra-pair ≤ 5 ps (~0 target); ~6.1–6.7 ps/mm | S8, S12 |

## 5. SMPS and regulators

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-PWR-1 | I | Buck sizing: D = Vout/(Vin·η); ΔI_L = (Vin−Vout)·D/(f_SW·L); I_peak = I_load + ΔI_L/2; L_min = Vout(Vin−Vout)/(k·I_load·f_SW·Vin), k = 0.2–0.4. FB divider 10s–100s kΩ, 1% resistors | k = 0.2–0.4 | S5 |
| PHIL-PWR-2 | E | Hot loops physically minimal. Verified: the two HF loops are (a) switch-closed "power switching loop" (input cap → switch → inductor → output cap → load) and (b) switch-open "rectifier loop" (inductor → cap → diode); "keep the input loop small, most importantly the power switching loop very small and very tight, and the rectifier loop very small" [S11 5:21–6:05]. Polygon pours + multiple vias for SMD power parts [S11 17:39] | — | S8, S11 5:21 |
| PHIL-PWR-3 | E | SW-node copper small [S11 16:44]; inductor close to SW pin; FB trace short, routed away from SW node/inductor ("don't route this very sensitive feedback trace close to this magnetic element" [S11 8:22]). **NEW: sense the feedback at the OUTPUT capacitor (remote-sense point), not near the SW node** — "feedback trace routed from the output capacitor, further away from [SW]" [S11 24:19] | — | S11 8:22, 16:44, 24:19 |
| PHIL-PWR-4 | E | LDOs always have input AND output caps for stability; check MLCC DC-bias derating (see DEC-7) and voltage rating. Verified: "linear regulators always require input and output capacitors for stability; AMS1117 datasheet needs ≥ 22 µF on output, similar on input" [S6 36:27–36:53] | 22 µF/22 µF (AMS1117 example) | S6 36:27 |
| PHIL-PWR-5 | I | Power status LED per main rail | — | S6 |
| PHIL-PWR-6 | W | Multi-rail systems sequence via EN/power-good chaining (FPGA/DDR) | — | S8 |

## 6. Mixed signal

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-MIX-1 | E | ONE solid ground plane, no analog/digital split; partition by placement. Verified verbatim: "for **99% of mixed-signal designs, do not split your ground**, and this starts in the schematic... the ground plane underneath is not split in any way" [S9 3:35–4:32]. Directly agrees with Hartley G2 — the two authorities converge; implement once, cite both. | — | S9 3:35 |
| PHIL-MIX-2 | E | VSS and VSSA tied to same ground in "99% of cases". Verified: "tie all VSS and VSSA pins together; VSS = digital reference, VSSA = analog reference" [S6 8:54–9:15] | — | S6 8:54 |
| PHIL-MIX-3 | E | VDDA/VREF+ gets PI filter: ferrite bead + 10 nF ‖ 1 µF on MCU side, 1 µF upstream; separate net name (3.3VA). Verified structure: ferrite bead ("behaves resistive, dissipates heat at HF") + 1 µF on the VDDA side + parallel caps, analog/digital grounds separated, fed from the digital 3.3 V rail [S6 13:20–14:06]. The specific "120 Ω @ 100 MHz" bead value is on the schematic (slide), not spoken. | 120 Ω @ 100 MHz bead (slide) | S6 13:20; S3 (ST) |
| PHIL-MIX-4 | E | Signals crossing analog↔digital boundary need controlled return path; digital never routed through analog region. Verified: "all traces have a solid reference/return plane directly underneath, not crossing any splits or voids, staying clear of voids from through-hole/vias — to avoid field spreading" [S9 4:40–5:13] | — | S9 4:40 |
| PHIL-MIX-5 | W | Each domain gets own supply filtering; low-noise parts in analog path | — | S9 |

## 7. STM32-specific

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-STM-1 | W | NRST: 100 nF to GND (+ optional button); internal pull-up exists. **Severity corrected E→W:** NRST self-pulls-up (can float); Phil frames the 100 nF as "what I typically like to do if I don't use this pin," i.e. recommended, not mandatory [S6 15:20–15:44] | 100 nF (recommended) | S6 15:20 |
| PHIL-STM-2 | E | BOOT0 strapped (switch or resistor); tie low if SWD-only programming. Verified: "the BOOT0 pin enables or disables the internal [bootloader]" [S6 16:50] | — | S6 16:50 |
| PHIL-STM-3 | E | SWD header exposed (3.3 V, SWDIO, SWCLK, GND, opt. SWO+NRST); TVS on debug lines strongly recommended | 4–6 pin | S3, S7 |
| PHIL-STM-4 | I | VDD 3.3 V default (range 2.0–3.6 V); VBAT tied to VDD if no RTC battery | 3.3 V | S6 |
| PHIL-STM-5 | I | Pinout in STM32CubeIDE first, back-annotate to schematic; SWD enabled explicitly | — | S6 |
| PHIL-STM-6 | E | I2C pull-ups on SCL/SDA | ~2.2 kΩ (1k5 acceptable) | S3 (I2C is not implemented in #65; the 2.2 kΩ value is not from S6) |

## 8. Routing geometry, vias, DFM

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-RTE-1 | W | Trace spacing ≥ 3× dielectric height to reference plane; avoid long parallel runs at min clearance | 0.11 mm dielectric → ≥0.33 mm | S2 |
| PHIL-RTE-2 | W | Trace width by function: 0.3 mm signal / 0.5 mm power defaults; 0.2 mm ≈ 1 A at ~20 °C rise. Verified: "two standard track sizes, 0.3 mm for signals and 0.5 mm for power" [S6 55:23, 1:20:06] | 0.3/0.5 mm | S2, S6 55:23 |
| PHIL-RTE-3 | W | Standard via 0.7 mm pad / 0.3 mm drill (~1–2 A). #65 uses "a standard type of via" [S6 1:20:10]; the exact 0.7/0.3 mm is on the design-rules/fab-capability slide, not spoken | 0.7/0.3 mm (slide) | S2, S6 |
| PHIL-RTE-4 | E | Import fab-house capabilities (e.g. JLCPCB) into design rules BEFORE layout | — | S6 |
| PHIL-DFM-1 | I | Passives 0402/0603 default, 0805 for high-value/power | — | S6 |
| PHIL-DFM-2 | E | Fab output completeness: Gerbers + drill + BOM + CPL for assembly | — | S6 |
| PHIL-DFM-3 | I | Silkscreen: rails, LED functions, connector pinouts, name/rev; tooling holes | — | S8 |
| PHIL-DFM-4 | W | Mounting holes + board outline explicit; final checklist pass before Gerbers (video #131) | — | S6, S10 |
| PHIL-DFM-5 | I | BOM cost: consolidate values, prefer JLC basic parts | — | Altium article |

## 9. ESD, ferrites, connectors

| ID | Sev | Rule | Values | Src |
|---|---|---|---|---|
| PHIL-ESD-1 | E | TVS on all connector-facing signal lines, placed as close as possible to the connector, shunt to GND | — | S4 |
| PHIL-ESD-2 | W | TVS selection: V_working ≥ V_signal; clamping voltage; bidirectional for below-reference swings; low-C for high-speed; IEC 61000-4-2 rated; channel count matches interface | — | S4 |
| PHIL-FER-1 | W | Series ferrite for analog rail isolation, cap banks both sides | 120 Ω @ 100 MHz | S6 |
| PHIL-CON-1 | E | ≥1 ground pin per signal pin on headers; high-speed mezzanine alternate GND:signal grid | 1:1 | S6, S8 |

## Encoding notes

- Most machine-checkable with hard numbers: STK-1/2/3/6, RTE-1/2/3, DEC-1/2/7, XTL-1, USB-1/2/4, MIX-2/3, STM-1/6, ESD-1, PWR-2/3/4.
- New this pass (transcript-verified): **DEC-7** MLCC DC-bias (V_rating ≥ 2× V_applied) [S13]; **USB-4** delay-match in ps (intra-pair ≤ 5 ps, ~6.1–6.7 ps/mm) [S12]; **PWR-3** feedback sensed at the output cap [S11].
- Overlap with Hartley catalog is intentional and now **explicitly convergent** (both watched): STK-3 ≈ HARTLEY-K1; STK-6/MIX-4 ≈ HARTLEY-R5/C1; **MIX-1 ≈ HARTLEY-G2 (both: "do not split ground, partition by placement" — Phil "99% of designs" #88 3:35, Hartley S3 1:15–1:18)**; RTE-1 ≈ HARTLEY-C4; USB-4 "match by delay not length" ≈ HARTLEY-M5/F4. Implement once, cite both.
- Ground-truth test designs: https://github.com/pms67/HadesFCS (incl. `Hardware/HadesMicroJLCPCB/`).
