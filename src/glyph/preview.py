"""Qt widget for previewing writing trajectories.

Renders glyph paths as QPainterPath objects using the PySide6 QPainter API.
Integrates seamlessly with the existing PySide6 GUI.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from src.glyph.trajectory import GlyphPath, Point2D, WritingTrajectory


# ── colour palette ──────────────────────────────────────────────────────

PEN_COLOUR = QColor("#333333")
PEN_UP_COLOUR = QColor("#cccccc")
PAGE_BG = QColor("#ffffff")
GRID_COLOUR = QColor("#e8e8e8")
MARGIN_COLOUR = QColor("#eeeeee")


class TrajectoryPreviewWidget(QFrame):
    """A scrollable, zoomable canvas for previewing writing trajectories.

    Usage::

        preview = TrajectoryPreviewWidget()
        preview.set_trajectory(trajectory)
    """

    navigation_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._min_scale = 0.1
        self._max_scale = 50.0
        self._trajectory: WritingTrajectory | None = None
        self._scale = 2.0          # pixels per mm (default zoom)
        self._offset_x = 0.0       # pan offset in widget pixels
        self._offset_y = 0.0
        self._last_mouse: QPointF | None = None
        self._fit_to_view = True
        self._show_pen_up = False   # toggle pen-up travel lines
        self._show_grid = True

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(300, 400)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMouseTracking(True)

    # ── public API ──────────────────────────────────────────────────────

    def set_trajectory(self, trajectory: WritingTrajectory) -> None:
        """Set the trajectory to render and repaint."""
        self._trajectory = trajectory
        self.zoom_fit()

    def clear(self) -> None:
        """Clear the current trajectory and reset the view."""
        self._trajectory = None
        self._fit_to_view = True
        self._offset_x = 0.0
        self._offset_y = 0.0
        self.navigation_changed.emit()
        self.update()

    def set_show_pen_up(self, visible: bool) -> None:
        """Show or hide pen-up travel lines."""
        self._show_pen_up = visible
        self.update()

    def set_show_grid(self, visible: bool) -> None:
        self._show_grid = visible
        self.update()

    def zoom_in(self) -> None:
        self._zoom_at(1.2, self.rect().center())

    def zoom_out(self) -> None:
        self._zoom_at(1.0 / 1.2, self.rect().center())

    def zoom_fit(self) -> None:
        """Reset zoom and center the full page in the available view."""
        if self._trajectory is None:
            return
        page_w = self._trajectory.page_width_mm
        page_h = self._trajectory.page_height_mm
        if page_w <= 0 or page_h <= 0:
            return
        available_w = max(1.0, self.width() - 40.0)
        available_h = max(1.0, self.height() - 40.0)
        self._scale = min(available_w / page_w, available_h / page_h)
        self._scale = max(self._min_scale, min(self._max_scale, self._scale))
        self._offset_x = (self.width() - page_w * self._scale) / 2.0
        self._offset_y = (self.height() - page_h * self._scale) / 2.0
        self._fit_to_view = True
        self.navigation_changed.emit()
        self.update()

    def navigation_state(self) -> tuple[int, int, int, int]:
        """Return horizontal/vertical ranges and current scrollbar values."""
        if self._trajectory is None:
            return (0, 0, 0, 0)
        page_w = self._trajectory.page_width_mm * self._scale
        page_h = self._trajectory.page_height_mm * self._scale
        range_x = max(0, int(round(page_w - self.width() + 40.0)))
        range_y = max(0, int(round(page_h - self.height() + 40.0)))
        value_x = max(0, min(range_x, int(round(20.0 - self._offset_x))))
        value_y = max(0, min(range_y, int(round(20.0 - self._offset_y))))
        return (range_x, range_y, value_x, value_y)

    def set_scroll_position(self, x: int | None = None, y: int | None = None) -> None:
        """Move the page using values supplied by external scrollbars."""
        range_x, range_y, value_x, value_y = self.navigation_state()
        if range_x > 0:
            self._offset_x = 20.0 - max(0, min(range_x, x if x is not None else value_x))
        if range_y > 0:
            self._offset_y = 20.0 - max(0, min(range_y, y if y is not None else value_y))
        if range_x > 0 or range_y > 0:
            self._fit_to_view = False
        self.update()

    def _normalize_navigation(self) -> None:
        if self._trajectory is None:
            self.navigation_changed.emit()
            return
        page_w = self._trajectory.page_width_mm * self._scale
        page_h = self._trajectory.page_height_mm * self._scale
        range_x, range_y, value_x, value_y = self.navigation_state()
        self._offset_x = 20.0 - value_x if range_x else (self.width() - page_w) / 2.0
        self._offset_y = 20.0 - value_y if range_y else (self.height() - page_h) / 2.0
        self.navigation_changed.emit()

    def _zoom_at(self, factor: float, anchor) -> None:
        if self._trajectory is None or self._scale <= 0:
            return
        anchor = QPointF(anchor)
        old_scale = self._scale
        new_scale = max(
            self._min_scale,
            min(self._max_scale, old_scale * factor),
        )
        if new_scale == old_scale:
            return
        page_x = (anchor.x() - self._offset_x) / old_scale
        page_y = (anchor.y() - self._offset_y) / old_scale
        self._scale = new_scale
        self._offset_x = anchor.x() - page_x * new_scale
        self._offset_y = anchor.y() - page_y * new_scale
        self._fit_to_view = False
        self._normalize_navigation()
        self.update()

    # ── Qt painting ─────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background.
        painter.fillRect(self.rect(), QBrush(QColor("#f5f5f5")))

        if self._trajectory is None:
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无轨迹数据"
            )
            return

        # Draw the page.
        pw = self._trajectory.page_width_mm * self._scale
        ph = self._trajectory.page_height_mm * self._scale
        page_rect = QRectF(self._offset_x, self._offset_y, pw, ph)
        painter.fillRect(page_rect, PAGE_BG)
        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.drawRect(page_rect)

        # Grid.
        if self._show_grid:
            self._draw_grid(painter, page_rect)

        # Set up clipping to page area.
        painter.save()
        painter.setClipRect(page_rect)

        # Translate page origin.
        painter.translate(self._offset_x, self._offset_y)

        # Scale mm → pixels.
        painter.scale(self._scale, self._scale)

        # Draw all glyphs.
        pen_pen = QPen(PEN_COLOUR, 0.25)
        pen_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        for glyph in self._trajectory.glyphs:
            for contour in glyph.contours:
                if len(contour) < 2:
                    continue
                path = self._contour_to_qpainterpath(contour)
                painter.setPen(pen_pen)
                painter.drawPath(path)

        # Pen-up travel lines.
        if self._show_pen_up:
            up_pen = QPen(PEN_UP_COLOUR, 0.1)
            up_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(up_pen)
            up_path = self._pen_up_to_qpainterpath()
            if up_path:
                painter.drawPath(up_path)

        painter.restore()
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_to_view and self._trajectory is not None:
            self.zoom_fit()
        elif self._trajectory is not None:
            self._normalize_navigation()

    def _draw_grid(self, painter: QPainter, page_rect: QRectF) -> None:
        """Draw light grid lines every 10 mm."""
        if self._trajectory is None:
            return
        grid_spacing = 10.0 * self._scale  # 10 mm in pixels
        if grid_spacing < 20:
            return  # too zoomed out, skip grid

        painter.save()
        painter.setClipRect(page_rect)
        pen = QPen(GRID_COLOUR, 0.5)
        painter.setPen(pen)

        x = page_rect.left()
        while x < page_rect.right():
            painter.drawLine(
                QPointF(x, page_rect.top()),
                QPointF(x, page_rect.bottom()),
            )
            x += grid_spacing

        y = page_rect.top()
        while y < page_rect.bottom():
            painter.drawLine(
                QPointF(page_rect.left(), y),
                QPointF(page_rect.right(), y),
            )
            y += grid_spacing

        painter.restore()

    @staticmethod
    def _contour_to_qpainterpath(contour: list[Point2D]) -> QPainterPath:
        """Convert a single contour into a QPainterPath."""
        path = QPainterPath()
        if not contour:
            return path
        path.moveTo(QPointF(contour[0].x, contour[0].y))
        for pt in contour[1:]:
            path.lineTo(QPointF(pt.x, pt.y))
        return path

    def _pen_up_to_qpainterpath(self) -> QPainterPath | None:
        """Build a QPainterPath of all pen-up transitions."""
        if self._trajectory is None or not self._trajectory.points:
            return None

        path = QPainterPath()
        started = False
        for sp in self._trajectory.points:
            if sp.state.name == "UP":
                if not started:
                    path.moveTo(QPointF(sp.point.x, sp.point.y))
                    started = True
                else:
                    path.lineTo(QPointF(sp.point.x, sp.point.y))
            else:
                started = False
        return path if path.elementCount() > 0 else None

    # ── mouse interaction ───────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        """Zoom around the mouse cursor with the wheel."""
        delta = event.angleDelta().y()
        if delta:
            self._zoom_at(1.2 if delta > 0 else 1.0 / 1.2, event.position())
            event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_mouse = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_mouse = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Pan with middle mouse button (drag)."""
        if self._last_mouse is None:
            return
        delta = event.position() - self._last_mouse
        self._last_mouse = event.position()
        self._offset_x += delta.x()
        self._offset_y += delta.y()
        self._fit_to_view = False
        self._normalize_navigation()
        self.update()
        event.accept()


class TrajectoryPreviewWindow(QFrame):
    """A convenience container that wraps TrajectoryPreviewWidget with a toolbar.

    Can be embedded in the existing main_window.py or used standalone.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview = TrajectoryPreviewWidget(self)
        layout.addWidget(self.preview)

    def set_trajectory(self, trajectory: WritingTrajectory) -> None:
        self.preview.set_trajectory(trajectory)

    def zoom_in(self) -> None:
        self.preview.zoom_in()

    def zoom_out(self) -> None:
        self.preview.zoom_out()

    def zoom_fit(self) -> None:
        self.preview.zoom_fit()
