from src.audio.audio_recorder import AudioConfig, AudioRecorder
from src.stt.speech_recognizer import SttConfig


def test_config_defaults() -> None:
    assert AudioConfig().sample_rate == 16000
    assert SttConfig().language == "zh"
    assert AudioRecorder.list_input_devices is not None
