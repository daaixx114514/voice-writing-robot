"""Unit tests for the SpeechRecognizer and SttConfig."""

from __future__ import annotations

import numpy as np
import pytest

from src.stt.speech_recognizer import SttConfig


# ---------------------------------------------------------------------------
# SttConfig defaults
# ---------------------------------------------------------------------------

class TestSttConfig:
    def test_defaults(self) -> None:
        cfg = SttConfig()
        assert cfg.model_size == "small"
        assert cfg.device == "cpu"
        assert cfg.compute_type == "int8"
        assert cfg.language == "zh"
        assert cfg.beam_size == 5
        assert cfg.best_of == 5
        assert len(cfg.temperature) == 6

    def test_initial_prompt_is_chinese(self) -> None:
        cfg = SttConfig()
        assert cfg.initial_prompt is not None
        # prompt should be in Chinese and mention name-related terms
        assert "简体中文" in cfg.initial_prompt


# ---------------------------------------------------------------------------
# SpeechRecognizer boundary conditions
# ---------------------------------------------------------------------------

class TestTranscribeBoundary:
    """These tests check edge cases without loading the full model (slow)."""

    @classmethod
    @pytest.fixture(scope="class")
    def recognizer(cls) -> "SpeechRecognizer":
        from src.stt.speech_recognizer import SpeechRecognizer
        return SpeechRecognizer(SttConfig())

    def test_empty_array_returns_empty_string(self, recognizer) -> None:
        result = recognizer.transcribe(np.empty(0, dtype=np.float32))
        assert result == ""

    def test_tiny_array_does_not_crash(self, recognizer) -> None:
        """Very short audio (a few ms) should not throw."""
        audio = np.zeros(160, dtype=np.float32)  # 10 ms @ 16 kHz
        try:
            text = recognizer.transcribe(audio)
        except Exception as exc:
            pytest.fail(f"transcribe() raised unexpectedly: {exc}")
        # May be empty or may contain hallucinated content — both acceptable.
        assert isinstance(text, str)
