"""HTTP regressions for companion downloads, activation, and configuration."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.test_utils import AioHTTPTestCase

from diswhisper.api.server import DisWhisperApiServer
from diswhisper.bot import DisWhisperBot
from diswhisper.config import SECRET_FIELDS, Config
from diswhisper.exporter.file_logger import TranscriptFileLogger


class TestApiServer(AioHTTPTestCase):
    async def get_application(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            STT_ENGINE="sensevoice",
            ENABLE_API_SERVER=False,
            DISCORD_TOKEN="test-discord-secret",
            GROQ_API_KEY="test-groq-secret",
            OPENAI_API_KEY="test-openai-secret",
        )
        self.cfg._config_path = Path(self.temp.name) / "config.json"
        engine = MagicMock(
            engine_name="SenseVoice",
            model_name="SenseVoiceSmall-int8",
            active_device="cpu",
            active_compute_type="int8",
        )
        self.bot = DisWhisperBot(self.cfg, engine)
        self.bot.is_ready = MagicMock(return_value=True)
        self.bot.file_logger = TranscriptFileLogger(
            Path(self.temp.name) / "transcripts"
        )
        self.api = DisWhisperApiServer(self.bot)
        self.bot.api_server = self.api
        self.ollama_patch = patch(
            "diswhisper.models.ollama_models", AsyncMock(return_value=(False, set()))
        )
        self.ollama_patch.start()
        return self.api.app

    async def test_hostname_rebinding_is_rejected(self):
        response = await self.client.get("/api/config", headers={"Host": "malicious.example:8765"})
        assert response.status == 403

    async def test_transcript_reader_limits_access_to_exported_markdown(self):
        directory = self.bot.file_logger.output_dir
        (directory / "meeting.md").write_text("# Meeting\nHello", encoding="utf-8")
        (directory / "private.txt").write_text("private", encoding="utf-8")
        response = await self.client.get("/api/transcripts/meeting.md")
        assert response.status == 200
        assert (await response.json())["content"] == "# Meeting\nHello"
        assert (await self.client.get("/api/transcripts/private.txt")).status == 404
        assert (await self.client.get("/api/transcripts/..%5Cprivate.txt")).status in (400, 404)

    async def asyncTearDown(self):
        await super().asyncTearDown()
        await self.bot.close()
        self.ollama_patch.stop()
        self.temp.cleanup()

    async def test_get_status(self):
        response = await self.client.get("/api/status")
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "online"
        assert data["engine_name"] == "SenseVoice"
        assert data["queue_depth"] == 0

    async def test_model_inventory_reports_actual_availability(self):
        with patch("diswhisper.models.is_downloaded", return_value=False):
            response = await self.client.get("/api/models")
        data = await response.json()
        models = {model["id"]: model for model in data["models"]}
        assert "whisper-base" in models
        assert "vosk-model-small-en-us-0.15" in models
        assert "ollama-qwen2.5" in models
        assert not models["sensevoice"]["downloaded"]
        assert not models["ollama-qwen2.5"]["available"]
        assert not models["cloud-openai"]["downloadable"]

    async def test_config_responses_and_events_never_expose_secrets(self):
        socket = await self.client.ws_connect("/api/events")
        await socket.receive_json()
        response = await self.client.get("/api/config")
        config = await response.json()
        assert config["DISCORD_TOKEN_CONFIGURED"]
        assert not SECRET_FIELDS & config.keys()
        response = await self.client.post(
            "/api/config", json={"SILENCE_THRESHOLD": 0.02}
        )
        assert response.status == 200
        body = await response.text()
        event = await socket.receive_json()
        assert event["event"] == "config_updated"
        assert not SECRET_FIELDS & event["data"].keys()
        assert "test-discord-secret" not in body
        assert "test-groq-secret" not in body
        saved = json.loads(self.cfg._config_path.read_text())
        assert saved == {"SILENCE_THRESHOLD": 0.02}
        assert self.bot.cfg.DISCORD_TOKEN == "test-discord-secret"
        await socket.close()

    async def test_invalid_config_does_not_mutate_or_persist(self):
        for updates in (
            {"CHUNKING_DURATION_SEC": 0},
            {"DEVICE": "invalid"},
            {"TYPO": 1},
            {"SILENCE_THRESHOLD": 2},
        ):
            response = await self.client.post("/api/config", json=updates)
            assert response.status == 400
        assert self.bot.cfg.CHUNKING_DURATION_SEC == 2.5
        assert not self.cfg._config_path.exists()

    async def test_rejects_non_object_and_malformed_json(self):
        for route in (
            "config",
            "models/download",
            "models/activate",
            "engine/switch",
            "summarize",
        ):
            response = await self.client.post(f"/api/{route}", json=[])
            assert response.status == 400
            response = await self.client.post(
                f"/api/{route}",
                data="{broken",
                headers={"Content-Type": "application/json"},
            )
            assert response.status == 400

    async def test_rejects_unknown_and_cloud_downloads(self):
        for id_ in ("not-a-model", "cloud-groq", None, 23):
            response = await self.client.post(
                "/api/models/download", json={"model_id": id_}
            )
            assert response.status == 400
        assert self.api.download_state == {}

    async def test_legacy_whisper_id_downloads_once(self):
        release = asyncio.Event()

        async def download(config, model, progress):
            assert model.model_name == "large-v3"
            await progress(None, "Downloading files")
            await release.wait()

        with patch(
            "diswhisper.api.server.download_model", side_effect=download
        ) as mocked:
            first = await self.client.post(
                "/api/models/download", json={"model_id": "large-v3"}
            )
            second = await self.client.post(
                "/api/models/download", json={"model_id": "whisper-large-v3"}
            )
            assert first.status == second.status == 202
            assert (await second.json())["status"] == "download_in_progress"
            release.set()
            await self.api._download_tasks["whisper-large-v3"]
            assert mocked.call_count == 1
        response = await self.client.get("/api/models/progress")
        assert (await response.json())["whisper-large-v3"]["status"] == "completed"

    async def test_download_failure_is_not_marked_completed(self):
        with patch(
            "diswhisper.api.server.download_model",
            side_effect=RuntimeError("Network unavailable"),
        ):
            response = await self.client.post(
                "/api/models/download", json={"model_id": "whisper-tiny"}
            )
            assert response.status == 202
            await self.api._download_tasks["whisper-tiny"]
        state = self.api.download_state["whisper-tiny"]
        assert state["status"] == "failed" and state["error"] == "Network unavailable"

    async def test_model_activation_selects_and_persists_exact_model(self):
        new_engine = MagicMock(
            engine_name="Whisper", model_name="base", active_device="cpu"
        )
        with (
            patch("diswhisper.bot.is_downloaded", return_value=True),
            patch(
                "diswhisper.bot.create_stt_engine", return_value=new_engine
            ) as factory,
        ):
            response = await self.client.post(
                "/api/models/activate", json={"model_id": "whisper-base"}
            )
        assert response.status == 200
        assert factory.call_args.args[0].WHISPER_MODEL_SIZE == "base"
        assert self.bot.cfg.WHISPER_MODEL_SIZE == "base"
        assert self.bot.engine is new_engine
        assert (
            json.loads(self.cfg._config_path.read_text())["WHISPER_MODEL_SIZE"]
            == "base"
        )

    async def test_failed_engine_switch_preserves_old_config_and_engine(self):
        old_engine = self.bot.engine
        with patch(
            "diswhisper.bot.create_stt_engine", side_effect=RuntimeError("No memory")
        ):
            response = await self.client.post(
                "/api/engine/switch", json={"engine": "whisper"}
            )
        assert response.status == 500
        assert self.bot.engine is old_engine
        assert self.bot.cfg.STT_ENGINE == "sensevoice"
        assert not self.cfg._config_path.exists()

    async def test_ollama_activation_changes_only_summary_settings(self):
        old_engine = self.bot.engine
        with patch(
            "diswhisper.api.server.ollama_models",
            AsyncMock(return_value=(True, {"qwen2.5:3b"})),
        ):
            response = await self.client.post(
                "/api/models/activate", json={"model_id": "ollama-qwen2.5"}
            )
        assert response.status == 200
        assert self.bot.cfg.LOCAL_SUMMARIZER_MODEL == "qwen2.5:3b"
        assert self.bot.cfg.SUMMARIZER_PROVIDER == "local"
        assert self.bot.engine is old_engine

    async def test_summary_honors_selected_cloud_platform_and_null_model(self):
        with patch("diswhisper.api.server.MeetingSummarizer") as summarizer:
            summarizer.return_value.summarize_transcript = AsyncMock(
                return_value="Meeting notes"
            )
            response = await self.client.post(
                "/api/summarize",
                json={
                    "transcript_text": "Alice: Hello",
                    "provider": "cloud",
                    "cloud_platform": "openai",
                    "model": None,
                },
            )
        assert response.status == 200
        assert summarizer.call_args.kwargs["cloud_platform"] == "openai"
        assert summarizer.call_args.kwargs["api_key"] == "test-openai-secret"
        assert summarizer.call_args.kwargs["model_name"] is None

    async def test_cross_origin_requests_are_rejected(self):
        response = await self.client.post(
            "/api/config",
            json={"SILENCE_THRESHOLD": 0.5},
            headers={"Origin": "https://untrusted.example"},
        )
        assert response.status == 403
        assert self.bot.cfg.SILENCE_THRESHOLD == 0.01
