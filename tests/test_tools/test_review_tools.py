"""Review tools through the resolution/project layer (run everywhere)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from kicad_mcp.config import Config
from kicad_mcp.context import AppContext
from kicad_mcp.review_engine.registry import TOPICS
from kicad_mcp.tools import review

REVIEW_FIXTURES = Path(__file__).parent.parent / "fixtures" / "review"


@pytest.fixture
def review_ctx():
    return AppContext.create(Config.from_env({"KICAD_MCP_SEARCH_PATHS": str(REVIEW_FIXTURES)}))


def _pro(name: str) -> str:
    return str(REVIEW_FIXTURES / name / f"{name}.kicad_pro")


def test_review_design_clean(review_ctx):
    report = review.review_design_impl(review_ctx, _pro("clean_4layer"))
    assert report["total"] == 0
    assert "No findings" in report["summary_markdown"]


def test_review_design_faults(review_ctx):
    report = review.review_design_impl(review_ctx, _pro("faults_4layer"))
    ids = {f["rule_id"] for f in report["findings"]}
    assert "HARTLEY-K2" in ids
    assert report["counts"]["warning"] >= 1
    # Every finding is fully cited (the trust contract).
    for f in report["findings"]:
        assert f["rationale"] and f["citation"] and f["rule_id"]


def test_review_topic_filters_family(review_ctx):
    grounding = review.review_topic_impl(review_ctx, _pro("split_ground_4layer"), "grounding")
    ids = {f["rule_id"] for f in grounding["findings"]}
    assert "HARTLEY-G1" in ids  # grounding family
    assert "HARTLEY-R5" not in ids  # R5 is the return_path family


def test_review_topic_rejects_unknown(review_ctx):
    with pytest.raises(ValueError, match="Unknown topic"):
        review.review_topic_impl(review_ctx, _pro("clean_4layer"), "nonsense")


def test_set_design_context_roundtrip(review_ctx):
    result = review.set_design_context_impl(
        review_ctx, _pro("clean_4layer"), rise_time_ns=1.0, connector_nets=["USB_DP", "USB_DM"]
    )
    assert result["context"]["rise_time_ns"] == 1.0
    # f_knee = 0.5 / t_rise → 500 MHz for 1 ns.
    assert result["context"]["f_knee_hz"] == pytest.approx(0.5e9)
    assert result["context"]["connector_nets"] == ["USB_DP", "USB_DM"]
    # Context persists and the review still runs clean.
    assert review.review_design_impl(review_ctx, _pro("clean_4layer"))["total"] == 0


def test_set_design_context_rejects_zero_rise_time(review_ctx):
    # rise_time_ns=0 would otherwise reach f_knee_hz = 0.5 / (0 * 1e-9) and
    # crash with an opaque ZeroDivisionError instead of an actionable error.
    with pytest.raises(ValueError, match="positive"):
        review.set_design_context_impl(review_ctx, _pro("clean_4layer"), rise_time_ns=0)


def test_set_design_context_rejects_negative_rise_time(review_ctx):
    # A negative rise time silently flips f_knee_hz (and HARTLEY-F2's critical
    # length) negative, flooding every routed net with false positives.
    with pytest.raises(ValueError, match="positive"):
        review.set_design_context_impl(review_ctx, _pro("clean_4layer"), rise_time_ns=-1.0)


def test_review_topic_docstring_lists_all_topics():
    # The docstring is the LLM client's primary source of truth for what's
    # callable; it must never drift behind review_engine.registry.TOPICS
    # (Phase 4 grew that tuple from 5 to 10 families without this update).
    from kicad_mcp.server import create_server

    srv = create_server()

    async def go():
        return await srv.list_tools()

    tools = asyncio.run(go())
    (review_topic_tool,) = [t for t in tools if t.name == "review_topic"]
    description = review_topic_tool.description or ""
    missing = [topic for topic in TOPICS if topic not in description]
    assert not missing, f"review_topic docstring is missing topics: {missing}"
