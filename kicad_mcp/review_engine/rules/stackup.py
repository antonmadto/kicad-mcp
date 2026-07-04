"""Stackup rules — Hartley K*, Phil STK*.

The single highest-leverage family: a signal without a close reference plane is a
defect (A2), and the pwr–gnd cavity is the only HF charge source (A3).
"""

from __future__ import annotations

from ..model import CopperLayer, DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity

_PLANE_ROLES = {"ground_plane", "power_plane", "mixed_plane"}


def _is_plane(layer: CopperLayer) -> bool:
    return layer.role in _PLANE_ROLES


@register
class SignalLayersNeedAdjacentPlane(Rule):
    id = "HARTLEY-K1"
    severity = Severity.ERROR
    topic = "stackup"
    title = "Adjacent signal layers with no plane between them"
    rationale = "A trace's return is in its adjacent plane; two adjacent signal layers have none, so fields from one couple into the other."
    citation = "HARTLEY-K1 / PHIL-STK-3 (Altium stackup, S1)"

    def check(self, model: DesignModel) -> list[Finding]:
        findings: list[Finding] = []
        layers = model.copper_layers
        for a, b in zip(layers, layers[1:], strict=False):
            if not _is_plane(a) and not _is_plane(b):
                findings.append(
                    self.make(
                        f"Copper layers '{a.name}' and '{b.name}' are physically adjacent "
                        f"but neither is a plane — signals on them have no local reference. "
                        f"Insert a ground plane between them.",
                        Location(layer=f"{a.name}/{b.name}"),
                    )
                )
        return findings


@register
class ConventionalFourLayer(Rule):
    id = "HARTLEY-K2"
    severity = Severity.WARNING
    topic = "stackup"
    title = "Conventional 4-layer Sig/Pwr/Gnd/Sig stackup"
    rationale = "Sig/Pwr/Gnd/Sig at 1.6 mm puts the planes ~40 mil apart (poor HF power) and references the outer signals to power, not ground."
    citation = "HARTLEY-K2 / PHIL-STK-1 (S1, S7)"

    def check(self, model: DesignModel) -> list[Finding]:
        roles = [ly.role for ly in model.copper_layers]
        if roles == ["signal", "power_plane", "ground_plane", "signal"]:
            return [
                self.make(
                    "4-layer stack is Sig/PWR/GND/Sig. Prefer Sig/GND/GND/Sig (or pour power "
                    "on the signal layers) so every signal references ground and the pwr–gnd "
                    "cavity is tight.",
                    Location(layer="stackup"),
                )
            ]
        return []


@register
class PowerGroundCavityTooThick(Rule):
    id = "HARTLEY-K5"
    severity = Severity.ERROR
    topic = "stackup"
    title = "Power and ground planes not a tight adjacent pair"
    rationale = "Interplane capacitance is the only HF charge source; it needs an adjacent pwr–gnd pair with ≤ 0.2 mm (8 mil) dielectric."
    citation = "HARTLEY-K5 / PHIL-STK-4 (verified S3 1:18:49)"

    _MAX_MM = 0.2

    def check(self, model: DesignModel) -> list[Finding]:
        layers = model.copper_layers
        has_power = any(ly.role == "power_plane" for ly in layers)
        has_ground = any(ly.role in ("ground_plane", "mixed_plane") for ly in layers)
        if not (has_power and has_ground):
            return []

        findings: list[Finding] = []
        adjacent_pairs = list(zip(layers, layers[1:], strict=False))
        pg_pairs = [
            (a, b) for a, b in adjacent_pairs if {a.role, b.role} == {"power_plane", "ground_plane"}
        ]
        if not pg_pairs:
            findings.append(
                self.make(
                    "The board has power and ground planes but they are not an adjacent pair "
                    "(a signal layer separates them). Put pwr and gnd on adjacent layers with a "
                    "thin dielectric.",
                    Location(layer="stackup"),
                )
            )
            return findings

        for a, b in pg_pairs:
            gap = a.dielectric_to_next_mm
            if gap is None or gap > self._MAX_MM:
                findings.append(
                    self.make(
                        f"Power/ground plane pair '{a.name}'/'{b.name}' has a "
                        f"{gap if gap is not None else '?'} mm dielectric (> {self._MAX_MM} mm). "
                        f"Tighten it so interplane capacitance can supply HF charge.",
                        Location(layer=f"{a.name}/{b.name}"),
                    )
                )
        return findings


@register
class TwoLayerNeedsGroundBottom(Rule):
    id = "HARTLEY-K6"
    severity = Severity.WARNING
    topic = "stackup"
    title = "2-layer board without a solid ground reference"
    rationale = "At ns rise times a 2-layer board needs a solid ground under every top route to give return current a defined path."
    citation = "HARTLEY-K6 (S1, S4) / PHIL-STK-7 (S6)"

    def check(self, model: DesignModel) -> list[Finding]:
        layers = model.copper_layers
        if len(layers) != 2:
            return []
        has_ground_plane = any(ly.role in ("ground_plane", "mixed_plane") for ly in layers)
        if has_ground_plane:
            return []
        if not model.tracks:
            return []
        return [
            self.make(
                "2-layer board carries routed tracks but neither layer is a solid ground plane. "
                "Pour a solid ground on the bottom under the top-side routes.",
                Location(layer="stackup"),
            )
        ]
