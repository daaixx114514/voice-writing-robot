# Voice Writing Robot - Speech Recognition Module

[English](README.md) | [简体中文](README.zh-CN.md)

This module is designed for Windows 11, Python 3.10/3.11, Intel i5-12450H, and no dedicated GPU.

Default runtime:

```text
Microphone -> Silero VAD -> faster-whisper -> Chinese text
```

CUDA is not required. The default STT config is CPU + int8.

## 1. New Technical Plan

### Audio Capture

The microphone is opened through `sounddevice.InputStream`.

Runtime flow:

```text
Windows microphone
-> 16 kHz mono float32 audio blocks
-> Python queue
-> Silero VAD
```

The callback only copies audio blocks into a queue. Model inference runs outside the callback, which keeps audio capture stable and avoids buffer overflow.

### Silero VAD

Silero VAD replaces `webrtcvad`.

Workflow:

```text
512-sample audio block
-> torch tensor
-> Silero VAD model
-> speech probability
-> threshold decision
```

Default threshold:

```yaml
speech_threshold: 0.5
```

Recording logic:

```text
Wait for speech
-> keep short pre-roll audio
-> start recording when speech probability exceeds threshold
-> stop after continuous silence
-> return valid speech segment
```

### faster-whisper

The recorder returns `numpy.ndarray` audio:

```text
sample_rate: 16000
dtype: float32
range: -1.0 to 1.0
channels: mono
```

`SpeechRecognizer.transcribe(audio)` sends this directly to faster-whisper and returns Chinese text.

Default config:

```yaml
stt:
  model_size: base
  device: cpu
  compute_type: int8
  language: zh
```

For better accuracy on CPU, change `model_size` to `small`. The first download will be larger and slower.

### Data Format Conversion

```text
sounddevice float32 block
-> numpy.ndarray, shape=(512,)
-> torch.Tensor for Silero VAD
-> numpy.ndarray full utterance for faster-whisper
-> str Chinese text
```

## 2. Project Structure

```text
voice-writing-robot/
├─ requirements.txt
├─ README.md
├─ config/
│  └─ stt.yaml
├─ src/
│  ├─ main.py
│  ├─ audio/
│  │  ├─ __init__.py
│  │  └─ audio_recorder.py
│  ├─ stt/
│  │  ├─ __init__.py
│  │  └─ speech_recognizer.py
│  └─ utils/
│     ├─ __init__.py
│     └─ config.py
└─ tests/
   └─ test_imports.py
```

## 3. requirements.txt

Current dependencies:

```text
faster-whisper  Local offline STT.
sounddevice     Microphone capture.
numpy           Audio buffers and PCM conversion.
torch           Silero VAD CPU inference.
torchaudio      PyTorch audio companion package; installed from official wheel.
PyYAML          YAML config loading.
```

`webrtcvad` has been removed because it commonly needs local C/C++ compilation on Windows.

Silero VAD is loaded from the `silero-vad` PyPI package. The code no longer uses `torch.hub`, so it does not depend on GitHub zip downloads at runtime.

## 4. Core Files

- `src/audio/audio_recorder.py`: microphone streaming and Silero VAD speech endpoint detection.
- `src/stt/speech_recognizer.py`: faster-whisper model loading and Chinese transcription.
- `src/main.py`: command-line test program.
- `config/stt.yaml`: CPU-friendly runtime parameters.

## 5. Run on Windows

Create and activate a virtual environment:

```powershell
cd "D:\My Code\voice-writing-robot"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install CPU PyTorch wheels first:

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Install the remaining dependencies:

```powershell
pip install -r requirements.txt
```

List microphone devices:

```powershell
python -m src.main --list-devices
```

Recognize one utterance:

```powershell
python -m src.main --once
```

Continuous recognition:

```powershell
python -m src.main
```

The Silero VAD model is provided by the `silero-vad` Python package. The first STT run may still download the faster-whisper model. After the faster-whisper model is cached, the module can run offline.

## 6. Windows Troubleshooting

### `webrtcvad` install failed

This is expected in the old architecture. The new architecture no longer uses `webrtcvad`.

Run:

```powershell
pip uninstall webrtcvad
pip install -r requirements.txt
```

### `Error querying device`

The microphone index is wrong or the device is unavailable.

Run:

```powershell
python -m src.main --list-devices
```

Then set the selected index in `config/stt.yaml`:

```yaml
audio:
  device: 1
```

### `PortAudioError`

Common causes:

- Windows microphone permission is disabled.
- Another application is using the microphone.
- The selected device does not support 16 kHz input.

Fixes:

- Enable microphone permission for desktop apps in Windows Settings.
- Close voice chat or recording software.
- Try another microphone device index.

### `torch.hub` Silero download failed

The current code no longer uses `torch.hub`. If you saw an error such as:

```text
silero_vad.jit: No such file or directory
```

install the updated dependency:

```powershell
pip install silero-vad
```

The old corrupted cache under `%USERPROFILE%\.cache\torch\hub` can be ignored because this project no longer loads Silero from that path.


### Recognition is slow

For Intel i5-12450H CPU:

```yaml
stt:
  model_size: base
  device: cpu
  compute_type: int8
```

Use `small` for better accuracy, `base` for lower latency and easier first setup.

## 7. Future Arduino/STM32 Interface

The current output should remain a clean text event, not a serial command.

Recommended interface:

```python
@dataclass
class RecognizedText:
    text: str
    language: str = "zh"
    source: str = "microphone"
    confidence: float | None = None
```

Future pipeline:

```text
RecognizedText
-> text normalizer
-> text layout
-> glyph/stroke path generator
-> motion planner
-> serial protocol
-> Arduino/STM32
```

Keep STT independent from the writing mechanism. The speech module should only output verified Chinese text; the trajectory and machine-control modules should consume that text through a simple function or queue.

## 8. Single-Line Chinese Trajectories

The GUI defaults to `Single-line strokes`. This source uses the ordered stroke
medians from Hanzi Writer Data rather than tracing both sides of a font outline.
It supports 9,574 simplified/traditional characters offline and preserves pen
lift boundaries between strokes.

```python
from src.glyph import HanziWriterData, LayoutConfig, SingleLineLayoutEngine
from src.glyph import build_trajectory

engine = SingleLineLayoutEngine(
    HanziWriterData(),
    LayoutConfig(char_size=14.0, page_width=148, page_height=210),
)
trajectory = build_trajectory(engine, "\u4f60\u597d")
```

The original archive and Arphic Public License are stored in
`data/hanzi_writer/`. Rebuild the compact runtime index with:

```powershell
python scripts/build_hanzi_writer_index.py
```

## 9. Third-Party Software and Data

This project builds on open-source work from other authors. In particular, the
single-line Chinese stroke provider redistributes data from
[Hanzi Writer Data](https://github.com/chanind/hanzi-writer-data) under the
Arphic Public License. The repository includes both the upstream archive and a
modified runtime derivative containing the ordered `medians` arrays.

Speech recognition, VAD, GUI, font processing, and numeric processing are
provided by independently licensed packages including faster-whisper, Silero
VAD, PySide6, fontTools, NumPy, PyTorch, and others listed in
`requirements.txt`.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
`data/hanzi_writer/ARPHICPL.TXT` for source links, modification details, and
license information. System fonts used at runtime are not distributed with
this project.
