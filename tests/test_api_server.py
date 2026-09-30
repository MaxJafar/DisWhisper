"""
Unit tests for DisWhisperApiServer endpoints.
"""

from unittest.mock import MagicMock
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import pytest

from diswhisper.api.server import DisWhisperApiServer
from diswhisper.config import Config


class TestApiServer(AioHTTPTestCase):
    async def get_application(self):
        mock_bot = MagicMock()
        mock_bot.start_time = MagicMock()
        mock_bot.user = "TestBot#1234"
        mock_bot.active_vc = None
        mock_bot.engine.engine_name = "SenseVoice"
        mock_bot.engine.model_name = "SenseVoiceSmall-int8"
        mock_bot.engine.active_device = "cpu"
        mock_bot.engine.active_compute_type = "int8"
        mock_bot.queue.qsize.return_value = 0
        mock_bot.buffer_manager = None
        mock_bot.cfg = Config()

        api_server = DisWhisperApiServer(bot=mock_bot)
        return api_server.app

    @unittest_run_loop
    async def test_get_status(self):
        resp = await self.client.request("GET", "/api/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "online"
        assert data["engine_name"] == "SenseVoice"

    @unittest_run_loop
    async def test_get_models(self):
        resp = await self.client.request("GET", "/api/models")
        assert resp.status == 200
        data = await resp.json()
        assert "models" in data
        assert len(data["models"]) >= 4

    @unittest_run_loop
    async def test_get_config(self):
        resp = await self.client.request("GET", "/api/config")
        assert resp.status == 200
        data = await resp.json()
        assert "STT_ENGINE" in data
