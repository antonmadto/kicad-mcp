"""Backend factory + capability router with graceful degradation (PLAN.md §3).

``create_backends`` instantiates all three backends; :class:`Backends` answers
"who can do X?" and raises actionable errors when nobody can — so analysis and
export keep working headless even when the GUI (IPC) is down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import Backend, BackendUnavailableError, Capability
from .cli import CliBackend
from .ipc import IpcBackend
from .sexpr import SexprBackend

if TYPE_CHECKING:
    from kicad_mcp.config import Config

# Guidance shown when a requested capability has no available provider.
_REMEDIES: dict[Capability, str] = {
    Capability.VERIFY: ("ERC/DRC needs kicad-cli. Install KiCad 9 or set KICAD_MCP_CLI_PATH."),
    Capability.EXPORT: ("Exports need kicad-cli. Install KiCad 9 or set KICAD_MCP_CLI_PATH."),
    Capability.READ_SCHEMATIC: (
        "Schematic reads need the S-expr layer. `pip install sexpdata kicad-skip`."
    ),
    Capability.READ_BOARD: (
        "Board reads need the S-expr layer (`pip install sexpdata kicad-skip`) "
        "or a running KiCad with the IPC API enabled."
    ),
    Capability.WRITE_SCHEMATIC: (
        "Schematic writes are experimental: set KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1 "
        "and ensure the file is closed in KiCad."
    ),
    Capability.EDIT_BOARD: (
        "Live board editing needs a running KiCad 9 with the board open and "
        "Preferences → Plugins → Enable KiCad API (IPC), plus `pip install "
        "kicad-python`. Headless analysis/review/export tools work without it."
    ),
}


@dataclass
class Backends:
    """Container + capability router for the three backends."""

    cli: CliBackend
    sexpr: SexprBackend
    ipc: IpcBackend

    def all(self) -> tuple[Backend, ...]:
        return (self.cli, self.sexpr, self.ipc)

    def available_capabilities(self) -> frozenset[Capability]:
        caps: frozenset[Capability] = frozenset()
        for backend in self.all():
            caps |= backend.capabilities()
        return caps

    def providers(self, capability: Capability) -> list[Backend]:
        return [b for b in self.all() if capability in b.capabilities()]

    def require(self, capability: Capability) -> Backend:
        """Return the first available backend providing ``capability``, else raise."""
        for backend in self.all():
            if capability in backend.capabilities():
                return backend
        remedy = _REMEDIES.get(capability, "")
        raise BackendUnavailableError(
            f"No backend can provide capability '{capability.value}'. {remedy}".strip()
        )

    def summary(self) -> dict:
        """Graceful-degradation view for the diagnostics tool."""
        return {backend.name: backend.describe() for backend in self.all()}

    def refresh(self) -> None:
        for backend in self.all():
            backend.refresh()


def create_backends(config: Config) -> Backends:
    return Backends(
        cli=CliBackend(config),
        sexpr=SexprBackend(config),
        ipc=IpcBackend(config),
    )
