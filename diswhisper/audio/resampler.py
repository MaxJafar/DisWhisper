"""
Audio resampling and format normalization module.
Converts Discord 48kHz stereo 16-bit PCM audio to 16kHz mono float32 for Whisper.
"""

from __future__ import annotations

import numpy as np

# Audio constants
DISCORD_SAMPLE_RATE = 48000
DISCORD_CHANNELS = 2
WHISPER_SAMPLE_RATE = 16000
DOWNSAMPLE_FACTOR = DISCORD_SAMPLE_RATE // WHISPER_SAMPLE_RATE  # 3


def pcm_to_whisper_mono(pcm_bytes: bytes) -> np.ndarray:
    """
    Convert raw Discord PCM bytes (48kHz, 16-bit signed integer, stereo)
    into a 1D NumPy array (16kHz, mono, float32, normalized [-1.0, 1.0]).

    Parameters:
        pcm_bytes: Raw bytes from Discord Opus decoder.

    Returns:
        1D np.ndarray with dtype float32 at 16,000Hz.
    """
    if not pcm_bytes:
        return np.empty(0, dtype=np.float32)

    # Decode 16-bit PCM bytes to signed int16
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if len(samples) == 0:
        return np.empty(0, dtype=np.float32)

    # Ensure even number of samples for stereo channels
    if len(samples) % DISCORD_CHANNELS != 0:
        samples = samples[: len(samples) - (len(samples) % DISCORD_CHANNELS)]

    # Downmix Stereo (2 channels) -> Mono by averaging
    stereo = samples.reshape(-1, DISCORD_CHANNELS)
    mono = stereo.mean(axis=1).astype(np.float32) / 32768.0

    # Downsample from 48kHz to 16kHz via 3:1 decimation
    resampled = mono[::DOWNSAMPLE_FACTOR]

    return np.ascontiguousarray(resampled, dtype=np.float32)


def calculate_rms(audio_array: np.ndarray) -> float:
    """
    Calculate the Root Mean Square (RMS) amplitude of a float32 audio array.

    Parameters:
        audio_array: 1D NumPy array of normalized audio samples in [-1.0, 1.0].

    Returns:
        RMS amplitude as float (0.0 to 1.0).
    """
    if audio_array.size == 0:
        return 0.0

    mean_square = np.mean(np.square(audio_array))
    return float(np.sqrt(mean_square))
