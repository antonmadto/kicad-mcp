"""Connector / ESD rules — Phil ESD-1, CON-1.

Connector-facing lines take ESD strikes and leave the board as antennas, so they
need a TVS at the connector and enough ground return pins.
"""

from __future__ import annotations

import re

from ..model import DesignModel, Schematic
from ..registry import register
from .base import Finding, Location, Rule, Severity

# Reference-designator patterns for connectors. 'P<digits>' only (not PT100/PWR/
# PS/PROBE), plus J/CN/CON/USB families.
_CONNECTOR_RE = re.compile(r"^(J\d|CN\d|CON\d|USB|P\d)", re.I)

# Common TVS/ESD-array part-number stems (value or MPN), plus D/TVS/U ref prefixes.
_TVS_STEMS = (
    "tvs",
    "esd",
    "clamp",
    "smaj",
    "smbj",
    "smf",
    "esda",
    "pesd",
    "prtr",
    "usblc",
    "tpd",
    "sp05",
    "esd9",
    "cdsod",
    "nup",
    "d5v0",
    "srv05",
)


def _sch(model: DesignModel) -> Schematic | None:
    return model.schematic


def _is_connector(ref: str) -> bool:
    return bool(_CONNECTOR_RE.match(ref))


@register
class ConnectorGroundReturn(Rule):
    id = "PHIL-CON-1"
    # Catalog severity is E; kept WARNING as intentional false-positive control —
    # the rule fires only when a connector has ≥2 signal pins and literally zero
    # ground pins, and connector detection is a ref-designator heuristic.
    severity = Severity.WARNING
    topic = "connectors"
    title = "Connector short of ground-return pins"
    rationale = "Every signal leaving on a header needs a nearby ground return; too few ground pins forces return current to detour and radiate."
    citation = "PHIL-CON-1 (#65; ≥1 GND per signal, alternate GND:signal for high speed)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        findings: list[Finding] = []
        for conn in sch.components:
            if not _is_connector(conn.ref):
                continue
            nets = sch.nets_of(conn.ref)
            if not nets:
                continue
            grounds = sum(1 for n in nets if n.kind == "ground")
            signals = sum(1 for n in nets if n.kind in ("signal", "clock", "diff", "analog"))
            if signals >= 2 and grounds == 0:
                findings.append(
                    self.make(
                        f"Connector '{conn.ref}' carries {signals} signal pins but no ground "
                        f"pin. Add at least one ground return (more for high-speed).",
                        Location(footprint=conn.ref),
                    )
                )
        return findings


@register
class ConnectorEsdProtection(Rule):
    id = "PHIL-ESD-1"
    # Catalog severity is E; kept WARNING as intentional false-positive control —
    # TVS detection is name/prefix-based and not every external line needs a TVS.
    severity = Severity.WARNING
    topic = "connectors"
    title = "Externally-facing lines without ESD protection"
    rationale = "Connector-facing signals take ESD strikes; a TVS at the connector shunts the strike to ground before it reaches the IC."
    citation = "PHIL-ESD-1 (Phil's Lab S4 'ESD Protection Basics'; place TVS at the connector)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        findings: list[Finding] = []
        for conn in sch.components:
            if not _is_connector(conn.ref):
                continue
            signal_nets = [
                n for n in sch.nets_of(conn.ref) if n.kind in ("signal", "clock", "diff", "analog")
            ]
            if not signal_nets:
                continue
            protected = any(self._has_tvs(sch, n.name) for n in signal_nets)
            if not protected:
                findings.append(
                    self.make(
                        f"Connector '{conn.ref}' has externally-facing signal lines with no "
                        f"TVS/ESD protection. Add a TVS array at the connector, shunt to GND.",
                        Location(footprint=conn.ref),
                    )
                )
        return findings

    def _has_tvs(self, sch: Schematic, net_name: str) -> bool:
        for comp in sch.components_on(net_name):
            ref = comp.ref.upper()
            val = comp.value.lower().replace(" ", "").replace("-", "")
            # TVS/ESD parts are referenced D*, TVS*, or U* (arrays), and their
            # value/MPN carries a recognizable clamp stem.
            if ref.startswith(("D", "TVS", "U")) and any(stem in val for stem in _TVS_STEMS):
                return True
        return False
