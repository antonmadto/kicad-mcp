"""Freerouting autorouter integration (Phase 6, PLAN.md §5).

Pipeline: export a Specctra DSN → run the Freerouting JAR headlessly → import the
resulting SES back into the board. Gated on ``KICAD_MCP_FREEROUTING_JAR`` and a
JRE on PATH.

Important KiCad-9 limitation: ``kicad-cli`` in KiCad 9 cannot export Specctra DSN
(only the GUI/plugin can), so a ``.dsn`` must be provided (exported from the GUI)
until the IPC/CLI gains DSN export. This module runs Freerouting on a supplied
DSN and returns the SES; it degrades with an actionable error otherwise.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from kicad_mcp.utils.subprocess import run

from .base import BackendError


def _java() -> str | None:
    return shutil.which("java")


def freerouting_available(jar_path: Path | str | None) -> bool:
    return bool(jar_path) and Path(jar_path).exists() and _java() is not None


def route_dsn(
    dsn_path: Path | str,
    jar_path: Path | str | None,
    output_ses: Path | str | None = None,
    *,
    timeout: float = 1800.0,
    max_passes: int = 10,
) -> dict:
    """Run Freerouting on a Specctra ``.dsn`` and produce a ``.ses`` session file."""
    dsn = Path(dsn_path)
    if not dsn.exists():
        raise BackendError(f"DSN file not found: {dsn}")
    if not jar_path or not Path(jar_path).exists():
        raise BackendError(
            "Freerouting is not configured. Set KICAD_MCP_FREEROUTING_JAR to the "
            "freerouting.jar path (see github.com/freerouting/freerouting)."
        )
    java = _java()
    if java is None:
        raise BackendError("Autorouting needs a Java runtime ('java') on PATH.")

    ses = Path(output_ses) if output_ses else dsn.with_suffix(".ses")
    # Remove any pre-existing target so we never report success on a stale file.
    ses.unlink(missing_ok=True)
    result = run(
        [
            java,
            "-jar",
            str(jar_path),
            "-de",
            str(dsn),
            "-do",
            str(ses),
            "-mp",
            str(max_passes),
        ],
        timeout=timeout,
    )
    if result.returncode != 0 or not ses.exists():
        raise BackendError(
            f"Freerouting failed (exit {result.returncode}); no session file produced. "
            f"stderr: {result.stderr.strip()[:400]}"
        )
    return {"ses": str(ses), "dsn": str(dsn), "passes": max_passes}
