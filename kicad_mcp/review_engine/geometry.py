"""Small 2D geometry helpers for the review engine (pure, stdlib only).

KiCad units are millimetres throughout. Y grows downward, but every routine here
is orientation-agnostic (areas use absolute value, point-in-polygon is winding
independent), so that does not matter.
"""

from __future__ import annotations

import math

Point = tuple[float, float]


def polygon_area(pts: list[Point]) -> float:
    """Absolute area of a simple polygon (shoelace)."""
    n = len(pts)
    if n < 3:
        return 0.0
    acc = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def bbox(pts: list[Point]) -> tuple[float, float, float, float]:
    """(min_x, min_y, max_x, max_y) of a point set."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def point_in_polygon(pt: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon (boundary treated as inside-ish)."""
    x, y = pt
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def rotate(x: float, y: float, deg: float) -> Point:
    """Rotate (x, y) by ``deg`` degrees (KiCad footprint pad transform)."""
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return (x * c - y * s, x * s + y * c)


def transform_pad(local: Point, fp_at: Point, fp_rot: float) -> Point:
    """Absolute position of a pad given its footprint origin + rotation."""
    rx, ry = rotate(local[0], local[1], fp_rot)
    return (fp_at[0] + rx, fp_at[1] + ry)


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def sample_segment(a: Point, b: Point, step: float = 1.0) -> list[Point]:
    """Points along segment a→b at ~``step`` mm spacing (endpoints included)."""
    length = distance(a, b)
    n = max(1, int(math.ceil(length / max(step, 1e-6))))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Shortest distance from point ``p`` to segment a→b."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-18:
        return distance(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    return distance(p, (ax + t * dx, ay + t * dy))


def point_to_polygon_edge_distance(p: Point, polygon: list[Point]) -> float:
    """Shortest distance from ``p`` to any edge of ``polygon``."""
    n = len(polygon)
    if n == 0:
        return float("inf")
    if n == 1:
        return distance(p, polygon[0])
    return min(point_segment_distance(p, polygon[i], polygon[(i + 1) % n]) for i in range(n))


def segment_parallel_proximity(
    a1: Point, a2: Point, b1: Point, b2: Point
) -> tuple[bool, float, float]:
    """(parallel, perpendicular_distance, parallel_overlap_length) for two segments.

    ``parallel`` is True when the directions are within ~15°. Distance is the
    perpendicular offset of segment b's midpoint from segment a's line; overlap is
    the length over which the two run alongside each other (0 if they don't).
    Used for the crosstalk keep-out check.
    """
    ax, ay = a2[0] - a1[0], a2[1] - a1[1]
    bx, by = b2[0] - b1[0], b2[1] - b1[1]
    la = math.hypot(ax, ay)
    lb = math.hypot(bx, by)
    if la < 1e-9 or lb < 1e-9:
        return (False, float("inf"), 0.0)
    uax, uay = ax / la, ay / la
    ubx, uby = bx / lb, by / lb
    cos = abs(uax * ubx + uay * uby)
    parallel = cos > 0.966  # within ~15°

    # Perpendicular distance of b's midpoint from a's infinite line.
    mbx, mby = (b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2
    perp = abs((mbx - a1[0]) * (-uay) + (mby - a1[1]) * uax)

    # Overlap of b's projection onto a's direction with a's own [0, la] span.
    t_b1 = (b1[0] - a1[0]) * uax + (b1[1] - a1[1]) * uay
    t_b2 = (b2[0] - a1[0]) * uax + (b2[1] - a1[1]) * uay
    lo, hi = sorted((t_b1, t_b2))
    overlap = max(0.0, min(hi, la) - max(lo, 0.0))
    return (parallel, perp, overlap)


def offset_polyline(points: list[Point], offset: float) -> list[Point]:
    """Offset an open polyline perpendicular to its direction (miter joints).

    Positive offset is to the left of the travel direction. Used to derive the
    P/N paths of a differential pair from its centerline.
    """
    n = len(points)
    if n < 2:
        return list(points)

    def normal(a: Point, b: Point) -> Point:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return (0.0, 0.0)
        return (-dy / length, dx / length)

    out: list[Point] = []
    for i in range(n):
        if i == 0:
            nx, ny = normal(points[0], points[1])
        elif i == n - 1:
            nx, ny = normal(points[-2], points[-1])
        else:
            n1 = normal(points[i - 1], points[i])
            n2 = normal(points[i], points[i + 1])
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            m_len = math.hypot(mx, my)
            if m_len < 1e-9:  # 180° reversal — fall back to incoming normal
                nx, ny = n1
            else:
                # Miter: scale so the offset distance is preserved at the joint.
                nx, ny = mx / m_len, my / m_len
                cos_half = nx * n1[0] + ny * n1[1]
                if abs(cos_half) > 1e-9:
                    scale = 1.0 / cos_half
                    # Clamp extreme miters (very acute angles) to 4x.
                    scale = max(min(scale, 4.0), -4.0)
                    nx, ny = nx * scale, ny * scale
        out.append((points[i][0] + nx * offset, points[i][1] + ny * offset))
    return out
