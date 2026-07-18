"""Decoupling rules — Phil DEC-1, Hartley D2.

One 100 nF ceramic per IC power pin, physically close (loop inductance). This is
a board-level proximity heuristic: it checks that each IC has a 100 nF cap
nearby, using footprint positions.
"""

from __future__ import annotations

from .. import geometry as geo
from ..model import DesignModel, Footprint
from ..registry import register
from .base import Finding, Location, Rule, Severity

_NEAR_MM = 5.0


def _is_ic(fp: Footprint) -> bool:
    # Reference-designator prefix only. A pad-count heuristic would sweep in
    # connectors (J), switches (SW), resistor networks (RN)... — false positives.
    ref = fp.ref.upper()
    return ref.startswith("IC") or (ref.startswith("U") and not ref.startswith("USB"))


def _is_100nf_cap(fp: Footprint) -> bool:
    if fp.ref[:1].upper() != "C":
        return False
    v = fp.value.lower().replace(" ", "").replace("µ", "u").replace("μ", "u")
    return v.startswith(("100n", "0.1u"))


@register
class DecouplingCapPerIC(Rule):
    id = "PHIL-DEC-1"
    # Catalog severity is E; softened to WARNING because this is a footprint-
    # proximity heuristic (it cannot see pin functions), and false positives
    # destroy trust (CLAUDE.md). Physics guidance unchanged.
    severity = Severity.WARNING
    topic = "decoupling"
    title = "IC without a nearby 100 nF decoupling cap"
    rationale = "Each IC power pin needs a 100 nF ceramic close by; distance is loop inductance, and inductance is what kills HF decoupling."
    citation = "PHIL-DEC-1 (#65 11:15) ≈ HARTLEY-D2 (S2 1:00:37)"

    def check(self, model: DesignModel) -> list[Finding]:
        caps = [fp for fp in model.footprints if _is_100nf_cap(fp)]
        ics = [fp for fp in model.footprints if _is_ic(fp)]
        if not ics:
            return []

        findings: list[Finding] = []
        for ic in ics:
            # Measure pin-to-cap, not centroid-to-cap: on a large package the power
            # pins (and their caps) sit near the edge, several mm off the centroid.
            ic_points = [p.at for p in ic.pads] or [ic.at]
            nearest = min(
                (geo.distance(ip, c.at) for c in caps for ip in ic_points),
                default=None,
            )
            if nearest is None or nearest > _NEAR_MM:
                where = (
                    "no 100 nF cap on the board"
                    if nearest is None
                    else f"nearest 100 nF cap is {round(nearest, 1)} mm away"
                )
                findings.append(
                    self.make(
                        f"IC '{ic.ref}' has no 100 nF decoupling cap within {_NEAR_MM} mm "
                        f"({where}). Place a 100 nF ceramic at each power pin.",
                        Location(
                            footprint=ic.ref,
                            at={"x": round(ic.at[0], 3), "y": round(ic.at[1], 3)},
                        ),
                    )
                )
        return findings
