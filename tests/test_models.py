"""Model downloads, safe extraction, and provider selection regressions."""

import asyncio
import json
import sys
import threading
import time
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from diswhisper.config import Config
from diswhisper.models import (
    VOSK_REQUIRED_FILES,
    _extract_vosk,
    download_model,
    get_model,
    is_downloaded,
    model_path,
)
from diswhisper.transcriber.factory import create_stt_engine
from diswhisper.transcriber.vosk_engine import VoskEngine


def test_partial_local_model_is_not_reported_as_installed(tmp_path):
    config = Config(LOCAL_MODEL_DIR=str(tmp_path))
    model = get_model("vosk-model-small-en-us-0.15")
    root = model_path(config, model)
    root.mkdir(parents=True)
    assert not is_downloaded(config, model)
    for file in VOSK_REQUIRED_FILES:
        path = root / file
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"model file")
    assert is_downloaded(config, model)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.txt",
        "/absolute.txt",
        "vosk-model-small-en-us-0.15/../../escape.txt",
        "vosk-model-small-en-us-0.15/..\\escape.txt",
    ],
)
def test_vosk_archives_cannot_escape_the_model_directory(tmp_path, unsafe_path):
    archive = tmp_path / "model.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(unsafe_path, b"invalid")
    with pytest.raises(ValueError, match="Unsafe path"):
        _extract_vosk(archive, tmp_path / "extract", "vosk-model-small-en-us-0.15")
    assert not (tmp_path / "outside.txt").exists()


def test_valid_vosk_archive_extracts_required_files(tmp_path):
    name = "vosk-model-small-en-us-0.15"
    archive = tmp_path / "model.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for file in VOSK_REQUIRED_FILES:
            zipped.writestr(f"{name}/{file}", b"model file")
    assert _extract_vosk(archive, tmp_path / "extract", name).name == name


@pytest.mark.anyio
async def test_whisper_download_uses_runtime_model_name_and_shared_local_directory(
    tmp_path,
):
    config = Config(LOCAL_MODEL_DIR=str(tmp_path))
    model = get_model("whisper-large-v3-turbo")
    progress = AsyncMock()
    with (
        patch("huggingface_hub.snapshot_download") as download,
        patch("diswhisper.models.is_downloaded", return_value=True),
    ):
        await download_model(config, model, progress)
    assert download.call_args.args == (model.repo_id,)
    assert download.call_args.kwargs["local_dir"] == str(model_path(config, model))
    assert download.call_args.kwargs["token"] is False
    assert progress.await_args.args == (100, "Download complete")


@pytest.mark.anyio
async def test_huggingface_cancellation_joins_the_worker_before_retry(tmp_path):
    entered, stopped = threading.Event(), threading.Event()
    def transfer(*args, **kwargs):
        bar = kwargs["tqdm_class"](total=100, unit="B", desc="model.bin")
        entered.set()
        try:
            while True:
                bar.update(1)
                time.sleep(0.005)
        finally:
            stopped.set()
            bar.close()
    with patch("huggingface_hub.snapshot_download", side_effect=transfer):
        task = asyncio.create_task(download_model(Config(LOCAL_MODEL_DIR=str(tmp_path)), get_model("whisper-base"), AsyncMock()))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    assert stopped.is_set()


@pytest.mark.anyio
async def test_ollama_streamed_progress_downloads_the_exact_selected_model():
    requests = []

    async def pull(request):
        requests.append(await request.json())
        return web.Response(
            body=(
                json.dumps({"status": "pulling layer", "total": 100, "completed": 50})
                + "\n"
                + json.dumps({"status": "success"})
                + "\n"
            ).encode(),
            content_type="application/x-ndjson",
        )

    app = web.Application()
    app.router.add_post("/api/pull", pull)
    async with TestServer(app) as server:
        config = Config(LOCAL_LLM_URL=str(server.make_url("")))
        progress = AsyncMock()
        await download_model(config, get_model("ollama-qwen2.5"), progress)
    assert requests == [{"model": "qwen2.5:3b", "stream": True}]
    assert any(call.args[0] == 50 for call in progress.await_args_list)
    assert progress.await_args.args == (100, "Download complete")


@pytest.mark.anyio
async def test_truncated_ollama_download_is_a_failure():
    async def pull(request):
        return web.Response(
            body=b'{"status":"pulling layer","total":100,"completed":50}\n'
        )

    app = web.Application()
    app.router.add_post("/api/pull", pull)
    async with TestServer(app) as server:
        with pytest.raises(RuntimeError, match="before reporting success"):
            await download_model(
                Config(LOCAL_LLM_URL=str(server.make_url(""))),
                get_model("ollama-llama3.2"),
                AsyncMock(),
            )


def test_vosk_converts_to_pcm_and_includes_intermediate_and_final_results(tmp_path):
    recognizer = MagicMock()
    recognizer.AcceptWaveform.side_effect = [True, False]
    recognizer.Result.return_value = '{"text":"first phrase"}'
    recognizer.FinalResult.return_value = '{"text":"last phrase"}'
    runtime = SimpleNamespace(
        Model=MagicMock(), KaldiRecognizer=MagicMock(return_value=recognizer)
    )
    with patch.dict(sys.modules, {"vosk": runtime}):
        engine = VoskEngine(tmp_path, "test", "en")
        text, language = engine.transcribe(np.full(8000, 2.0, np.float32))
        assert (text, language) == ("first phrase last phrase", "en")
        pcm = recognizer.AcceptWaveform.call_args_list[0].args[0]
        assert np.frombuffer(pcm, dtype="<i2").max() == 32767
        assert engine.transcribe(np.array([], np.float32)) == ("", None)


def test_cloud_factory_honors_configured_provider_and_rejects_unknown_engines():
    config = Config(
        STT_ENGINE="cloud", CLOUD_STT_PROVIDER="openai", OPENAI_API_KEY="test"
    )
    engine = create_stt_engine(config)
    assert engine.provider == "openai"
    with pytest.raises(ValueError, match="Unknown"):
        create_stt_engine(config, "unknown-engine")
