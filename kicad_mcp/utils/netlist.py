"""Parse the ``kicadxml`` netlist emitted by ``kicad-cli sch export netlist``.

Gives net-level connectivity (which pins are on which net) that the schematic
S-expression does not directly expose — this is the "sexpr + cli netlist" split
in PLAN.md §5 for ``list_schematic_nets`` / ``trace_net``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def parse_netlist(path: Path | str) -> dict:
    """Return ``{"components": [...], "nets": [...]}`` from a kicadxml netlist."""
    # Input is produced by our own kicad-cli subprocess (trusted), not user data.
    root = ET.parse(str(path)).getroot()  # noqa: S314

    components = []
    for comp in root.findall("./components/comp"):
        components.append(
            {
                "reference": comp.get("ref"),
                "value": _text(comp.find("value")),
                "footprint": _text(comp.find("footprint")),
            }
        )

    nets = []
    for net in root.findall("./nets/net"):
        nodes = [
            {"reference": n.get("ref"), "pin": n.get("pin"), "pin_function": n.get("pinfunction")}
            for n in net.findall("node")
        ]
        nets.append(
            {
                "code": net.get("code"),
                "name": net.get("name"),
                "node_count": len(nodes),
                "nodes": nodes,
            }
        )
    nets.sort(key=lambda n: n["name"] or "")
    return {"components": components, "nets": nets}


def _text(el) -> str | None:
    return el.text if el is not None else None
