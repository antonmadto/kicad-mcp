"""Transmission-line rules — Hartley F1/F2/F4/F5.

Circuit frequency is rise time, not clock (F1); a trace longer than the critical
length behaves as a transmission line (F2); differential-pair skew is a TIME
budget in picoseconds, never a length in millimetres (F4 / anti-myth M5).
"""

from __future__ import annotations

from ..model import DesignModel
from ..registry import register
from .base import Finding, Location, Rule, Severity

# Nets whose kind means "not a routed signal" — skip for critical-length.
_NON_SIGNAL = {"ground", "power", "unconnected"}


@register
class CriticalLengthUncontrolled(Rule):
    id = "HARTLEY-F2"
    severity = Severity.WARNING
    topic = "transmission"
    title = "Signal net exceeds its critical length"
    rationale = "Past L_crit ≈ (t_rise/2)·v a trace is a transmission line: it needs controlled impedance and termination, or it rings and radiates."
    citation = "HARTLEY-F2/F1 (S2); L_crit from set_design_context rise time"

    def check(self, model: DesignModel) -> list[Finding]:
        t_rise_ns = model.context.default_rise_time_ns
        # Nets the user has declared controlled-impedance are handled by design;
        # F2's whole point is *un*controlled ones.
        controlled = {k.lstrip("/") for k in model.context.target_impedances}
        # One entry per over-length signal net (length aggregated across its segments).
        over: list[tuple[str, float, float, str]] = []  # (name, length, l_crit, layer)
        seen: set[int] = set()
        for track in model.tracks:
            net = model.nets.get(track.net_code)
            if net is None or net.kind in _NON_SIGNAL or track.net_code in seen:
                continue
            if net.name.lstrip("/") in controlled:
                continue
            length = model.net_length_mm(track.net_code)
            v = model.signal_velocity_mm_per_ns(track.layer)
            l_crit = (t_rise_ns / 2.0) * v
            if length > l_crit:
                seen.add(track.net_code)
                over.append((net.name, length, l_crit, track.layer))

        if not over:
            return []

        # An ASSUMED edge rate must not flood a real board with per-net warnings —
        # false positives destroy trust (CLAUDE.md: severity tiers + design context are
        # the guardrails). Until the user declares a real rise time, summarize as ONE
        # INFO; only an explicit rise time earns per-net WARNINGs.
        if not model.context.rise_time_explicit:
            top = sorted(over, key=lambda o: o[1], reverse=True)[:5]
            longest = ", ".join(f"{name} {round(length, 1)} mm" for name, length, _, _ in top)
            return [
                Finding(
                    rule_id=self.id,
                    severity=Severity.INFO,
                    title=self.title,
                    message=(
                        f"{len(over)} signal net(s) exceed the critical length for the "
                        f"ASSUMED {t_rise_ns} ns edge (f_knee ≈ "
                        f"{round(model.context.f_knee_hz / 1e6)} MHz) — the default used when "
                        f"no rise time was declared. Longest: {longest}. Call "
                        f"set_design_context with the real rise time for a per-net "
                        f"transmission-line audit."
                    ),
                    rationale=self.rationale,
                    citation=self.citation,
                    topic=self.topic,
                )
            ]

        findings: list[Finding] = []
        for name, length, l_crit, layer in over:
            findings.append(
                self.make(
                    f"Net '{name}' is routed {round(length, 1)} mm, above the "
                    f"critical length {round(l_crit, 1)} mm for a {t_rise_ns} ns edge "
                    f"(f_knee ≈ {round(model.context.f_knee_hz / 1e6)} MHz). Use a "
                    f"controlled-impedance trace and terminate it, or confirm the real "
                    f"rise time via set_design_context.",
                    Location(net=name, layer=layer),
                )
            )
        return findings


@register
class DiffPairIntraSkew(Rule):
    id = "HARTLEY-F4"
    severity = Severity.WARNING
    topic = "transmission"
    title = "Differential pair intra-pair skew (in time)"
    rationale = "Match a pair by delay, not length: residual skew converts differential to common-mode, which radiates from cables. Budget is picoseconds."
    citation = "HARTLEY-F4/M5 ≈ PHIL-USB-4 (S2 44:43; #110 14:30) — intra-pair target ~0 ps"

    _SKEW_WARN_PS = 5.0  # DDR3-class intra-pair budget; a general 'tight' threshold

    def check(self, model: DesignModel) -> list[Finding]:
        findings: list[Finding] = []
        for p_code, n_code, stem in _diff_pairs(model):
            p_len = model.net_length_mm(p_code)
            n_len = model.net_length_mm(n_code)
            if p_len == 0 and n_len == 0:
                continue
            # Use the P net's layer for the prop-delay constant (pairs share a layer).
            layer = _first_layer(model, p_code) or "F.Cu"
            skew_ps = abs(p_len - n_len) * model.prop_delay_ps_per_mm(layer)
            if skew_ps > self._SKEW_WARN_PS:
                findings.append(
                    self.make(
                        f"Differential pair '{stem}' has {round(skew_ps, 1)} ps intra-pair "
                        f"skew ({round(abs(p_len - n_len), 2)} mm length mismatch). Match the "
                        f"pair by delay toward ~0 ps; do not length-match in mm.",
                        Location(net=stem, layer=layer),
                    )
                )
        return findings


_NON_PAIR_KINDS = {"power", "ground", "unconnected"}


def _diff_pairs(model: DesignModel):
    """Yield (p_net_code, n_net_code, stem) for name-recognized differential pairs."""
    by_stem: dict[str, dict[str, int]] = {}
    for code, net in model.nets.items():
        # Power/ground nets are never diff pairs (guards VIN vs a phantom "VIP").
        if net.kind in _NON_PAIR_KINDS:
            continue
        stem, polarity = _split_polarity(net.name)
        if polarity is None:
            continue
        by_stem.setdefault(stem.lstrip("/"), {})[polarity] = code
    for stem, ends in by_stem.items():
        if "P" in ends and "N" in ends:
            yield ends["P"], ends["N"], stem


def _split_polarity(name: str) -> tuple[str, str | None]:
    """Split a diff-pair net name into (stem, 'P'|'N'|None).

    Only DELIMITED or token forms count as a pair — a bare trailing letter must
    not (``VIN``/``VIP``, ``EN``, ``SPIN`` are not diff pairs). Recognized:
    ``+``/``-``, ``_P``/``_N``, ``DP``/``DM`` (USB), and ``P``/``N`` only when
    preceded by ``_`` or a digit (``LVDS0P``/``LVDS0N``).
    """
    n = name.rstrip()
    if n.endswith("+"):
        return n[:-1], "P"
    if n.endswith("-"):
        return n[:-1], "N"
    for suffix, pol in (("_DP", "P"), ("_DM", "N"), ("DP", "P"), ("DM", "N")):
        if n.endswith(suffix) and len(n) > len(suffix):
            return n[: -len(suffix)].rstrip("_"), pol
    if n.endswith("_P"):
        return n[:-2], "P"
    if n.endswith("_N"):
        return n[:-2], "N"
    # Bare P/N only after a digit — a letter before P/N is an ordinary net.
    if len(n) >= 2 and n[-1] in ("P", "N") and n[-2].isdigit():
        return n[:-1], ("P" if n[-1] == "P" else "N")
    return name, None


def _first_layer(model: DesignModel, net_code: int) -> str | None:
    return next((t.layer for t in model.tracks if t.net_code == net_code), None)
