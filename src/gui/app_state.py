"""Application state model (Model in MVC).

Keeps track of the current recording/recognition lifecycle
and notifies listeners via Qt signals.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class AppPhase(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


class AppState(QObject):
    phase_changed = Signal(AppPhase)
    text_appended = Signal(str)
    status_message = Signal(str)
    elapsed_updated = Signal(str)
    level_updated = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._phase = AppPhase.IDLE
        self.model_name: str = ""
        self.last_elapsed: float = 0.0
        self.serial_connected: bool = False

    @property
    def phase(self) -> AppPhase:
        return self._phase

    @phase.setter
    def phase(self, value: AppPhase) -> None:
        if value != self._phase:
            self._phase = value
            self.phase_changed.emit(value)

    def append_text(self, text: str) -> None:
        self.text_appended.emit(text)

    def emit_status(self, msg: str) -> None:
        self.status_message.emit(msg)

    def emit_level(self, level: float) -> None:
        self.level_updated.emit(level)
