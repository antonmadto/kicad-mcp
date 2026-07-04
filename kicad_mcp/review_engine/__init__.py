"""The review engine — the project's differentiator (PLAN.md §6).

A rule engine that audits a *normalized design model* (never raw files) against
the codified Hartley and Phil's Lab catalogs in ``docs/rules/``. Every rule
carries an id, severity, one-line physics rationale, and a citation; every
finding carries a location.

Phase 2 (v1) implements the highest-value, most machine-checkable families:
stackup, return path, grounding, decoupling proximity, and DFM. Transmission
line / crosstalk / SMPS / subcircuit rules and the explicit anti-myth guards
arrive in Phase 4 — but v1 already must NOT emit myth findings (no 90° corner
warnings, no guard-trace nags).
"""
