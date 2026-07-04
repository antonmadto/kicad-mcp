"""offset_polyline (differential-pair path derivation) — pure math tests."""

from __future__ import annotations

import math

import pytest

from kicad_mcp.review_engine.geometry import distance, offset_polyline


def test_straight_line_offsets_perpendicular():
    center = [(0.0, 0.0), (10.0, 0.0)]
    left = offset_polyline(center, +0.5)
    right = offset_polyline(center, -0.5)
    # Travel +x → left normal is (0, +1)... (KiCad Y is down but math is consistent)
    assert left == [(0.0, 0.5), (10.0, 0.5)]
    assert right == [(0.0, -0.5), (10.0, -0.5)]
    # P and N stay exactly 2*offset apart along the run.
    for lp, rp in zip(left, right, strict=True):
        assert distance(lp, rp) == pytest.approx(1.0)


def test_right_angle_miter_preserves_offset_distance():
    center = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    off = offset_polyline(center, 0.5)
    # The middle joint is mitered: for a 90° turn the miter point sits at
    # offset*sqrt(2) from the corner.
    corner = (10.0, 0.0)
    assert distance(off[1], corner) == pytest.approx(0.5 * math.sqrt(2), rel=1e-6)
    # Endpoints remain exactly 0.5 from their segments.
    assert distance(off[0], (0.0, 0.0)) == pytest.approx(0.5)
    assert distance(off[2], (10.0, 10.0)) == pytest.approx(0.5)


def test_single_point_passthrough():
    assert offset_polyline([(1.0, 2.0)], 0.5) == [(1.0, 2.0)]


def test_symmetric_pair_never_crosses():
    center = [(0.0, 0.0), (5.0, 0.0), (10.0, 5.0), (15.0, 5.0)]
    p = offset_polyline(center, +0.25)
    n = offset_polyline(center, -0.25)
    for a, b in zip(p, n, strict=True):
        assert distance(a, b) >= 0.49  # never collapses
