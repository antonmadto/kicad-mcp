"""Grounding rules — Hartley G*, Phil MIX-1.

Hartley's verified position: one continuous ground plane, partition by placement;
if you must isolate domains, split the POWER plane only (see return_path / G5).
Splitting ground diverts return current and worsens EMI.
"""

from __future__ import annotations

from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity


@register
class GroundPlaneSplit(Rule):
    id = "HARTLEY-G1"
    severity = Severity.ERROR
    topic = "grounding"
    title = "Ground plane is split into multiple zones"
    rationale = "A split diverts return current around the gap, ballooning loop area and EMI; a continuous ground plane is one pour."
    citation = "HARTLEY-G1 (verified S3 1:18:16 'leave a continuous ground plane')"

    def check(self, model: DesignModel) -> list[Finding]:
        findings: list[Finding] = []
        for layer in model.copper_layers:
            if layer.role in ("ground_plane", "mixed_plane") and layer.ground_zone_count >= 2:
                findings.append(
                    self.make(
                        f"Ground plane on '{layer.name}' is split into {layer.ground_zone_count} "
                        f"separate zones. Use one continuous ground pour and partition by placement "
                        f"instead of cutting the plane.",
                        Location(layer=layer.name, net="GND"),
                    )
                )
        return findings


@register
class SeparateAnalogDigitalGrounds(Rule):
    id = "HARTLEY-G2"
    # Catalog severity is E; softened to WARNING here because a net-name heuristic
    # cannot confirm the grounds are actually isolated vs single-point-tied, and
    # false positives destroy trust (CLAUDE.md). The physics guidance is unchanged.
    severity = Severity.WARNING
    topic = "grounding"
    title = "Separate analog/digital ground nets"
    rationale = "Placement partitioning beats splitting; for 99% of mixed-signal designs one continuous ground plane, not separate AGND/DGND nets, is correct."
    citation = "HARTLEY-G2 ≈ PHIL-MIX-1 (S3 1:15–1:18; #88 3:35 'do not split your ground')"

    def check(self, model: DesignModel) -> list[Finding]:
        ground_names = sorted(
            {n.name for n in model.nets.values() if n.kind == "ground" and n.name}
        )
        if len(ground_names) >= 2:
            return [
                self.make(
                    f"Found {len(ground_names)} distinct ground nets ({', '.join(ground_names)}). "
                    f"Prefer ONE continuous ground plane and partition analog vs digital by "
                    f"placement; if isolation is truly required, split the POWER plane, not ground.",
                    Location(net=", ".join(ground_names)),
                )
            ]
        return []
