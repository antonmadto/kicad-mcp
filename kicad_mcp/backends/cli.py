"""kicad-cli backend: discovery + headless verify/export (PLAN.md §3).

Phase 0 implements discovery + availability + ``version``. Phase 1 adds the typed
ERC/DRC/netlist/BOM/gerber/render wrappers on top of the discovered executable.
All verification and export goes through this backend only — the IPC API cannot
plot or run DRC in KiCad 9.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from kicad_mcp.utils.subprocess import CommandResult, run

from .base import Backend, BackendError, BackendUnavailableError, Capability

if TYPE_CHECKING:
    from kicad_mcp.config import Config

# Per-platform install locations to probe before falling back to PATH (PLAN.md §3).
PLATFORM_DEFAULT_PATHS: dict[str, tuple[Path, ...]] = {
    "darwin": (Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),),
    "win32": (
        Path(r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"),
        Path(r"C:\Program Files\KiCad\bin\kicad-cli.exe"),
    ),
    "linux": (),  # rely on PATH
}

_UNSET = object()


def _platform_key(platform: str) -> str:
    if platform.startswith("win"):
        return "win32"
    if platform.startswith("darwin"):
        return "darwin"
    return "linux"


def discover_cli_path(
    override: Path | str | None,
    *,
    platform: str = sys.platform,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[Path], bool] = lambda p: Path(p).exists(),
) -> Path | None:
    """Locate ``kicad-cli``.

    Order: explicit ``override`` → per-platform default install path → ``PATH``.
    Returns the first candidate that exists. If nothing exists but an override
    was given, the override is returned anyway so error messages can name the
    exact path the user configured. The ``platform``/``which``/``exists`` hooks
    make this deterministically testable across OSes.
    """
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    candidates.extend(PLATFORM_DEFAULT_PATHS.get(_platform_key(platform), ()))
    found = which("kicad-cli") or which("kicad-cli.exe")
    if found:
        candidates.append(Path(found))

    for candidate in candidates:
        if exists(candidate):
            return candidate
    return Path(override) if override else None


class CliBackend(Backend):
    name = "kicad-cli"

    def __init__(self, config: Config, *, path: Path | None | object = _UNSET) -> None:
        super().__init__(config)
        # ``path`` is injectable for tests; by default we discover.
        if path is _UNSET:
            self.path = discover_cli_path(config.cli_path)
        else:
            self.path = path  # type: ignore[assignment]

    def _detect_available(self) -> bool:
        p = self.path
        return bool(p) and Path(p).exists() and os.access(p, os.X_OK)

    def _capabilities_when_available(self) -> frozenset[Capability]:
        return frozenset({Capability.VERIFY, Capability.EXPORT})

    def require_available(self) -> Path:
        if self.is_available() and self.path is not None:
            return Path(self.path)
        searched = (
            ", ".join(str(p) for p in PLATFORM_DEFAULT_PATHS.get(_platform_key(sys.platform), ()))
            or "PATH"
        )
        raise BackendUnavailableError(
            "kicad-cli was not found. Install KiCad 9, or set KICAD_MCP_CLI_PATH "
            f"to the kicad-cli executable. Searched: {searched}."
        )

    def version(self) -> str:
        """Return the kicad-cli version string (e.g. ``9.0.8``)."""
        cli = self.require_available()
        result = run([cli, "version"], timeout=self.config.cli_timeout, check=True)
        return result.stdout.strip()

    def run_cli(self, args: list[str], *, timeout: float | None = None) -> CommandResult:
        """Run ``kicad-cli <args...>``. Foundation for the Phase-1 wrappers."""
        cli = self.require_available()
        return run(
            [cli, *args],
            timeout=self.config.cli_timeout if timeout is None else timeout,
        )

    def _run_checked(self, args: list[str]) -> CommandResult:
        result = self.run_cli(args)
        if not result.ok:
            raise BackendError(
                f"kicad-cli {args[0]} {args[1] if len(args) > 1 else ''} failed "
                f"(exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    # --- Verification (ERC / DRC) ------------------------------------------

    def run_erc(self, sch_path: Path | str) -> dict:
        """Run ERC and return a normalized report (violations flattened)."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "erc.json"
            self._run_checked(
                ["sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(sch_path)]
            )
            if not out.exists():
                raise BackendError("ERC produced no report file")
            data = json.loads(out.read_text(encoding="utf-8"))
        return _normalize_erc(data)

    def run_drc(self, pcb_path: Path | str) -> dict:
        """Run DRC and return a normalized report (violations + unconnected)."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "drc.json"
            self._run_checked(
                ["pcb", "drc", "--format", "json", "--severity-all", "-o", str(out), str(pcb_path)]
            )
            if not out.exists():
                raise BackendError("DRC produced no report file")
            data = json.loads(out.read_text(encoding="utf-8"))
        return _normalize_drc(data)

    # --- Exports ------------------------------------------------------------

    def export_netlist(
        self, sch_path: Path | str, output: Path | str, *, fmt: str = "kicadxml"
    ) -> Path:
        out = Path(output)
        self._run_checked(
            ["sch", "export", "netlist", "--format", fmt, "-o", str(out), str(sch_path)]
        )
        return out

    def export_bom(self, sch_path: Path | str, output: Path | str) -> Path:
        out = Path(output)
        self._run_checked(["sch", "export", "bom", "-o", str(out), str(sch_path)])
        return out

    def export_gerbers(self, pcb_path: Path | str, output_dir: Path | str) -> list[Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        before = set(out_dir.iterdir())
        self._run_checked(["pcb", "export", "gerbers", "-o", f"{out_dir}{os.sep}", str(pcb_path)])
        return sorted(set(out_dir.iterdir()) - before)

    def export_drill(self, pcb_path: Path | str, output_dir: Path | str) -> list[Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        before = set(out_dir.iterdir())
        self._run_checked(["pcb", "export", "drill", "-o", f"{out_dir}{os.sep}", str(pcb_path)])
        return sorted(set(out_dir.iterdir()) - before)

    def export_pos(self, pcb_path: Path | str, output: Path | str, *, fmt: str = "csv") -> Path:
        out = Path(output)
        self._run_checked(
            [
                "pcb",
                "export",
                "pos",
                "--format",
                fmt,
                "--units",
                "mm",
                "-o",
                str(out),
                str(pcb_path),
            ]
        )
        return out

    def export_step(self, pcb_path: Path | str, output: Path | str) -> Path:
        out = Path(output)
        self._run_checked(["pcb", "export", "step", "-o", str(out), str(pcb_path)])
        return out

    def export_svg(
        self,
        pcb_path: Path | str,
        output: Path | str,
        *,
        layers: str = "F.Cu,F.SilkS,Edge.Cuts",
    ) -> Path:
        """2D SVG plot of the given layers (fast; used for the visual loop)."""
        out = Path(output)
        self._run_checked(
            [
                "pcb",
                "export",
                "svg",
                "--layers",
                layers,
                "--page-size-mode",
                "2",
                "-o",
                str(out),
                str(pcb_path),
            ]
        )
        return out

    def render_board(self, pcb_path: Path | str, output: Path | str, *, side: str = "top") -> Path:
        """Raytraced 3D PNG of the board from ``side`` (top/bottom/...)."""
        out = Path(output)
        self._run_checked(["pcb", "render", "--side", side, "-o", str(out), str(pcb_path)])
        return out


def _summarize(violations: list[dict], *, kind: str, data: dict) -> dict:
    counts = {"error": 0, "warning": 0, "exclusion": 0, "info": 0}
    for v in violations:
        sev = v.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return {
        "kind": kind,
        "source": data.get("source"),
        "kicad_version": data.get("kicad_version"),
        "coordinate_units": data.get("coordinate_units"),
        "total": len(violations),
        "counts": counts,
        "violations": violations,
    }


def _normalize_erc(data: dict) -> dict:
    """Flatten ERC's per-sheet violations into one list (schema: sheets[].violations[])."""
    violations: list[dict] = []
    for sheet in data.get("sheets", []):
        sheet_path = sheet.get("path")
        for v in sheet.get("violations", []):
            violations.append(
                {
                    "severity": v.get("severity"),
                    "type": v.get("type"),
                    "description": v.get("description"),
                    "sheet": sheet_path,
                    "items": v.get("items", []),
                }
            )
    return _summarize(violations, kind="erc", data=data)


def _normalize_drc(data: dict) -> dict:
    """Flatten DRC's flat violations plus unconnected_items into one list."""
    violations: list[dict] = []
    for v in data.get("violations", []):
        violations.append(
            {
                "severity": v.get("severity"),
                "type": v.get("type"),
                "description": v.get("description"),
                "items": v.get("items", []),
            }
        )
    for v in data.get("unconnected_items", []):
        violations.append(
            {
                "severity": v.get("severity", "error"),
                "type": v.get("type", "unconnected_items"),
                "description": v.get("description"),
                "items": v.get("items", []),
            }
        )
    report = _summarize(violations, kind="drc", data=data)
    report["schematic_parity_checked"] = bool(data.get("schematic_parity"))
    return report
