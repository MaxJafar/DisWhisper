"""
Cloud Whisper Inference Engine supporting Groq Cloud and OpenAI Whisper APIs.
Converts 16kHz float32 audio arrays to in-memory WAV streams and executes
asynchronous transcription via cloud REST endpoints.
"""

from __future__ import annotations

import io
import json
import logging
import wave
from typing import Optional, Tuple

import aiohttp
import numpy as np

from diswhisper.transcriber.base import BaseSTTEngine

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"


def float32_to_wav_bytes(audio_data: np.ndarray, sample_rate: int = 16000) -> bytes:
    """
    Convert a 1D float32 audio array normalized in [-1.0, 1.0] to WAV audio bytes.
    """
    # Clip and convert to 16-bit PCM integer
    clipped = np.clip(audio_data, -1.0, 1.0)
    int16_samples = (clipped * 32767.0).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int16_samples.tobytes())

    return buffer.getvalue()


class CloudWhisperEngine(BaseSTTEngine):
    """
    Cloud STT Engine utilizing Groq Whisper or OpenAI Whisper API.
    """

    def __init__(
        self,
        provider: str = "groq",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.provider = provider.lower().strip()
        self.api_key = api_key or ""
        self.language = language

        if self.provider == "groq":
            self._endpoint = GROQ_TRANSCRIPTION_URL
            self._model_name = model_name or "whisper-large-v3-turbo"
        else:
            self._endpoint = OPENAI_TRANSCRIPTION_URL
            self._model_name = model_name or "whisper-1"

    @property
    def engine_name(self) -> str:
        return f"Cloud Whisper ({self.provider.upper()})"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def active_device(self) -> str:
        return "cloud-api"

    @property
    def active_compute_type(self) -> str:
        return "cloud-managed"

    def purge_gpu_cache(self) -> None:
        """No-op for cloud engine."""
        pass

    async def transcribe_async(self, audio_data: np.ndarray) -> Tuple[str, Optional[str]]:
        """
        Send audio to cloud provider asynchronously.
        """
        if audio_data.size == 0:
            return "", None

        if not self.api_key:
            err = f"Missing API key for {self.provider.upper()} STT!"
            logger.error(err)
            return f"[{err}]", None

        wav_bytes = float32_to_wav_bytes(audio_data, sample_rate=16000)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            wav_bytes,
            filename="audio.wav",
            content_type="audio/wav",
        )
        form_data.add_field("model", self._model_name)
        form_data.add_field("response_format", "json")

        if self.language and self.language != "auto":
            form_data.add_field("language", self.language)

        try:
            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self._endpoint, headers=headers, data=form_data) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("text", "").strip()
                        return text, self.language
                    else:
                        error_body = await resp.text()
                        logger.error(f"Cloud STT API error ({resp.status}): {error_body}")
                        return f"[Cloud STT error: HTTP {resp.status}]", None
        except Exception as e:
            logger.error(f"Exception during Cloud STT request: {e}", exc_info=True)
            return "", None

    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, Optional[str]]:
        """
        Synchronous wrapper for BaseSTTEngine compliance.
        Uses asyncio event loop if available or creates a short runner.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # If called from a thread without running loop
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(self.transcribe_async(audio_data), loop)
            return future.result(timeout=10.0)
        except RuntimeError:
            return asyncio.run(self.transcribe_async(audio_data))
