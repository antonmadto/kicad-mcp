"""Subcircuit rules — Phil XTL / USB / STM / MIX / DEC-5.

Schematic-connectivity checks (need a netlist; skip cleanly when absent). These
encode the concrete, verified numbers from Phil's Lab #65 and the ST app notes.
Honors CHANGES.md: NRST 100 nF is a WARNING (self-pulls-up), not an error.
"""

from __future__ import annotations

from ..model import DesignModel, Schematic
from ..registry import register
from .base import Finding, Location, Rule, Severity


def _sch(model: DesignModel) -> Schematic | None:
    return model.schematic


def _is_100nf(value: str) -> bool:
    v = value.lower().replace(" ", "").replace("µ", "u").replace("μ", "u")
    return v.startswith(("100n", "0.1u"))


def _cap_on(sch: Schematic, net_name: str, predicate=None) -> bool:
    for cap in sch.components_on(net_name, prefix="C"):
        if predicate is None or predicate(cap):
            return True
    return False


@register
class CrystalLoadCaps(Rule):
    id = "PHIL-XTL-1"
    # Catalog severity is E; kept WARNING — crystal detection (ref Y*/X*) and
    # per-leg cap counting is a connectivity heuristic that can miss a shared node.
    severity = Severity.WARNING
    topic = "subcircuits"
    title = "Crystal without load capacitors"
    rationale = "A crystal needs matched load caps C = 2·(C_L − C_stray) on each leg or it starts unreliably / off-frequency."
    citation = "PHIL-XTL-1 (#65 30:10, per ST AN2867)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        findings: list[Finding] = []
        for xtal in sch.by_prefix("Y") + sch.by_prefix("X"):
            legs = [n for n in sch.nets_of(xtal.ref) if n.kind not in ("ground", "power")]
            caps = sum(1 for leg in legs if sch.components_on(leg.name, prefix="C"))
            if caps < 2:
                findings.append(
                    self.make(
                        f"Crystal '{xtal.ref}' has load caps on {caps} of its 2 legs. Add a "
                        f"matched load capacitor on each leg (C = 2·(C_L − C_stray)).",
                        Location(footprint=xtal.ref),
                    )
                )
        return findings


@register
class NrstDecoupling(Rule):
    id = "PHIL-STM-1"
    severity = Severity.WARNING  # verified E→W (NRST self-pulls-up), CHANGES.md
    topic = "subcircuits"
    title = "STM32 NRST without a 100 nF cap"
    rationale = "NRST self-pulls-up but is noise-sensitive; a 100 nF to GND is Phil's recommended reset filter."
    citation = "PHIL-STM-1 (#65 15:20; severity corrected E→W in CHANGES.md)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        nrst = sch.net("NRST") or sch.net("RESET") or sch.net("~{RESET}")
        if nrst is None:
            return []
        if not _cap_on(sch, nrst.name, lambda c: _is_100nf(c.value)):
            return [
                self.make(
                    "NRST has no 100 nF cap to GND. Add one as a reset-noise filter "
                    "(recommended, not mandatory — NRST has an internal pull-up).",
                    Location(net=nrst.name),
                )
            ]
        return []


@register
class Boot0Strapped(Rule):
    id = "PHIL-STM-2"
    severity = Severity.ERROR
    topic = "subcircuits"
    title = "STM32 BOOT0 left floating"
    rationale = "BOOT0 selects the boot source; floating it makes the boot mode nondeterministic. Strap it (low for SWD-only)."
    citation = "PHIL-STM-2 (#65 16:50)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        boot = sch.net("BOOT0")
        if boot is None:
            return []
        # A strapped BOOT0 connects to GND/power or through a resistor/switch.
        pins = boot.pins
        strapped = any(p.ref[:1].upper() in ("R", "SW") for p in pins) or boot.kind in (
            "ground",
            "power",
        )
        if not strapped and len(pins) <= 1:
            return [
                self.make(
                    "BOOT0 is not strapped (no resistor/switch/rail). Tie it low through a "
                    "resistor for SWD-only programming.",
                    Location(net=boot.name),
                )
            ]
        return []


@register
class I2CPullups(Rule):
    id = "PHIL-STM-6"
    severity = Severity.ERROR
    topic = "subcircuits"
    title = "I2C bus without pull-ups"
    rationale = "I2C is open-drain; without pull-ups on SCL/SDA the bus cannot signal a high level."
    citation = "PHIL-STM-6 (I2C fundamentals; ~2.2 kΩ typical)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        findings: list[Finding] = []
        for token in ("SCL", "SDA"):
            for net in sch.nets:
                base = net.name.split("/")[-1].upper()
                if base == token or base.startswith(token + "_") or base.endswith("_" + token):
                    if not sch.components_on(net.name, prefix="R"):
                        findings.append(
                            self.make(
                                f"I2C line '{net.name}' has no pull-up resistor. Add ~2.2 kΩ "
                                f"to the bus rail.",
                                Location(net=net.name),
                            )
                        )
        return findings


@register
class UsbDataPullup(Rule):
    id = "PHIL-USB-2"
    severity = Severity.ERROR
    topic = "subcircuits"
    title = "USB full-speed D+ without a 1.5 kΩ pull-up"
    rationale = "Full-speed USB is detected by a 1.5 kΩ pull-up from D+ to 3.3 V; without it the host never enumerates the device."
    citation = "PHIL-USB-2 (#65 33:01, per ST AN4879)"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        dp = sch.net("USB_D+") or sch.net("USB_DP") or sch.net("D+") or sch.net("DP")
        if dp is None:
            return []
        # If any MCU family with an internal pull-up is used this may be optional,
        # but we cannot tell from the netlist — flag when there is no pull resistor.
        if not sch.components_on(dp.name, prefix="R"):
            return [
                self.make(
                    "USB D+ has no pull-up resistor. Full-speed devices need 1.5 kΩ from D+ "
                    "to 3.3 V (unless the MCU provides an internal pull-up — verify AN4879).",
                    Location(net=dp.name),
                )
            ]
        return []


@register
class VssVssaTied(Rule):
    id = "PHIL-MIX-2"
    # Catalog severity is E; kept WARNING — VSSA on a separate net is sometimes an
    # intentional single-point tie, which the netlist alone cannot distinguish.
    severity = Severity.WARNING
    topic = "subcircuits"
    title = "VSSA not tied to VSS"
    rationale = "VSS (digital reference) and VSSA (analog reference) belong to one ground; leaving VSSA on a separate net splits the reference."
    citation = "PHIL-MIX-2 (#65 8:54 'tie all VSS and VSSA together')"

    def check(self, model: DesignModel) -> list[Finding]:
        sch = _sch(model)
        if sch is None:
            return []
        vssa = sch.net("VSSA")
        vss = sch.net("VSS") or sch.net("GND")
        if vssa is None or vss is None:
            return []
        if vssa.name.lstrip("/") != vss.name.lstrip("/"):
            return [
                self.make(
                    f"VSSA is on its own net ('{vssa.name}') rather than tied to "
                    f"'{vss.name}'. Tie VSS and VSSA to one ground.",
                    Location(net=vssa.name),
                )
            ]
        return []
