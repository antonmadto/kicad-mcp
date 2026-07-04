from __future__ import annotations

from kicad_mcp.review_engine.report import build_report
from kicad_mcp.review_engine.rules.base import Finding, Location, Severity


def _finding(rule_id, sev):
    return Finding(
        rule_id=rule_id,
        severity=sev,
        title="t",
        message="m",
        rationale="because physics",
        citation="SRC",
        topic="stackup",
        location=Location(net="GND", layer="In1.Cu"),
    )


def test_report_dict_and_counts():
    findings = [
        _finding("HARTLEY-K2", Severity.WARNING),
        _finding("HARTLEY-K1", Severity.ERROR),
    ]
    report = build_report(findings, source="board.kicad_pcb").to_dict()
    assert report["total"] == 2
    assert report["counts"] == {"error": 1, "warning": 1, "info": 0}
    # Errors sort before warnings.
    assert report["findings"][0]["rule_id"] == "HARTLEY-K1"
    assert report["findings"][0]["location"]["net"] == "GND"
    assert "HARTLEY-K1" in report["summary_markdown"]
    assert "because physics" in report["summary_markdown"]


def test_empty_report_is_clean():
    report = build_report([], source="board.kicad_pcb").to_dict()
    assert report["total"] == 0
    assert "No findings" in report["summary_markdown"]
