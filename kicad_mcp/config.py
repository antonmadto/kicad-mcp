"""Configuration for kicad-mcp, sourced from ``KICAD_MCP_*`` environment variables.

All configuration is namespaced ``KICAD_MCP_*`` (PLAN.md §3). This module is pure
(stdlib only) so it can be tested without KiCad, MCP, or any backend installed.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

# --- Environment variable names (single source of truth) --------------------

ENV_SEARCH_PATHS = "KICAD_MCP_SEARCH_PATHS"
ENV_CLI_PATH = "KICAD_MCP_CLI_PATH"
ENV_FREEROUTING_JAR = "KICAD_MCP_FREEROUTING_JAR"
ENV_ALLOW_SCHEMATIC_WRITE = "KICAD_MCP_ALLOW_SCHEMATIC_WRITE"
ENV_CLI_TIMEOUT = "KICAD_MCP_CLI_TIMEOUT"
ENV_IPC_TIMEOUT = "KICAD_MCP_IPC_TIMEOUT"

DEFAULT_CLI_TIMEOUT = 120.0
DEFAULT_IPC_TIMEOUT = 10.0

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off", ""}


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return default


def _parse_float(value: str | None, *, default: float, positive: bool = False) -> float:
    if value is None:
        return default
    try:
        result = float(value.strip())
    except (ValueError, AttributeError):
        return default
    # nan/inf silently defeat subprocess.run(timeout=...) (nan never expires;
    # inf overflows int() in the IPC millisecond conversion), and a non-positive
    # timeout fires TimeoutExpired instantly — all fall back to the safe default.
    if not math.isfinite(result):
        return default
    if positive and result <= 0:
        return default
    return result


def _parse_paths(value: str | None) -> tuple[Path, ...]:
    if not value:
        return ()
    parts = [p.strip() for p in value.split(os.pathsep)]
    return tuple(Path(p).expanduser() for p in parts if p)


def _parse_optional_path(value: str | None) -> Path | None:
    if not value or not value.strip():
        return None
    return Path(value.strip()).expanduser()


def _default_search_paths() -> tuple[Path, ...]:
    """Sensible default project roots when the user has not configured any.

    Kept purely computational (no filesystem probing) so ``from_env`` is
    deterministic and test-friendly; non-existent roots simply never match
    during path-confinement checks.
    """
    home = Path.home()
    return (home / "Documents" / "KiCad", home / "KiCad")


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration.

    ``project_roots`` is the confinement boundary for all path validation: the
    server refuses to read or write outside these directories (PLAN.md §3).
    """

    search_paths: tuple[Path, ...] = field(default_factory=_default_search_paths)
    cli_path: Path | None = None
    freerouting_jar: Path | None = None
    allow_schematic_write: bool = False
    cli_timeout: float = DEFAULT_CLI_TIMEOUT
    ipc_timeout: float = DEFAULT_IPC_TIMEOUT

    @property
    def project_roots(self) -> tuple[Path, ...]:
        """Directories within which file access is permitted."""
        return self.search_paths

    @classmethod
    def from_env(cls, environ: os._Environ[str] | dict[str, str] | None = None) -> Config:
        env = os.environ if environ is None else environ
        search = _parse_paths(env.get(ENV_SEARCH_PATHS))
        return cls(
            search_paths=search if search else _default_search_paths(),
            cli_path=_parse_optional_path(env.get(ENV_CLI_PATH)),
            freerouting_jar=_parse_optional_path(env.get(ENV_FREEROUTING_JAR)),
            allow_schematic_write=_parse_bool(env.get(ENV_ALLOW_SCHEMATIC_WRITE)),
            cli_timeout=_parse_float(
                env.get(ENV_CLI_TIMEOUT), default=DEFAULT_CLI_TIMEOUT, positive=True
            ),
            ipc_timeout=_parse_float(
                env.get(ENV_IPC_TIMEOUT), default=DEFAULT_IPC_TIMEOUT, positive=True
            ),
        )

    def describe(self) -> dict:
        """Redaction-free, JSON-serializable view for diagnostics tools."""
        return {
            "search_paths": [str(p) for p in self.search_paths],
            "cli_path": str(self.cli_path) if self.cli_path else None,
            "freerouting_jar": str(self.freerouting_jar) if self.freerouting_jar else None,
            "allow_schematic_write": self.allow_schematic_write,
            "cli_timeout": self.cli_timeout,
            "ipc_timeout": self.ipc_timeout,
        }
