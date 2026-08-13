"""Offscreen tests for preview and simulator scroll navigation."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from src.glyph.trajectory import WritingTrajectory
from src.gui.widgets.glyph_preview import GlyphPreviewWidget
from src.gui.widgets.simulator_widget import SimulatorWidget
from src.trajectory.config import MotionConfig
from src.trajectory.models import draw_to, move_to, pen_down, pen_up


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_preview_scrollbars_enable_after_zoom_and_move_canvas():
    app = _app()
    widget = GlyphPreviewWidget()
    widget.resize(640, 480)
    widget.show()
    widget.set_trajectory(WritingTrajectory(
        text="x", page_width_mm=148, page_height_mm=210,
    ))
    app.processEvents()
    assert widget._h_scroll.maximum() == 0
    assert widget._v_scroll.maximum() == 0

    for _ in range(8):
        widget._canvas.zoom_in()
    app.processEvents()
    assert widget._h_scroll.maximum() > 0
    assert widget._v_scroll.maximum() > 0

    widget._h_scroll.setValue(widget._h_scroll.maximum())
    widget._v_scroll.setValue(widget._v_scroll.maximum())
    assert widget._canvas._offset_x < 20
    assert widget._canvas._offset_y < 20


def test_simulator_scrollbars_enable_after_zoom_and_move_canvas():
    app = _app()
    widget = SimulatorWidget()
    widget.resize(640, 480)
    widget.show()
    widget.load_commands([
        pen_up(), move_to(10, 10, 50), pen_down(),
        draw_to(80, 60, 20), pen_up(),
    ], MotionConfig(work_width_mm=100, work_height_mm=80))
    widget._timer.stop()
    app.processEvents()
    assert widget._h_scroll.maximum() == 0
    assert widget._v_scroll.maximum() == 0

    for _ in range(6):
        widget._canvas.zoom_in()
    app.processEvents()
    assert widget._h_scroll.maximum() > 0
    assert widget._v_scroll.maximum() > 0

    widget._h_scroll.setValue(widget._h_scroll.maximum())
    widget._v_scroll.setValue(widget._v_scroll.maximum())
    assert widget._canvas._pan_x < 0
    assert widget._canvas._pan_y < 0
