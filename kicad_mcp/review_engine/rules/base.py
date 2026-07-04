"""Rule anatomy (PLAN.md §6): id, severity, physics rationale, citation, check.

Findings carry a location so Claude can point at the exact footprint/net/spot and
(later) fix it via the editing tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from typing import ClassVar

from ..model import DesignModel


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Location:
    footprint: str | None = None
    net: str | None = None
    layer: str | None = None
    at: dict | None = None  # {"x": .., "y": ..}

    def is_empty(self) -> bool:
        return not (self.footprint or self.net or self.layer or self.at)


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    message: str
    rationale: str
    citation: str
    topic: str
    location: Location | None = None

    def to_dict(self) -> dict:
        d = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "topic": self.topic,
            "title": self.title,
            "message": self.message,
            "rationale": self.rationale,
            "citation": self.citation,
        }
        if self.location and not self.location.is_empty():
            d["location"] = {k: v for k, v in asdict(self.location).items() if v is not None}
        return d


class Rule(ABC):
    """Base class for every rule. Subclasses set the class vars and ``check``."""

    id: ClassVar[str]
    severity: ClassVar[Severity]
    topic: ClassVar[str]  # stackup / grounding / return_path / decoupling / dfm
    title: ClassVar[str]
    rationale: ClassVar[str]  # one-sentence physics
    citation: ClassVar[str]  # rule-catalog id(s) + source

    @abstractmethod
    def check(self, model: DesignModel) -> list[Finding]:
        """Return findings for this rule against the normalized model."""

    def make(self, message: str, location: Location | None = None) -> Finding:
        return Finding(
            rule_id=self.id,
            severity=self.severity,
            title=self.title,
            message=message,
            rationale=self.rationale,
            citation=self.citation,
            topic=self.topic,
            location=location,
        )
