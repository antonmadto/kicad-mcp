"""S-expression backend — schematic/board file read (and, later, gated writes).

Hard rule (PLAN.md §3): schematic read/write goes through this layer ONLY
(kicad-skip preferred, sexpdata as the low-level engine). There is no schematic
IPC API in KiCad 9/10. Writes are feature-flagged behind
``KICAD_MCP_ALLOW_SCHEMATIC_WRITE`` and refused while the file is open.

Phase 0 provides availability/capability detection. The Phase-1 read methods
(components, nets, stackup) are built on the ``skip`` / ``sexpdata`` imports
detected here.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from .base import Backend, BackendError, Capability

try:  # both are pure-python and light, but keep detection non-fatal.
    import sexpdata  # type: ignore  # noqa: F401
    import skip  # type: ignore  # noqa: F401  (the kicad-skip package imports as `skip`)

    _SEXP_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - import environment dependent
    sexpdata = None  # type: ignore[assignment]
    skip = None  # type: ignore[assignment]
    _SEXP_IMPORT_ERROR = exc


class SexprBackend(Backend):
    name = "sexpr"

    def _detect_available(self) -> bool:
        return sexpdata is not None and skip is not None

    def _capabilities_when_available(self) -> frozenset[Capability]:
        caps = {Capability.READ_SCHEMATIC, Capability.READ_BOARD}
        # Writing additionally requires the experimental feature flag (PLAN.md §7).
        if self.config.allow_schematic_write:
            caps.add(Capability.WRITE_SCHEMATIC)
        return frozenset(caps)

    @staticmethod
    def import_error() -> Exception | None:
        return _SEXP_IMPORT_ERROR

    # --- Phase 5 write layer (EXPERIMENTAL, feature-flagged) ----------------

    def assert_writable(self, sch_path: Path | str) -> Path:
        """Enforce the write safety gate (PLAN.md §7) BEFORE any mutation:
        the feature flag must be on and the file must not be open in KiCad.

        The ``~<name>.lck`` lock file is the authoritative "open in KiCad" signal
        for a *schematic*: eeschema creates it while the sheet is open. (The IPC
        connection reflects the PCB editor, not eeschema, so it is not a reliable
        proxy for a schematic being open.)
        """
        if not self.config.allow_schematic_write:
            raise BackendError(
                "Schematic writes are disabled (experimental). Set "
                "KICAD_MCP_ALLOW_SCHEMATIC_WRITE=1 to enable them."
            )
        path = Path(sch_path)
        lock = path.parent / f"~{path.name}.lck"
        if lock.exists():
            raise BackendError(
                f"Refusing to write '{path.name}': it appears open in KiCad "
                f"(lock file {lock.name} present). Close it first."
            )
        return path

    def edit_schematic(
        self,
        sch_path: Path | str,
        mutate: Callable[[object], None],
        cli_backend=None,
    ) -> dict:
        """Transactional schematic edit with rollback + ERC validity gate.

        1. gate (flag + lock) → 2. load → 3. mutate → 4. write → 5. re-parse
        (rollback from an in-memory backup on failure) → 6. ``kicad-cli sch erc``.
        """
        path = self.assert_writable(sch_path)
        has_cli = cli_backend is not None and cli_backend.is_available()
        # Non-fatal: an ERC invocation problem on the PRE-edit file (crash, no
        # report, malformed JSON) must never block an otherwise-safe edit.
        baseline_errors = None
        if has_cli:
            try:
                baseline_errors = cli_backend.run_erc(path)["counts"]["error"]
            except BackendError:
                baseline_errors = None

        # Atomic swap: build the edited file in a sibling temp, validate it by
        # re-parsing, then os.replace() into place. The original .kicad_sch is
        # NEVER truncated — if mutate/serialize/re-parse fails at any point, the
        # temp is discarded and the original is untouched (no rollback needed).
        tmp = path.with_name(path.name + ".kicad-mcp.tmp")
        try:
            sch = skip.Schematic(str(path))
            mutate(sch)
            sch.write(str(tmp))
            skip.Schematic(str(tmp))  # must parse before it goes live
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise BackendError(f"Edit failed; original left untouched. ({exc})") from exc
        os.replace(str(tmp), str(path))

        # Soft gate (PLAN.md §7): re-run ERC and REPORT it — including the delta
        # vs before the edit — so the caller can see new violations. An in-progress
        # design may legitimately gain floating-pin errors (e.g. a just-added part
        # not yet wired), so this is informational, not an auto-rollback. The write
        # above already committed via os.replace(), so an ERC failure here (CLI
        # crash, no report, malformed JSON) must be reported as informational data,
        # NOT raised — raising here would tell the caller the edit failed when the
        # file on disk was in fact successfully mutated.
        erc = None
        if has_cli:
            try:
                erc = cli_backend.run_erc(path)
                erc = {**erc, "new_errors": erc["counts"].get("error", 0) - (baseline_errors or 0)}
            except BackendError as exc:
                erc = {"error": f"post-edit ERC could not run: {exc}"}
        return {"schematic": str(path), "erc": erc}

    def set_symbol_property(
        self, sch_path: Path | str, reference: str, name: str, value: str, cli_backend=None
    ) -> dict:
        """Set a property (Value, Footprint, ...) on an existing symbol."""

        def mutate(sch):
            sym = _find_symbol(sch, reference)
            try:
                getattr(sym.property, name).value = value
            except Exception as exc:  # unknown property name
                raise BackendError(
                    f"Symbol '{reference}' has no settable property '{name}'."
                ) from exc

        result = self.edit_schematic(sch_path, mutate, cli_backend)
        result.update({"reference": reference, "property": name, "value": value})
        return result

    def duplicate_symbol(
        self,
        sch_path: Path | str,
        reference: str,
        new_reference: str,
        dx_mm: float = 12.7,
        dy_mm: float = 0.0,
        cli_backend=None,
    ) -> dict:
        """Clone an existing placed symbol (fresh UUIDs), re-reference, offset it.

        Cloning an on-sheet symbol is safer than injecting a library definition:
        the lib_symbols cache and pin geometry are already correct.
        """

        def mutate(sch):
            if _symbol_exists(sch, new_reference):
                raise BackendError(f"Reference '{new_reference}' already exists.")
            src = _find_symbol(sch, reference)
            pos = list(getattr(getattr(src, "at", None), "value", []) or [])
            if len(pos) < 2:
                raise BackendError(f"Symbol '{reference}' has no usable position to offset from.")
            clone = src.clone()
            clone.property.Reference.value = new_reference
            clone.move(pos[0] + dx_mm, pos[1] + dy_mm)

        result = self.edit_schematic(sch_path, mutate, cli_backend)
        result.update({"source": reference, "new_reference": new_reference})
        return result

    # --- Phase 1 read layer -------------------------------------------------

    def read_components(self, sch_path: Path | str) -> list[dict]:
        """List schematic symbols with reference, value, lib_id, footprint.

        Uses kicad-skip. Power symbols and graphical-only items are skipped
        (no reference designator). Deterministically sorted by reference.
        """
        sch = skip.Schematic(str(sch_path))
        components: list[dict] = []
        for symbol in sch.symbol:
            comp = {
                "reference": _prop(symbol, "Reference"),
                "value": _prop(symbol, "Value"),
                "lib_id": _lib_id(symbol),
                "footprint": _prop(symbol, "Footprint"),
                "datasheet": _prop(symbol, "Datasheet"),
            }
            if comp["reference"] is None:
                continue
            components.append(comp)
        components.sort(key=lambda c: _natural_ref(c["reference"]))
        return components

    def read_stackup(self, pcb_path: Path | str) -> list[dict]:
        """Ordered physical stackup: dielectric + copper layers with thickness.

        Feeds the Phase-2 stackup rules (adjacency, pwr-gnd cavity). Returns []
        if the board has no stored stackup.
        """
        from kicad_mcp.utils import sexpr as sx

        root = sx.parse_file(pcb_path)
        stackup = sx.find(root, "stackup")
        if stackup is None:
            return []
        layers: list[dict] = []
        for layer in sx.children(stackup, "layer"):
            layers.append(
                {
                    "name": layer[1],
                    "type": sx.first_value(layer, "type"),
                    "thickness_mm": sx.first_value(layer, "thickness"),
                    "material": sx.first_value(layer, "material"),
                    "epsilon_r": sx.first_value(layer, "epsilon_r"),
                    "loss_tangent": sx.first_value(layer, "loss_tangent"),
                }
            )
        return layers

    def read_board_info(self, pcb_path: Path | str) -> dict:
        """Summarize a board: layer table, thickness, nets, footprints, extents."""
        from kicad_mcp.utils import sexpr as sx

        root = sx.parse_file(pcb_path)

        layer_table = sx.find(root, "layers")
        layers: list[dict] = []
        if layer_table is not None:
            for entry in layer_table[1:]:
                # (<ordinal> "F.Cu" signal ["User Name"])
                if isinstance(entry, list) and len(entry) >= 3:
                    layers.append(
                        {
                            "ordinal": sx.sym(entry[0]),
                            "canonical": entry[1],
                            "type": sx.sym(entry[2]),
                        }
                    )
        copper = [ly for ly in layers if ly["type"] in ("signal", "power", "mixed", "jumper")]

        general = sx.find(root, "general")
        thickness = sx.first_value(general, "thickness") if general is not None else None

        # Only the top-level (net <code> "<name>") declarations — NOT the
        # structurally identical (net N "GND") references inside footprint pads,
        # which would otherwise inflate the count once per pad. Direct children only.
        nets = []
        for net in sx.children(root, "net"):
            if len(net) >= 3:
                nets.append({"code": sx.sym(net[1]), "name": net[2]})

        footprints = []
        for fp in sx.find_all(root, "footprint"):
            ref = None
            for prop in sx.children(fp, "property"):
                if len(prop) >= 3 and prop[1] == "Reference":
                    ref = prop[2]
            footprints.append(ref)
        footprints = [r for r in footprints if r]

        return {
            "layer_count": len(copper),
            "copper_layers": [ly["canonical"] for ly in copper],
            "layers": layers,
            "board_thickness_mm": thickness,
            "net_count": len(nets),
            "nets": nets,
            "footprint_count": len(footprints),
            "footprints": sorted(footprints, key=_natural_ref),
            "extents_mm": _edge_extents(root),
        }


def _symbol_exists(sch, reference: str) -> bool:
    return any(_prop(s, "Reference") == reference for s in sch.symbol)


def _find_symbol(sch, reference: str):
    for s in sch.symbol:
        if _prop(s, "Reference") == reference:
            return s
    raise BackendError(f"Symbol '{reference}' not found in the schematic.")


def _prop(symbol, name: str) -> str | None:
    try:
        return getattr(symbol.property, name).value
    except Exception:
        return None


def _lib_id(symbol) -> str | None:
    try:
        return symbol.lib_id.value
    except Exception:
        return None


def _natural_ref(ref: str | None) -> tuple:
    """Sort key so R2 < R10 and letters group together."""
    if not ref:
        return ("", 0)
    prefix = "".join(ch for ch in ref if not ch.isdigit())
    digits = "".join(ch for ch in ref if ch.isdigit())
    return (prefix, int(digits) if digits else 0)


def _edge_extents(root) -> dict | None:
    """Bounding box (mm) of Edge.Cuts geometry (shared impl; handles arcs/circles)."""
    from kicad_mcp.utils import sexpr as sx

    return sx.edge_extents(root)
