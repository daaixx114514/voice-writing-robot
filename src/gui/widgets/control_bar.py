"""Top control bar with title, status indicator and action buttons."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.app_state import AppPhase, AppState


class ControlBar(QFrame):

    # Public so MainWindow can read the current device selection.
    @property
    def device_selection(self) -> str:
        return self.device_combo.currentText()

    @property
    def device_index(self) -> int | None:
        """Parse '0: Microphone ...' -> 0, or 'default' -> None."""
        sel = self.device_combo.currentText()
        if sel == "default":
            return None
        if ":" in sel:
            try:
                return int(sel.split(":")[0])
            except ValueError:
                return None
        return None

    @property
    def hotwords_text(self) -> str:
        """Comma/semicolon/space-separated terms for decoder bias."""
        return self._hotwords_input.text().strip()

    @property
    def trajectory_source(self) -> str:
        """Return ``single_line`` or ``font_outline``."""
        return str(self.trajectory_source_combo.currentData())

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlBar")
        self._state = state
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # --- Row 1: title + status ---
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Voice Writing Robot")
        title.setObjectName("titleLabel")
        row1.addWidget(title)

        row1.addStretch()

        self._dot = QLabel()
        self._dot.setObjectName("statusDot")
        row1.addWidget(self._dot)

        self._status_label = QLabel("Idle")
        self._status_label.setObjectName("statusText")
        row1.addWidget(self._status_label)

        root.addLayout(row1)

        # --- Row 2: buttons ---
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)

        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("secondaryBtn")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        row2.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondaryBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.clear_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setObjectName("secondaryBtn")
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.setToolTip("Generate and show writing trajectory for recognized text")
        row2.addWidget(self.preview_btn)

        self.simulate_btn = QPushButton("Simulate")
        self.simulate_btn.setObjectName("secondaryBtn")
        self.simulate_btn.setCursor(Qt.PointingHandCursor)
        self.simulate_btn.setToolTip("Simulate pen writing the current trajectory")
        row2.addWidget(self.simulate_btn)

        row2.addStretch()
        root.addLayout(row2)

        source_row = QHBoxLayout()
        source_row.setContentsMargins(0, 0, 0, 0)
        source_label = QLabel("Trajectory source:")
        source_label.setObjectName("statusText")
        source_row.addWidget(source_label)

        self.trajectory_source_combo = QComboBox()
        self.trajectory_source_combo.setObjectName("trajectorySourceCombo")
        self.trajectory_source_combo.addItem("Single-line strokes", "single_line")
        self.trajectory_source_combo.addItem("Font outlines", "font_outline")
        self.trajectory_source_combo.setToolTip("Select standard stroke medians or font contours")
        source_row.addWidget(self.trajectory_source_combo)

        source_info = QLabel("9,574 chars")
        source_info.setObjectName("statusText")
        source_info.setToolTip("Offline single-line data with standard stroke order")
        source_row.addWidget(source_info)
        source_row.addStretch()
        root.addLayout(source_row)

        # Microphone selector row (added for real recording support)
        mic_row = QHBoxLayout()
        mic_row.setContentsMargins(0, 0, 0, 0)
        mic_label = QLabel("Microphone:")
        mic_label.setObjectName("statusText")
        mic_row.addWidget(mic_label)
        self.device_combo = self._build_device_combo()
        mic_row.addWidget(self.device_combo)
        mic_row.addStretch()

        # Level meter
        self.level_meter = QProgressBar()
        self.level_meter.setObjectName("levelMeter")
        self.level_meter.setMinimum(0)
        self.level_meter.setMaximum(100)
        self.level_meter.setValue(0)
        self.level_meter.setFixedWidth(120)
        self.level_meter.setFixedHeight(8)
        self.level_meter.setTextVisible(False)
        mic_row.addWidget(self.level_meter)

        root.addLayout(mic_row)

        # Hotwords row — decoder biasing for names / jargon
        hw_row = QHBoxLayout()
        hw_row.setContentsMargins(0, 0, 0, 0)
        hw_label = QLabel("Hotwords:")
        hw_label.setObjectName("statusText")
        hw_row.addWidget(hw_label)
        self._hotwords_input = QLineEdit()
        self._hotwords_input.setObjectName("hotwordsInput")
        self._hotwords_input.setPlaceholderText("e.g. 张三, 李建国, 术语A")
        self._hotwords_input.setClearButtonEnabled(True)
        hw_row.addWidget(self._hotwords_input)
        hw_row.addStretch()
        root.addLayout(hw_row)

    def _connect_signals(self) -> None:
        self._state.phase_changed.connect(self._on_phase_changed)
        self._state.status_message.connect(self._on_status_message)
        self._state.level_updated.connect(self._on_level_updated)

    def _on_phase_changed(self, phase: AppPhase) -> None:
        if phase == AppPhase.IDLE:
            self._dot.setStyleSheet("background-color: #10B981; border-radius: 5px;")
            self._status_label.setText("Idle")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        elif phase == AppPhase.RECORDING:
            self._dot.setStyleSheet("background-color: #EF4444; border-radius: 5px;")
            self._status_label.setText("Recording")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        elif phase == AppPhase.TRANSCRIBING:
            self._dot.setStyleSheet("background-color: #F59E0B; border-radius: 5px;")
            self._status_label.setText("Transcribing")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

    def _on_status_message(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_level_updated(self, level: float) -> None:
        # Map raw RMS (0.0 – ~0.5 typical speech) to 0-100 gauge
        gauge = int(min(level * 200, 100))
        self.level_meter.setValue(gauge)

    @staticmethod
    def _build_device_combo() -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(260)
        combo.addItem("default")
        try:
            from src.audio.audio_recorder import AudioRecorder
            for d in AudioRecorder.list_input_devices():
                combo.addItem(f'{d["index"]}: {d["name"]}')
        except Exception:
            pass
        return combo
