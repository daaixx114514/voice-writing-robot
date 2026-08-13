from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel
from zhconv import convert as zh_convert

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SttConfig:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "zh"
    beam_size: int = 5
    best_of: int = 5
    temperature: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    repetition_penalty: float = 1.1
    no_speech_threshold: float = 0.6
    compression_ratio_threshold: float = 2.4
    cpu_threads: int = 4
    initial_prompt: Optional[str] = (
        "以下是中文语音识别。说话内容可能包含中国人名、地名、机构名称和专业术语。"
        "请使用常见姓名用字，如：伟、芳、建国、志强、小明、秀英、"
        "李明、王红、张华、刘洋、陈静、赵刚、孙丽、周杰、吴鑫。"
        "一律输出简体中文。"
    )


class SpeechRecognizer:
    """faster-whisper wrapper for Chinese speech recognition."""

    def __init__(self, config: SttConfig) -> None:
        self.config = config
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        logger.info(
            "Loading faster-whisper model: %s, device=%s, compute_type=%s",
            config.model_size, config.device, config.compute_type,
        )
        logger.info("If this is the first run, the model may be downloading. Please wait...")
        self.model = WhisperModel(
            config.model_size,
            device=config.device,
            compute_type=config.compute_type,
            cpu_threads=config.cpu_threads,
        )

    def transcribe(self, audio: np.ndarray, hotwords: str | None = None) -> str:
        """Transcribe 16 kHz float32 PCM audio and return Chinese text.

        Args:
            audio: float32 numpy array at 16 kHz.
            hotwords: Optional comma/semicolon/space-separated terms to
                bias the decoder toward (e.g. names, jargon).
        """
        if audio.size == 0:
            return ""

        # VAD 已经在录音阶段完成，这里关闭 faster-whisper 内置 VAD，避免重复切分。
        segments, info = self.model.transcribe(
            audio,
            language=self.config.language,
            beam_size=self.config.beam_size,
            best_of=self.config.best_of,
            temperature=self.config.temperature,
            repetition_penalty=self.config.repetition_penalty,
            no_speech_threshold=self.config.no_speech_threshold,
            compression_ratio_threshold=self.config.compression_ratio_threshold,
            vad_filter=False,
            initial_prompt=self.config.initial_prompt,
            hotwords=hotwords or None,
        )
        texts = [segment.text.strip() for segment in segments if segment.text.strip()]
        text = "".join(texts).strip()
        text = zh_convert(text, "zh-cn")

        if info.language_probability is not None:
            logger.info(
                "Detected language: %s, probability: %.2f",
                info.language, info.language_probability,
            )
        return text
