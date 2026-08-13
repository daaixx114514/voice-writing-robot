"""Center result area with tabbed view — recognized text + trajectory preview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFrame, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from src.gui.app_state import AppState
from src.gui.widgets.glyph_preview import GlyphPreviewWidget


class ResultPanel(QFrame):

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resultPanel")
        self._state = state
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("resultTabs")

        # Tab 1 — Recognized text
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("resultArea")
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("Recognized text will appear here...")
        self._tabs.addTab(self.text_edit, "文本")

        # Tab 2 — Writing trajectory preview
        self.preview = GlyphPreviewWidget()
        self._tabs.addTab(self.preview, "轨迹预览")

        layout.addWidget(self._tabs)

    def _connect_signals(self) -> None:
        self._state.text_appended.connect(self._on_text_appended)

    def _on_text_appended(self, text: str) -> None:
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.text_edit.toPlainText():
            cursor.insertText("\n")
        cursor.insertText(text)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def clear(self) -> None:
        self.text_edit.clear()
        self.preview.clear()

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def show_trajectory(
        self,
        trajectory,  # WritingTrajectory
    ) -> None:
        """Load and display a WritingTrajectory in the preview tab."""
        self.preview.set_trajectory(trajectory)
        self._tabs.setCurrentWidget(self.preview)
