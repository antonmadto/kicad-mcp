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
        findings: list[Finding] = []
        extents = model.extents
        for track in model.tracks:
            ref = _reference_plane(model, track.layer)
            if ref is None:
                continue
            # All copper pours on the plane layer are reference copper (see
            # module docstring for why this is not filtered by net kind).
            ref_zones = [z for z in model.zones_on(ref.name) if len(z.polygon) >= 3]
            if not ref_zones:
                continue

            crossing = self._first_gap(track, ref_zones, extents)
            if crossing is not None:
                net = model.nets.get(track.net_code)
                findings.append(
                    self.make(
                        f"Track on '{track.layer}' crosses a gap in its reference plane "
                        f"'{ref.name}' near ({round(crossing[0], 2)}, {round(crossing[1], 2)}). "
                        f"Reroute so the trace stays over continuous plane copper.",
                        Location(
                            net=net.name if net else str(track.net_code),
                            layer=track.layer,
                            at={"x": round(crossing[0], 3), "y": round(crossing[1], 3)},
                        ),
                    )
                )
        return findings

    def _covered(self, sample: geo.Point, ref_zones) -> bool:
        for z in ref_zones:
            if geo.point_in_polygon(sample, z.polygon):
                return True
        # Boundary tolerance: abutting-zone seams and pullback regions.
        for z in ref_zones:
            if geo.point_to_polygon_edge_distance(sample, z.polygon) < _ZONE_EDGE_TOL_MM:
                return True
        return False

    def _first_gap(self, track, ref_zones, extents):
        run: list[geo.Point] = []
        for sample in geo.sample_segment(track.start, track.end, _SAMPLE_STEP_MM):
            if extents and not _interior(sample, extents, _EDGE_MARGIN_MM):
                run = []
                continue
            if self._covered(sample, ref_zones):
                run = []
                continue
            run.append(sample)
            if len(run) >= _MIN_GAP_RUN:
                return run[len(run) // 2]  # midpoint of the uncovered run
        return None
