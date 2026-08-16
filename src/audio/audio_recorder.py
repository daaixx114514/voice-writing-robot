from __future__ import annotations

import collections
import io
import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    block_size: int = 512
    speech_threshold: float = 0.5
    start_padding_ms: int = 300
    silence_duration_ms: int = 900
    min_speech_duration_ms: int = 400
    max_record_seconds: float = 20.0
    device: Optional[int | str] = None


class AudioRecorder:

    def __init__(self, config: AudioConfig, on_status: Callable[[str], None] | None = None) -> None:
        if config.channels != 1:
            raise ValueError("Only mono microphone input is supported.")
        if config.block_size <= 0:
            raise ValueError("block_size must be greater than 0.")
        self.config = config
        self.on_status = on_status
        self.vad_model = self._load_silero_vad()

    @staticmethod
    def list_input_devices() -> list[dict]:
        devices = []
        for index, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                devices.append({
                    "index": index,
                    "name": device["name"],
                    "default_samplerate": device["default_samplerate"],
                })
        return devices

    @staticmethod
    def _load_silero_vad() -> torch.nn.Module:
        logger.info("Loading Silero VAD model on CPU...")
        torch.set_num_threads(1)
        try:
            model = load_silero_vad(onnx=False)
        except (OSError, RuntimeError, ImportError) as exc:
            bundle_root = Path(getattr(sys, "_MEIPASS", ""))
            candidates = []
            if bundle_root:
                candidates.append(bundle_root / "silero_vad" / "data" / "silero_vad.jit")
            import silero_vad
            candidates.append(Path(silero_vad.__file__).resolve().parent / "data" / "silero_vad.jit")
            model_path = next((path for path in candidates if path.is_file()), None)
            if model_path is None:
                raise RuntimeError(f"Silero VAD model file not found; checked: {candidates}") from exc
            logger.warning("Using explicit Silero VAD resource: %s", model_path)
            # Torch's Windows file loader can fail on non-ASCII bundle paths.
            # Reading first and passing a file-like object avoids that path
            # conversion while keeping the packaged model unchanged.
            model = torch.jit.load(io.BytesIO(model_path.read_bytes()), map_location="cpu")
        model.eval()
        return model

    def _get_device_rate(self) -> int:
        try:
            info = sd.query_devices(self.config.device)
            rate = int(info["default_samplerate"])
            if rate > 0:
                return rate
        except Exception:
            pass
        return 44100

    def listen_once(
        self,
        on_status: Callable[[str], None] | None = None,
        on_level: Callable[[float], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> np.ndarray:
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        if hasattr(self.vad_model, "reset_states"):
            self.vad_model.reset_states()

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning("[audio] %s", status)
            audio_queue.put(indata[:, 0].copy())

        say = on_status or self.on_status or (lambda _: None)
        actual_rate = self.config.sample_rate

        # Try the configured rate first; fall back to device default on failure.
        logger.info("Listening for speech...")
        say("Waiting for speech...")
        try:
            stream = sd.InputStream(
                samplerate=actual_rate,
                blocksize=self.config.block_size,
                dtype="float32",
                channels=self.config.channels,
                device=self.config.device,
                callback=callback,
            )
            stream.start()
        except sd.PortAudioError:
            fallback_rate = self._get_device_rate()
            logger.warning("16 kHz not supported; falling back to %d Hz", fallback_rate)
            actual_rate = fallback_rate
            stream = sd.InputStream(
                samplerate=actual_rate,
                blocksize=self.config.block_size,
                dtype="float32",
                channels=self.config.channels,
                device=self.config.device,
                callback=callback,
            )
            stream.start()

        try:
            block_duration_ms = self.config.block_size / actual_rate * 1000
            padding_block_count = max(1, int(self.config.start_padding_ms / block_duration_ms))
            silence_block_limit = max(1, int(self.config.silence_duration_ms / block_duration_ms))
            min_speech_blocks = max(1, int(self.config.min_speech_duration_ms / block_duration_ms))

            padding_blocks = collections.deque(maxlen=padding_block_count)
            recorded_blocks = []
            speech_blocks = 0
            silence_blocks = 0
            has_started = False
            started_at = time.monotonic()
            last_level_at = 0.0

            while True:
                try:
                    block = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    if stop_event and stop_event.is_set():
                        return np.empty(0, dtype=np.float32)
                    if time.monotonic() - started_at > self.config.max_record_seconds:
                        break
                    continue

                # Emit level with 100 ms throttling to avoid flooding the UI.
                now = time.monotonic()
                if on_level and now - last_level_at >= 0.1:
                    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
                    on_level(rms)
                    last_level_at = now

                # If recording at a non-16k rate, VAD still needs 16k audio.
                vad_block = block if actual_rate == 16000 else self._resample(block, actual_rate, 16000)
                speech_prob = self._speech_probability(vad_block)
                is_speech = speech_prob >= self.config.speech_threshold

                if not has_started:
                    padding_blocks.append(block)
                    if is_speech:
                        has_started = True
                        recorded_blocks.extend(padding_blocks)
                        speech_blocks = 1
                        silence_blocks = 0
                        logger.info("Speech detected – recording")
                        say("Speech detected - recording...")
                    elif time.monotonic() - started_at > self.config.max_record_seconds:
                        break
                    continue

                recorded_blocks.append(block)
                if is_speech:
                    speech_blocks += 1
                    silence_blocks = 0
                else:
                    silence_blocks += 1

                if speech_blocks >= min_speech_blocks and silence_blocks >= silence_block_limit:
                    logger.info("Silence threshold reached – ending capture")
                    say("Transcribing...")
                    break

                if time.monotonic() - started_at > self.config.max_record_seconds:
                    logger.info("Max recording time reached – ending capture")
                    say("Transcribing...")
                    break
        finally:
            stream.stop()
            stream.close()

        if not recorded_blocks:
            return np.empty(0, dtype=np.float32)

        audio = np.concatenate(recorded_blocks).astype(np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        if actual_rate != 16000:
            audio = self._resample(audio, actual_rate, 16000)
        return audio

    def _speech_probability(self, audio_block: np.ndarray) -> float:
        with torch.no_grad():
            tensor = torch.from_numpy(audio_block).float()
            probability = self.vad_model(tensor, 16000).item()
        return float(probability)

    @staticmethod
    def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        if orig_sr == target_sr:
            return audio
        duration = len(audio) / orig_sr
        target_len = max(1, int(duration * target_sr))
        src_indices = np.linspace(0, len(audio) - 1, target_len)
        return np.interp(src_indices, np.arange(len(audio)), audio).astype(np.float32)
