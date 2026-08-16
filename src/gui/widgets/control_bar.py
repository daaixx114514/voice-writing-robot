"""Desktop command rail for recording and trajectory controls."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
    QWidget,
)

from src.gui.app_state import AppPhase, AppState


class ControlBar(QFrame):
    """A compact, instrument-like command rail for the main workflow."""

    @property
    def device_selection(self) -> str:
        return self.device_combo.currentText()

    @property
    def device_index(self) -> int | None:
        selection = self.device_combo.currentText()
        if selection == "系统默认":
            return None
        if ":" in selection:
            try:
                return int(selection.split(":", 1)[0])
            except ValueError:
                return None
        return None

    @property
    def hotwords_text(self) -> str:
        return self._hotwords_input.text().strip()

    @property
    def trajectory_source(self) -> str:
        return str(self.trajectory_source_combo.currentData())

    @property
    def auto_simulate(self) -> bool:
        return self.auto_simulate_toggle.isChecked()

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlBar")
        self.setFixedWidth(320)
        self._state = state
        self._build_ui()
        self._configure_status_pulse()
        self._connect_signals()
        self._on_phase_changed(state.phase)

    def _configure_status_pulse(self) -> None:
        self._dot_effect = QGraphicsOpacityEffect(self._dot)
        self._dot.setGraphicsEffect(self._dot_effect)
        self._pulse = QPropertyAnimation(self._dot_effect, b"opacity", self)
        self._pulse.setDuration(900)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.28)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)

        brand = QLabel("VOICE · PLOT")
        brand.setObjectName("brandLabel")
        root.addWidget(brand)
        title = QLabel("声写机器人")
        title.setObjectName("titleLabel")
        root.addWidget(title)
        subtitle = QLabel("把中文语音转换为可执行的书写轨迹")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(10)
        self._dot = QLabel()
        self._dot.setObjectName("statusDot")
        status_layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignTop)
        status_copy = QVBoxLayout()
        status_copy.setSpacing(2)
        status_caption = QLabel("当前状态")
        status_caption.setObjectName("statusCaption")
        status_copy.addWidget(status_caption)
        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("statusText")
        self._status_label.setWordWrap(True)
        status_copy.addWidget(self._status_label)
        status_layout.addLayout(status_copy, 1)
        root.addWidget(status_card)

        root.addWidget(self._section_label("采集设置"))
        self.device_combo = self._build_device_combo()
        self.device_combo.setObjectName("deviceCombo")
        root.addWidget(self.device_combo)
        level_row = QHBoxLayout()
        level_label = QLabel("输入电平")
        level_label.setObjectName("fieldLabel")
        level_row.addWidget(level_label)
        self.level_meter = QProgressBar()
        self.level_meter.setObjectName("levelMeter")
        self.level_meter.setRange(0, 100)
        self.level_meter.setValue(0)
        self.level_meter.setFixedHeight(7)
        self.level_meter.setTextVisible(False)
        level_row.addWidget(self.level_meter, 1)
        root.addLayout(level_row)
        self._hotwords_input = QLineEdit()
        self._hotwords_input.setObjectName("hotwordsInput")
        self._hotwords_input.setPlaceholderText("热词：人名、术语，用逗号分隔")
        self._hotwords_input.setClearButtonEnabled(True)
        root.addWidget(self._hotwords_input)

        root.addWidget(self._section_label("轨迹模式"))
        self.trajectory_source_combo = QComboBox()
        self.trajectory_source_combo.setObjectName("trajectorySourceCombo")
        self.trajectory_source_combo.addItem("标准单线笔画 · 9,574 字", "single_line")
        self.trajectory_source_combo.addItem("字体轮廓", "font_outline")
        self.trajectory_source_combo.setToolTip("选择标准笔顺中线，或字体外轮廓")
        root.addWidget(self.trajectory_source_combo)

        display_row = QVBoxLayout()
        display_row.setSpacing(7)
        self.show_grid_toggle = QCheckBox("显示书写网格")
        self.show_grid_toggle.setObjectName("settingToggle")
        self.show_grid_toggle.setChecked(True)
        self.show_grid_toggle.setToolTip("显示或隐藏轨迹预览和模拟画布中的毫米网格")
        display_row.addWidget(self.show_grid_toggle)
        self.auto_simulate_toggle = QCheckBox("模拟后自动播放")
        self.auto_simulate_toggle.setObjectName("settingToggle")
        self.auto_simulate_toggle.setChecked(True)
        self.auto_simulate_toggle.setToolTip("生成机器人模拟后立即播放书写过程")
        display_row.addWidget(self.auto_simulate_toggle)
        root.addLayout(display_row)

        root.addWidget(self._section_label("操作"))
        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.start_btn = QPushButton("开始录音")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        actions.addWidget(self.start_btn, 0, 0, 1, 2)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        actions.addWidget(self.stop_btn, 1, 0)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("secondaryBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        actions.addWidget(self.clear_btn, 1, 1)
        self.preview_btn = QPushButton("生成轨迹")
        self.preview_btn.setObjectName("accentBtn")
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.setToolTip("根据当前文字生成书写轨迹")
        actions.addWidget(self.preview_btn, 2, 0)
        self.simulate_btn = QPushButton("运行模拟")
        self.simulate_btn.setObjectName("warmBtn")
        self.simulate_btn.setCursor(Qt.PointingHandCursor)
        self.simulate_btn.setToolTip("模拟机器人书写当前轨迹")
        actions.addWidget(self.simulate_btn, 2, 1)
        root.addLayout(actions)
        root.addStretch(1)
        hint = QLabel("建议先录音或直接编辑文字，随后生成轨迹并运行模拟。")
        hint.setObjectName("railHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def _connect_signals(self) -> None:
        self._state.phase_changed.connect(self._on_phase_changed)
        self._state.status_message.connect(self._on_status_message)
        self._state.level_updated.connect(self._on_level_updated)

    def _on_phase_changed(self, phase: AppPhase) -> None:
        if phase == AppPhase.IDLE:
            color, message = "#49D7B0", "就绪"
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self._pulse.stop()
            self._dot_effect.setOpacity(1.0)
        elif phase == AppPhase.RECORDING:
            color, message = "#FF6B72", "正在录音，请讲话…"
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self._pulse.start()
        else:
            color, message = "#FFBE5C", "正在识别语音…"
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self._pulse.start()
        self._dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self._status_label.setText(message)

    def _on_status_message(self, msg: str) -> None:
        translations = {
            "Waiting for speech...": "等待检测到语音…",
            "Speech detected - recording...": "检测到语音，正在录制…",
        }
        self._status_label.setText(translations.get(msg, msg))

    def _on_level_updated(self, level: float) -> None:
        self.level_meter.setValue(int(min(level * 200, 100)))

    @staticmethod
    def _build_device_combo() -> QComboBox:
        combo = QComboBox()
        combo.addItem("系统默认")
        try:
            from src.audio.audio_recorder import AudioRecorder
            for device in AudioRecorder.list_input_devices():
                combo.addItem(f'{device["index"]}: {device["name"]}')
        except Exception:
            pass
        return combo
