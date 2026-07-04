"""Turn findings into a structured report + a markdown summary (PLAN.md §6)."""

from __future__ import annotations

from dataclasses import dataclass

from .rules.base import Finding, Severity

_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


@dataclass
class Report:
    findings: list[Finding]
    source: str
    topic: str | None = None

    def counts(self) -> dict:
        counts = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.rule_id),
        )

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "topic": self.topic or "all",
            "total": len(self.findings),
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.sorted_findings()],
            "summary_markdown": self.to_markdown(),
        }

    def to_markdown(self) -> str:
        counts = self.counts()
        scope = f" ({self.topic})" if self.topic else ""
        lines = [
            f"# Design review{scope}",
            "",
            f"**{counts['error']} errors · {counts['warning']} warnings · {counts['info']} info**",
            "",
        ]
        if not self.findings:
            lines.append("No findings. ✅")
            return "\n".join(lines)

        icon = {Severity.ERROR: "🔴", Severity.WARNING: "🟡", Severity.INFO: "🔵"}
        for f in self.sorted_findings():
            loc = ""
            if f.location and not f.location.is_empty():
                bits = []
                if f.location.footprint:
                    bits.append(f.location.footprint)
                if f.location.net:
                    bits.append(f"net {f.location.net}")
                if f.location.layer:
                    bits.append(f.location.layer)
                if f.location.at:
                    bits.append(f"@({f.location.at.get('x')}, {f.location.at.get('y')})")
                loc = f" — _{', '.join(bits)}_"
            lines.append(f"### {icon[f.severity]} `{f.rule_id}` {f.title}{loc}")
            lines.append(f"{f.message}")
            lines.append(f"*Why:* {f.rationale}")
            lines.append(f"*Source:* {f.citation}")
            lines.append("")
        return "\n".join(lines)


def build_report(findings: list[Finding], *, source: str, topic: str | None = None) -> Report:
    return Report(findings=findings, source=source, topic=topic)
