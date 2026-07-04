"""Generate synthetic KiCad-9 boards that exercise the review engine (Phase 2).

These are minimal, self-authored boards built to drive the review engine's
*name-based* parser (stackup/zones/tracks by layer name + net). They are not
guaranteed to open in the KiCad GUI (copper layer-ID numbering is layer-count
dependent and not reproduced here); they exist purely to give each rule a
must-trigger / must-not-trigger golden fixture. Each board is a mini-project
(.kicad_pro + .kicad_pcb).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

OUT = Path(__file__).parent


def u() -> str:
    return str(uuid.uuid4())


# --- stackup construction ---------------------------------------------------

_TECH_TOP = '(layer "F.SilkS" (type "Top Silk Screen"))\n(layer "F.Paste" (type "Top Solder Paste"))\n(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))'
_TECH_BOT = '(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))\n(layer "B.Paste" (type "Bottom Solder Paste"))\n(layer "B.SilkS" (type "Bottom Silk Screen"))'


def _cu(name: str) -> str:
    return f'(layer "{name}" (type "copper") (thickness 0.035))'


def _diel(mm: float) -> str:
    return f'(layer "dielectric" (type "core") (thickness {mm}) (material "FR4") (epsilon_r 4.5))'


def stackup_4(g_top: float, g_mid: float, g_bot: float) -> str:
    layers = [
        _TECH_TOP,
        _cu("F.Cu"),
        _diel(g_top),
        _cu("In1.Cu"),
        _diel(g_mid),
        _cu("In2.Cu"),
        _diel(g_bot),
        _cu("B.Cu"),
        _TECH_BOT,
    ]
    return "(stackup\n" + "\n".join(layers) + '\n(copper_finish "None"))'


def stackup_2(g: float) -> str:
    layers = [_TECH_TOP, _cu("F.Cu"), _diel(g), _cu("B.Cu"), _TECH_BOT]
    return "(stackup\n" + "\n".join(layers) + '\n(copper_finish "None"))'


def layers_table(copper: list[str]) -> str:
    # Numbering is not GUI-canonical (see module docstring); names are what matter.
    rows = []
    n = 0
    for name in copper:
        rows.append(f'({n} "{name}" signal)')
        n += 1
    for name, kind in [
        ("F.SilkS", "user"),
        ("B.SilkS", "user"),
        ("F.Mask", "user"),
        ("B.Mask", "user"),
        ("Edge.Cuts", "user"),
        ("F.Paste", "user"),
        ("B.Paste", "user"),
        ("F.Fab", "user"),
    ]:
        rows.append(f'({n} "{name}" {kind})')
        n += 1
    return "(layers\n" + "\n".join("\t\t" + r for r in rows) + "\n\t)"


# --- elements ---------------------------------------------------------------


def zone(net_code: int, net_name: str, layer: str, pts: list[tuple[float, float]]) -> str:
    xy = " ".join(f"(xy {x} {y})" for x, y in pts)
    return (
        f'(zone (net {net_code}) (net_name "{net_name}") (layer "{layer}") (uuid "{u()}")\n'
        f"(hatch edge 0.5) (filled_areas_thickness no)\n"
        f"(polygon (pts {xy})))"
    )


def track(x1, y1, x2, y2, width, layer, net) -> str:
    return (
        f"(segment (start {x1} {y1}) (end {x2} {y2}) (width {width}) "
        f'(layer "{layer}") (net {net}) (uuid "{u()}"))'
    )


def via(x, y, size, drill, layers, net) -> str:
    lyr = " ".join(f'"{ly}"' for ly in layers)
    return f'(via (at {x} {y}) (size {size}) (drill {drill}) (layers {lyr}) (net {net}) (uuid "{u()}"))'


def footprint(ref, value, lib_id, x, y, pads) -> str:
    pad_s = ""
    for num, lx, ly, ncode, nname in pads:
        pad_s += (
            f'\n(pad "{num}" smd rect (at {lx} {ly}) (size 0.9 0.9) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") (net {ncode} "{nname}") (uuid "{u()}"))'
        )
    return (
        f'(footprint "{lib_id}" (layer "F.Cu") (uuid "{u()}") (at {x} {y} 0) (attr smd)\n'
        f'(property "Reference" "{ref}" (at 0 -2 0) (layer "F.SilkS") (uuid "{u()}") (effects (font (size 1 1) (thickness 0.15))))\n'
        f'(property "Value" "{value}" (at 0 2 0) (layer "F.Fab") (uuid "{u()}") (effects (font (size 1 1) (thickness 0.15)))){pad_s})'
    )


def edge_rect(x1, y1, x2, y2) -> str:
    return (
        f"(gr_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.1) (type default)) "
        f'(fill no) (layer "Edge.Cuts") (uuid "{u()}"))'
    )


def emit(name: str, copper: list[str], stackup: str, nets, body_elements, outline=True) -> None:
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.kicad_pro").write_text(
        json.dumps(
            {"meta": {"filename": f"{name}.kicad_pro", "version": 3}, "sheets": []}, indent=2
        )
        + "\n"
    )
    net_lines = "\n".join(f'(net {c} "{nm}")' for c, nm in nets)
    outline_s = edge_rect(100, 100, 140, 130) if outline else ""
    body = "\n".join(body_elements)
    pcb = f"""(kicad_pcb
(version 20241229)
(generator "pcbnew")
(generator_version "9.0")
(general (thickness 1.6))
(paper "A4")
{layers_table(copper)}
(setup {stackup})
{net_lines}
{outline_s}
{body}
)
"""
    (d / f"{name}.kicad_pcb").write_text(pcb)


# Board footprint of every plane zone (inside the 40x30 outline at 100,100).
FULL = [(101, 101), (139, 101), (139, 129), (101, 129)]
LEFT = [(101, 101), (119, 101), (119, 129), (101, 129)]
RIGHT = [(121, 101), (139, 101), (139, 129), (121, 129)]

CU4 = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
CU2 = ["F.Cu", "B.Cu"]
NETS = [(0, ""), (1, "GND"), (2, "+3V3"), (3, "SIG1")]


def gen_clean_4layer():
    # Sig / GND / PWR / Sig, tight pwr-gnd (0.2), solid planes, IC + 100nF, mount hole.
    body = [
        zone(1, "GND", "In1.Cu", FULL),
        zone(2, "+3V3", "In2.Cu", FULL),
        track(110, 115, 130, 115, 0.5, "F.Cu", 2),  # 0.5mm power track over solid GND
        footprint(
            "U1",
            "STM32",
            "Package_QFP:LQFP-48",
            115,
            112,
            [(str(i), i * 0.5, 0, 2, "+3V3") for i in range(1, 9)],
        ),
        footprint(
            "C1",
            "100nF",
            "Capacitor_SMD:C_0402",
            117,
            112,
            [("1", -0.5, 0, 2, "+3V3"), ("2", 0.5, 0, 1, "GND")],
        ),
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("clean_4layer", CU4, stackup_4(0.6, 0.2, 0.6), NETS, body)


def gen_faults_4layer():
    # Sig / PWR / GND / Sig (K2), IC with no cap (DEC-1), thin power track (RTE-2),
    # small-ring via (RTE-3), no mounting hole (DFM-4 info).
    body = [
        zone(2, "+3V3", "In1.Cu", FULL),  # In1 = power
        zone(1, "GND", "In2.Cu", FULL),  # In2 = ground
        track(110, 115, 130, 115, 0.15, "F.Cu", 2),  # thin power track
        via(120, 118, 0.4, 0.35, ["F.Cu", "B.Cu"], 2),  # ring 0.025mm
        footprint(
            "U1",
            "STM32",
            "Package_QFP:LQFP-48",
            115,
            112,
            [(str(i), i * 0.5, 0, 2, "+3V3") for i in range(1, 9)],
        ),
    ]
    emit("faults_4layer", CU4, stackup_4(0.6, 0.2, 0.6), NETS, body)


def gen_split_ground_4layer():
    # Clean stackup, but the GND plane is split into two zones and a track crosses
    # the gap → G1 (split ground) + R5 (trace crosses reference gap).
    body = [
        zone(1, "GND", "In1.Cu", LEFT),
        zone(1, "GND", "In1.Cu", RIGHT),
        zone(2, "+3V3", "In2.Cu", FULL),
        track(110, 115, 130, 115, 0.3, "F.Cu", 3),  # SIG1 crosses the x≈120 gap
        footprint(
            "U1",
            "STM32",
            "Package_QFP:LQFP-48",
            108,
            112,
            [(str(i), i * 0.5, 0, 3, "SIG1") for i in range(1, 9)],
        ),
        footprint(
            "C1",
            "100nF",
            "Capacitor_SMD:C_0402",
            110,
            112,
            [("1", -0.5, 0, 2, "+3V3"), ("2", 0.5, 0, 1, "GND")],
        ),
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("split_ground_4layer", CU4, stackup_4(0.6, 0.2, 0.6), NETS, body)


def gen_thick_cavity_4layer():
    # Sig / GND / PWR / Sig but the pwr-gnd dielectric is 0.5mm (> 0.2) → K5.
    body = [
        zone(1, "GND", "In1.Cu", FULL),
        zone(2, "+3V3", "In2.Cu", FULL),
        track(110, 115, 130, 115, 0.5, "F.Cu", 2),
        footprint(
            "U1",
            "STM32",
            "Package_QFP:LQFP-48",
            115,
            112,
            [(str(i), i * 0.5, 0, 2, "+3V3") for i in range(1, 9)],
        ),
        footprint(
            "C1",
            "100nF",
            "Capacitor_SMD:C_0402",
            117,
            112,
            [("1", -0.5, 0, 2, "+3V3"), ("2", 0.5, 0, 1, "GND")],
        ),
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("thick_cavity_4layer", CU4, stackup_4(0.6, 0.5, 0.6), NETS, body)


def gen_abutting_zones_4layer():
    # Continuous ground plane drawn as TWO abutting zones sharing the x=120 edge,
    # with a track crossing the seam. Electrically continuous copper → must NOT
    # trigger R5 (regression: seam previously read as a gap) nor G1-equivalent
    # nonsense... G1 counts zones though — two same-net zones on the plane layer
    # WILL trigger G1 (split ground) by zone count. To isolate R5, pour POWER as
    # the abutting pair instead and keep ground solid.
    left_pwr = [(101, 101), (120, 101), (120, 129), (101, 129)]
    right_pwr = [(120, 101), (139, 101), (139, 129), (120, 129)]
    body = [
        zone(1, "GND", "In1.Cu", FULL),
        zone(2, "+3V3", "In2.Cu", left_pwr),
        zone(2, "+3V3", "In2.Cu", right_pwr),
        # Track on B.Cu references In2 (the abutting power pour) from below.
        track(110, 115, 130, 115, 0.3, "B.Cu", 3),
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("abutting_zones_4layer", CU4, stackup_4(0.6, 0.2, 0.6), NETS, body)


def gen_highspeed_4layer():
    # Clean 4-layer stackup. Exercises transmission + crosstalk:
    #  - SIG1 routed as a 59 mm L → over critical length (F2)
    #  - USB_D+/USB_D- pair with a 2 mm length mismatch → intra-pair skew (F4)
    #  - AGGR runs 0.8 mm from the pair over 10 mm → too close (C4)
    nets = [
        (0, ""),
        (1, "GND"),
        (2, "+3V3"),
        (3, "SIG1"),
        (4, "USB_D+"),
        (5, "USB_D-"),
        (6, "AGGR"),
    ]
    body = [
        zone(1, "GND", "In1.Cu", FULL),
        zone(2, "+3V3", "In2.Cu", FULL),
        # SIG1: long L-route (36 + 23 = 59 mm > 43 mm L_crit), away from the pair.
        track(102, 106, 138, 106, 0.2, "F.Cu", 3),
        track(138, 106, 138, 129, 0.2, "F.Cu", 3),
        # Diff pair: P 15 mm, N 17 mm (2 mm mismatch → ~11.6 ps skew).
        track(110, 119.8, 125, 119.8, 0.2, "F.Cu", 4),
        track(110, 120.2, 127, 120.2, 0.2, "F.Cu", 5),
        # Aggressor 0.8 mm from P, parallel, 10 mm overlap.
        track(112, 119.0, 122, 119.0, 0.2, "F.Cu", 6),
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("highspeed_4layer", CU4, stackup_4(0.6, 0.2, 0.6), nets, body)


def gen_smps_4layer():
    # FB net routed 1.5 mm from the SW node → PHIL-PWR-3.
    nets = [(0, ""), (1, "GND"), (2, "+3V3"), (4, "FB"), (5, "SW")]
    body = [
        zone(1, "GND", "In1.Cu", FULL),
        zone(2, "+3V3", "In2.Cu", FULL),
        track(110, 115, 115, 115, 0.25, "F.Cu", 4),  # FB
        track(110, 116.5, 115, 116.5, 0.5, "F.Cu", 5),  # SW, 1.5 mm away
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("smps_4layer", CU4, stackup_4(0.6, 0.2, 0.6), nets, body)


def gen_antimyth_2layer():
    # 2-layer with a solid bottom ground plane and top tracks with 90° corners.
    # Must produce ZERO findings — 90° corners are a myth, not a defect.
    body = [
        zone(1, "GND", "B.Cu", FULL),
        track(110, 110, 130, 110, 0.3, "F.Cu", 3),  # horizontal
        track(130, 110, 130, 125, 0.3, "F.Cu", 3),  # 90° turn, vertical
        footprint("H1", "MountingHole", "MountingHole:MountingHole_3.2mm_M3", 104, 104, []),
    ]
    emit("antimyth_2layer", CU2, stackup_2(1.5), NETS, body)


if __name__ == "__main__":
    gen_clean_4layer()
    gen_faults_4layer()
    gen_split_ground_4layer()
    gen_thick_cavity_4layer()
    gen_abutting_zones_4layer()
    gen_highspeed_4layer()
    gen_smps_4layer()
    gen_antimyth_2layer()
    print("generated:", sorted(p.name for p in OUT.iterdir() if p.is_dir()))
