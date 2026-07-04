"""DFM rules — Phil RTE-2/3, DFM-4.

Manufacturability basics: sane track widths by function, sane via annular rings,
and an explicit board outline. These are the cheapest findings to fix and the
most embarrassing to ship.
"""

from __future__ import annotations

from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity

_MIN_POWER_TRACK_MM = 0.25  # 0.2 mm ≈ 1 A; power defaults to 0.5 mm
_MIN_ANNULAR_MM = 0.1  # (pad - drill) / 2


@register
class PowerTrackTooThin(Rule):
    id = "PHIL-RTE-2"
    severity = Severity.WARNING
    topic = "dfm"
    title = "Power-net tracks narrower than the power default"
    rationale = "Track width is current capacity; power nets default to ~0.5 mm (0.2 mm ≈ 1 A), so a thin power trace risks heating and drop."
    citation = "PHIL-RTE-2 (#65 55:23 '0.3 mm signal / 0.5 mm power')"

    def check(self, model: DesignModel) -> list[Finding]:
        thin = []
        for t in model.tracks:
            net = model.nets.get(t.net_code)
            if net and net.kind == "power" and 0 < t.width < _MIN_POWER_TRACK_MM:
                thin.append(t)
        if not thin:
            return []
        thinnest = min(thin, key=lambda t: t.width)
        net = model.nets.get(thinnest.net_code)
        return [
            self.make(
                f"{len(thin)} power-net track segment(s) are narrower than "
                f"{_MIN_POWER_TRACK_MM} mm (thinnest {thinnest.width} mm). Widen power routing "
                f"to ~0.5 mm for current capacity.",
                Location(
                    net=net.name if net else str(thinnest.net_code),
                    layer=thinnest.layer,
                ),
            )
        ]


@register
class ViaAnnularRingTooSmall(Rule):
    id = "PHIL-RTE-3"
    severity = Severity.WARNING
    topic = "dfm"
    title = "Via annular ring below fab minimum"
    rationale = "A standard via is 0.7 mm pad / 0.3 mm drill (0.2 mm ring); too small a ring risks breakout during drilling."
    citation = "PHIL-RTE-3 (#65 design-rules slide, 0.7/0.3 mm)"

    def check(self, model: DesignModel) -> list[Finding]:
        bad = []
        for v in model.vias:
            if v.size > 0 and v.drill > 0:
                ring = (v.size - v.drill) / 2.0
                if ring < _MIN_ANNULAR_MM:
                    bad.append((v, ring))
        if not bad:
            return []
        worst_v, worst_ring = min(bad, key=lambda pair: pair[1])
        return [
            self.make(
                f"{len(bad)} via(s) have an annular ring below {_MIN_ANNULAR_MM} mm "
                f"(worst {round(worst_ring, 3)} mm at "
                f"({round(worst_v.at[0], 2)}, {round(worst_v.at[1], 2)})). "
                f"Use ≥ 0.7 mm pad / 0.3 mm drill unless your fab confirms tighter.",
                Location(at={"x": round(worst_v.at[0], 3), "y": round(worst_v.at[1], 3)}),
            )
        ]


@register
class BoardOutlineAndMountingHoles(Rule):
    id = "PHIL-DFM-4"
    # Catalog severity is W; escalated to ERROR here intentionally — a missing
    # Edge.Cuts outline is fab-blocking (no gerber set can be produced from it),
    # not merely a checklist item. The mounting-hole sub-finding stays INFO.
    severity = Severity.ERROR
    topic = "dfm"
    title = "Board outline missing"
    rationale = "Without an Edge.Cuts outline the fab cannot determine board shape; mounting holes should also be explicit."
    citation = "PHIL-DFM-4 (#65, #131 final-checklist)"

    def check(self, model: DesignModel) -> list[Finding]:
        findings: list[Finding] = []
        if not model.extents:
            findings.append(
                self.make(
                    "No board outline found on Edge.Cuts. Draw a closed board outline.",
                    Location(layer="Edge.Cuts"),
                )
            )
        has_mounting = any("mountinghole" in fp.lib_id.lower() for fp in model.footprints)
        if model.footprints and not has_mounting:
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=Severity.INFO,
                    title="No mounting holes",
                    message="No mounting-hole footprints found. Add explicit mounting holes if the board is enclosed or connectorized.",
                    rationale=self.rationale,
                    citation=self.citation,
                    topic=self.topic,
                    location=None,
                )
            )
        return findings
