"""SMPS layout rules — Phil PWR-3.

The switch node (SW/LX) is the noisiest net on a regulator; the feedback trace is
the most sensitive. Route FB away from SW and the inductor, and sense it at the
output capacitor. This is a board-geometry proximity heuristic on named nets.
"""

from __future__ import annotations

from .. import geometry as geo
from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity

_FB_NAMES = ("FB", "FEEDBACK", "VFB", "V_FB")
_SW_NAMES = ("SW", "SWITCH", "LX", "PHASE", "SW_NODE")
_MIN_CLEARANCE_MM = 2.0


def _net_codes_named(model: DesignModel, names) -> set[int]:
    out: set[int] = set()
    for code, net in model.nets.items():
        base = net.name.split("/")[-1].upper()
        if base in names or any(base.startswith(n + "_") for n in names):
            out.add(code)
    return out


@register
class FeedbackNearSwitchNode(Rule):
    id = "PHIL-PWR-3"
    # Catalog severity is E; kept WARNING — this is a name-based geometry heuristic
    # (FB/SW net names + track proximity), so a WARNING avoids over-asserting.
    severity = Severity.WARNING
    topic = "smps"
    title = "Regulator feedback routed close to the switch node"
    rationale = "SW is the loudest net on the converter; a nearby FB trace couples switching noise into the control loop, causing jitter and instability."
    citation = "PHIL-PWR-3 (#60 8:22, 24:19 — sense FB at the output cap, away from SW)"

    def check(self, model: DesignModel) -> list[Finding]:
        fb_codes = _net_codes_named(model, _FB_NAMES)
        sw_codes = _net_codes_named(model, _SW_NAMES)
        if not fb_codes or not sw_codes:
            return []
        fb_tracks = [t for t in model.tracks if t.net_code in fb_codes]
        sw_tracks = [t for t in model.tracks if t.net_code in sw_codes]

        findings: list[Finding] = []
        reported: set[int] = set()
        for fb in fb_tracks:
            if fb.net_code in reported:
                continue
            for sw in sw_tracks:
                if sw.layer != fb.layer:
                    continue
                if self._too_close(fb, sw):
                    reported.add(fb.net_code)
                    fb_net = model.nets.get(fb.net_code)
                    sw_net = model.nets.get(sw.net_code)
                    findings.append(
                        self.make(
                            f"Feedback net '{fb_net.name if fb_net else fb.net_code}' runs "
                            f"within {_MIN_CLEARANCE_MM} mm of switch node "
                            f"'{sw_net.name if sw_net else sw.net_code}' on {fb.layer}. Route "
                            f"FB away from SW/the inductor and sense it at the output cap.",
                            Location(net=fb_net.name if fb_net else None, layer=fb.layer),
                        )
                    )
                    break
        return findings

    def _too_close(self, a, b) -> bool:
        # Shortest distance between the two segments (endpoints vs opposite segment).
        d = min(
            geo.point_segment_distance(a.start, b.start, b.end),
            geo.point_segment_distance(a.end, b.start, b.end),
            geo.point_segment_distance(b.start, a.start, a.end),
            geo.point_segment_distance(b.end, a.start, a.end),
        )
        return d < _MIN_CLEARANCE_MM
