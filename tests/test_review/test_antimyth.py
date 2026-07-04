"""Anti-myth guards (HARTLEY-M1..M7): the engine must NEVER fire on these.

Hartley's credibility comes from removing superstition as much as adding rules.
Every rule ID registered is checked against the myth list, and a myth-laden board
is asserted to produce zero findings rooted in those myths.
"""

from __future__ import annotations

from pathlib import Path

from kicad_mcp.review_engine.model import build_model
from kicad_mcp.review_engine.registry import all_rule_classes, run_rules

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"

# Substrings that, if they appeared in a rule's title/message, would indicate the
# engine is nagging about a myth.
_MYTH_TERMS = (
    "90",
    "right angle",
    "right-angle",
    "corner",
    "guard trace",
    "guard-trace",
    "via fill",
    "via-fill",
    "peanut butter",
    "length match",
    "length-match",
    "shield",  # a plane is a reference, not a shield (M7)
)


def test_no_rule_is_a_myth():
    """No registered rule should be about a myth (defensive: catches a future
    rule that regresses the anti-myth stance)."""
    for cls in all_rule_classes():
        text = f"{cls.id} {cls.title} {cls.rationale}".lower()
        # 'length' alone is fine (F2/F4 talk about length in ps); 'length match' is the myth.
        for term in _MYTH_TERMS:
            assert term not in text, f"{cls.id} mentions myth term '{term}': {cls.title}"


def test_ninety_degree_board_has_zero_findings():
    pcb = REVIEW_FIXTURES / "antimyth_2layer" / "antimyth_2layer.kicad_pcb"
    findings = run_rules(build_model(pcb))
    assert findings == [], f"anti-myth board produced findings: {[f.rule_id for f in findings]}"


def test_diff_pair_gap_is_not_flagged():
    """M2: the engine must not enforce a minimum intra-pair gap. The high-speed
    fixture's pair has a 0.4 mm gap; no finding may complain about the gap being
    too wide/tight (only F4 skew-in-time is allowed)."""
    pcb = REVIEW_FIXTURES / "highspeed_4layer" / "highspeed_4layer.kicad_pcb"
    for f in run_rules(build_model(pcb)):
        assert "gap" not in f.message.lower() or "reference plane" in f.message.lower()
