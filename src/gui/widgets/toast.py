"""Small non-blocking notifications for the desktop workspace."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class ToastNotification(QFrame):
    """An auto-dismissing status notification that never blocks the workflow."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setFixedWidth(350)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(9)
        self._marker = QLabel()
        self._marker.setObjectName("toastMarker")
        self._marker.setFixedSize(8, 8)
        layout.addWidget(self._marker, 0, Qt.AlignmentFlag.AlignTop)
        self._message = QLabel()
        self._message.setObjectName("toastMessage")
        self._message.setWordWrap(True)
        layout.addWidget(self._message, 1)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hide_when_finished = False
        self._animation.finished.connect(self._on_animation_finished)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

    def show_message(self, message: str, level: str = "info") -> None:
        colors = {
            "error": "#F17869",
            "success": "#66E4C3",
            "warning": "#E9C36B",
            "info": "#72D7E5",
        }
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)
        self._marker.setStyleSheet(
            f"background-color: {colors.get(level, colors['info'])}; border-radius: 4px;"
        )
        self._message.setText(message)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(3600)
        self._animation.stop()
        self._hide_when_finished = False
        self._animation.setStartValue(self._opacity.opacity())
        self._animation.setEndValue(1.0)
        self._animation.start()

    def reposition(self) -> None:
        self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(max(16, parent.width() - self.width() - 28), 24)

    def _fade_out(self) -> None:
        self._animation.stop()
        self._hide_when_finished = True
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.start()

    def _on_animation_finished(self) -> None:
        if self._hide_when_finished:
            self.hide()
