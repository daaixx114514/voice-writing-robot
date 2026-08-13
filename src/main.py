from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.audio.audio_recorder import AudioRecorder
from src.stt.speech_recognizer import SpeechRecognizer
from src.utils.config import load_audio_config, load_stt_config

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chinese microphone STT test with Silero VAD and faster-whisper.")
    parser.add_argument(
        "--config",
        default="config/stt.yaml",
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available microphone input devices and exit.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Recognize one utterance and exit.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()

    if args.list_devices:
        for device in AudioRecorder.list_input_devices():
            print(
                f'{device["index"]}: {device["name"]} '
                f'(default_samplerate={device["default_samplerate"]})'
            )
        return

    config_path = Path(args.config)
    audio_config = load_audio_config(config_path)
    stt_config = load_stt_config(config_path)

    # 启动顺序：先加载 VAD 录音器，再加载 faster-whisper 识别器。
    recorder = AudioRecorder(audio_config)
    recognizer = SpeechRecognizer(stt_config)

    logger.info("Speech recognition module started. Press Ctrl+C to exit.")
    try:
        while True:
            audio = recorder.listen_once()
            text = recognizer.transcribe(audio)
            if text:
                logger.info("Recognition result: %s", text)
            else:
                logger.info("No valid text recognized.")

            if args.once:
                break
    except KeyboardInterrupt:
        logger.info("Exited.")


if __name__ == "__main__":
    main()
