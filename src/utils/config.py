from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import yaml

from src.audio.audio_recorder import AudioConfig
from src.stt.speech_recognizer import SttConfig


def resource_path(relative_path: str | Path) -> Path:
    """Resolve a project resource in source runs and PyInstaller bundles."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundle_root / Path(relative_path)


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML object: {path}")
    return data


def load_audio_config(path: str | Path) -> AudioConfig:
    data = load_yaml(path).get("audio", {})
    return AudioConfig(**data)


def load_stt_config(path: str | Path) -> SttConfig:
    data = load_yaml(path).get("stt", {})
    return SttConfig(**data)
