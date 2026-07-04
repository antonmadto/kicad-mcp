"""Backend layer: three implementations behind one capability interface.

  * :class:`~kicad_mcp.backends.cli.CliBackend`    — kicad-cli subprocess (headless verify/export)
  * :class:`~kicad_mcp.backends.sexpr.SexprBackend` — S-expression read/write (schematic + files)
  * :class:`~kicad_mcp.backends.ipc.IpcBackend`     — kipy live PCB editing (needs GUI; Phase 3)

Selected by capability at runtime (PLAN.md §3). Designed so a future KiCad 11
headless-IPC backend drops in behind the same interface.
"""

from .base import (
    Backend,
    BackendError,
    BackendNotImplementedError,
    BackendUnavailableError,
    Capability,
)
from .cli import CliBackend, discover_cli_path
from .factory import Backends, create_backends
from .ipc import IpcBackend
from .sexpr import SexprBackend

__all__ = [
    "Backend",
    "BackendError",
    "BackendNotImplementedError",
    "BackendUnavailableError",
    "Capability",
    "CliBackend",
    "discover_cli_path",
    "SexprBackend",
    "IpcBackend",
    "Backends",
    "create_backends",
]
