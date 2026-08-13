# PROJECT_CONTEXT

## 1. Project Goal

Voice Writing Robot — a desktop application that converts spoken Chinese into written text for eventual output to an XY plotter (handwriting robot).

Target pipeline:

```text
Microphone -> Silero VAD -> faster-whisper STT -> Chinese text
                                                     |
                 (future) text normalizer -> glyph paths -> G-code -> Arduino/STM32
```

Current phase: speech recognition MVP is fully functional with a PySide6 desktop GUI.

## 2. Development Environment

- OS: Windows 11
- Python: 3.11.9
- CPU: Intel i5-12450H (8 cores / 12 threads)
- GPU: NONE — no CUDA
- All inference runs CPU + int8
- Virtual env at: `.venv`

## 3. Current Technical Route

### VAD (Voice Activity Detection)

- Library: `silero-vad` PyPI package (NOT `torch.hub`)
- Loading: `silero_vad.load_silero_vad(onnx=False)`
- Sample rate: 16000 Hz (Silero VAD analysis block)
- Fallback: if microphone does not support 16 kHz, automatically uses device default rate and numpy resamples to 16 kHz
- Speech threshold: 0.3 (lowered from 0.5 for easier detection)

### STT (Speech-to-Text)

- Library: `faster-whisper`
- Model: `small` (better accuracy than base; ~1-2 GB first download)
- Device: `cpu`, compute type: `int8`, cpu_threads: `4`
- Language: `zh`
- Accuracy / speed balance:
  - `beam_size: 5` (retained for Chinese homophone disambiguation)
  - `best_of: 2` (reduced from 5 — ~2× speedup; 3 decodes: 1 greedy + 2 temperature samples)
  - `temperature: [0.0, 0.2, 0.4]` (trimmed from 6 values to 3)
  - `repetition_penalty: 1.1`
  - `no_speech_threshold: 0.6`
  - `compression_ratio_threshold: 2.4`
  - `vad_filter: False` (VAD already done during recording)

### Name / jargon accuracy enhancements

- **hotwords** support via `faster-whisper` native `hotwords` parameter — user fills a text field before recording; terms are passed to decoder for token-level bias
- **`initial_prompt`** now in Chinese, with embedded common name-character list to softly bias the decoder toward name-typical glyphs

### Post-processing

- `zhconv` (pure Python) converts traditional Chinese characters to simplified

### Audio capture

- `sounddevice.InputStream` — float32, mono
- Configurable block_size (default 512 samples at 16 kHz = 32 ms)
- Audio callback is kept lightweight; VAD runs in the main recording loop

## 4. Completed Work

- Microphone device enumeration
- Real-time audio capture via sounddevice
- Silero VAD speech endpoint detection (auto start/stop)
- faster-whisper Chinese transcription with balanced speed/accuracy
- Traditional-to-simplified Chinese conversion (zhconv)
- PySide6 desktop GUI with MVC architecture
- GUI status indicator (Idle/Recording/Transcribing with color dots)
- Microphone device selector in GUI
- Bottom status bar: model name, elapsed time, serial status (reserved)
- Recording level meter (QProgressBar) showing real-time RMS during capture
- Single-shot recording model: click Start, speak, text appears, ready for next
- Thread-safe background recording with stop_event interrupt
- Auto sample-rate fallback for devices that do not support 16 kHz
- Transcription phase is now cancellable (Stop button stays enabled during TRANSCRIBING)
- Hotwords input field for decoder biasing (names, jargon)
- Config-driven parameters (`config/stt.yaml` + typed dataclasses)
- CLI entry point preserved: `python -m src.main --once`
- Batch launcher: `run.bat` (double-click from desktop)
- Unit tests: 17 tests covering resample, VAD probability, device enumeration, config validation, and STT boundaries
- Text-to-writing-trajectory module (`src/glyph/`) with 15 additional unit tests
  - fontTools-based glyph outline extraction from TTF fonts
  - Quadratic Bezier → polyline flattening (recursive de Casteljau)
  - Text layout engine with auto line-wrapping
  - SVG vector export
  - PySide6 `TrajectoryPreviewWidget` for GUI preview
  - CLI demo: `python demo_glyph.py "文字" --font STXINGKA`
- Motion control layer (`src/trajectory/`) with 10 unit tests
  - Machine-agnostic `MotionCommand` model (PEN_UP/PEN_DOWN/MOVE/DRAW)
  - `CoordinateTransformer`: page coord → machine coord (flip Y, scale, translate)
  - `TrajectoryProcessor`: dedup, merge close points, Douglas-Peucker simplify, bounds check
  - `VirtualPlotter`: step-driven pen-plotter simulator
  - GUI: `SimulatorWidget` with Play/Pause/Stop, speed slider (1x–20x), real-time canvas
- G-code exporter (`src/trajectory/exporters/gcode.py`) with 5 unit tests
  - GRBL-compatible: G0/G1/M3 S1/M5
  - Configurable write/travel speed, mm/min or mm/s
- Simulator integration tests (4 tests): load/step, segments, reset, speed override
- **Total: 51 unit tests, all passing**
- Font: STXINGKA (华文行楷) — changed from simkai; both GUI and CLI use lowercase name matching
- Writing quality pass (2026-08-13):
  - GUI now uses the original STXINGKA vector outlines by default; bitmap skeletonization remains optional
  - TrueType quadratic curves use standard implied on-curve midpoint decomposition
  - Closed font contours retain their final closing segment
  - Motion simplification defaults reduced to 0.02 mm point spacing / 0.03 mm tolerance
  - Preview and simulator support wheel zoom, centered button zoom, fit-to-page, and middle-button pan
  - Machine coordinates expose independent `flip_x` / `flip_y`; simulator converts Y-up to Qt Y-down only while painting
- **Total: 63 unit tests, all passing**
- Single-line stroke provider (2026-08-13):
  - Offline Hanzi Writer Data 2.0.1 integration with 9,574 characters
  - Standard stroke order from each character's ordered `medians` arrays
  - `SingleLineLayoutEngine` maps the official 1024-unit coordinates to page-space millimeters
  - Corner-aware Hermite interpolation improves curved strokes without changing stroke boundaries
  - GUI trajectory source selector defaults to `Single-line strokes`; `Font outlines` remains available
  - Missing single-line characters are reported explicitly and never silently replaced by outlines
  - Upstream archive, SHA-256, source notice, derivative builder, and Arphic Public License are included under `data/hanzi_writer/`

## 5. Current Code Structure

```text
voice-writing-robot/
├── PROJECT_CONTEXT.md
├── README.md
├── requirements.txt
├── run.bat                    # double-click launcher
├── run.ps1
├── config/
│   └── stt.yaml               # all runtime parameters (audio + stt)
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point (preserved)
│   ├── audio/
│   │   ├── __init__.py
│   │   └── audio_recorder.py  # Mic + Silero VAD + sample-rate fallback + level callback
│   ├── stt/
│   │   ├── __init__.py
│   │   └── speech_recognizer.py # faster-whisper + zhconv + hotwords support
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main.py              # PySide6 entry point + logging.basicConfig
│   │   ├── main_window.py       # Main window: assembles views + wiring (Controller)
│   │   ├── app_state.py         # Model: AppPhase, signals (incl. level_updated, elapsed_updated)
│   │   ├── app.py               # Old tkinter GUI (deprecated, kept for reference)
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── control_bar.py   # Title, status dot, buttons, mic selector, level meter, hotwords input
│   │   │   ├── result_panel.py  # Tabbed: text area + trajectory preview
│   │   │   ├── simulator_widget.py  # Virtual plotter: Play/Pause/Stop + speed slider
│   │   │   ├── glyph_preview.py # Embedded trajectory preview widget
│   │   │   └── status_bar.py    # Bottom: model / elapsed / serial
│   │   └── styles/
│   │       └── style.qss         # Global QSS stylesheet (incl. level meter + hotwords input)
│   ├── glyph/
│   │   ├── __init__.py            # Public API + build_trajectory()
│   │   ├── trajectory.py          # Point2D, StrokePoint, GlyphPath, WritingTrajectory
│   │   ├── bezier.py             # Quadratic Bezier → polyline flattening
│   │   ├── font_manager.py       # System font discovery (Windows/macOS/Linux)
│   │   ├── glyph_extractor.py   # fontTools RecordingPen → polyline contours
│   │   ├── layout_engine.py     # Text layout with auto line-wrapping
│   │   ├── preview.py           # PySide6 TrajectoryPreviewWidget
│   │   └── svg_export.py        # SVG vector export (page-scale + debug)
│   ├── trajectory/
│   │   ├── __init__.py            # motion control layer public API
│   │   ├── config.py              # MotionConfig: work area, speeds, simplify params
│   │   ├── models.py              # MotionCommand: PEN_UP/DOWN/MOVE/DRAW
│   │   ├── coordinate.py          # CoordinateTransformer: Y-flip, scale, translate
│   │   ├── processor.py           # TrajectoryProcessor: dedup, merge, Doug-Peucker
│   │   ├── motion.py              # StrokePoint → MotionCommand converter
│   │   ├── simulator.py           # VirtualPlotter: step-driven pen-plotter engine
│   │   └── exporters/
│   │       ├── __init__.py
│   │       └── gcode.py           # GRBL-compatible G-code export
│   └── utils/
│       ├── __init__.py
│       └── config.py            # YAML -> AudioConfig / SttConfig loader
├── demo_glyph.py                 # CLI demo: text → SVG writing trajectory
└── tests/
    ├── test_imports.py
    ├── test_audio.py            # resample, VAD prob, device enum, config validation
    ├── test_stt.py              # SttConfig defaults, transcribe boundary conditions
    ├── test_glyph.py            # Point2D, Bezier flatten, trajectory building, PenState
    ├── test_trajectory.py       # coordinate, motion, processor, bounds, full pipeline
    └── test_exporter.py         # G-code export, VirtualPlotter step/segment/reset/speed
```

## 6. MVC Architecture (GUI)

- **Model**: `app_state.py` — `AppState(QObject)` with signals: `phase_changed`, `text_appended`, `status_message`, `elapsed_updated`, `level_updated`
- **View**: `control_bar.py`, `result_panel.py`, `status_bar.py` — pure QWidget subclasses, no business logic
- **Controller**: `main_window.py` — connects button clicks, manages background recording thread, dispatches to model

Recording lifecycle:

```text
User clicks Start
-> main_window._on_start()
-> phase = RECORDING (red dot, level meter active)
-> background thread: recorder.listen_once(stop_event, on_status, on_level)
   -> status messages emitted via AppState.status_message
   -> RMS level emitted via AppState.level_updated (100 ms throttle)
   -> on speech end: phase = TRANSCRIBING (yellow dot, Stop enabled)
   -> recognizer.transcribe(audio, hotwords=...)
   -> text appended via AppState.text_appended
   -> elapsed time emitted via AppState.elapsed_updated (thread-safe)
   -> phase = IDLE (green dot)
```

## 7. Current Config (config/stt.yaml)

```yaml
audio:
  sample_rate: 16000
  channels: 1
  block_size: 512
  speech_threshold: 0.3
  start_padding_ms: 300
  silence_duration_ms: 1200       # raised from 900ms for natural Chinese pauses
  min_speech_duration_ms: 400
  max_record_seconds: 20
  device: null

stt:
  model_size: small
  device: cpu
  compute_type: int8
  language: zh
  beam_size: 5
  best_of: 2                      # reduced from 5 for ~2x speedup
  temperature: [0.0, 0.2, 0.4]    # trimmed from 6 values
  repetition_penalty: 1.1
  no_speech_threshold: 0.6
  compression_ratio_threshold: 2.4
  cpu_threads: 4                  # leverages i5 multi-core
  initial_prompt: "以下是中文语音识别。说话内容可能包含中国人名、地名、机构名称和专业术语。请使用常见姓名用字，如：伟、芳、建国、志强、小明、秀英、李明、王红、张华、刘洋、陈静、赵刚、孙丽、周杰、吴鑫。一律输出简体中文。"
```

## 8. Requirements

```text
faster-whisper>=1.0.0,<2.0.0
sounddevice>=0.4.6,<0.5.0
numpy>=1.24.0,<2.0.0
torch>=2.2.0,<3.0.0
torchaudio>=2.2.0,<3.0.0
silero-vad>=6.0.0,<7.0.0
PyYAML>=6.0.1,<7.0.0
zhconv>=1.4.0,<2.0.0
PySide6>=6.6.0,<7.0.0
pytest (dev)
```

## 9. Problems Encountered And Solutions

### Problem 1: `webrtcvad` install failed on Windows
- Cause: C extension needs MSVC build tools
- Solution: replaced with `silero-vad` pure Python/PyTorch package

### Problem 2: `torch.hub` GitHub API 403 rate limit
- Error: `HTTP Error 403: rate limit exceeded` + `KeyError: 'Authorization'`
- Solution: migrated from `torch.hub.load("snakers4/silero-vad")` to `silero_vad.load_silero_vad()` from the `silero-vad` PyPI package

### Problem 3: Silero torch hub cache missing `silero_vad.jit`
- Cause: incomplete GitHub zip download via torch.hub
- Solution: same as Problem 2 — switched to PyPI package

### Problem 4: faster-whisper first run appears hung
- Cause: downloading model from Hugging Face (small model ~1-2 GB)
- Solution: kept `small` model, improved status messages

### Problem 5: Windows Hugging Face symlink warning
- Symptoms: `cache-system uses symlinks by default...`
- Not an error; suppressed with `HF_HUB_DISABLE_SYMLINKS_WARNING=1`

### Problem 6: Traditional Chinese characters in output
- Cause: faster-whisper training data contains both simplified and traditional
- Solution: added `zhconv` for post-processing + Chinese-language `initial_prompt`

### Problem 7: Microphone sample rate not supported (-9997)
- Error: `Invalid sample rate [PaErrorCode -9997]`
- Solution: `listen_once()` tries 16 kHz first, falls back to device default rate, resamples to 16 kHz via numpy `interp`

### Problem 8: Second recording after first fails
- Cause: continuous loop + thread race condition
- Solution: switched to single-shot recording model + `threading.Event` for clean interrupt

### Problem 9: PySide6 `QTextCursor.End` AttributeError
- Error: `'PySide6.QtGui.QTextCursor' object has no attribute 'End'`
- Solution: `QTextCursor.MoveOperation.End` (PySide6 enum syntax)

### Problem 10: `show_idle()` called from background thread
- Cause: `elapsed_value.setText()` directly touched widget from non-GUI thread
- Solution: added `elapsed_updated` signal; `show_idle()` emits it instead; Qt marshalls to GUI thread

### Problem 11: Transcription could not be cancelled
- Cause: Stop button was disabled during TRANSCRIBING phase
- Solution: Stop stays enabled; `_cancel_transcriber` flag checked before/after `transcribe()`

### Problem 12: `dataclasses.__dict__` hack for frozen config
- Cause: `AudioConfig` is frozen; device change needed manual dict manipulation
- Solution: `dataclasses.replace(config, device=idx)`

### Problem 13: Low-quality or distorted handwriting paths
- Cause: GUI enabled low-resolution bitmap skeletonization by default, and consecutive TrueType off-curve points were paired incorrectly
- Solution: preserve original vector outlines by default and use fontTools quadratic decomposition with implied on-curve midpoints

### Problem 14: Preview zoom ineffective and simulated text appeared mirrored
- Cause: preview only fitted page width, required Ctrl+wheel, and had no pan state; machine Y-up coordinates were painted directly in Qt's Y-down canvas
- Solution: add cursor-centered wheel zoom, fit-to-page, middle-button pan, and a display-only Y-axis conversion in the simulator

### Problem 15: Font outlines are not single-line handwriting strokes
- Cause: TrueType fonts describe filled boundaries and contain neither centerline trajectories nor standard stroke order
- Solution: integrate Hanzi Writer Data `medians` as the default source; each ordered median is one machine-executable pen-down stroke

### Problem 16: Simulated strokes fan out from one fixed point
- Cause: `VirtualPlotter` did not advance the start position after completing each `DRAW`/`MOVE`, and motion generation lowered the pen before travelling to the first stroke point
- Solution: use standard plotter polyline semantics (`PEN_UP -> MOVE stroke start -> PEN_DOWN -> adjacent DRAW points`), advance every command endpoint, and hide pen-up travel traces in normal simulation

### Problem 17: Zoomed preview and simulation could not be moved precisely
- Cause: both canvases supported middle-button panning but exposed no persistent navigation controls or visible content range
- Solution: add synchronized horizontal and vertical scrollbars to Preview and Simulate; scrollbar dragging, middle-button panning, wheel zoom, resize, and Fit now share one navigation state

## 10. How To Run

First-time setup:

```powershell
cd "D:\My Code\voice-writing-robot"
.\.venv\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Then:

- **GUI**: double-click `run.bat`
- **CLI**: `python -m src.main --once`
- **Tests**: `python -m pytest tests/ -v`

## 11. Important Notes For Future AI Models

- **NO CUDA**. This machine has Intel i5-12450H with no dedicated GPU. Always use `device: cpu`, `compute_type: int8`.
- **Do NOT reintroduce `webrtcvad`**. VAD is handled by `silero-vad` PyPI package.
- **Do NOT use `torch.hub` for Silero VAD**. Use `from silero_vad import load_silero_vad`.
- **Default model is `small`**, not `base`. If download is too slow, mention switching to `base` in `config/stt.yaml`.
- **`listen_once()` has sample-rate fallback**. If 16 kHz fails, it falls back to device default and resamples. The `AudioRecorder.__init__` no longer enforces 16 kHz.
- **The GUI is single-shot**: each click of "Start" records one utterance. This avoids the thread race condition that existed in the continuous-loop version.
- **`stop_event` threading.Event** is used to interrupt blocking `listen_once()` calls. Always pass it through.
- **`_cancel_transcriber` flag** is checked before and after `transcribe()` to allow user to abort during transcription.
- **`zhconv` handles trad-to-simplified**. It runs inside `SpeechRecognizer.transcribe()` automatically.
- **GUI MVC separation**: Model (`app_state.py`), View (widgets/), Controller (`main_window.py`). Business logic should go in `main_window.py` or new controller files; widgets should stay pure presentation.
- **Thread safety**: All widget mutations from background threads must go through Qt signals. The `elapsed_updated` signal is the pattern to follow.
- **Old tkinter GUI** (`src/gui/app.py`) is deprecated but kept for reference.
- **CLI entry point** (`src/main.py`) is preserved and still functional.
- **`logging` module** is used throughout (not `print()`). `logging.basicConfig` is set up in both `src/gui/main.py` and `src/main.py`.
- **Configuration**: use `dataclasses.replace()` for modifying frozen dataclass fields; never `__dict__` manipulation.
- The STT module should only output text. Future serial/Arduino control should consume text through a separate module.
- **Hotwords** are passed as a raw string from the GUI input field to `model.transcribe(hotwords=...)`. `faster-whisper` handles the tokenization internally.
- **`cpu_threads: 4`** is set on `WhisperModel` to leverage the i5-12450H's multi-core capability. Adjust if running on different hardware.

## 12. Next Steps

1. ~~Implement glyph/stroke path generation for handwriting robot~~ ✅ DONE — `src/glyph/` module
2. ~~Integrate trajectory preview into GUI~~ ✅ DONE — Preview button + tabbed result panel
3. ~~Implement motion control layer~~ ✅ DONE — `src/trajectory/` (models, coordinate, processor, motion)
4. ~~Implement virtual plotter simulator~~ ✅ DONE — `SimulatorWidget` with Play/Pause/Stop
5. ~~Implement G-code exporter~~ ✅ DONE — `src/trajectory/exporters/gcode.py`
6. Add model pre-download script so first run does not appear hung
7. Add text normalizer module (whitespace, punctuation, numbers, English mixing)
8. Evaluate name accuracy in real use; if hotwords + prompt are insufficient, implement post-processing name correction module (pypinyin + name frequency table)
9. Serial communication module (pyserial) + connect GUI serial status indicator
10. Arduino/STM32 firmware for XY plotter control
11. ~~Integrate a stroke-order single-line dataset~~ DONE - Hanzi Writer Data 2.0.1
12. Add GUI controls for `flip_x` / `flip_y` before physical hardware calibration
13. Calibrate interpolation and write speed against the physical pen mechanism
