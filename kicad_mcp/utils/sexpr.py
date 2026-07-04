"""Thin helpers over ``sexpdata`` for walking KiCad s-expression trees.

Used by the read layer to extract board structure (stackup, layers, nets) that
kicad-skip does not model. Schematic symbol reads go through kicad-skip instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sexpdata


def parse_file(path: Path | str) -> list:
    # KiCad files are UTF-8; never decode with the platform-default codec.
    return sexpdata.loads(Path(path).read_text(encoding="utf-8"))


def sym(x: Any) -> Any:
    """Unwrap a sexpdata Symbol to its string; pass through everything else."""
    return x.value() if isinstance(x, sexpdata.Symbol) else x


def head(node: Any) -> Any:
    """The tag of an s-expr node, e.g. ``head(['layer', ...]) == 'layer'``."""
    if isinstance(node, list) and node:
        return sym(node[0])
    return None


def find(node: Any, tag: str) -> list | None:
    """Depth-first search for the first node tagged ``tag``."""
    if isinstance(node, list):
        if head(node) == tag:
            return node
        for child in node:
            result = find(child, tag)
            if result is not None:
                return result
    return None


def find_all(node: Any, tag: str) -> list[list]:
    """All nodes tagged ``tag``, searched recursively."""
    out: list[list] = []
    if isinstance(node, list):
        if head(node) == tag:
            out.append(node)
        for child in node:
            out.extend(find_all(child, tag))
    return out


def children(node: list, tag: str) -> list[list]:
    """Direct children of ``node`` tagged ``tag`` (non-recursive)."""
    return [c for c in node[1:] if head(c) == tag]


def first_value(node: list, tag: str, default: Any = None) -> Any:
    """The first argument of the first direct child tagged ``tag``.

    e.g. ``first_value(layer_node, 'thickness')`` → the numeric thickness.
    """
    for c in node[1:]:
        if head(c) == tag and len(c) > 1:
            return sym(c[1])
    return default


def _pt(node: list, tag: str) -> tuple[float, float] | None:
    p = find(node, tag)
    if p is not None and len(p) >= 3:
        return (float(sym(p[1])), float(sym(p[2])))
    return None


def edge_extents(root: Any) -> dict | None:
    """Bounding box (mm) of Edge.Cuts geometry.

    Circles contribute center ± radius; arcs are sampled along their true sweep
    (via the circumcircle of start/mid/end) so a bulge past the endpoints is not
    missed. Line/rect segments contribute their endpoints.
    """
    import math

    xs: list[float] = []
    ys: list[float] = []

    def on_edge(node: list) -> bool:
        layer = find(node, "layer")
        return layer is not None and "Edge.Cuts" in [str(v) for v in layer[1:]]

    for tag in ("gr_rect", "gr_line", "gr_poly"):
        for node in find_all(root, tag):
            if not on_edge(node):
                continue
            for point_tag in ("start", "end"):
                pt = _pt(node, point_tag)
                if pt is not None:
                    xs.append(pt[0])
                    ys.append(pt[1])
            pts_node = find(node, "pts")
            if pts_node is not None:
                for xy in children(pts_node, "xy"):
                    if len(xy) >= 3:
                        xs.append(float(sym(xy[1])))
                        ys.append(float(sym(xy[2])))

    for node in find_all(root, "gr_circle"):
        if not on_edge(node):
            continue
        center = _pt(node, "center")
        end = _pt(node, "end")
        if center and end:
            r = math.hypot(end[0] - center[0], end[1] - center[1])
            xs.extend([center[0] - r, center[0] + r])
            ys.extend([center[1] - r, center[1] + r])

    for node in find_all(root, "gr_arc"):
        if not on_edge(node):
            continue
        start, mid, end = _pt(node, "start"), _pt(node, "mid"), _pt(node, "end")
        pts = [p for p in (start, mid, end) if p is not None]
        if start and mid and end:
            sampled = _sample_arc(start, mid, end)
            if sampled:
                pts = sampled
        for p in pts:
            xs.append(p[0])
            ys.append(p[1])

    if not xs or not ys:
        return None
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
        "width": round(max(xs) - min(xs), 4),
        "height": round(max(ys) - min(ys), 4),
    }


def _sample_arc(
    start: tuple[float, float], mid: tuple[float, float], end: tuple[float, float], n: int = 16
) -> list[tuple[float, float]] | None:
    """Sample an arc defined by 3 points along its sweep (circumcircle param)."""
    import math

    ax, ay = start
    bx, by = mid
    cx, cy = end
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:  # collinear — treat as a line
        return [start, mid, end]
    ux = (
        (ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)
    ) / d
    uy = (
        (ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)
    ) / d
    r = math.hypot(ax - ux, ay - uy)
    a0 = math.atan2(ay - uy, ax - ux)
    a1 = math.atan2(by - uy, bx - ux)
    a2 = math.atan2(cy - uy, cx - ux)

    # Sweep from a0 to a2 passing through a1.
    def norm(a: float) -> float:
        while a < 0:
            a += 2 * math.pi
        return a % (2 * math.pi)

    ccw_mid = norm(a1 - a0)
    ccw_end = norm(a2 - a0)
    if ccw_mid <= ccw_end:  # counter-clockwise through mid
        sweep = ccw_end
        sign = 1.0
    else:  # clockwise
        sweep = 2 * math.pi - ccw_end
        sign = -1.0
    return [
        (ux + r * math.cos(a0 + sign * sweep * i / n), uy + r * math.sin(a0 + sign * sweep * i / n))
        for i in range(n + 1)
    ]
