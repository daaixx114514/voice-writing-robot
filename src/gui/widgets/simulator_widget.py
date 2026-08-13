"""Virtual plotter simulator widget for PySide6.

Renders the VirtualPlotter state in real-time using QPainter.
Supports play / pause / stop / speed control.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF, QSignalBlocker
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollBar,
    QSlider, QVBoxLayout, QWidget,
)

from src.trajectory.config import MotionConfig
from src.trajectory.simulator import VirtualPlotter


# Colour palette
PAGE_BG = QColor("#ffffff")
GRID_COLOR = QColor("#e8e8e8")
DRAW_COLOR = QColor("#1a1a2e")
PEN_COLOR = QColor("#ef4444")
PEN_UP_COLOR = QColor("#f59e0b")


class SimulatorWidget(QFrame):
    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("simulatorWidget")
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumSize(400, 300)

        self._plotter = VirtualPlotter()
        self._scale = 2.0
        self._offset_x = 20.0
        self._offset_y = 20.0
        self._speed_factor = 1.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("primaryBtn")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self._on_play)
        toolbar.addWidget(self.play_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("secondaryBtn")
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)
        toolbar.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("secondaryBtn")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        toolbar.addWidget(self.stop_btn)

        toolbar.addSpacing(12)

        speed_label = QLabel("Speed:")
        speed_label.setObjectName("barLabel")
        toolbar.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        toolbar.addWidget(self.speed_slider)

        self.speed_value = QLabel("5x")
        self.speed_value.setObjectName("barValue")
        self.speed_value.setFixedWidth(30)
        toolbar.addWidget(self.speed_value)

        toolbar.addStretch()

        fit_btn = QPushButton("Fit")
        fit_btn.setObjectName("secondaryBtn")
        fit_btn.setCursor(Qt.PointingHandCursor)
        fit_btn.setToolTip("Fit to view")
        fit_btn.clicked.connect(lambda: self._canvas.zoom_fit())
        toolbar.addWidget(fit_btn)

        zo_btn = QPushButton("+")
        zo_btn.setObjectName("secondaryBtn")
        zo_btn.setCursor(Qt.PointingHandCursor)
        zo_btn.setToolTip("Zoom in (or scroll up)")
        zo_btn.clicked.connect(lambda: self._canvas.zoom_in())
        toolbar.addWidget(zo_btn)

        zi_btn = QPushButton("-")
        zi_btn.setObjectName("secondaryBtn")
        zi_btn.setCursor(Qt.PointingHandCursor)
        zi_btn.setToolTip("Zoom out (or scroll down)")
        zi_btn.clicked.connect(lambda: self._canvas.zoom_out())
        toolbar.addWidget(zi_btn)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("barLabel")
        toolbar.addWidget(self.progress_label)

        layout.addLayout(toolbar)

        # Canvas
        canvas_layout = QGridLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        self._canvas = _PlotterCanvas(self._plotter, self)
        self._h_scroll = QScrollBar(Qt.Orientation.Horizontal, self)
        self._v_scroll = QScrollBar(Qt.Orientation.Vertical, self)
        self._h_scroll.setToolTip("Move simulation horizontally")
        self._v_scroll.setToolTip("Move simulation vertically")
        self._h_scroll.valueChanged.connect(self._on_horizontal_scroll)
        self._v_scroll.valueChanged.connect(self._on_vertical_scroll)
        self._canvas.navigation_changed.connect(self._sync_scrollbars)

        canvas_layout.addWidget(self._canvas, 0, 0)
        canvas_layout.addWidget(self._v_scroll, 0, 1)
        canvas_layout.addWidget(self._h_scroll, 1, 0)
        layout.addLayout(canvas_layout, stretch=1)
        self._sync_scrollbars()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_commands(self, commands, config=None):
        self._on_stop()
        self._plotter = VirtualPlotter(config)
        self._canvas._plotter = self._plotter
        self._plotter.load_commands(commands)
        self._canvas.zoom_fit()
        self._canvas.update()
        self._update_progress()
        # Auto-start so user sees the simulation immediately.
        self._on_play()

    def reset(self):
        self._on_stop()
        self._plotter.reset()
        self._canvas.update()
        self._update_progress()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_play(self):
        if self._plotter.finished:
            self._plotter.reset()
        if self._plotter.finished and self._plotter.total_commands == 0:
            return
        self._timer.start(16)  # ~60 fps
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

    def _on_pause(self):
        self._timer.stop()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

    def _on_stop(self):
        self._timer.stop()
        self._plotter.reset()
        self._canvas.update()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._update_progress()

    def _on_speed_changed(self, value):
        self._speed_factor = value
        self.speed_value.setText(f"{value}x")

    def _tick(self):
        dt = 0.016 * self._speed_factor
        has_more = self._plotter.step(dt)
        self._canvas.update()
        self._update_progress()
        if not has_more:
            self._timer.stop()
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.finished.emit()

    def _update_progress(self):
        total = self._plotter.total_commands
        idx = self._plotter.current_command_index
        if total > 0:
            self.progress_label.setText(f"{idx}/{total}")
        else:
            self.progress_label.setText("")

    def _on_horizontal_scroll(self, value):
        self._canvas.set_scroll_position(x=value)

    def _on_vertical_scroll(self, value):
        self._canvas.set_scroll_position(y=value)

    def _sync_scrollbars(self):
        range_x, range_y, value_x, value_y = self._canvas.navigation_state()
        with QSignalBlocker(self._h_scroll), QSignalBlocker(self._v_scroll):
            self._h_scroll.setRange(0, range_x)
            self._v_scroll.setRange(0, range_y)
            self._h_scroll.setPageStep(max(1, self._canvas.width()))
            self._v_scroll.setPageStep(max(1, self._canvas.height()))
            self._h_scroll.setValue(value_x)
            self._v_scroll.setValue(value_y)
        self._h_scroll.setEnabled(range_x > 0)
        self._v_scroll.setEnabled(range_y > 0)


class _PlotterCanvas(QFrame):
    navigation_changed = Signal()

    def __init__(self, plotter: VirtualPlotter, parent=None):
        super().__init__(parent)
        self._plotter = plotter
        self.setMinimumSize(300, 200)
        self.setMouseTracking(True)
        self._zoom = 1.0          # user zoom multiplier
        self._pan_x = 0.0          # pan offset in mm
        self._pan_y = 0.0
        self._last_mouse = None    # for pan tracking

    def zoom_in(self):
        self._zoom_at(1.25, self.rect().center())

    def zoom_out(self):
        self._zoom_at(1.0 / 1.25, self.rect().center())

    def zoom_fit(self):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.navigation_changed.emit()
        self.update()

    def navigation_state(self):
        cfg = self._plotter._cfg
        scale = self._base_scale() * self._zoom
        page_w = cfg.work_width_mm * scale
        page_h = cfg.work_height_mm * scale
        range_x = max(0, int(round(page_w - self.width() + 40.0)))
        range_y = max(0, int(round(page_h - self.height() + 40.0)))
        pan_px_x = self._pan_x * scale
        pan_px_y = self._pan_y * scale
        value_x = max(0, min(range_x, int(round(range_x / 2.0 - pan_px_x))))
        value_y = max(0, min(range_y, int(round(range_y / 2.0 - pan_px_y))))
        return (range_x, range_y, value_x, value_y)

    def set_scroll_position(self, x=None, y=None):
        scale = self._base_scale() * self._zoom
        range_x, range_y, value_x, value_y = self.navigation_state()
        if range_x > 0:
            target_x = max(0, min(range_x, x if x is not None else value_x))
            self._pan_x = (range_x / 2.0 - target_x) / scale
        if range_y > 0:
            target_y = max(0, min(range_y, y if y is not None else value_y))
            self._pan_y = (range_y / 2.0 - target_y) / scale
        self.update()

    def _normalize_navigation(self):
        scale = self._base_scale() * self._zoom
        range_x, range_y, value_x, value_y = self.navigation_state()
        self._pan_x = (range_x / 2.0 - value_x) / scale if range_x else 0.0
        self._pan_y = (range_y / 2.0 - value_y) / scale if range_y else 0.0
        self.navigation_changed.emit()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self._zoom_at(1.25 if delta > 0 else 1.0 / 1.25, event.position())
            event.accept()

    def _base_scale(self) -> float:
        cfg = self._plotter._cfg
        sx = (self.width() - 40) / cfg.work_width_mm if cfg.work_width_mm > 0 else 2.0
        sy = (self.height() - 40) / cfg.work_height_mm if cfg.work_height_mm > 0 else 2.0
        return max(0.01, min(sx, sy))

    def _zoom_at(self, factor: float, anchor) -> None:
        old_zoom = self._zoom
        new_zoom = max(0.1, min(20.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return
        scale_before = self._base_scale() * old_zoom
        scale_after = self._base_scale() * new_zoom
        anchor = QPointF(anchor)
        cfg = self._plotter._cfg
        old_ox = (self.width() - cfg.work_width_mm * scale_before) / 2.0
        old_oy = (self.height() - cfg.work_height_mm * scale_before) / 2.0
        world_x = (anchor.x() - old_ox) / scale_before - self._pan_x
        world_y = (anchor.y() - old_oy) / scale_before - self._pan_y
        self._zoom = new_zoom
        new_ox = (self.width() - cfg.work_width_mm * scale_after) / 2.0
        new_oy = (self.height() - cfg.work_height_mm * scale_after) / 2.0
        self._pan_x = (anchor.x() - new_ox) / scale_after - world_x
        self._pan_y = (anchor.y() - new_oy) / scale_after - world_y
        self._normalize_navigation()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_mouse = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_mouse = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self._last_mouse is not None:
            delta = event.position() - self._last_mouse
            self._last_mouse = event.position()
            cfg = self._plotter._cfg
            base_scale = self._base_scale() * self._zoom
            self._pan_x += delta.x() / base_scale
            self._pan_y += delta.y() / base_scale
            self._normalize_navigation()
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._normalize_navigation()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QBrush(QColor("#f5f5f5")))

        cfg = self._plotter._cfg
        ww, wh = cfg.work_width_mm, cfg.work_height_mm

        # Compute base scale to fit.
        base = self._base_scale()
        scale = base * self._zoom
        ox = (self.width() - ww * scale) / 2.0 + self._pan_x * scale
        oy = (self.height() - wh * scale) / 2.0 + self._pan_y * scale

        # Page background.
        pw, ph = ww * scale, wh * scale
        page_rect = QRectF(ox, oy, pw, ph)
        painter.fillRect(page_rect, PAGE_BG)
        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.drawRect(page_rect)

        # Grid.
        grid_spacing = 10.0 * scale
        if grid_spacing >= 20:
            painter.save()
            painter.setClipRect(page_rect)
            painter.setPen(QPen(GRID_COLOR, 0.5))
            gx = ox
            while gx < ox + pw:
                painter.drawLine(QPointF(gx, oy), QPointF(gx, oy + ph))
                gx += grid_spacing
            gy = oy
            while gy < oy + ph:
                painter.drawLine(QPointF(ox, gy), QPointF(ox + pw, gy))
                gy += grid_spacing
            painter.restore()

        # Translate to work origin, apply pan and zoom.
        painter.save()
        # Motion coordinates are Cartesian (origin bottom-left, Y-up), while
        # Qt uses a top-left origin with Y-down. Flip only for screen display.
        painter.translate(ox, oy + ph)
        painter.scale(scale, -scale)
        painter.setClipRect(QRectF(0.0, 0.0, ww, wh))

        # Drawn segments.
        draw_pen = QPen(DRAW_COLOR, 0.3)
        draw_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        draw_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        for seg in self._plotter.segments:
            if not seg.is_draw:
                continue
            painter.setPen(draw_pen)
            painter.drawLine(QPointF(seg.x1, seg.y1), QPointF(seg.x2, seg.y2))

        # Pen position.
        pen = self._plotter.pen
        pen_r = 2.0 / scale if scale > 0 else 2.0
        pen_color = PEN_COLOR if pen.is_down else PEN_UP_COLOR
        painter.setBrush(QBrush(pen_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(
            pen.x - pen_r, pen.y - pen_r, pen_r * 2, pen_r * 2,
        ))

        painter.restore()
        painter.end()
