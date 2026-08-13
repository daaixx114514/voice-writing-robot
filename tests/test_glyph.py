"""Tests for glyph trajectory module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.glyph.bezier import flatten_quadratic
from src.glyph.glyph_extractor import GlyphExtractor
from src.glyph.trajectory import (
    GlyphPath,
    PenState,
    Point2D,
    StrokePoint,
    WritingTrajectory,
    build_trajectory_points,
)


# ── Point2D tests ──────────────────────────────────────────────────────

class TestPoint2D:
    def test_add(self):
        a = Point2D(1, 2)
        b = Point2D(3, 4)
        assert a + b == Point2D(4, 6)

    def test_sub(self):
        assert Point2D(5, 3) - Point2D(2, 1) == Point2D(3, 2)

    def test_scaled(self):
        assert Point2D(2, 3).scaled(0.5) == Point2D(1.0, 1.5)

    def test_frozen(self):
        p = Point2D(0, 0)
        with pytest.raises(Exception):
            p.x = 1  # type: ignore[misc]


# ── Bezier flattening ──────────────────────────────────────────────────

class TestBezierFlatten:
    def test_straight_line(self):
        """A quadratic where control point is on the chord → collinear output."""
        pts = flatten_quadratic(
            Point2D(0, 0), Point2D(50, 0), Point2D(100, 0),
            tolerance=0.1,
        )
        assert len(pts) >= 2
        assert pts[0] == Point2D(0, 0)
        assert pts[-1] == Point2D(100, 0)
        # All points should be on y=0 line.
        for p in pts:
            assert abs(p.y) < 0.01

    def test_degenerate_curve(self):
        """Control point same as endpoints → valid output."""
        pts = flatten_quadratic(
            Point2D(10, 10), Point2D(10, 10), Point2D(10, 10),
            tolerance=0.1,
        )
        assert len(pts) >= 1
        assert pts[0] == Point2D(10, 10)

    def test_output_starts_at_p0(self):
        pts = flatten_quadratic(
            Point2D(10, 0), Point2D(50, 80), Point2D(90, 0),
            tolerance=0.5,
        )
        assert pts[0] == Point2D(10, 0)

    def test_output_ends_at_p2(self):
        pts = flatten_quadratic(
            Point2D(10, 0), Point2D(50, 80), Point2D(90, 0),
            tolerance=0.5,
        )
        assert pts[-1] == Point2D(90, 0)

    def test_consecutive_off_curve_points_use_implied_midpoint(self):
        extractor = object.__new__(GlyphExtractor)
        extractor.tolerance = 0.1
        contour = extractor._flatten_contour([
            ("M", 0.0, 0.0),
            ("Q", 10.0, 20.0),
            ("Q", 20.0, 20.0),
            ("QE", 30.0, 0.0),
        ])
        assert contour is not None
        assert Point2D(15.0, 20.0) in contour
        assert contour[-1] == Point2D(30.0, 0.0)

    def test_adjacent_quadratic_commands_keep_their_endpoints(self):
        extractor = object.__new__(GlyphExtractor)
        extractor.tolerance = 0.1
        contour = extractor._flatten_contour([
            ("M", 0.0, 0.0),
            ("Q", 10.0, 10.0),
            ("QE", 20.0, 0.0),
            ("Q", 30.0, -10.0),
            ("QE", 40.0, 0.0),
        ])
        assert contour is not None
        assert Point2D(20.0, 0.0) in contour
        assert contour[-1] == Point2D(40.0, 0.0)

    def test_close_path_restores_final_outline_segment(self):
        extractor = object.__new__(GlyphExtractor)
        extractor.tolerance = 0.1
        contours = extractor._pen_to_contours([
            ("moveTo", ((0.0, 0.0),)),
            ("lineTo", ((10.0, 0.0),)),
            ("lineTo", ((10.0, 10.0),)),
            ("closePath", ()),
        ])
        assert len(contours) == 1
        assert contours[0][-1] == Point2D(0.0, 0.0)

    def test_all_off_curve_contour_handles_none_endpoint(self):
        extractor = object.__new__(GlyphExtractor)
        extractor.tolerance = 0.1
        contours = extractor._pen_to_contours([
            ("qCurveTo", ((0.0, 10.0), (10.0, 10.0), (10.0, 0.0), None)),
            ("closePath", ()),
        ])
        assert len(contours) == 1
        assert contours[0][0] == Point2D(5.0, 5.0)
        assert contours[0][-1] == Point2D(5.0, 5.0)


# ── Trajectory data structures ─────────────────────────────────────────

class TestWritingTrajectory:
    def test_empty(self):
        traj = WritingTrajectory(text="")
        assert traj.text == ""
        assert traj.glyphs == []
        assert traj.points == []

    def test_default_page_size(self):
        traj = WritingTrajectory(text="x")
        assert traj.page_width_mm == 210.0
        assert traj.page_height_mm == 297.0


class TestBuildTrajectoryPoints:
    def test_empty_glyphs(self):
        assert build_trajectory_points([]) == []

    def test_single_glyph_single_contour(self):
        glyph = GlyphPath(
            char="A",
            contours=[[Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)]],
        )
        pts = build_trajectory_points([glyph])
        assert len(pts) == 3  # no pen-up within first contour
        assert all(sp.state == PenState.DOWN for sp in pts)

    def test_single_glyph_two_contours(self):
        glyph = GlyphPath(
            char="A",
            contours=[
                [Point2D(0, 0), Point2D(10, 10)],
                [Point2D(5, 0), Point2D(15, 10)],
            ],
        )
        pts = build_trajectory_points([glyph])
        # Contour 1: 2 DOWN points → pen-up at last DOWN point → pen-up at contour 2 start → 2 DOWN points
        # Result: D D U U D D = 6 points
        down_count = sum(1 for sp in pts if sp.state == PenState.DOWN)
        up_count = sum(1 for sp in pts if sp.state == PenState.UP)
        assert down_count == 4
        assert up_count == 2

    def test_two_glyphs(self):
        g1 = GlyphPath(
            char="A",
            contours=[[Point2D(0, 0), Point2D(5, 5)]],
        )
        g2 = GlyphPath(
            char="B",
            contours=[[Point2D(10, 0), Point2D(15, 5)]],
        )
        pts = build_trajectory_points([g1, g2])
        # g1 contour: 2 DOWN → pen-up before g2: 2 UP (last DOWN then next start) → 2 DOWN
        down_count = sum(1 for sp in pts if sp.state == PenState.DOWN)
        up_count = sum(1 for sp in pts if sp.state == PenState.UP)
        assert down_count == 4
        assert up_count == 2


# ── PenState ───────────────────────────────────────────────────────────

class TestPenState:
    def test_values(self):
        assert PenState.DOWN != PenState.UP
        assert PenState.DOWN.name == "DOWN"
        assert PenState.UP.name == "UP"
