"""Project discovery / info / creation tools (file layer, Phase 1)."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext
from kicad_mcp.projects import find_projects
from kicad_mcp.utils.paths import validate_within_roots

from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# A project name is a bare filename stem — no separators, no traversal. This is a
# security boundary: an unsanitized name would let `root / name` escape the roots.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def list_projects_impl(ctx: AppContext) -> list[dict]:
    return [p.describe() for p in find_projects(ctx.config.project_roots)]


def get_project_info_impl(ctx: AppContext, project: str) -> dict:
    return resolve(ctx, project).describe()


def create_project_impl(ctx: AppContext, name: str, directory: str) -> dict:
    """Create a minimal valid project (pro + empty sch + empty 2-layer pcb).

    The new schematic is gated through ``kicad-cli sch erc`` as a validity check.
    """
    if not _SAFE_NAME.match(name):
        raise ValueError(
            f"Invalid project name {name!r}: use letters, digits, '_', '-', '.' "
            "(no path separators or '..')."
        )
    roots = ctx.config.project_roots
    root = validate_within_roots(directory, roots)
    root.mkdir(parents=True, exist_ok=True)
    base = root / name
    pro, sch, pcb = (
        base.with_suffix(".kicad_pro"),
        base.with_suffix(".kicad_sch"),
        base.with_suffix(".kicad_pcb"),
    )
    # Defense in depth: confirm every write target still resolves inside the roots
    # before touching disk, so no crafted name can escape the confinement boundary.
    for target in (pro, sch, pcb):
        validate_within_roots(target, roots)
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {target}")

    pro.write_text(
        json.dumps(
            {
                "meta": {"filename": f"{name}.kicad_pro", "version": 3},
                "sheets": [],
                "text_variables": {},
            },
            indent=2,
        )
        + "\n"
    )
    sch.write_text(_EMPTY_SCH)
    pcb.write_text(_EMPTY_PCB)

    # Validity gate: a fresh, empty schematic must pass ERC with zero violations.
    erc = None
    if ctx.backends.cli.is_available():
        erc = ctx.backends.cli.run_erc(sch)

    info = resolve(ctx, str(pro)).describe()
    info["erc_violations"] = erc["total"] if erc else None
    return info


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def list_projects() -> list[dict]:
        """List KiCad projects discoverable under the configured search paths."""
        return list_projects_impl(ctx)

    @mcp.tool()
    def get_project_info(project: str) -> dict:
        """Info for a project (.kicad_pro path or its directory): associated files."""
        return get_project_info_impl(ctx, project)

    @mcp.tool()
    def create_project(name: str, directory: str) -> dict:
        """Create a new, minimal KiCad project under ``directory`` (within roots)."""
        return create_project_impl(ctx, name, directory)


# --- Minimal templates for create_project ----------------------------------

_EMPTY_SCH = """(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "9.0")
\t(uuid "00000000-0000-4000-8000-000000000001")
\t(paper "A4")
\t(lib_symbols)
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""

_EMPTY_PCB = """(kicad_pcb
\t(version 20241229)
\t(generator "pcbnew")
\t(generator_version "9.0")
\t(general
\t\t(thickness 1.6)
\t\t(legacy_teardrops no)
\t)
\t(paper "A4")
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(25 "Edge.Cuts" user)
\t)
\t(setup
\t\t(pad_to_mask_clearance 0)
\t)
\t(net 0 "")
)
"""
