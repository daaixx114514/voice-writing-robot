"""Compact glyph trajectory preview widget for embedding in the GUI.

Wraps TrajectoryPreviewWidget with a lightweight toolbar (font selector,
Zoom buttons) so it fits cleanly inside the result-panel tab.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollBar,
    QGridLayout,
    QVBoxLayout,
    QWidget,
)

from src.glyph.preview import TrajectoryPreviewWidget
from src.glyph.trajectory import WritingTrajectory


class GlyphPreviewWidget(QWidget):
    """Embeddable widget: toolbar + zoomable trajectory canvas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._trajectory: WritingTrajectory | None = None
        self._build_ui()

    # ── public API ──────────────────────────────────────────────────────

    def set_trajectory(self, trajectory: WritingTrajectory) -> None:
        """Display a WritingTrajectory and populate font info."""
        self._trajectory = trajectory
        self._canvas.set_trajectory(trajectory)
        # Update font label (optional, for user info).
        self._font_label.setText(
            f"{len(trajectory.glyphs)} chars, "
            f"{len(trajectory.points)} pts"
        )

    def clear(self) -> None:
        """Clear the canvas (no trajectory to show)."""
        self._trajectory = None
        self._canvas.clear()
        self._font_label.setText("暂无轨迹")

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._font_label = QLabel("暂无轨迹")
        self._font_label.setObjectName("barLabel")
        toolbar.addWidget(self._font_label)

        toolbar.addStretch()

        fit_btn = QPushButton("适应")
        fit_btn.setObjectName("secondaryBtn")
        fit_btn.setCursor(Qt.PointingHandCursor)
        fit_btn.setToolTip("适应完整页面")
        fit_btn.clicked.connect(self._on_zoom_fit)
        toolbar.addWidget(fit_btn)

        zo_btn = QPushButton("放大")
        zo_btn.setObjectName("secondaryBtn")
        zo_btn.setCursor(Qt.PointingHandCursor)
        zo_btn.setToolTip("放大（也可使用鼠标滚轮）")
        zo_btn.clicked.connect(self._on_zoom_in)
        toolbar.addWidget(zo_btn)

        zi_btn = QPushButton("缩小")
        zi_btn.setObjectName("secondaryBtn")
        zi_btn.setCursor(Qt.PointingHandCursor)
        zi_btn.setToolTip("缩小（也可使用鼠标滚轮）")
        zi_btn.clicked.connect(self._on_zoom_out)
        toolbar.addWidget(zi_btn)

        layout.addLayout(toolbar)

        # ── Canvas ────────────────────────────────────────────────────
        canvas_layout = QGridLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        self._canvas = TrajectoryPreviewWidget(self)
        self._h_scroll = QScrollBar(Qt.Orientation.Horizontal, self)
        self._v_scroll = QScrollBar(Qt.Orientation.Vertical, self)
        self._h_scroll.setToolTip("Move preview horizontally")
        self._v_scroll.setToolTip("Move preview vertically")
        self._h_scroll.valueChanged.connect(self._on_horizontal_scroll)
        self._v_scroll.valueChanged.connect(self._on_vertical_scroll)
        self._canvas.navigation_changed.connect(self._sync_scrollbars)

        canvas_layout.addWidget(self._canvas, 0, 0)
        canvas_layout.addWidget(self._v_scroll, 0, 1)
        canvas_layout.addWidget(self._h_scroll, 1, 0)
        layout.addLayout(canvas_layout, stretch=1)
        self._sync_scrollbars()

    # ── slots ───────────────────────────────────────────────────────────

    def _on_zoom_in(self) -> None:
        self._canvas.zoom_in()

    def _on_zoom_out(self) -> None:
        self._canvas.zoom_out()

    def _on_zoom_fit(self) -> None:
        self._canvas.zoom_fit()

    def _on_horizontal_scroll(self, value: int) -> None:
        self._canvas.set_scroll_position(x=value)

    def _on_vertical_scroll(self, value: int) -> None:
        self._canvas.set_scroll_position(y=value)

    def _sync_scrollbars(self) -> None:
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
