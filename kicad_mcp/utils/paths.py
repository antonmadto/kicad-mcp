"""Path-confinement helpers.

Security rule (PLAN.md §3): file access is confined to configured project roots.
No arbitrary reads/writes outside them. Everything here is stdlib-only and pure.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class PathConfinementError(ValueError):
    """Raised when a path resolves outside all permitted project roots."""


def _resolve(path: Path | str) -> Path:
    # strict=False: works for not-yet-created paths (e.g. export targets).
    return Path(path).expanduser().resolve(strict=False)


def is_within_roots(path: Path | str, roots: Iterable[Path | str]) -> bool:
    resolved = _resolve(path)
    for root in roots:
        r = _resolve(root)
        if resolved == r or resolved.is_relative_to(r):
            return True
    return False


def validate_within_roots(path: Path | str, roots: Iterable[Path | str]) -> Path:
    """Return the resolved path if it is inside one of ``roots``; else raise.

    Symlinks are resolved before the check, so a symlink inside a root that
    points outside it is rejected.
    """
    roots = list(roots)
    resolved = _resolve(path)
    for root in roots:
        r = _resolve(root)
        if resolved == r or resolved.is_relative_to(r):
            return resolved
    allowed = ", ".join(str(_resolve(r)) for r in roots) or "(none configured)"
    raise PathConfinementError(
        f"Path {resolved} is outside the permitted project roots. "
        f"Allowed roots: {allowed}. Set KICAD_MCP_SEARCH_PATHS to widen access."
    )
