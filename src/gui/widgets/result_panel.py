"""Editable transcription and trajectory workspace."""

from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from src.gui.app_state import AppState
from src.gui.widgets.glyph_preview import GlyphPreviewWidget


class ResultPanel(QFrame):
    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resultPanel")
        self._state = state
        self._build_ui()
        self._state.text_appended.connect(self._on_text_appended)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel("文字与轨迹")
        title.setObjectName("panelTitle")
        copy.addWidget(title)
        subtitle = QLabel("识别结果可直接修改；确认后生成机器人书写路径")
        subtitle.setObjectName("panelSubtitle")
        copy.addWidget(subtitle)
        header.addLayout(copy)
        header.addStretch()
        copy_btn = QPushButton("复制文字")
        copy_btn.setObjectName("quietBtn")
        copy_btn.clicked.connect(self._copy_text)
        header.addWidget(copy_btn)
        layout.addLayout(header)
        self._tabs = QTabWidget()
        self._tabs.setObjectName("resultTabs")
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("resultArea")
        self.text_edit.setPlaceholderText("点击“开始录音”说话，或者在这里直接输入需要书写的文字…")
        self._tabs.addTab(self.text_edit, "识别文字")
        self.preview = GlyphPreviewWidget()
        self._tabs.addTab(self.preview, "轨迹预览")
        layout.addWidget(self._tabs, 1)

    def _copy_text(self) -> None:
        text = self.get_text()
        if text:
            QApplication.clipboard().setText(text)
            self._state.emit_status("文字已复制到剪贴板")

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
        self._state.emit_status("工作区已清空")

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def show_trajectory(self, trajectory) -> None:
        self.preview.set_trajectory(trajectory)
        self._tabs.setCurrentWidget(self.preview)

    def set_grid_visible(self, visible: bool) -> None:
        self.preview.set_grid_visible(visible)
