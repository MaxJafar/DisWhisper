import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from diswhisper.audio.buffer import AudioBufferManager, AudioChunk
from diswhisper.transcriber.worker import TranscriptionWorker


@pytest.mark.anyio
async def test_worker_stop_drains_queued_cloud_transcriptions():
    queue = asyncio.Queue()
    callback = AsyncMock()
    engine = SimpleNamespace(
        transcribe_async=AsyncMock(return_value=("recognized", "en"))
    )
    worker = TranscriptionWorker(queue, engine, callback)
    for user in (1, 2, 3):
        queue.put_nowait(
            AudioChunk(
                user, f"User{user}", np.ones(16000, np.float32), time.time(), 1, 1
            )
        )
    worker.start()
    await worker.stop()
    assert callback.await_count == engine.transcribe_async.await_count == 3
    assert queue.empty()
    assert worker._task is None


@pytest.mark.anyio
async def test_short_speech_flushes_on_pause_and_close_rejects_new_packets():
    queue = asyncio.Queue()
    manager = AudioBufferManager(queue, asyncio.get_running_loop())
    stream = manager.get_or_create_stream(1, "Alice")
    stream.feed_samples(np.full(8000, 0.2, np.float32))
    stream.last_packet_time = time.time() - 2
    manager.flush_idle()
    await asyncio.sleep(0)
    assert queue.qsize() == 1
    chunk = queue.get_nowait()
    queue.task_done()
    assert chunk.duration_sec == 0.5
    assert chunk.timestamp == stream.last_packet_time
    manager.close()
    manager.process_pcm_packet(1, "Alice", np.full(48000 * 2, 5000, np.int16).tobytes())
    await asyncio.sleep(0)
    assert queue.empty()


@pytest.mark.anyio
async def test_backlog_is_bounded_without_event_loop_queuefull_errors():
    queue = asyncio.Queue(maxsize=1)
    manager = AudioBufferManager(
        queue, asyncio.get_running_loop(), chunk_duration_sec=0.5
    )
    chunk = AudioChunk(1, "Alice", np.ones(8000, np.float32), time.time(), 0.5, 1)
    manager._dispatch_chunk(chunk)
    manager._dispatch_chunk(chunk)
    await asyncio.sleep(0)
    assert queue.qsize() == 1
