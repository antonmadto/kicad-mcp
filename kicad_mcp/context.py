"""Shared application context passed to every tool.

Built once in the server lifespan and threaded through tool registration. Kept
free of any MCP import so it (and everything under it) stays unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .backends.factory import Backends, create_backends
from .config import Config
from .tasks import TaskStore

if TYPE_CHECKING:
    from .review_engine.model import DesignContext


@dataclass
class AppContext:
    config: Config
    backends: Backends
    # Per-board design context (rise times, clocks, ...) set via set_design_context.
    # Keyed by the resolved .kicad_pcb path. Facts a file cannot contain (PLAN.md §6).
    design_contexts: dict[str, DesignContext] = field(default_factory=dict)
    # Background queue for long operations (autoroute, batch export) — PLAN.md §3.
    tasks: TaskStore = field(default_factory=TaskStore)

    @classmethod
    def create(cls, config: Config | None = None) -> AppContext:
        cfg = config if config is not None else Config.from_env()
        return cls(config=cfg, backends=create_backends(cfg))
