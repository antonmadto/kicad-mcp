"""Rule registry + runner (PLAN.md §6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .model import DesignModel

if TYPE_CHECKING:
    # Imported lazily at runtime (via _ensure_loaded) to avoid a circular import:
    # rule modules import `register` from here.
    from .rules.base import Finding, Rule

_REGISTRY: list[type[Rule]] = []
_LOADED = False

# The rule families that reviews are grouped/filtered by.
TOPICS = (
    "stackup",
    "grounding",
    "return_path",
    "decoupling",
    "dfm",
    "transmission",
    "crosstalk",
    "smps",
    "subcircuits",
    "connectors",
)


def register(cls: type[Rule]) -> type[Rule]:
    """Class decorator: add a rule to the registry."""
    _REGISTRY.append(cls)
    return cls


def _ensure_loaded() -> None:
    global _LOADED
    if not _LOADED:
        # Importing the package registers every family's rules.
        import kicad_mcp.review_engine.rules  # noqa: F401

        _LOADED = True


def all_rule_classes() -> list[type[Rule]]:
    _ensure_loaded()
    return list(_REGISTRY)


def all_rules(topic: str | None = None) -> list[Rule]:
    classes = all_rule_classes()
    if topic is not None:
        classes = [c for c in classes if c.topic == topic]
    return [c() for c in classes]


def run_rules(model: DesignModel, topic: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for rule in all_rules(topic):
        findings.extend(rule.check(model))
    return findings
