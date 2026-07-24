"""IPC backend (kipy) — live PCB editing (Phase 3).

Hard rules (PLAN.md §3):
- PCB mutation goes through this backend ONLY. Never write ``.kicad_pcb`` while
  KiCad runs.
- Every multi-item mutation is wrapped in ``begin_commit()``/``push_commit()``
  so it lands as a single undo step in the GUI.
- When the GUI is down, tools get an actionable error (graceful degradation).

All public methods take millimetres and degrees; conversion to KiCad's
nanometre/decidegree internals happens here and only here.
"""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from .base import Backend, BackendError, BackendUnavailableError, Capability

if TYPE_CHECKING:
    from collections.abc import Iterator

try:  # kipy is an optional heavy dependency; detection must not hard-fail without it.
    import kipy  # type: ignore
    import kipy.board_types as _bt  # type: ignore
    import kipy.errors as _kerr  # type: ignore
    from kipy.geometry import PolygonWithHoles, PolyLineNode, Vector2  # type: ignore
    from kipy.util.units import from_mm, to_mm  # type: ignore

    _KIPY_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - import environment dependent
    kipy = None  # type: ignore[assignment]
    _bt = None  # type: ignore[assignment]
    _kerr = None  # type: ignore[assignment]
    _KIPY_IMPORT_ERROR = exc

_GUI_HELP = (
    "No running KiCad with the IPC API was found. Start KiCad 9, open the board, "
    "and enable Preferences → Plugins → Enable KiCad API. Headless analysis, "
    "review, and export tools keep working without it."
)


def _safe_mm(value) -> float | None:
    """to_mm(value) as a float, or None for an unset/zero constraint."""
    try:
        mm = to_mm(value)
    except Exception:
        return None
    return mm if mm else None


def layer_id(name: str) -> int:
    """Map a canonical layer name ('F.Cu', 'In1.Cu', 'B.Cu') to the IPC enum."""
    if _bt is None:  # pragma: no cover
        raise BackendUnavailableError("kicad-python (kipy) is not installed.")
    enum_name = "BL_" + name.replace(".", "_")
    try:
        return _bt.BoardLayer.Value(enum_name)
    except ValueError as exc:
        raise BackendError(
            f"Unknown board layer '{name}'. Use canonical names like F.Cu, In1.Cu, B.Cu."
        ) from exc


class IpcBackend(Backend):
    name = "kicad-ipc"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._kicad: Any = None

    # --- Connection management ----------------------------------------------

    def _detect_available(self) -> bool:
        if kipy is None:
            return False
        try:
            self._connect()
            return True
        except Exception:
            return False

    def _connect(self) -> Any:
        """Return a live KiCad client, creating (and version-checking) it lazily.

        Every KiCad process serves its own socket (``api.sock`` for the first,
        ``api-<pid>.sock`` for others — e.g. a standalone PCB editor). We probe
        all of them and prefer a connection that actually has a board open, so
        editing works no matter which window came up first.
        """
        if kipy is None:
            raise BackendUnavailableError(
                f"kicad-python (kipy) is not installed: {_KIPY_IMPORT_ERROR}. "
                "Run `pip install kicad-python==0.7.1`."
            )
        if self._kicad is not None:
            try:
                self._kicad.ping()
                return self._kicad
            except Exception:
                self._kicad = None  # stale socket — reconnect

        timeout_ms = int(self.config.ipc_timeout * 1000)
        fallback = None
        last_error: Exception | None = None
        for socket_path in self._candidate_sockets():
            try:
                client = kipy.KiCad(socket_path=socket_path, timeout_ms=timeout_ms)
                client.ping()
            except Exception as exc:  # dead/stale socket — try the next
                last_error = exc
                continue
            if self._has_open_board(client):
                self._kicad = client
                return client
            if fallback is None:
                fallback = client
        if fallback is not None:
            self._kicad = fallback
            return fallback
        raise BackendUnavailableError(_GUI_HELP) from last_error

    @staticmethod
    def _candidate_sockets() -> list[str | None]:
        """Socket paths to probe: env/default first, then per-PID sockets."""
        import glob
        import os

        candidates: list[str | None] = [None]  # kipy default (env var or api.sock)
        # KiCad puts sockets in /tmp/kicad on macOS/Linux, which is NOT what
        # tempfile.gettempdir() returns on macOS ($TMPDIR) — probe both.
        sock_dirs = {"/tmp/kicad", os.path.join(tempfile.gettempdir(), "kicad")}  # noqa: S108
        pid_socks: list[str] = []
        for sock_dir in sock_dirs:
            if os.path.isdir(sock_dir):
                pid_socks.extend(glob.glob(os.path.join(sock_dir, "api-*.sock")))
        pid_socks.sort(key=os.path.getmtime, reverse=True)
        candidates.extend("ipc://" + p for p in pid_socks)
        return candidates

    @staticmethod
    def _has_open_board(client: Any) -> bool:
        try:
            client.get_board()
            return True
        except Exception:
            return False

    def refresh(self) -> None:
        super().refresh()
        self._kicad = None

    def _capabilities_when_available(self) -> frozenset[Capability]:
        return frozenset({Capability.READ_BOARD, Capability.EDIT_BOARD})

    @staticmethod
    def import_error() -> Exception | None:
        """The ImportError if kipy could not be imported, else None."""
        return _KIPY_IMPORT_ERROR

    def get_version(self) -> str:
        kicad = self._connect()
        return str(kicad.get_version())

    def get_board(self) -> Any:
        """The board open in the running KiCad (raises with guidance if none)."""
        kicad = self._connect()
        try:
            return kicad.get_board()
        except Exception as exc:
            raise BackendError(
                "Connected to KiCad, but no board is open in the PCB editor. "
                "Open the .kicad_pcb in KiCad first."
            ) from exc

    @contextmanager
    def commit(self, message: str) -> Iterator[Any]:
        """Single-undo-step mutation scope: begin → yield board → push.

        On any exception the commit is dropped, leaving the board untouched.
        """
        board = self.get_board()
        commit = board.begin_commit()
        try:
            yield board
        except Exception:
            try:
                board.drop_commit(commit)
            except Exception:  # noqa: S110 - best-effort rollback, original error matters more
                pass
            raise
        board.push_commit(commit, message)

    # --- Reads ----------------------------------------------------------------

    def board_status(self) -> dict:
        board = self.get_board()
        fps = board.get_footprints()
        nets = board.get_nets()
        return {
            "board": board.name,
            "kicad_version": self.get_version(),
            "copper_layers": board.get_copper_layer_count(),
            "footprints": len(fps),
            "nets": len(nets),
            "tracks": len(board.get_tracks()),
            "vias": len(board.get_vias()),
            "zones": len(board.get_zones()),
        }

    def list_footprints(self) -> list[dict]:
        board = self.get_board()
        out = []
        for fp in board.get_footprints():
            out.append(
                {
                    "reference": fp.reference_field.text.value,
                    "value": fp.value_field.text.value,
                    "x_mm": to_mm(fp.position.x),
                    "y_mm": to_mm(fp.position.y),
                    "rotation_deg": fp.orientation.degrees,
                    "layer": self._layer_name(board, fp.layer),
                }
            )
        return out

    def _layer_name(self, board, layer: int) -> str:
        try:
            return board.get_layer_name(layer)
        except Exception:
            return str(layer)

    def _find_footprint(self, board, reference: str):
        for fp in board.get_footprints():
            if fp.reference_field.text.value == reference:
                return fp
        raise BackendError(
            f"Footprint '{reference}' not found on the open board. "
            "Use list_footprints to see available references."
        )

    def _net_by_name(self, board, net_name: str | None):
        if not net_name:
            return None
        for net in board.get_nets():
            if net.name == net_name:
                return net
        raise BackendError(f"Net '{net_name}' not found on the open board.")

    # --- Footprint edits --------------------------------------------------------

    def move_footprint(self, reference: str, x_mm: float, y_mm: float) -> dict:
        with self.commit(f"kicad-mcp: move {reference}") as board:
            fp = self._find_footprint(board, reference)
            fp.position = Vector2.from_xy_mm(x_mm, y_mm)
            board.update_items(fp)
        return {"reference": reference, "x_mm": x_mm, "y_mm": y_mm}

    def rotate_footprint(self, reference: str, degrees: float) -> dict:
        with self.commit(f"kicad-mcp: rotate {reference}") as board:
            fp = self._find_footprint(board, reference)
            # ``orientation`` returns a copy — mutate it, then assign through the
            # setter (which also rotates pads/fields/child items around the origin).
            angle = fp.orientation
            angle.degrees = degrees
            fp.orientation = angle
            board.update_items(fp)
        return {"reference": reference, "rotation_deg": degrees}

    def duplicate_footprint(
        self,
        reference: str,
        new_reference: str,
        x_mm: float | None = None,
        y_mm: float | None = None,
        dx_mm: float = 5.0,
        dy_mm: float = 0.0,
    ) -> dict:
        """Copy an existing placed footprint to a new reference + position.

        KiCad 9's IPC API cannot instantiate a footprint from a *library*, so the
        supported "add a part" operation is to clone one already on the board
        (same footprint, fresh identity). Pads keep their nets from the source —
        reassign them via routing/DRC as needed.
        """
        with self.commit(f"kicad-mcp: duplicate {reference} -> {new_reference}") as board:
            if any(fp.reference_field.text.value == new_reference for fp in board.get_footprints()):
                raise BackendError(f"Reference '{new_reference}' already exists on the board.")
            src = self._find_footprint(board, reference)
            new = _bt.FootprintInstance()
            new.proto.CopyFrom(src.proto)
            new.proto.ClearField("id")  # let KiCad assign a fresh KIID
            new.reference_field.text.value = new_reference
            if x_mm is not None and y_mm is not None:
                new.position = Vector2.from_xy_mm(x_mm, y_mm)
            else:
                new.position = Vector2.from_xy_mm(
                    to_mm(src.position.x) + dx_mm, to_mm(src.position.y) + dy_mm
                )
            board.create_items(new)
        return {"source": reference, "new_reference": new_reference}

    def get_netclasses(self) -> list[dict]:
        """Read netclass assignments + key constraints for the live board."""
        board = self.get_board()
        nets = board.get_nets()
        by_class: dict[str, dict] = {}
        for net_name, nc in board.get_netclass_for_nets(nets).items():
            entry = by_class.setdefault(
                nc.name,
                {
                    "name": nc.name,
                    "track_width_mm": _safe_mm(nc.track_width),
                    "clearance_mm": _safe_mm(nc.clearance),
                    "via_diameter_mm": _safe_mm(nc.via_diameter),
                    "via_drill_mm": _safe_mm(nc.via_drill),
                    "diff_pair_track_width_mm": _safe_mm(nc.diff_pair_track_width),
                    "diff_pair_gap_mm": _safe_mm(nc.diff_pair_gap),
                    "nets": [],
                },
            )
            entry["nets"].append(net_name)
        return sorted(by_class.values(), key=lambda c: c["name"])

    # --- Routing -----------------------------------------------------------------

    def route_trace(
        self,
        points_mm: list[tuple[float, float]],
        width_mm: float,
        layer: str,
        net_name: str | None = None,
    ) -> dict:
        """Route a polyline as track segments (one commit → one undo step)."""
        if len(points_mm) < 2:
            raise BackendError("route_trace needs at least 2 points.")
        if width_mm <= 0:
            raise BackendError("Track width must be positive (mm).")
        lid = layer_id(layer)
        with self.commit("kicad-mcp: route trace") as board:
            net = self._net_by_name(board, net_name)
            tracks = []
            for a, b in zip(points_mm, points_mm[1:], strict=False):
                t = _bt.Track()
                t.start = Vector2.from_xy_mm(a[0], a[1])
                t.end = Vector2.from_xy_mm(b[0], b[1])
                t.width = from_mm(width_mm)
                t.layer = lid
                if net is not None:
                    t.net = net
                tracks.append(t)
            created = board.create_items(tracks)
        return {"segments": len(created), "layer": layer, "width_mm": width_mm, "net": net_name}

    def add_via(
        self,
        x_mm: float,
        y_mm: float,
        size_mm: float = 0.7,
        drill_mm: float = 0.3,
        net_name: str | None = None,
    ) -> dict:
        if drill_mm >= size_mm:
            raise BackendError("Via drill must be smaller than via size.")
        with self.commit("kicad-mcp: add via") as board:
            net = self._net_by_name(board, net_name)
            v = _bt.Via()
            v.position = Vector2.from_xy_mm(x_mm, y_mm)
            v.diameter = from_mm(size_mm)
            v.drill_diameter = from_mm(drill_mm)
            if net is not None:
                v.net = net
            board.create_items(v)
        return {
            "x_mm": x_mm,
            "y_mm": y_mm,
            "size_mm": size_mm,
            "drill_mm": drill_mm,
            "net": net_name,
        }

    def route_differential_pair(
        self,
        points_mm: list[tuple[float, float]],
        width_mm: float,
        gap_mm: float,
        layer: str,
        net_p: str,
        net_n: str,
    ) -> dict:
        """Route P and N as parallel polylines offset ±(width+gap)/2 (one commit)."""
        from kicad_mcp.review_engine.geometry import offset_polyline

        if len(points_mm) < 2:
            raise BackendError("route_differential_pair needs at least 2 points.")
        half = (width_mm + gap_mm) / 2.0
        path_p = offset_polyline(points_mm, +half)
        path_n = offset_polyline(points_mm, -half)
        lid = layer_id(layer)
        with self.commit("kicad-mcp: route differential pair") as board:
            net_p_obj = self._net_by_name(board, net_p)
            net_n_obj = self._net_by_name(board, net_n)
            tracks = []
            for path, net in ((path_p, net_p_obj), (path_n, net_n_obj)):
                for a, b in zip(path, path[1:], strict=False):
                    t = _bt.Track()
                    t.start = Vector2.from_xy_mm(a[0], a[1])
                    t.end = Vector2.from_xy_mm(b[0], b[1])
                    t.width = from_mm(width_mm)
                    t.layer = lid
                    t.net = net
                    tracks.append(t)
            created = board.create_items(tracks)
        return {
            "segments": len(created),
            "layer": layer,
            "width_mm": width_mm,
            "gap_mm": gap_mm,
            "nets": [net_p, net_n],
        }

    # --- Rip up (delete routing) -----------------------------------------------------

    def rip_up_nets(self, net_names: list[str]) -> dict:
        """Delete every track segment and via on the given nets — a "rip up".

        Only tracks/vias are removed; pads and zones are left intact. Runs as a
        single commit (one GUI undo step); any error rolls the whole thing back.
        Unknown net names raise ``BackendError`` listing them, before anything is
        removed. Uses ``get_tracks()``/``get_vias()`` (KiCad 9-compatible), NOT
        ``get_items_by_net`` (kipy 0.7 / KiCad 10.0.1+ only).
        """
        requested = list(dict.fromkeys(net_names))  # de-dup, keep order
        if not requested:
            raise BackendError("rip_up_nets needs at least one net name.")
        removed_tracks = removed_vias = 0
        with self.commit("kicad-mcp: rip up " + ", ".join(requested)) as board:
            known = {n.name for n in board.get_nets()}
            missing = [n for n in requested if n not in known]
            if missing:
                raise BackendError(
                    "Net(s) not found on the open board: "
                    + ", ".join(sorted(missing))
                    + ". Use get_netclasses to see available net names."
                )
            targets = set(requested)
            tracks = [t for t in board.get_tracks() if t.net.name in targets]
            vias = [v for v in board.get_vias() if v.net.name in targets]
            removed_tracks, removed_vias = len(tracks), len(vias)
            victims = tracks + vias
            if victims:  # avoid a no-op remove_items([]) round-trip
                board.remove_items(victims)
        return {
            "nets": sorted(requested),
            "removed_tracks": removed_tracks,
            "removed_vias": removed_vias,
        }

    @staticmethod
    def _net_fanout(board) -> dict[str, int]:
        """net name → number of distinct footprints with a pad on that net.

        Used to spot "shared" nets (GND, power, buses) so ``rip_up_footprint``
        doesn't tear up a whole plane when it only meant to free one part.
        """
        fanout: dict[str, set[str]] = {}
        for fp in board.get_footprints():
            ref = fp.reference_field.text.value
            for pad in fp.definition.pads:
                name = getattr(getattr(pad, "net", None), "name", None)
                if name:
                    fanout.setdefault(name, set()).add(ref)
        return {name: len(refs) for name, refs in fanout.items()}

    def rip_up_footprint(self, reference: str, include_shared: bool = False) -> dict:
        """Rip up the track/via copper on a footprint's local nets.

        Frees a part so it can be moved and re-routed. The footprint's pad nets
        are split into *local* signal nets (touching at most two footprints) and
        *shared* nets (GND, power, buses — more than two footprints); by default
        only the local nets are ripped up, so we never tear up a plane/pour or
        another part's routing. Pass ``include_shared=True`` to rip up shared
        nets too. Pads and zones are always left intact. Single undo step.

        Scoping by net (not by physical connection) is deliberate: KiCad 9's IPC
        has no ``get_connected_items`` (that's KiCad 10.0.1+, like
        ``get_items_by_net``), and for a two-footprint net every segment on it is
        exactly the routing to re-do — so removing the whole net is correct.
        """
        removed_tracks = removed_vias = 0
        with self.commit(f"kicad-mcp: rip up around {reference}") as board:
            fp = self._find_footprint(board, reference)
            pad_nets = {
                p.net.name
                for p in fp.definition.pads
                if getattr(getattr(p, "net", None), "name", None)
            }
            fanout = self._net_fanout(board)
            shared = set() if include_shared else {n for n in pad_nets if fanout.get(n, 0) > 2}
            local = pad_nets - shared
            tracks = [t for t in board.get_tracks() if t.net.name in local]
            vias = [v for v in board.get_vias() if v.net.name in local]
            removed_tracks, removed_vias = len(tracks), len(vias)
            victims = tracks + vias
            if victims:
                board.remove_items(victims)
        return {
            "reference": reference,
            "nets": sorted(local),
            "skipped_shared_nets": sorted(shared),
            "removed_tracks": removed_tracks,
            "removed_vias": removed_vias,
        }

    # --- Zones ---------------------------------------------------------------------

    def add_zone(
        self,
        layer: str,
        polygon_mm: list[tuple[float, float]],
        net_name: str | None = None,
    ) -> dict:
        if len(polygon_mm) < 3:
            raise BackendError("add_zone needs a polygon with at least 3 points.")
        lid = layer_id(layer)
        with self.commit("kicad-mcp: add zone") as board:
            net = self._net_by_name(board, net_name)
            zone = _bt.Zone()
            outline = PolygonWithHoles()
            for x, y in polygon_mm:
                outline.outline.append(PolyLineNode.from_xy(from_mm(x), from_mm(y)))
            outline.outline.closed = True
            zone.outline = outline
            zone.layers = [lid]
            if net is not None:
                zone.net = net
            board.create_items(zone)
        return {"layer": layer, "points": len(polygon_mm), "net": net_name}

    def refill_zones(self) -> dict:
        board = self.get_board()
        board.refill_zones()
        return {"refilled": True}

    # --- Persistence ------------------------------------------------------------------

    def save_board(self) -> dict:
        """Save the live board to disk (required before kicad-cli render/DRC
        sees the edits — the visual-loop sync point)."""
        board = self.get_board()
        board.save()
        return {"saved": True, "board": board.name}
