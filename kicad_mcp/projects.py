"""KiCad project model + discovery/resolution (file layer, Phase 1).

A project is a directory holding ``<name>.kicad_pro`` alongside its
``<name>.kicad_sch`` and ``<name>.kicad_pcb``. Resolution is always confined to
the configured project roots (PLAN.md §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .utils.paths import PathConfinementError, validate_within_roots


@dataclass(frozen=True)
class Project:
    name: str
    directory: Path
    pro: Path | None
    sch: Path | None
    pcb: Path | None

    def describe(self) -> dict:
        return {
            "name": self.name,
            "directory": str(self.directory),
            "pro": str(self.pro) if self.pro else None,
            "schematic": str(self.sch) if self.sch else None,
            "board": str(self.pcb) if self.pcb else None,
            "has_schematic": self.sch is not None and self.sch.exists(),
            "has_board": self.pcb is not None and self.pcb.exists(),
        }

    def require_schematic(self) -> Path:
        if self.sch is None or not self.sch.exists():
            raise FileNotFoundError(f"Project '{self.name}' has no schematic (.kicad_sch).")
        return self.sch

    def require_board(self) -> Path:
        if self.pcb is None or not self.pcb.exists():
            raise FileNotFoundError(f"Project '{self.name}' has no board (.kicad_pcb).")
        return self.pcb


def _project_from_pro(pro: Path) -> Project:
    base = pro.with_suffix("")
    sch = base.with_suffix(".kicad_sch")
    pcb = base.with_suffix(".kicad_pcb")
    return Project(
        name=base.name,
        directory=pro.parent,
        pro=pro,
        sch=sch if sch.exists() else None,
        pcb=pcb if pcb.exists() else None,
    )


def find_projects(roots) -> list[Project]:
    """All projects (``*.kicad_pro``) discoverable under the configured roots."""
    seen: dict[Path, Project] = {}
    for root in roots:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        for pro in sorted(root.rglob("*.kicad_pro")):
            resolved = pro.resolve()
            if resolved not in seen:
                seen[resolved] = _project_from_pro(pro)
    return list(seen.values())


def resolve_project(path: Path | str, roots) -> Project:
    """Resolve a ``.kicad_pro`` path or a project directory to a :class:`Project`.

    Rejects anything outside the configured roots.
    """
    resolved = validate_within_roots(path, roots)
    if resolved.is_dir():
        pros = sorted(resolved.glob("*.kicad_pro"))
        if not pros:
            raise FileNotFoundError(f"No .kicad_pro found in directory: {resolved}")
        if len(pros) > 1:
            raise ValueError(
                f"Multiple projects in {resolved}: {[p.name for p in pros]}. "
                "Pass the specific .kicad_pro path."
            )
        return _project_from_pro(pros[0])
    if resolved.suffix == ".kicad_pro":
        if not resolved.exists():
            raise FileNotFoundError(f"Project file not found: {resolved}")
        return _project_from_pro(resolved)
    # A schematic/board path also identifies its project.
    if resolved.suffix in (".kicad_sch", ".kicad_pcb"):
        pro = resolved.with_suffix(".kicad_pro")
        return _project_from_pro(pro if pro.exists() else resolved.with_suffix(".kicad_pro"))
    raise PathConfinementError(f"Not a KiCad project path: {resolved}")
