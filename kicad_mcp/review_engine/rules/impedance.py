"""Controlled-impedance rule — Hartley Z1.

A net the user declared controlled-impedance whose routed geometry yields a Z0
far from target reflects and rings at every impedance step. The rule fires ONLY
on nets with a declared target (set_design_context) and only when the geometry
gives a confident Z0 — it never invents a 50/90/100 Ω expectation, so an
un-declared board stays silent (anti-myth).
"""

from __future__ import annotations

from .. import impedance as imp
from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity


@register
class ControlledImpedanceMismatch(Rule):
    id = "HARTLEY-Z1"
    severity = Severity.WARNING
    topic = "transmission"
    title = "Controlled-impedance net misses its target impedance"
    rationale = (
        "A net declared controlled-impedance whose routed geometry yields a Z0 far "
        "from target reflects and rings at every impedance step; adjust trace width or stackup."
    )
    citation = (
        "HARTLEY-Z1 (operationalizes controlled-impedance discipline behind HARTLEY-F2 & "
        "PHIL-USB-1); Z0 via Hammerstad-Jensen microstrip / IPC-2141 stripline; "
        "±10% = standard PCB-fab controlled-impedance tolerance (±5% premium)"
    )

    def check(self, model: DesignModel) -> list[Finding]:
        targets = model.context.target_impedances
        if not targets:  # anti-myth early-out: never invent a target
            return []
        analysis = imp.analyze_model(model)
        verdicts, _unmatched = imp.evaluate_targets(model, analysis)
        findings: list[Finding] = []
        for v in verdicts:
            if v.verdict not in ("fail", "info"):  # 'pass'/'unknown'/low-confidence → silent
                continue
            sev = Severity.WARNING if v.verdict == "fail" else Severity.INFO
            kindword = "differential" if v.kind == "differential" else "single-ended"
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=sev,
                    title=self.title,
                    message=(
                        f"Net '{v.key}' targets {v.target_ohms:g} Ω {kindword} but the routed "
                        f"geometry ({v.model}) computes to {v.computed_ohms:.1f} Ω — "
                        f"{v.deviation_pct:+.1f}% "
                        f"({'outside' if v.verdict == 'fail' else 'near the edge of'} "
                        f"the ±10% fab band). Adjust the trace width or pair spacing, or confirm "
                        f"the fab's stackup matches this estimate."
                    ),
                    rationale=self.rationale,
                    citation=self.citation,
                    topic=self.topic,
                    location=Location(net=v.key, layer=v.layer),
                )
            )
        return findings
