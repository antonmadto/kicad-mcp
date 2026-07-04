"""Crosstalk rules — Hartley C4, Phil RTE-1.

Keep other signals ≥ 3×H (H = height above the reference plane) from a
differential pair: at 1×H, crosstalk is ~12% into the near line vs 1–2% into the
far line — a guaranteed imbalance that becomes cable EMI. Targeted at aggressors
near diff pairs to keep false positives low (buses legitimately run parallel).
"""

from __future__ import annotations

from .. import geometry as geo
from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity
from .transmission import _diff_pairs

_KEEPOUT_H = 3.0
_MIN_OVERLAP_MM = 5.0  # ignore brief crossings — only sustained parallel runs couple
_DEFAULT_H_MM = 0.2  # typical microstrip height when the stackup is unknown


def _height_to_reference(model: DesignModel, layer: str) -> float:
    ly = model.copper_layer(layer)
    if ly is not None and ly.dielectric_to_next_mm:
        return ly.dielectric_to_next_mm
    # Look at the previous copper layer's gap (its dielectric_to_next is to us).
    layers = model.copper_layers
    for i, cur in enumerate(layers):
        if cur.name == layer and i > 0 and layers[i - 1].dielectric_to_next_mm:
            return layers[i - 1].dielectric_to_next_mm
    return _DEFAULT_H_MM


@register
class AggressorTooCloseToDiffPair(Rule):
    id = "HARTLEY-C4"
    severity = Severity.WARNING
    topic = "crosstalk"
    title = "Aggressor trace too close to a differential pair"
    rationale = "At 1×H crosstalk is ~12% near vs 1–2% far — an asymmetry that converts to common mode and radiates; keep aggressors ≥ 3×H away."
    citation = "HARTLEY-C4 ≈ PHIL-RTE-1 (S2 37:31–38:40, 55:46)"

    def check(self, model: DesignModel) -> list[Finding]:
        pair_codes = {c for p, n, _ in _diff_pairs(model) for c in (p, n)}
        if not pair_codes:
            return []
        pair_tracks = [t for t in model.tracks if t.net_code in pair_codes]
        others = [t for t in model.tracks if t.net_code not in pair_codes]

        # Accumulate the close-parallel overlap length per (aggressor, pair, layer)
        # ACROSS all segment comparisons, so a route split into many short
        # segments still trips the threshold (a single segment rarely spans 5 mm).
        overlap_by_key: dict[tuple[int, int, str], float] = {}
        for pt in pair_tracks:
            keepout = _KEEPOUT_H * _height_to_reference(model, pt.layer)
            for ot in others:
                if ot.layer != pt.layer:
                    continue
                parallel, perp, overlap = geo.segment_parallel_proximity(
                    pt.start, pt.end, ot.start, ot.end
                )
                if parallel and 0 < perp < keepout and overlap > 0:
                    key = (ot.net_code, pt.net_code, pt.layer)
                    overlap_by_key[key] = overlap_by_key.get(key, 0.0) + overlap

        findings: list[Finding] = []
        for (agg_code, pair_code, layer), total in sorted(overlap_by_key.items()):
            if total < _MIN_OVERLAP_MM:
                continue
            keepout = _KEEPOUT_H * _height_to_reference(model, layer)
            agg = model.nets.get(agg_code)
            pair = model.nets.get(pair_code)
            findings.append(
                self.make(
                    f"Net '{agg.name if agg else agg_code}' runs parallel within "
                    f"{round(keepout, 2)} mm (3×H) of diff-pair net "
                    f"'{pair.name if pair else pair_code}' for {round(total, 1)} mm on "
                    f"{layer}. Move it away or it will couple asymmetrically into the pair.",
                    Location(net=agg.name if agg else None, layer=layer),
                )
            )
        return findings
