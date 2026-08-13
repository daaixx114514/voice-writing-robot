"""Main window assembling all UI widgets and the recording pipeline."""

from __future__ import annotations

from dataclasses import replace
import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout, QWidget

from src.audio.audio_recorder import AudioRecorder
from src.glyph import (
    HanziWriterData,
    LayoutConfig,
    LayoutEngine,
    SingleLineLayoutEngine,
    build_trajectory,
    get_chinese_fonts,
    load_font,
)
from src.gui.app_state import AppPhase, AppState
from src.gui.widgets.control_bar import ControlBar
from src.gui.widgets.result_panel import ResultPanel
from src.gui.widgets.simulator_widget import SimulatorWidget
from src.gui.widgets.status_bar import StatusBar
from src.stt.speech_recognizer import SpeechRecognizer
from src.utils.config import load_audio_config, load_stt_config
from src.trajectory.config import MotionConfig
from src.trajectory.coordinate import CoordinateTransformer
from src.trajectory.motion import trajectory_to_commands
from src.trajectory.processor import TrajectoryProcessor


class MainWindow(QMainWindow):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = AppState(self)
        self._stop_event = threading.Event()
        self._cancel_transcriber = False
        self._worker: threading.Thread | None = None
        self._recorder: AudioRecorder | None = None
        self._recognizer: SpeechRecognizer | None = None
        self._glyph_engine: LayoutEngine | None = None
        self._single_line_engine: SingleLineLayoutEngine | None = None
        self._last_trajectory = None

        self._build_ui()
        self._connect_signals()
        self._load_models()

    @property
    def state(self) -> AppState:
        return self._state

    # ------------------------------------------------------------------
    # UI assembly
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("Voice Writing Robot")
        self.resize(900, 600)
        self.setMinimumSize(640, 420)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.control_bar = ControlBar(self._state)
        layout.addWidget(self.control_bar)

        self.result_panel = ResultPanel(self._state)
        layout.addWidget(self.result_panel, stretch=1)

        self.simulator_widget = SimulatorWidget()
        self.simulator_widget.setMaximumHeight(300)
        layout.addWidget(self.simulator_widget)

        self.bottom_bar = StatusBar(self._state)
        layout.addWidget(self.bottom_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.control_bar.start_btn.clicked.connect(self._on_start)
        self.control_bar.stop_btn.clicked.connect(self._on_stop)
        self.control_bar.clear_btn.clicked.connect(self._on_clear)
        self.control_bar.preview_btn.clicked.connect(self._on_preview)
        self.control_bar.simulate_btn.clicked.connect(self._on_simulate)
        self.control_bar.trajectory_source_combo.currentIndexChanged.connect(
            self._on_trajectory_source_changed
        )
        self._state.status_message.connect(self._on_status_message)
        self._state.elapsed_updated.connect(self.bottom_bar.elapsed_value.setText)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        try:
            config_path = Path("config/stt.yaml")
            audio_cfg = load_audio_config(config_path)
            stt_cfg = load_stt_config(config_path)
            self._recorder = AudioRecorder(audio_cfg)
            self._recognizer = SpeechRecognizer(stt_cfg)
            self.set_model_info(f"faster-whisper {stt_cfg.model_size}")

            # Lazy-init glyph engine — will be created on first preview.
            self._init_glyph_engine()

        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load models:\n{exc}")

    def _init_glyph_engine(self) -> None:
        """Initialize glyph layout engine with preferred Chinese font.

        To change font: edit the ``preferred`` list below (lowercase).
        Run ``python demo_glyph.py --list-fonts`` to see all 41 choices.
        NOTE: ``demo_glyph.py`` has its own preferred list — keep them in sync.
        """
        config = LayoutConfig(
            char_size=14.0,
            page_width=148,
            page_height=210,
            use_skeleton=False,
        )
        try:
            self._single_line_engine = SingleLineLayoutEngine(
                HanziWriterData(), config,
            )
        except Exception:
            self._single_line_engine = None

        try:
            fonts = get_chinese_fonts()
            if not fonts:
                self.set_serial_status(False)
                return

            # fmt: off
            preferred = ["stxingka", "stkaiti", "simkai", "simsun", "msyh"]
            # fmt: on
            font_path = None
            for name in preferred:
                for f in fonts:
                    if name in f.name.lower():
                        font_path = f.path
                        break
                if font_path:
                    break
            if font_path is None:
                font_path = fonts[0].path

            font = load_font(font_path)
            self._glyph_engine = LayoutEngine(font, config)
            self.set_model_info(
                f"faster-whisper {self._recognizer.config.model_size if self._recognizer else '?'}"
                f"  |  {font_path.stem}"
            )
        except Exception:
            self._glyph_engine = None

    # ------------------------------------------------------------------
    # Recording lifecycle
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        if self._recorder is None or self._recognizer is None:
            return
        device_idx = self.control_bar.device_index
        if device_idx is not None:
            self._recorder.config = replace(self._recorder.config, device=device_idx)
        self._stop_event.clear()
        self._cancel_transcriber = False
        self._state.phase = AppPhase.RECORDING
        self._worker = threading.Thread(target=self._record_and_transcribe, daemon=True)
        self._worker.start()

    def _on_stop(self) -> None:
        self._stop_event.set()
        self._cancel_transcriber = True

    def _on_clear(self) -> None:
        self.result_panel.clear()
        self._last_trajectory = None
        self.simulator_widget.reset()

    def _on_preview(self) -> None:
        """Generate and display the writing trajectory for the recognized text."""
        text = self.result_panel.get_text()
        if not text:
            self._state.emit_status("No text to preview — record or type some text first.")
            return
        try:
            source = self.control_bar.trajectory_source
            if source == "single_line":
                if self._single_line_engine is None:
                    self._state.emit_status("Single-line stroke data is not available.")
                    return
                trajectory = build_trajectory(self._single_line_engine, text)
                missing = self._single_line_engine.missing_characters
            else:
                if self._glyph_engine is None:
                    self._state.emit_status("Font outline engine is not available.")
                    return
                trajectory = build_trajectory(self._glyph_engine, text)
                missing = []

            if not trajectory.glyphs:
                self._state.emit_status("No supported characters were found in this text.")
                return
            self.result_panel.show_trajectory(trajectory)
            if missing:
                missing_text = "".join(missing[:8])
                suffix = "..." if len(missing) > 8 else ""
                self._state.emit_status(
                    f"Preview ready; missing single-line data: {missing_text}{suffix}"
                )
            else:
                mode = "single-line" if source == "single_line" else "outline"
                self._state.emit_status(
                    f"Preview ({mode}): {len(trajectory.glyphs)} chars, "
                    f"~{len(trajectory.points)} points"
                )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._state.emit_status(f"Preview failed: {exc}")
            return
        self._last_trajectory = trajectory

    def _on_trajectory_source_changed(self) -> None:
        self._last_trajectory = None
        self.result_panel.preview.clear()
        self.simulator_widget.reset()
        self._state.emit_status("Trajectory source changed. Generate a new preview.")

    def _on_simulate(self) -> None:
        if self._last_trajectory is None:
            self._state.emit_status("No trajectory to simulate. Preview first.")
            return
        try:
            traj = self._last_trajectory
            cfg = MotionConfig(
                work_width_mm=200,
                work_height_mm=280,
                flip_x=False,
                flip_y=True,
                min_point_distance=0.02,
                simplify_tolerance=0.03,
            )
            processor = TrajectoryProcessor(cfg)
            transformer = CoordinateTransformer(cfg)
            transformer.fit_bounds(traj.page_width_mm, traj.page_height_mm)
            cleaned = processor.process(traj.points)
            transformed = transformer.transform(cleaned)
            commands = trajectory_to_commands(transformed, cfg)
            self.simulator_widget.load_commands(commands, cfg)
            self._state.emit_status(
                f"Simulation: {len(commands)} commands, {len(cleaned)} points"
            )
        except Exception as exc:
            self._state.emit_status(f"Simulation error: {exc}")

    def set_enable_debug(self, flag: bool) -> None:
        """Enable/disable debug traceback printing for all background ops."""
        self._debug = flag

    def _on_status_message(self, msg: str) -> None:
        # Status updates flow directly from AppState signal to ControlBar
        # (connected in ControlBar._connect_signals).  This slot is a
        # deliberate no-op — re-emitting here would create a signal loop.
        pass

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _record_and_transcribe(self) -> None:
        assert self._recorder is not None
        assert self._recognizer is not None

        def on_status(msg: str) -> None:
            self._state.emit_status(msg)

        def on_level(level: float) -> None:
            self._state.emit_level(level)

        try:
            t0 = time.monotonic()
            audio = self._recorder.listen_once(on_status=on_status, on_level=on_level, stop_event=self._stop_event)
            if audio.size == 0:
                return
            self._state.phase = AppPhase.TRANSCRIBING
            if self._cancel_transcriber:
                return
            text = self._recognizer.transcribe(audio, hotwords=self.control_bar.hotwords_text)
            if self._cancel_transcriber:
                return
            elapsed = time.monotonic() - t0
            if text:
                self._state.append_text(text)
            self.show_idle(elapsed)
        except Exception as exc:
            self._state.append_text(f"[Error] {exc}")
            self.show_idle()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def show_transcribing(self) -> None:
        self._state.phase = AppPhase.TRANSCRIBING

    def show_idle(self, duration_s: float = 0.0) -> None:
        self._state.phase = AppPhase.IDLE
        self._state.last_elapsed = duration_s
        self._state.elapsed_updated.emit(f"{duration_s:.2f} s")

    def set_model_info(self, name: str) -> None:
        self._state.model_name = name
        self.bottom_bar.model_value.setText(name)

    def set_serial_status(self, connected: bool) -> None:
        self._state.serial_connected = connected
        self.bottom_bar.serial_value.setText("Connected" if connected else "Disconnected")

    def closeEvent(self, event) -> None:
        self._stop_event.set()
        super().closeEvent(event)
