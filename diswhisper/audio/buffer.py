"""
User-Isolated Audio Buffer and Temporal Chunking Engine.
Accumulates resampled audio streams per user, slices them into temporal chunks (e.g. 2.5s),
and performs RMS silence gating before queueing for Whisper transcription.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from diswhisper.audio.resampler import (
    WHISPER_SAMPLE_RATE,
    calculate_rms,
    pcm_to_whisper_mono,
)

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """Represents a sliced audio segment ready for transcription."""

    user_id: int
    display_name: str
    audio: np.ndarray  # 1D float32 at 16kHz
    timestamp: float  # Unix timestamp when slice completed
    duration_sec: float
    rms: float


class UserAudioStream:
    """Maintains isolated audio buffer for an individual user."""

    def __init__(
        self,
        user_id: int,
        display_name: str,
        chunk_duration_sec: float = 2.5,
        silence_threshold: float = 0.01,
    ):
        self.user_id = user_id
        self.display_name = display_name
        self.chunk_duration_sec = chunk_duration_sec
        self.target_samples = int(WHISPER_SAMPLE_RATE * chunk_duration_sec)
        self.silence_threshold = silence_threshold

        self._buffer: list[np.ndarray] = []
        self._current_sample_count = 0
        self._lock = threading.Lock()
        self.last_packet_time = time.time()

    def update_display_name(self, name: str) -> None:
        self.display_name = name

    def feed_samples(self, samples: np.ndarray) -> list[AudioChunk]:
        """
        Append 16kHz mono float32 audio samples and extract complete chunks.
        Thread-safe method.
        """
        if samples.size == 0:
            return []

        chunks_to_emit: list[AudioChunk] = []

        with self._lock:
            self.last_packet_time = time.time()
            self._buffer.append(samples)
            self._current_sample_count += len(samples)

            # Check if we have accumulated enough samples for one or more chunks
            while self._current_sample_count >= self.target_samples:
                # Concatenate current buffer
                full_array = np.concatenate(self._buffer)

                # Extract exactly target_samples
                chunk_audio = full_array[: self.target_samples]
                remainder = full_array[self.target_samples :]

                # Reset buffer with remainder
                if len(remainder) > 0:
                    self._buffer = [remainder]
                    self._current_sample_count = len(remainder)
                else:
                    self._buffer = []
                    self._current_sample_count = 0

                # Silence Gating via RMS
                rms = calculate_rms(chunk_audio)
                if rms >= self.silence_threshold:
                    chunk = AudioChunk(
                        user_id=self.user_id,
                        display_name=self.display_name,
                        audio=chunk_audio,
                        timestamp=time.time(),
                        duration_sec=self.chunk_duration_sec,
                        rms=rms,
                    )
                    chunks_to_emit.append(chunk)
                else:
                    logger.debug(
                        f"Discarded silent chunk ({rms:.4f} < {self.silence_threshold}) "
                        f"for user '{self.display_name}' ({self.user_id})"
                    )

        return chunks_to_emit

    def flush(self, min_duration_sec: float = 0.8) -> Optional[AudioChunk]:
        """Flush remaining buffered audio if it exceeds min_duration_sec."""
        with self._lock:
            if not self._buffer:
                return None

            full_array = np.concatenate(self._buffer)
            self._buffer = []
            self._current_sample_count = 0

            duration = len(full_array) / WHISPER_SAMPLE_RATE
            if duration < min_duration_sec:
                return None

            rms = calculate_rms(full_array)
            if rms >= self.silence_threshold:
                return AudioChunk(
                    user_id=self.user_id,
                    display_name=self.display_name,
                    audio=full_array,
                    timestamp=time.time(),
                    duration_sec=duration,
                    rms=rms,
                )
            return None


class AudioBufferManager:
    """
    Manages isolated audio streams across all users in the voice channel.
    Coordinates between Discord voice threads and the asyncio transcription pipeline.
    """

    def __init__(
        self,
        transcription_queue: asyncio.Queue[AudioChunk],
        loop: asyncio.AbstractEventLoop,
        chunk_duration_sec: float = 2.5,
        silence_threshold: float = 0.01,
    ):
        self.queue = transcription_queue
        self.loop = loop
        self.chunk_duration_sec = chunk_duration_sec
        self.silence_threshold = silence_threshold

        self._streams: Dict[int, UserAudioStream] = {}
        self._lock = threading.Lock()

    def get_or_create_stream(self, user_id: int, display_name: str) -> UserAudioStream:
        with self._lock:
            if user_id not in self._streams:
                self._streams[user_id] = UserAudioStream(
                    user_id=user_id,
                    display_name=display_name,
                    chunk_duration_sec=self.chunk_duration_sec,
                    silence_threshold=self.silence_threshold,
                )
            else:
                self._streams[user_id].update_display_name(display_name)
            return self._streams[user_id]

    def process_pcm_packet(self, user_id: int, display_name: str, pcm_bytes: bytes) -> None:
        """
        Called by VoiceReceiver on audio packet reception.
        Converts PCM bytes to 16kHz mono float32, feeds to stream, and queues chunks.
        """
        samples = pcm_to_whisper_mono(pcm_bytes)
        if samples.size == 0:
            return

        stream = self.get_or_create_stream(user_id, display_name)
        chunks = stream.feed_samples(samples)

        for chunk in chunks:
            self._dispatch_chunk(chunk)

    def _dispatch_chunk(self, chunk: AudioChunk) -> None:
        """Push chunk into asyncio queue safely from any thread."""
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, chunk)
        except Exception as e:
            logger.error(f"Failed to queue audio chunk: {e}")

    def flush_all(self) -> None:
        """Flush remaining buffered audio for all active users."""
        with self._lock:
            for stream in self._streams.values():
                chunk = stream.flush()
                if chunk:
                    self._dispatch_chunk(chunk)

    def clear(self) -> None:
        """Clear all active user streams."""
        with self._lock:
            self._streams.clear()

    @property
    def active_user_count(self) -> int:
        with self._lock:
            return len(self._streams)
