"""Bottom status bar with model info, timing, and serial status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QWidget

from src.gui.app_state import AppState


class StatusBar(QFrame):

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomBar")
        self._state = state
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        # Model name
        self._add_item(layout, "识别模型", "")
        self.model_value = self._last_value(layout)

        # Elapsed time
        self._add_item(layout, "耗时", "0.00 s")
        self.elapsed_value = self._last_value(layout)

        layout.addStretch()

        # Serial status (reserved)
        self._add_item(layout, "机器人连接", "未连接")
        self.serial_value = self._last_value(layout)

    @staticmethod
    def _add_item(layout: QHBoxLayout, label_text: str, value_text: str) -> None:
        label = QLabel(label_text)
        label.setObjectName("barLabel")
        layout.addWidget(label)

        value = QLabel(value_text)
        value.setObjectName("barValue")
        layout.addWidget(value)

    @staticmethod
    def _last_value(layout: QHBoxLayout) -> QLabel:
        item = layout.itemAt(layout.count() - 1)
        return item.widget()  # type: ignore[return-value]
