"""
Unit tests for SenseVoice rich transcription parsing and engine factory.
"""

from unittest.mock import MagicMock, patch
import pytest

from diswhisper.config import Config
from diswhisper.transcriber.factory import create_stt_engine
from diswhisper.transcriber.sensevoice_engine import SenseVoiceEngine


def test_sensevoice_rich_transcription_formatting():
    # Mocking recognizer to avoid full model load during unit test
    with patch.object(SenseVoiceEngine, "_initialize_recognizer"):
        engine = SenseVoiceEngine(enable_rich_events=True)

        raw = "<|en|><|HAPPY|>Hello world!<|LAUGHTER|> Thank you very much.<|APPLAUSE|><|withitn|>"
        formatted, lang = engine.format_rich_transcription(raw)

        assert lang == "en"
        assert "😄" in formatted
        assert "😂 [laughter]" in formatted
        assert "👏 [applause]" in formatted
        assert "<|withitn|>" not in formatted
        assert "Hello world!" in formatted


def test_sensevoice_rich_transcription_disabled():
    with patch.object(SenseVoiceEngine, "_initialize_recognizer"):
        engine = SenseVoiceEngine(enable_rich_events=False)

        raw = "<|en|><|HAPPY|>Hello world!<|LAUGHTER|><|withitn|>"
        formatted, lang = engine.format_rich_transcription(raw)

        assert lang == "en"
        assert "😄" not in formatted
        assert "laughter" not in formatted
        assert formatted == "Hello world!"


def test_sensevoice_audio_events_mapping():
    with patch.object(SenseVoiceEngine, "_initialize_recognizer"):
        engine = SenseVoiceEngine(enable_rich_events=True)

        raw = "<|zh|><|BGM|>Music playing<|CRY|>so sad"
        formatted, lang = engine.format_rich_transcription(raw)

        assert lang == "zh"
        assert "🎵 [music]" in formatted
        assert "😭 [crying]" in formatted


def test_create_stt_engine_factory():
    cfg_sense = Config(STT_ENGINE="sensevoice")
    cfg_whisper = Config(STT_ENGINE="whisper")

    with patch.object(SenseVoiceEngine, "_initialize_recognizer"):
        engine1 = create_stt_engine(cfg_sense)
        assert engine1.engine_name == "SenseVoice (Alibaba / sherpa-onnx)"

    with patch("diswhisper.transcriber.factory.WhisperEngine") as mock_whisper:
        mock_instance = MagicMock()
        mock_whisper.return_value = mock_instance
        engine2 = create_stt_engine(cfg_whisper)
        assert engine2 == mock_instance
