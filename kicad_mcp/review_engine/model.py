"""Normalized design model (PLAN.md §6).

Rules consume this structure, never raw files. It is built from the parsed
``.kicad_pcb`` (via the S-expr layer) plus optional schematic components and
user-supplied :class:`DesignContext`. One place extracts board reality; every
rule reasons over the same normalized view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from kicad_mcp.utils import sexpr as sx

from . import geometry as geo

# --- Net classification ------------------------------------------------------

# Deliberately conservative: misclassification feeds rules (e.g. RTE-2 reads
# "power"), and false positives destroy trust. Prefer under-matching "signal"
# over over-matching a specific kind.
GROUND_RE = re.compile(r"(^|_)(gnd\w*|ground|vss\w*|agnd|dgnd|pgnd|earth)($|_)|gnd", re.I)
POWER_RE = re.compile(
    r"(^\+\d)"  # +3V3, +5V, +12V
    r"|(^|_)(vcc\w*|vdd\w*|vbat|vin|vout|vbus|vaa|pwr|vdda|vcca)($|_)"
    r"|(^\d+v\d*(_\w+)?$)",  # 3V3, 5V, 12V0, 3V3_A
    re.I,
)
CLOCK_RE = re.compile(r"(^|_)(clk\w*|sclk|sck|osc\w*|xtal\w*|mco|hse|lse|clock)($|_)", re.I)
DIFF_RE = re.compile(r"(_[pn]$)|(^|_)(usb_)?d[+-]$|(usb_d[pm]$)", re.I)
ANALOG_RE = re.compile(r"(^|_)(adc\w*|dac\w*|ain\d*|vref\w*|analog)($|_)", re.I)


def classify_net(name: str) -> str:
    """Best-effort net kind from its name: ground/power/clock/diff/analog/signal."""
    if not name:
        return "unconnected"
    n = name.strip()
    if GROUND_RE.search(n):
        return "ground"
    if POWER_RE.search(n):
        return "power"
    if CLOCK_RE.search(n):
        return "clock"
    if DIFF_RE.search(n):
        return "diff"
    if ANALOG_RE.search(n):
        return "analog"
    return "signal"


# --- Dataclasses -------------------------------------------------------------


@dataclass
class Net:
    code: int
    name: str
    kind: str  # ground/power/clock/diff/analog/signal/unconnected


@dataclass
class Pad:
    footprint_ref: str
    number: str
    net_code: int
    net_name: str
    at: geo.Point  # absolute (mm)
    layer_span: str  # e.g. "F.Cu" or "*.Cu"


@dataclass
class Footprint:
    ref: str
    value: str
    lib_id: str
    at: geo.Point
    rotation: float
    layer: str
    pads: list[Pad] = field(default_factory=list)

    @property
    def pad_count(self) -> int:
        return len(self.pads)


@dataclass
class Track:
    start: geo.Point
    end: geo.Point
    width: float
    layer: str
    net_code: int

    @property
    def length(self) -> float:
        return geo.distance(self.start, self.end)


@dataclass
class Via:
    at: geo.Point
    size: float
    drill: float
    layers: tuple[str, ...]
    net_code: int


@dataclass
class Zone:
    net_code: int
    net_name: str
    layers: tuple[str, ...]
    polygon: list[geo.Point]
    net_kind: str

    @property
    def area(self) -> float:
        return geo.polygon_area(self.polygon)


@dataclass
class PhysicalLayer:
    name: str
    type: str
    thickness_mm: float | None
    is_copper: bool
    material: str | None = None
    epsilon_r: float | None = None


@dataclass
class CopperLayer:
    name: str
    stack_index: int  # 0 = topmost copper
    role: str = "unknown"  # signal/ground_plane/power_plane/mixed_plane/split_plane/unknown
    ground_zone_count: int = 0
    power_zone_count: int = 0
    dielectric_to_next_mm: float | None = None  # to the next copper layer down


@dataclass
class DesignContext:
    """User-supplied facts a file cannot contain (PLAN.md §6). Conservative
    defaults: t_rise 0.5 ns → f_knee 1 GHz."""

    default_rise_time_ns: float = 0.5
    clocks_hz: dict[str, float] = field(default_factory=dict)
    target_impedances: dict[str, float] = field(default_factory=dict)
    connector_nets: list[str] = field(default_factory=list)
    fab_house: str | None = None

    @property
    def f_knee_hz(self) -> float:
        return 0.5 / (self.default_rise_time_ns * 1e-9)


# --- Schematic connectivity (from the kicad-cli netlist, PLAN.md §6) ----------


@dataclass
class SchematicPin:
    ref: str
    pin: str
    function: str | None = None


@dataclass
class SchematicNet:
    name: str
    kind: str
    pins: list[SchematicPin] = field(default_factory=list)


@dataclass
class SchematicComponent:
    ref: str
    value: str
    footprint: str | None = None

    @property
    def prefix(self) -> str:
        return "".join(c for c in self.ref if not c.isdigit()).upper()


@dataclass
class Schematic:
    components: list[SchematicComponent]
    nets: list[SchematicNet]

    def component(self, ref: str) -> SchematicComponent | None:
        return next((c for c in self.components if c.ref == ref), None)

    def net(self, name: str) -> SchematicNet | None:
        wanted = name.lstrip("/")
        return next((n for n in self.nets if n.name.lstrip("/") == wanted), None)

    def nets_of(self, ref: str) -> list[SchematicNet]:
        """Nets that touch any pin of ``ref``."""
        return [n for n in self.nets if any(p.ref == ref for p in n.pins)]

    def components_on(self, net_name: str, prefix: str | None = None) -> list[SchematicComponent]:
        """Components with a pin on ``net_name`` (optionally filtered by ref prefix)."""
        net = self.net(net_name)
        if net is None:
            return []
        refs = {p.ref for p in net.pins}
        out = [c for c in self.components if c.ref in refs]
        if prefix:
            out = [c for c in out if c.prefix == prefix.upper()]
        return out

    def by_prefix(self, prefix: str) -> list[SchematicComponent]:
        return [c for c in self.components if c.prefix == prefix.upper()]


def build_schematic(netlist: dict) -> Schematic:
    """Build a :class:`Schematic` from a parsed kicadxml netlist (utils.netlist)."""
    components = [
        SchematicComponent(
            ref=c.get("reference") or "",
            value=c.get("value") or "",
            footprint=c.get("footprint"),
        )
        for c in netlist.get("components", [])
    ]
    nets = []
    for n in netlist.get("nets", []):
        name = n.get("name") or ""
        pins = [
            SchematicPin(
                ref=node.get("reference") or "",
                pin=node.get("pin") or "",
                function=node.get("pin_function"),
            )
            for node in n.get("nodes", [])
        ]
        nets.append(SchematicNet(name=name, kind=classify_net(name), pins=pins))
    return Schematic(components=components, nets=nets)


@dataclass
class DesignModel:
    source: str
    stackup: list[PhysicalLayer]
    copper_layers: list[CopperLayer]
    nets: dict[int, Net]
    footprints: list[Footprint]
    tracks: list[Track]
    vias: list[Via]
    zones: list[Zone]
    board_thickness_mm: float | None
    extents: dict | None
    context: DesignContext
    components: list[dict] = field(default_factory=list)  # schematic-side, optional
    schematic: Schematic | None = None  # net connectivity, when a netlist is available

    @property
    def layer_count(self) -> int:
        return len(self.copper_layers)

    def copper_layer(self, name: str) -> CopperLayer | None:
        return next((ly for ly in self.copper_layers if ly.name == name), None)

    def zones_on(self, layer: str) -> list[Zone]:
        return [z for z in self.zones if layer in z.layers]

    def tracks_on(self, layer: str) -> list[Track]:
        return [t for t in self.tracks if t.layer == layer]

    def net_length_mm(self, net_code: int) -> float:
        """Total routed copper length on a net (sum of its track segments)."""
        return sum(t.length for t in self.tracks if t.net_code == net_code)

    def signal_velocity_mm_per_ns(self, layer: str) -> float:
        """~150 mm/ns inner (stripline, ≈6.7 ps/mm); outer microstrip faster.

        The outer factor 1.093 lands microstrip at ≈6.1 ps/mm to match the
        authoritative constant (PHIL-USB-4 #110; CLAUDE.md).
        """
        outer = layer in ("F.Cu", "B.Cu")
        return 150.0 * (1.093 if outer else 1.0)

    def prop_delay_ps_per_mm(self, layer: str) -> float:
        """Inverse of velocity: ≈6.7 ps/mm stripline, ≈6.1 ps/mm microstrip."""
        return 1000.0 / self.signal_velocity_mm_per_ns(layer)


# --- Extraction --------------------------------------------------------------


def _point(node: list, tag: str) -> geo.Point | None:
    p = sx.find(node, tag)
    if p is not None and len(p) >= 3:
        return (float(sx.sym(p[1])), float(sx.sym(p[2])))
    return None


def _polygon_pts(node: list) -> list[geo.Point]:
    poly = sx.find(node, "polygon")
    pts_node = sx.find(poly, "pts") if poly is not None else None
    if pts_node is None:
        return []
    out: list[geo.Point] = []
    for xy in sx.children(pts_node, "xy"):
        if len(xy) >= 3:
            out.append((float(sx.sym(xy[1])), float(sx.sym(xy[2]))))
    return out


def _extract_nets(root: list) -> dict[int, Net]:
    nets: dict[int, Net] = {}
    for net in sx.children(root, "net"):
        if len(net) >= 3:
            code = int(sx.sym(net[1]))
            name = str(net[2])
            nets[code] = Net(code=code, name=name, kind=classify_net(name))
    return nets


def _extract_footprints(root: list) -> list[Footprint]:
    footprints: list[Footprint] = []
    for fp in sx.find_all(root, "footprint"):
        at = sx.find(fp, "at")
        fx = float(sx.sym(at[1])) if at and len(at) >= 3 else 0.0
        fy = float(sx.sym(at[2])) if at and len(at) >= 3 else 0.0
        frot = float(sx.sym(at[3])) if at and len(at) >= 4 else 0.0
        ref, value = "", ""
        for prop in sx.children(fp, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = str(prop[2])
            elif len(prop) >= 3 and prop[1] == "Value":
                value = str(prop[2])
        layer_node = sx.find(fp, "layer")
        layer = str(layer_node[1]) if layer_node and len(layer_node) >= 2 else "F.Cu"
        lib_id = str(fp[1]) if len(fp) >= 2 and isinstance(fp[1], str) else ""

        pads: list[Pad] = []
        for pad in sx.children(fp, "pad"):
            number = str(pad[1]) if len(pad) >= 2 else ""
            local = _point(pad, "at") or (0.0, 0.0)
            abs_pos = geo.transform_pad(local, (fx, fy), frot)
            net_node = sx.find(pad, "net")
            ncode = int(sx.sym(net_node[1])) if net_node and len(net_node) >= 2 else 0
            nname = str(net_node[2]) if net_node and len(net_node) >= 3 else ""
            layers_node = sx.find(pad, "layers")
            span = str(layers_node[1]) if layers_node and len(layers_node) >= 2 else "F.Cu"
            pads.append(
                Pad(
                    footprint_ref=ref,
                    number=number,
                    net_code=ncode,
                    net_name=nname,
                    at=abs_pos,
                    layer_span=span,
                )
            )
        footprints.append(
            Footprint(
                ref=ref,
                value=value,
                lib_id=lib_id,
                at=(fx, fy),
                rotation=frot,
                layer=layer,
                pads=pads,
            )
        )
    return footprints


def _extract_tracks(root: list) -> list[Track]:
    tracks: list[Track] = []
    for seg in sx.children(root, "segment"):
        start = _point(seg, "start")
        end = _point(seg, "end")
        if start is None or end is None:
            continue
        width = float(sx.first_value(seg, "width", 0.0))
        layer_node = sx.find(seg, "layer")
        layer = str(layer_node[1]) if layer_node and len(layer_node) >= 2 else ""
        net = int(sx.first_value(seg, "net", 0))
        tracks.append(Track(start=start, end=end, width=width, layer=layer, net_code=net))
    return tracks


def _extract_vias(root: list) -> list[Via]:
    vias: list[Via] = []
    for via in sx.children(root, "via"):
        at = _point(via, "at")
        if at is None:
            continue
        size = float(sx.first_value(via, "size", 0.0))
        drill = float(sx.first_value(via, "drill", 0.0))
        layers_node = sx.find(via, "layers")
        layers = tuple(str(x) for x in layers_node[1:]) if layers_node else ()
        net = int(sx.first_value(via, "net", 0))
        vias.append(Via(at=at, size=size, drill=drill, layers=layers, net_code=net))
    return vias


def _extract_zones(root: list, nets: dict[int, Net]) -> list[Zone]:
    zones: list[Zone] = []
    for z in sx.children(root, "zone"):
        ncode = int(sx.first_value(z, "net", 0))
        nname = str(sx.first_value(z, "net_name", "") or "")
        layer_node = sx.find(z, "layer")
        layers_node = sx.find(z, "layers")
        if layer_node is not None and len(layer_node) >= 2:
            layers = (str(layer_node[1]),)
        elif layers_node is not None:
            layers = tuple(str(x) for x in layers_node[1:])
        else:
            layers = ()
        kind = nets[ncode].kind if ncode in nets else classify_net(nname)
        zones.append(
            Zone(
                net_code=ncode,
                net_name=nname,
                layers=layers,
                polygon=_polygon_pts(z),
                net_kind=kind,
            )
        )
    return zones


def _extract_stackup_and_copper(
    root: list, zones: list[Zone], tracks: list[Track], extents: dict | None
) -> tuple[list[PhysicalLayer], list[CopperLayer]]:
    stackup_node = sx.find(root, "stackup")
    physical: list[PhysicalLayer] = []
    copper_order: list[str] = []
    if stackup_node is not None:
        for layer in sx.children(stackup_node, "layer"):
            name = str(layer[1])
            ltype = sx.first_value(layer, "type")
            is_cu = ltype == "copper"
            physical.append(
                PhysicalLayer(
                    name=name,
                    type=str(ltype) if ltype is not None else "",
                    thickness_mm=sx.first_value(layer, "thickness"),
                    is_copper=is_cu,
                    material=sx.first_value(layer, "material"),
                    epsilon_r=sx.first_value(layer, "epsilon_r"),
                )
            )
            if is_cu:
                copper_order.append(name)

    # Fall back to the (layers ...) table if there is no stored stackup.
    if not copper_order:
        layer_table = sx.find(root, "layers")
        if layer_table is not None:
            for entry in layer_table[1:]:
                if (
                    isinstance(entry, list)
                    and len(entry) >= 3
                    and sx.sym(entry[2])
                    in (
                        "signal",
                        "power",
                        "mixed",
                        "jumper",
                    )
                ):
                    copper_order.append(str(entry[1]))

    # Only trust extents that are meaningfully sized; a degenerate bbox would turn
    # any zone into a spurious "full plane".
    board_area = None
    if extents and extents.get("width", 0) > 1e-3 and extents.get("height", 0) > 1e-3:
        board_area = extents["width"] * extents["height"]

    copper_layers: list[CopperLayer] = []
    for idx, name in enumerate(copper_order):
        layer_zones = [z for z in zones if name in z.layers]
        gnd = [z for z in layer_zones if z.net_kind == "ground"]
        pwr = [z for z in layer_zones if z.net_kind == "power"]
        role = _classify_layer_role(gnd, pwr, layer_zones, board_area, extents)
        copper_layers.append(
            CopperLayer(
                name=name,
                stack_index=idx,
                role=role,
                ground_zone_count=len(gnd),
                power_zone_count=len(pwr),
            )
        )

    _assign_dielectrics(physical, copper_layers)
    return physical, copper_layers


# Area coverage is measured against the extents bbox, which OVERSTATES the board
# area on L-shaped/cut boards — a genuine full pour can sit well below 30% of the
# bbox. The span test catches that case: a plane pour stretches across (most of)
# the board in both dimensions even when its area is a small bbox fraction.
_AREA_THRESH = 0.30
_SPAN_THRESH = 0.60
_MIN_PLANE_AREA_MM2 = 100.0


def _plane_like(zones: list, board_area: float | None, extents: dict | None) -> bool:
    if not zones:
        return False
    if board_area is not None:
        cov = sum(z.area for z in zones) / board_area
        if cov >= _AREA_THRESH:
            return True
    if extents and extents.get("width", 0) > 0 and extents.get("height", 0) > 0:
        for z in zones:
            if len(z.polygon) < 3 or z.area < _MIN_PLANE_AREA_MM2:
                continue
            zx0, zy0, zx1, zy1 = geo.bbox(z.polygon)
            span_x = (zx1 - zx0) / extents["width"]
            span_y = (zy1 - zy0) / extents["height"]
            if span_x >= _SPAN_THRESH and span_y >= _SPAN_THRESH:
                return True
    return False


def _classify_layer_role(gnd, pwr, all_zones, board_area, extents=None) -> str:
    if not all_zones:
        return "signal"
    if board_area is None and extents is None:
        # Nothing to normalize against; classify by presence.
        if gnd and pwr:
            return "mixed_plane"
        if gnd:
            return "ground_plane"
        if pwr:
            return "power_plane"
        return "signal"
    gnd_plane = _plane_like(gnd, board_area, extents)
    pwr_plane = _plane_like(pwr, board_area, extents)
    if gnd_plane and pwr_plane:
        return "mixed_plane"
    if gnd_plane:
        return "ground_plane"
    if pwr_plane:
        return "power_plane"
    if board_area is not None:
        distinct_nets = {z.net_code for z in all_zones if z.area / board_area > 0.1}
        if len(distinct_nets) >= 2:
            return "split_plane"
    return "signal"


def _assign_dielectrics(physical: list[PhysicalLayer], copper_layers: list[CopperLayer]) -> None:
    """Sum dielectric thickness between each copper layer and the next one down."""
    copper_positions = [i for i, ly in enumerate(physical) if ly.is_copper]
    for k in range(len(copper_positions) - 1):
        lo, hi = copper_positions[k], copper_positions[k + 1]
        gap = sum(
            physical[j].thickness_mm or 0.0 for j in range(lo + 1, hi) if not physical[j].is_copper
        )
        if k < len(copper_layers):
            copper_layers[k].dielectric_to_next_mm = gap if gap > 0 else None


def build_model(
    pcb_path: Path | str,
    *,
    context: DesignContext | None = None,
    components: list[dict] | None = None,
    board_info: dict | None = None,
    netlist: dict | None = None,
) -> DesignModel:
    """Parse a ``.kicad_pcb`` into a :class:`DesignModel`.

    ``netlist`` is a parsed kicadxml netlist (utils.netlist); when supplied it
    populates ``model.schematic`` so subcircuit/connector rules can reason about
    net connectivity.
    """
    root = sx.parse_file(pcb_path)
    nets = _extract_nets(root)
    footprints = _extract_footprints(root)
    tracks = _extract_tracks(root)
    vias = _extract_vias(root)
    zones = _extract_zones(root, nets)

    general = sx.find(root, "general")
    thickness = sx.first_value(general, "thickness") if general is not None else None
    extents = (board_info or {}).get("extents_mm") or sx.edge_extents(root)

    stackup, copper_layers = _extract_stackup_and_copper(root, zones, tracks, extents)

    return DesignModel(
        source=str(pcb_path),
        stackup=stackup,
        copper_layers=copper_layers,
        nets=nets,
        footprints=footprints,
        tracks=tracks,
        vias=vias,
        zones=zones,
        board_thickness_mm=thickness,
        extents=extents,
        context=context or DesignContext(),
        components=components or [],
        schematic=build_schematic(netlist) if netlist else None,
    )


# Edge extents live in kicad_mcp.utils.sexpr.edge_extents (shared with the
# backend read layer; handles circles and true arc sweeps).
