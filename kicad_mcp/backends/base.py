"""Abstract backend interface and the capability model.

The three backends do very different things, but they share one contract:
*availability* and *capabilities*. The factory (:mod:`kicad_mcp.backends.factory`)
uses this contract to route each tool to a backend that can serve it, and to
degrade gracefully (PLAN.md §3) with actionable errors when none can.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from kicad_mcp.config import Config


class Capability(str, Enum):
    """What a backend can do. Tools request a capability, not a backend."""

    READ_SCHEMATIC = "read_schematic"
    WRITE_SCHEMATIC = "write_schematic"
    READ_BOARD = "read_board"
    EDIT_BOARD = "edit_board"
    VERIFY = "verify"  # ERC / DRC
    EXPORT = "export"  # gerbers, step, bom, renders, fab package


class BackendError(RuntimeError):
    """Base class for backend failures."""


class BackendUnavailableError(BackendError):
    """The backend (or the capability) is not available in this environment."""


class BackendNotImplementedError(BackendError):
    """The backend is available but the feature is not implemented yet.

    Used by the Phase-3 IPC editing surface while it is still a stub.
    """


class Backend(ABC):
    """Common lifecycle + capability contract for all backends."""

    name: ClassVar[str] = "backend"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._available: bool | None = None

    @abstractmethod
    def _detect_available(self) -> bool:
        """Probe (possibly expensive) whether this backend can be used."""

    @abstractmethod
    def _capabilities_when_available(self) -> frozenset[Capability]:
        """Capabilities this backend exposes *when available*."""

    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._detect_available()
        return self._available

    def refresh(self) -> None:
        """Drop the cached availability probe (e.g. after the GUI starts)."""
        self._available = None

    def capabilities(self) -> frozenset[Capability]:
        return self._capabilities_when_available() if self.is_available() else frozenset()

    def describe(self) -> dict:
        return {
            "name": self.name,
            "available": self.is_available(),
            "capabilities": sorted(c.value for c in self.capabilities()),
        }
