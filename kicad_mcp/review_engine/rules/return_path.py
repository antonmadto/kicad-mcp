"""Return-path rules — Hartley R5/C1, Phil STK-6/MIX-4.

Above ~20 kHz all return current flows directly under the trace; a trace crossing
a split, slot, or void in its reference plane balloons loop area and radiates
(measured 20–30 dB worse EMI, S3 42:59). Checked geometrically: sample points
along each track and confirm the adjacent reference plane's copper covers them.

Robustness choices (anti-false-positive, in order of importance):
- A sample within ``_ZONE_EDGE_TOL_MM`` of any reference-zone boundary counts as
  covered — so two abutting same-net pours (a continuous plane drawn as two
  zones) and normal pullback/clearance regions never read as "gaps".
- A gap is only flagged after ``_MIN_GAP_RUN`` consecutive uncovered samples —
  a single borderline sample never fires.
- ALL copper zones on the reference layer count as reference copper (not only
  name-classified ground/power): any plane copper under the trace carries the
  return; net-name misclassification must not silently disable the check.
- Keepout/rule-area zones (copperpour not_allowed) are voids, not copper: a sample
  inside a keepout reads as uncovered even when a pour outline spans it — that is
  exactly the EMI moat this rule is meant to catch.
"""

from __future__ import annotations

from .. import geometry as geo
from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity

_PLANE_ROLES = {"ground_plane", "power_plane", "mixed_plane"}
_EDGE_MARGIN_MM = 1.0  # ignore samples near the board edge (planes pull back there)
_SAMPLE_STEP_MM = 0.5
_ZONE_EDGE_TOL_MM = 0.5  # within this of a zone boundary counts as covered
_MIN_GAP_RUN = 2  # consecutive uncovered samples required to call it a gap


def _reference_plane(model: DesignModel, layer_name: str):
    layers = model.copper_layers
    idx = next((i for i, ly in enumerate(layers) if ly.name == layer_name), None)
    if idx is None or layers[idx].role in _PLANE_ROLES:
        return None
    neighbors = []
    if idx + 1 < len(layers):
        neighbors.append(layers[idx + 1])
    if idx - 1 >= 0:
        neighbors.append(layers[idx - 1])
    planes = [n for n in neighbors if n.role in _PLANE_ROLES]
    planes.sort(key=lambda c: 0 if c.role == "ground_plane" else 1)
    return planes[0] if planes else None


def _interior(pt: geo.Point, extents: dict, margin: float) -> bool:
    return (
        extents["min_x"] + margin <= pt[0] <= extents["max_x"] - margin
        and extents["min_y"] + margin <= pt[1] <= extents["max_y"] - margin
    )


@register
class TraceCrossesReferenceGap(Rule):
    id = "HARTLEY-R5"
    severity = Severity.ERROR
    topic = "return_path"
    title = "Trace crosses a gap/split in its reference plane"
    rationale = "Return current flows directly under the trace; a gap in the reference plane forces it around, ballooning loop area and EMI."
    citation = "HARTLEY-R5/C1 ≈ PHIL-STK-6/MIX-4 (S3 27:01, 42:59; #88 4:40)"

    def check(self, model: DesignModel) -> list[Finding]:
        extents = model.extents
        # Group per (net, layer): a net routed as many segments through one uncovered
        # region is ONE root cause, so it yields ONE finding — not one per segment
        # (a real board floods otherwise; the geometric detection is unchanged).
        grouped: dict[tuple[int, str], dict] = {}
        order: list[tuple[int, str]] = []
        for track in model.tracks:
            ref = _reference_plane(model, track.layer)
            if ref is None:
                continue
            # All copper pours on the plane layer are reference copper (see
            # module docstring for why this is not filtered by net kind). Keepout
            # rule-areas carve the copper, so they are voids, not reference copper.
            on_ref = [z for z in model.zones_on(ref.name) if len(z.polygon) >= 3]
            ref_pours = [z for z in on_ref if not z.keepout]
            ref_voids = [z for z in on_ref if z.keepout]
            if not ref_pours:
                continue

            crossing = self._first_gap(track, ref_pours, ref_voids, extents)
            if crossing is None:
                continue
            key = (track.net_code, track.layer)
            entry = grouped.get(key)
            if entry is None:
                grouped[key] = {"ref": ref.name, "count": 1, "first": crossing}
                order.append(key)
            else:
                entry["count"] += 1

        findings: list[Finding] = []
        for key in order:
            net_code, layer = key
            entry = grouped[key]
            count = entry["count"]
            first = entry["first"]
            net = model.nets.get(net_code)
            findings.append(
                self.make(
                    f"Net '{net.name if net else net_code}' crosses gaps in its reference "
                    f"plane '{entry['ref']}' at {count} "
                    f"place{'s' if count != 1 else ''} (first near "
                    f"({round(first[0], 2)}, {round(first[1], 2)})). Reroute so the trace "
                    f"stays over continuous plane copper.",
                    Location(
                        net=net.name if net else str(net_code),
                        layer=layer,
                        at={"x": round(first[0], 3), "y": round(first[1], 3)},
                    ),
                )
            )
        return findings

    def _covered(self, sample: geo.Point, ref_pours, ref_voids) -> bool:
        # A keepout void carved into the plane is not copper — the return has no
        # path here even if a pour outline still spans it.
        for z in ref_voids:
            if geo.point_in_polygon(sample, z.polygon):
                return False
        for z in ref_pours:
            if geo.point_in_polygon(sample, z.polygon):
                return True
        # Boundary tolerance: abutting-zone seams and pullback regions.
        for z in ref_pours:
            if geo.point_to_polygon_edge_distance(sample, z.polygon) < _ZONE_EDGE_TOL_MM:
                return True
        return False

    def _first_gap(self, track, ref_pours, ref_voids, extents):
        run: list[geo.Point] = []
        for sample in geo.sample_segment(track.start, track.end, _SAMPLE_STEP_MM):
            if extents and not _interior(sample, extents, _EDGE_MARGIN_MM):
                run = []
                continue
            if self._covered(sample, ref_pours, ref_voids):
                run = []
                continue
            run.append(sample)
            if len(run) >= _MIN_GAP_RUN:
                return run[len(run) // 2]  # midpoint of the uncovered run
        return None
