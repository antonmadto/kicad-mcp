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


def test_report_caps_per_rule_but_keeps_exact_counts():
    # A rule that fires 50 times must not serialize 50 findings (unusable on real
    # boards): to_dict caps at 20 and records the 30 omitted, while total/counts stay
    # exact; to_markdown collapses the tail to one elision line.
    findings = [_finding("HARTLEY-R5", Severity.WARNING) for _ in range(50)]
    report = build_report(findings, source="board.kicad_pcb")
    d = report.to_dict()
    assert d["total"] == 50
    assert d["counts"]["warning"] == 50
    assert len(d["findings"]) == 20
    assert d["omitted_findings"] == {"HARTLEY-R5": 30}
    assert "and 45 more" in d["summary_markdown"]
