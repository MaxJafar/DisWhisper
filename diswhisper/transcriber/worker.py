"""
Background Transcription Worker.
Asynchronously pulls audio chunks from the processing queue, executes CTranslate2
inference in a background thread to prevent event-loop latency, and notifies listeners.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Coroutine, Optional, Any

from diswhisper.audio.buffer import AudioChunk
from diswhisper.transcriber.base import BaseSTTEngine

logger = logging.getLogger(__name__)

TranscriptCallback = Callable[[int, str, str, float], Coroutine[Any, Any, None]]


class TranscriptionWorker:
    """
    Consumes AudioChunks from queue and executes inference via asyncio.to_thread.
    Supports any backend implementing BaseSTTEngine (Whisper, SenseVoice, etc.).
    """

    def __init__(
        self,
        queue: asyncio.Queue[AudioChunk],
        engine: BaseSTTEngine,
        on_transcript: TranscriptCallback,
    ):
        self.queue = queue
        self.engine = engine
        self.on_transcript = on_transcript
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        """Start the background consumer task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop(), name="DisWhisper-Transcriber")
        logger.info("Transcription worker started.")

    async def stop(self) -> None:
        """Stop worker and cancel pending task."""
        if not self._running:
            return
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Transcription worker stopped.")

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                chunk: AudioChunk = await self.queue.get()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error fetching from transcription queue: {e}")
                continue

            try:
                # Measure total latency
                start_inference = time.time()

                # Run heavy CTranslate2 inference in a thread worker
                text, detected_lang = await asyncio.to_thread(self.engine.transcribe, chunk.audio)

                inference_duration = time.time() - start_inference
                total_latency = time.time() - chunk.timestamp

                if text and text.strip():
                    logger.info(
                        f"Transcribed [{chunk.display_name}] (RMS: {chunk.rms:.3f}, "
                        f"Inference: {inference_duration:.2f}s, Latency: {total_latency:.2f}s): \"{text}\""
                    )
                    # Forward to UI and file logger
                    await self.on_transcript(chunk.user_id, chunk.display_name, text, chunk.timestamp)
                else:
                    logger.debug(
                        f"No speech recognized for chunk from '{chunk.display_name}' ({inference_duration:.2f}s)"
                    )

            except Exception as e:
                logger.error(f"Exception during chunk processing for {chunk.display_name}: {e}", exc_info=True)
            finally:
                self.queue.task_done()
