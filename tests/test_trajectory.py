"""Tests for the motion control layer."""

from __future__ import annotations

import math

import pytest

from src.glyph.trajectory import PenState, Point2D, StrokePoint
from src.trajectory.config import MotionConfig
from src.trajectory.coordinate import CoordinateTransformer
from src.trajectory.models import CmdType
from src.trajectory.motion import trajectory_to_commands
from src.trajectory.processor import TrajectoryProcessor


class TestSimpleLineSegment:
    def test_transform_and_commands(self):
        config = MotionConfig(work_width_mm=100, work_height_mm=100)
        transformer = CoordinateTransformer(config)
        transformer.fit_bounds(100, 100)
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(10, 10), PenState.DOWN),
        ]
        transformed = transformer.transform(pts)
        assert transformed[0].point.x == pytest.approx(0)
        assert transformed[0].point.y == pytest.approx(100)
        assert transformed[1].point.x == pytest.approx(10)
        assert transformed[1].point.y == pytest.approx(90)
        commands = trajectory_to_commands(transformed, config)
        assert len(commands) >= 5
        assert [command.type for command in commands[:3]] == [
            CmdType.PEN_UP,
            CmdType.MOVE,
            CmdType.PEN_DOWN,
        ]
        assert commands[-1].type == CmdType.PEN_UP
        draw_cmds = [c for c in commands if c.type == CmdType.DRAW]
        assert len(draw_cmds) == 1


class TestRectangle:
    def test_rectangle_commands(self):
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(50, 0), PenState.DOWN),
            StrokePoint(Point2D(50, 30), PenState.DOWN),
            StrokePoint(Point2D(0, 30), PenState.DOWN),
            StrokePoint(Point2D(0, 0), PenState.DOWN),
        ]
        config = MotionConfig()
        commands = trajectory_to_commands(pts, config)
        assert [command.type for command in commands[:3]] == [
            CmdType.PEN_UP,
            CmdType.MOVE,
            CmdType.PEN_DOWN,
        ]
        assert commands[-1].type == CmdType.PEN_UP
        draw_cmds = [c for c in commands if c.type == CmdType.DRAW]
        assert len(draw_cmds) == 4


class TestTwoStrokes:
    def test_strokes_not_connected(self):
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(10, 0), PenState.DOWN),
            StrokePoint(Point2D(10, 0), PenState.UP),
            StrokePoint(Point2D(5, 5), PenState.UP),
            StrokePoint(Point2D(5, 5), PenState.DOWN),
            StrokePoint(Point2D(15, 5), PenState.DOWN),
        ]
        config = MotionConfig()
        commands = trajectory_to_commands(pts, config)
        up_cmds = [c for c in commands if c.type == CmdType.PEN_UP]
        # Initial safety lift, lift between strokes, final safety lift.
        assert len(up_cmds) == 3
        down_cmds = [c for c in commands if c.type == CmdType.PEN_DOWN]
        assert len(down_cmds) == 2
        types = [c.type for c in commands]
        assert types[:3] == [CmdType.PEN_UP, CmdType.MOVE, CmdType.PEN_DOWN]
        assert CmdType.PEN_UP in types
        assert CmdType.MOVE in types


class TestChineseTextPipeline:
    def test_full_pipeline(self):
        config = MotionConfig(work_width_mm=200, work_height_mm=280)
        pts = [
            StrokePoint(Point2D(10, 20), PenState.DOWN),
            StrokePoint(Point2D(20, 20), PenState.DOWN),
            StrokePoint(Point2D(20, 30), PenState.DOWN),
            StrokePoint(Point2D(20, 30), PenState.UP),
            StrokePoint(Point2D(25, 20), PenState.UP),
            StrokePoint(Point2D(25, 20), PenState.DOWN),
            StrokePoint(Point2D(30, 30), PenState.DOWN),
            StrokePoint(Point2D(30, 30), PenState.UP),
            StrokePoint(Point2D(50, 20), PenState.UP),
            StrokePoint(Point2D(50, 20), PenState.DOWN),
            StrokePoint(Point2D(60, 20), PenState.DOWN),
        ]
        processor = TrajectoryProcessor(config)
        cleaned = processor.process(pts)
        assert len(cleaned) > 0
        assert not processor.warnings
        transformer = CoordinateTransformer(config)
        transformer.fit_bounds(100, 50)
        transformed = transformer.transform(cleaned)
        commands = trajectory_to_commands(transformed, config)
        assert commands[0].type == CmdType.PEN_UP
        assert commands[-1].type == CmdType.PEN_UP
        for cmd in commands:
            if cmd.type in (CmdType.DRAW, CmdType.MOVE):
                assert math.isfinite(cmd.x)
                assert math.isfinite(cmd.y)


class TestBoundsAndScaling:
    def test_exceeds_work_area_warns(self):
        config = MotionConfig(work_width_mm=50, work_height_mm=50, scale_to_fit=False)
        processor = TrajectoryProcessor(config)
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(100, 0), PenState.DOWN),
            StrokePoint(Point2D(100, 100), PenState.DOWN),
        ]
        cleaned = processor.process(pts)
        assert len(processor.warnings) > 0
        assert "exceeds work area" in processor.warnings[0].lower()

    def test_auto_scale_fits(self):
        config = MotionConfig(work_width_mm=100, work_height_mm=100, scale_to_fit=True)
        transformer = CoordinateTransformer(config)
        transformer.fit_bounds(200, 300)
        transformed = transformer.transform_point(Point2D(200, 300))
        assert 0 <= transformed.x <= config.work_width_mm + 0.01
        assert 0 <= transformed.y <= config.work_height_mm + 0.01

    def test_no_negative_after_transform(self):
        config = MotionConfig()
        transformer = CoordinateTransformer(config)
        transformer.fit_bounds(100, 100)
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(50, 50), PenState.DOWN),
        ]
        transformed = transformer.transform(pts)
        for sp in transformed:
            assert sp.point.x >= -0.01
            assert sp.point.y >= -0.01

    def test_horizontal_flip_is_independent_from_vertical_flip(self):
        config = MotionConfig(
            work_width_mm=100,
            work_height_mm=100,
            flip_x=True,
            flip_y=False,
        )
        transformer = CoordinateTransformer(config)
        transformer.fit_bounds(100, 100)
        transformed = transformer.transform_point(Point2D(10, 20))
        assert transformed == Point2D(90, 20)


class TestProcessorEdgeCases:
    def test_empty_input(self):
        processor = TrajectoryProcessor(MotionConfig())
        assert processor.process([]) == []

    def test_single_point(self):
        processor = TrajectoryProcessor(MotionConfig())
        pts = [StrokePoint(Point2D(5, 5), PenState.DOWN)]
        result = processor.process(pts)
        assert len(result) == 1

    def test_duplicates_removed(self):
        processor = TrajectoryProcessor(MotionConfig(min_point_distance=0.01))
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(10, 10), PenState.DOWN),
        ]
        result = processor.process(pts)
        assert len(result) == 2

    def test_close_point_merge_preserves_pen_state_transition(self):
        processor = TrajectoryProcessor(MotionConfig(min_point_distance=1.0))
        pts = [
            StrokePoint(Point2D(0, 0), PenState.DOWN),
            StrokePoint(Point2D(0, 0), PenState.UP),
            StrokePoint(Point2D(0.1, 0.1), PenState.DOWN),
        ]
        result = processor.process(pts)
        assert [sp.state for sp in result] == [
            PenState.DOWN,
            PenState.UP,
            PenState.DOWN,
        ]
