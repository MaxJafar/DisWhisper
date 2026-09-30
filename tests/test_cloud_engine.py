"""
Unit tests for CloudWhisperEngine and WAV byte serialization.
"""

import io
import wave
import numpy as np
import pytest

from diswhisper.transcriber.cloud_engine import CloudWhisperEngine, float32_to_wav_bytes


def test_float32_to_wav_bytes():
    # 1 second of 16kHz audio (16000 samples)
    sine = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000, endpoint=False)).astype(np.float32)
    wav_bytes = float32_to_wav_bytes(sine, sample_rate=16000)

    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 0

    # Parse with standard wave module to verify valid WAV container
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


def test_cloud_engine_properties():
    groq_engine = CloudWhisperEngine(provider="groq", api_key="test_key_123")
    assert groq_engine.engine_name == "Cloud Whisper (GROQ)"
    assert groq_engine.model_name == "whisper-large-v3-turbo"
    assert groq_engine.active_device == "cloud-api"

    openai_engine = CloudWhisperEngine(provider="openai", api_key="sk-test")
    assert openai_engine.engine_name == "Cloud Whisper (OPENAI)"
    assert openai_engine.model_name == "whisper-1"


@pytest.mark.anyio
async def test_cloud_engine_missing_key():
    engine = CloudWhisperEngine(provider="groq", api_key="")
    text, lang = await engine.transcribe_async(np.zeros(16000, dtype=np.float32))
    assert "Missing API key" in text
