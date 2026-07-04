"""Additional guided prompts (PLAN.md §5): plan_stackup, debug_emi, prepare_fab."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.prompt()
    def plan_stackup(layer_count: str = "4") -> str:
        """Interview + recommend a stackup following the Hartley/Phil rules."""
        return (
            f"Help me plan a {layer_count}-layer PCB stackup using the review engine's rules.\n\n"
            "Ask me: rise times / clock frequencies (for set_design_context), target impedances, "
            "and whether there are separate analog domains.\n\n"
            "Then recommend a stackup honoring: every signal layer adjacent to a plane "
            "(HARTLEY-K1); prefer Sig/GND/GND/Sig with poured power over Sig/PWR/GND/Sig "
            "(K2); a tight pwr–gnd pair ≤ 0.2 mm for interplane capacitance (K5); one "
            "continuous ground, partition by placement (G1/G2). Do NOT recommend split "
            "grounds or guard traces."
        )

    @mcp.prompt()
    def debug_emi(symptom: str = "failed radiated emissions") -> str:
        """Hartley-style EMI diagnostic tree."""
        return (
            f"Diagnose this EMI symptom on my board: {symptom}.\n\n"
            "Work the Hartley diagnostic order:\n"
            "1. review_topic(return_path) — any trace crossing a plane gap/split? That is the "
            "#1 cause (20–30 dB). Fix return paths first.\n"
            "2. review_topic(grounding) — is the ground plane continuous? Split grounds and "
            "moats make EMI worse, not better.\n"
            "3. review_topic(decoupling) — 100 nF at every power pin, short/wide connections?\n"
            "4. review_topic(stackup) — tight pwr–gnd cavity? Signals referenced to ground?\n"
            "5. review_topic(crosstalk) — aggressors ≥ 3×H from sensitive nets?\n\n"
            "Remember the anti-myths: 90° corners, guard traces, and via fill are NOT causes."
        )

    @mcp.prompt()
    def prepare_fab(project: str) -> str:
        """Pre-release DFM checklist before generating fab outputs."""
        return (
            f"Run a pre-fabrication check on `{project}` before I order boards.\n\n"
            "1. run_drc — resolve errors.\n"
            "2. review_topic(dfm) — board outline present, sane track widths and via annular "
            "rings, mounting holes.\n"
            "3. review_design — walk any remaining findings.\n"
            "4. export_fab_package — produce gerbers + drill + BOM + CPL, and confirm the file "
            "set is complete.\n\n"
            "Report a go/no-go with the specific blockers."
        )
