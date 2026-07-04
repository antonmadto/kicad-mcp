"""Regenerate tests/fixtures/sample_project/ — a minimal valid KiCad 9 project.

Self-authored for kicad-mcp (MIT); NOT derived from GPL KiCad demos. Only the
Device:R symbol geometry is pulled from the installed KiCad symbol library so the
schematic is valid for kicad-cli ERC/netlist. See README.md in this directory.

Needs KiCad installed to read Device.kicad_sym. Override discovery with
KICAD_SYMBOL_DIR=/path/to/kicad/symbols if needed.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "sample_project"

_SYMBOL_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols",
    r"C:\Program Files\KiCad\9.0\share\kicad\symbols",
    "/usr/share/kicad/symbols",
]


def find_device_lib() -> Path:
    dirs = [os.environ["KICAD_SYMBOL_DIR"]] if os.environ.get("KICAD_SYMBOL_DIR") else []
    dirs += _SYMBOL_CANDIDATES
    for d in dirs:
        candidate = Path(d) / "Device.kicad_sym"
        if candidate.exists():
            return candidate
    sys.exit(
        "Could not find Device.kicad_sym. Set KICAD_SYMBOL_DIR to your KiCad "
        "symbols directory (contains Device.kicad_sym)."
    )


def bblock(text: str, i: int) -> str:
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    raise ValueError("unbalanced")


def device_r_block() -> str:
    lib = find_device_lib().read_text()
    block = bblock(lib, lib.index('(symbol "R"'))
    block = block.replace('(symbol "R"', '(symbol "Device:R"', 1)
    return "\n".join("\t" + line for line in block.splitlines())


ROOT_UUID = str(uuid.uuid4())


def u() -> str:
    return str(uuid.uuid4())


def sym_instance(ref: str, value: str, x: float, y: float) -> str:
    return f"""\t(symbol
\t\t(lib_id "Device:R")
\t\t(at {x} {y} 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{u()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x + 2.54} {y - 1.5} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x + 2.54} {y + 1.5} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" "Resistor_SMD:R_0603_1608Metric"
\t\t\t(at {x - 1.778} {y} 90)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Description" "Resistor"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(pin "1"
\t\t\t(uuid "{u()}")
\t\t)
\t\t(pin "2"
\t\t\t(uuid "{u()}")
\t\t)
\t\t(instances
\t\t\t(project "sample"
\t\t\t\t(path "/{ROOT_UUID}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""


def write_schematic() -> None:
    # Device:R at (x,100): pin2 is at absolute (x, 103.81). Wire R1.pin2 -> R2.pin2
    # (both at y=103.81) and label N1 so the netlist has a real 2-node net.
    wire = f"""\t(wire
\t\t(pts
\t\t\t(xy 100 103.81) (xy 120 103.81)
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{u()}")
\t)"""
    label = f"""\t(label "N1"
\t\t(at 110 103.81 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify left bottom)
\t\t)
\t\t(uuid "{u()}")
\t)"""
    sch = f"""(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "9.0")
\t(uuid "{ROOT_UUID}")
\t(paper "A4")
\t(lib_symbols
{device_r_block()}
\t)
{sym_instance("R1", "10k", 100.0, 100.0)}
{sym_instance("R2", "1k", 120.0, 100.0)}
{wire}
{label}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""
    (OUT / "sample.kicad_sch").write_text(sch)


LAYERS = """\t(layers
\t\t(0 "F.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t\t(11 "B.Adhes" user "B.Adhesive")
\t\t(13 "F.Paste" user)
\t\t(15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(19 "Cmts.User" user "User.Comments")
\t\t(21 "Eco1.User" user "User.Eco1")
\t\t(23 "Eco2.User" user "User.Eco2")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard")
\t\t(29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user)
\t\t(33 "B.Fab" user)
\t)"""

SETUP = """\t(setup
\t\t(stackup
\t\t\t(layer "F.SilkS"
\t\t\t\t(type "Top Silk Screen")
\t\t\t)
\t\t\t(layer "F.Paste"
\t\t\t\t(type "Top Solder Paste")
\t\t\t)
\t\t\t(layer "F.Mask"
\t\t\t\t(type "Top Solder Mask")
\t\t\t\t(color "Green")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "F.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 1"
\t\t\t\t(type "core")
\t\t\t\t(thickness 1.51)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.5)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "B.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "B.Mask"
\t\t\t\t(type "Bottom Solder Mask")
\t\t\t\t(color "Green")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "B.Paste"
\t\t\t\t(type "Bottom Solder Paste")
\t\t\t)
\t\t\t(layer "B.SilkS"
\t\t\t\t(type "Bottom Silk Screen")
\t\t\t)
\t\t\t(copper_finish "None")
\t\t\t(dielectric_constraints no)
\t\t)
\t\t(pad_to_mask_clearance 0)
\t\t(allow_soldermask_bridges_in_footprints no)
\t\t(aux_axis_origin 100 100)
\t\t(grid_origin 100 100)
\t)"""


def footprint(ref: str, value: str, x: float, y: float, net1: int, net2: int) -> str:
    def net(n: int) -> str:
        return f'(net {n} "{"GND" if n == 1 else ""}")'

    return f"""\t(footprint "Resistor_SMD:R_0603_1608Metric"
\t\t(layer "F.Cu")
\t\t(uuid "{u()}")
\t\t(at {x} {y} 0)
\t\t(attr smd)
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -1.43 0)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{u()}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at 0 1.43 0)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{u()}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(pad "1" smd roundrect
\t\t\t(at -0.7875 0)
\t\t\t(size 0.875 0.95)
\t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
\t\t\t(roundrect_rratio 0.25)
\t\t\t{net(net1)}
\t\t\t(uuid "{u()}")
\t\t)
\t\t(pad "2" smd roundrect
\t\t\t(at 0.7875 0)
\t\t\t(size 0.875 0.95)
\t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
\t\t\t(roundrect_rratio 0.25)
\t\t\t{net(net2)}
\t\t\t(uuid "{u()}")
\t\t)
\t)"""


def write_pcb() -> None:
    r1 = footprint("R1", "10k", 110.0, 110.0, net1=0, net2=1)
    r2 = footprint("R2", "1k", 120.0, 110.0, net1=1, net2=0)
    edge = f"""\t(gr_rect
\t\t(start 105 105)
\t\t(end 125 115)
\t\t(stroke
\t\t\t(width 0.1)
\t\t\t(type default)
\t\t)
\t\t(fill no)
\t\t(layer "Edge.Cuts")
\t\t(uuid "{u()}")
\t)"""
    track = f"""\t(segment
\t\t(start 110.7875 110)
\t\t(end 119.2125 110)
\t\t(width 0.25)
\t\t(layer "F.Cu")
\t\t(net 1)
\t\t(uuid "{u()}")
\t)"""
    pcb = f"""(kicad_pcb
\t(version 20241229)
\t(generator "pcbnew")
\t(generator_version "9.0")
\t(general
\t\t(thickness 1.6)
\t\t(legacy_teardrops no)
\t)
\t(paper "A4")
{LAYERS}
{SETUP}
\t(net 0 "")
\t(net 1 "GND")
{edge}
{r1}
{r2}
{track}
)
"""
    (OUT / "sample.kicad_pcb").write_text(pcb)


def write_pro() -> None:
    import json

    (OUT / "sample.kicad_pro").write_text(
        json.dumps(
            {
                "meta": {"filename": "sample.kicad_pro", "version": 3},
                "sheets": [],
                "text_variables": {},
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    write_pro()
    write_schematic()
    write_pcb()
    print("wrote:", sorted(p.name for p in OUT.iterdir()))
