"""
Unit tests for audio resampling, silence detection, and buffering logic.
"""

import numpy as np
import pytest

from diswhisper.audio.buffer import UserAudioStream
from diswhisper.audio.resampler import (
    calculate_rms,
    pcm_to_whisper_mono,
)


def test_pcm_to_whisper_mono_empty():
    res = pcm_to_whisper_mono(b"")
    assert isinstance(res, np.ndarray)
    assert res.size == 0
    assert res.dtype == np.float32


def test_pcm_to_whisper_mono_conversion():
    # 20ms packet at 48kHz stereo = 960 samples per channel * 2 channels = 1920 int16 samples = 3840 bytes
    num_samples_48k = 960
    # Create stereo signal: Left channel = 16384 (0.5), Right channel = -16384 (-0.5) -> Average = 0.0
    stereo_data = np.zeros(num_samples_48k * 2, dtype=np.int16)
    stereo_data[0::2] = 16384
    stereo_data[1::2] = -16384

    res = pcm_to_whisper_mono(stereo_data.tobytes())

    # Expected length: 960 / 3 = 320 samples @ 16kHz
    assert len(res) == 320
    assert res.dtype == np.float32
    # The average of +0.5 and -0.5 is 0.0
    np.testing.assert_allclose(res, 0.0, atol=1e-4)


def test_pcm_to_whisper_mono_amplitude():
    # Constant signal across both channels: 16384 -> should normalize to ~0.5
    num_samples_48k = 960
    stereo_data = np.full(num_samples_48k * 2, 16384, dtype=np.int16)

    res = pcm_to_whisper_mono(stereo_data.tobytes())

    assert len(res) == 320
    np.testing.assert_allclose(res, 0.5, atol=1e-3)


def test_calculate_rms():
    # Silence
    silence = np.zeros(16000, dtype=np.float32)
    assert calculate_rms(silence) == 0.0

    # Constant signal of 0.5
    constant = np.full(16000, 0.5, dtype=np.float32)
    assert pytest.approx(calculate_rms(constant), 0.001) == 0.5

    # Sine wave with amplitude 1.0 -> theoretical RMS is 1 / sqrt(2) ≈ 0.7071
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    sine = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    assert pytest.approx(calculate_rms(sine), 0.01) == 0.7071


def test_user_audio_stream_chunking_and_silence_gating():
    chunk_duration = 1.0  # 1 second chunk = 16000 samples
    silence_threshold = 0.05
    stream = UserAudioStream(
        user_id=12345,
        display_name="TestUser",
        chunk_duration_sec=chunk_duration,
        silence_threshold=silence_threshold,
    )

    # 1. Feed 0.5s of audio (8,000 samples) -> No chunk emitted yet
    half_sec = np.full(8000, 0.1, dtype=np.float32)
    chunks = stream.feed_samples(half_sec)
    assert len(chunks) == 0

    # 2. Feed another 0.5s of audio (8,000 samples) -> 1 full second reached (16,000 samples)
    # RMS = 0.1 >= 0.05 -> should emit 1 chunk
    chunks = stream.feed_samples(half_sec)
    assert len(chunks) == 1
    assert chunks[0].user_id == 12345
    assert chunks[0].display_name == "TestUser"
    assert len(chunks[0].audio) == 16000
    assert chunks[0].duration_sec == 1.0
    assert pytest.approx(chunks[0].rms, 0.001) == 0.1

    # 3. Feed 1.0s of pure silence (16,000 samples of 0.0) -> Discarded due to silence gating
    silence_sec = np.zeros(16000, dtype=np.float32)
    silent_chunks = stream.feed_samples(silence_sec)
    assert len(silent_chunks) == 0
