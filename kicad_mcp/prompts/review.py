"""The review_board prompt — a full Hartley/Phil audit walkthrough (PLAN.md §5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext
from kicad_mcp.review_engine.registry import TOPICS

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.prompt()
    def review_board(project: str) -> str:
        """Guided full design review of a KiCad board using the review engine."""
        # Derive the family list from registry.TOPICS so it cannot drift behind the
        # rule engine (guarded by test_review_board_prompt_lists_all_topics).
        return (
            f"Perform a full PCB design review of the KiCad project `{project}` using the "
            "review engine.\n\n"
            "Steps:\n"
            "1. Call `get_board_info` and `get_board_stackup` to understand the board.\n"
            "2. If you know the rise times, clocks, target impedances, or which nets leave the "
            "board on a connector, call `set_design_context` first — it sharpens the review.\n"
            "3. Call `review_design` (or `review_topic` for one family: "
            f"{', '.join(TOPICS)}).\n"
            "4. Walk the findings by severity. For each, state the rule ID, the one-line physics "
            "rationale, the citation, and a concrete fix pointing at the exact spot.\n\n"
            "Honor the anti-myth guards — do NOT raise 90° corners, guard traces beside a plane, "
            "via-fill material, or length matching in millimetres. Hartley's credibility comes "
            "from removing superstition as much as adding rules."
        )
