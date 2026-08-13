"""Tests for G-code exporter and simulator integration."""

from __future__ import annotations

import pytest

from src.trajectory.exporters.gcode import export_gcode
from src.trajectory.models import CmdType, MotionCommand, draw_to, move_to, pen_down, pen_up
from src.trajectory.simulator import VirtualPlotter


class TestGCodeExporter:
    def test_empty_commands(self):
        gcode = export_gcode([], write_speed=800, travel_speed=2000)
        assert "G90" in gcode
        assert "G21" in gcode

    def test_starts_with_pen_up(self):
        cmds = [
            pen_up(),
            move_to(10, 20, 0),
            pen_down(),
            draw_to(30, 40, 0),
            pen_up(),
        ]
        gcode = export_gcode(cmds, write_speed=800, travel_speed=2000)
        lines = gcode.split("\n")
        assert any("M5" in l for l in lines)
        assert any("M3 S1" in l for l in lines)
        assert any("G0" in l for l in lines)
        assert any("G1" in l for l in lines)

    def test_ends_with_pen_up(self):
        cmds = [
            pen_down(),
            draw_to(10, 10, 0),
        ]
        gcode = export_gcode(cmds)
        lines = gcode.split("\n")
        # Last non-empty line should be pen-up.
        while lines and lines[-1].strip() == "":
            lines.pop()
        assert "M5" in lines[-1]

    def test_mm_per_s_mode(self):
        cmds = [pen_down(), draw_to(10, 10, 0), pen_up()]
        gcode = export_gcode(cmds, write_speed=20, travel_speed=50, feed_rate_unit="mm/s")
        assert "Write speed 20 mm/s" in gcode or "Write speed 20" in gcode

    def test_uses_command_speed(self):
        """When a command has its own speed (>0), it should override defaults."""
        cmds = [
            pen_up(),
            move_to(0, 0, 500),  # custom travel speed
            pen_down(),
            draw_to(10, 10, 300),  # custom write speed
            pen_up(),
        ]
        gcode = export_gcode(cmds, write_speed=800, travel_speed=2000)
        assert "F500" in gcode
        assert "F300" in gcode


class TestVirtualPlotter:
    def test_load_and_step(self):
        plotter = VirtualPlotter()
        cmds = [
            pen_up(),
            move_to(10, 0, 0),
            pen_down(),
            draw_to(20, 0, 0),
            draw_to(20, 10, 0),
            pen_up(),
        ]
        plotter.load_commands(cmds)
        assert not plotter.finished

        # Step through entire simulation.
        more = True
        steps = 0
        while more and steps < 5000:
            more = plotter.step(0.016)
            steps += 1

        assert plotter.finished
        assert len(plotter.segments) > 0
        # Last pen position should be near (20, 10).
        assert pytest.approx(plotter.pen.x, abs=1) == 20
        assert pytest.approx(plotter.pen.y, abs=1) == 10
        assert not plotter.pen.is_down  # ended with pen up

    def test_segments_only_when_moving(self):
        plotter = VirtualPlotter()
        cmds = [
            pen_up(),
            pen_down(),  # no-op for segments
            pen_up(),
        ]
        plotter.load_commands(cmds)
        plotter.step(1.0)
        assert len(plotter.segments) == 0  # PEN_UP/DOWN alone produce no segments

    def test_reset_clears_everything(self):
        plotter = VirtualPlotter()
        cmds = [pen_down(), draw_to(50, 50, 0), pen_up()]
        plotter.load_commands(cmds)
        while not plotter.finished:
            plotter.step(0.1)
        assert plotter.finished
        plotter.reset()
        assert not plotter.finished  # reset loads commands for replay
        assert plotter.pen.x == 0 and plotter.pen.y == 0
        assert not plotter.pen.is_down
        assert len(plotter.segments) == 0

    def test_speed_override(self):
        plotter = VirtualPlotter()
        plotter.set_speed_override(100.0)  # very fast
        cmds = [pen_down(), draw_to(100, 0, 0), pen_up()]
        plotter.load_commands(cmds)
        # Should complete in very few steps with high speed.
        steps = 0
        while not plotter.finished and steps < 500:
            plotter.step(0.016)
            steps += 1
        assert plotter.finished
        assert steps < 100  # fast enough to finish quickly

    def test_consecutive_draws_continue_from_previous_endpoint(self):
        plotter = VirtualPlotter()
        cmds = [
            pen_up(),
            move_to(10, 10, 100),
            pen_down(),
            draw_to(20, 10, 100),
            draw_to(20, 20, 100),
            draw_to(30, 20, 100),
            pen_up(),
        ]
        plotter.load_commands(cmds)
        while not plotter.finished:
            plotter.step(0.016)

        drawn = [segment for segment in plotter.segments if segment.is_draw]
        assert drawn
        assert drawn[0].x1 == pytest.approx(10)
        assert drawn[0].y1 == pytest.approx(10)
        for previous, current in zip(drawn, drawn[1:]):
            assert current.x1 == pytest.approx(previous.x2)
            assert current.y1 == pytest.approx(previous.y2)
        assert drawn[-1].x2 == pytest.approx(30)
        assert drawn[-1].y2 == pytest.approx(20)

    def test_partial_steps_keep_one_fixed_segment_start(self):
        plotter = VirtualPlotter()
        plotter.load_commands([
            pen_up(),
            move_to(10, 0, 100),
            pen_down(),
            draw_to(20, 0, 1),
            pen_up(),
        ])
        for _ in range(30):
            plotter.step(0.1)

        drawn = [segment for segment in plotter.segments if segment.is_draw]
        assert drawn
        assert drawn[0].x1 == pytest.approx(10)
        for previous, current in zip(drawn, drawn[1:]):
            assert current.x1 == pytest.approx(previous.x2)
