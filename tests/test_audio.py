"""Unit tests for core audio and STT modules."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.audio.audio_recorder import AudioRecorder


# ---------------------------------------------------------------------------
# Resample correctness
# ---------------------------------------------------------------------------

class TestResample:
    """Linear-interp resample used for sample-rate fallback."""

    def test_identity_noop(self) -> None:
        """resample(..., orig, orig) returns input unchanged."""
        audio = np.array([0.1, 0.2, 0.3, -0.1], dtype=np.float32)
        result = AudioRecorder._resample(audio, 16000, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_downsample_preserves_length_ratio(self) -> None:
        """8000 -> 4000 Hz should halve the sample count."""
        rng = np.random.default_rng(42)
        audio = rng.random(16000, dtype=np.float32)
        result = AudioRecorder._resample(audio, 8000, 4000)
        assert len(result) == 8000

    def test_upsample_preserves_length_ratio(self) -> None:
        """4000 -> 8000 Hz should double the sample count."""
        rng = np.random.default_rng(42)
        audio = rng.random(8000, dtype=np.float32)
        result = AudioRecorder._resample(audio, 4000, 8000)
        assert len(result) == 16000

    def test_single_sample_does_not_blow_up(self) -> None:
        """Edge case: single input sample should return single output."""
        audio = np.array([0.5], dtype=np.float32)
        result = AudioRecorder._resample(audio, 16000, 44100)
        assert len(result) >= 1
        assert np.isfinite(result).all()

    def test_output_is_float32(self) -> None:
        rng = np.random.default_rng(42)
        audio = rng.random(1000, dtype=np.float32)
        result = AudioRecorder._resample(audio, 8000, 16000)
        assert result.dtype == np.float32

    def test_downsample_dc_signal(self) -> None:
        """A constant (DC) signal should interpolate to the same constant."""
        audio = np.ones(8000, dtype=np.float32) * 0.7
        result = AudioRecorder._resample(audio, 8000, 4000)
        np.testing.assert_allclose(result, 0.7, atol=1e-6)


# ---------------------------------------------------------------------------
# Speech probability wrapper
# ---------------------------------------------------------------------------

class TestSpeechProbability:
    """_speech_probability is a thin wrapper around Silero VAD; we test
    that it returns a float in [0, 1] for a plausible 16-kHz block."""

    def test_returns_float_in_range(self) -> None:
        from silero_vad import load_silero_vad
        import torch

        # Construct recorder bypassing __init__ to avoid
        # instantiating AudioConfig, then inject just the VAD model.
        recorder = AudioRecorder.__new__(AudioRecorder)
        torch.set_num_threads(1)
        recorder.vad_model = load_silero_vad(onnx=False)
        recorder.vad_model.eval()

        rng = np.random.default_rng(99)
        block = (rng.random(512, dtype=np.float32) * 0.01).astype(np.float32)  # quiet noise
        prob = recorder._speech_probability(block)
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0


# ---------------------------------------------------------------------------
# Device enumeration
# ---------------------------------------------------------------------------

class TestDeviceEnumeration:
    """list_input_devices should return a list of dicts (or empty)."""

    def test_returns_list(self) -> None:
        devices = AudioRecorder.list_input_devices()
        assert isinstance(devices, list)

    def test_each_device_has_required_keys(self) -> None:
        for d in AudioRecorder.list_input_devices():
            assert "index" in d
            assert "name" in d
            assert "default_samplerate" in d


# ---------------------------------------------------------------------------
# AudioConfig validation
# ---------------------------------------------------------------------------

class TestAudioConfig:
    def test_defaults(self) -> None:
        from src.audio.audio_recorder import AudioConfig
        cfg = AudioConfig()
        assert cfg.sample_rate == 16000
        assert cfg.channels == 1
        assert cfg.block_size == 512

    def test_channels_must_be_one(self) -> None:
        from src.audio.audio_recorder import AudioRecorder, AudioConfig
        with pytest.raises(ValueError, match="mono"):
            AudioRecorder(AudioConfig(channels=2))

    def test_block_size_must_be_positive(self) -> None:
        from src.audio.audio_recorder import AudioRecorder, AudioConfig
        with pytest.raises(ValueError, match="block_size"):
            AudioRecorder(AudioConfig(block_size=0))
