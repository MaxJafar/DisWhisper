"""First-run and lifecycle regressions for the companion-managed backend."""
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from diswhisper.config import Config
from diswhisper.runtime import CompanionRuntime


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = Config()
    config._config_path = tmp_path / "config.json"
    service = CompanionRuntime(config, "test-session")
    service.api_server.broadcast_event = AsyncMock()
    return service


@pytest.mark.anyio
async def test_first_run_does_not_load_a_model_or_require_credentials(runtime, monkeypatch):
    factory = MagicMock(side_effect=AssertionError("First-run setup must not load a model"))
    monkeypatch.setattr("diswhisper.runtime.create_stt_engine", factory)
    assert runtime.state == "idle"
    assert not runtime.engine_loaded
    assert runtime.engine.model_name == "whisper-base"
    await runtime.update_configuration({"LANGUAGE": "ru", "AUTO_CONNECT_BOT": True})
    assert runtime.cfg.LANGUAGE == "ru"
    assert runtime.cfg._config_path.is_file()
    factory.assert_not_called()
    with pytest.raises(ValueError, match="Discord bot"):
        await runtime.start_bot()


@pytest.mark.anyio
async def test_uninstalled_model_cannot_start_or_be_selected(runtime, monkeypatch):
    runtime.cfg.DISCORD_TOKEN = "test-token"
    monkeypatch.setattr("diswhisper.runtime.is_downloaded", lambda *args: False)
    with pytest.raises(ValueError, match="Download"):
        await runtime.start_bot()
    with pytest.raises(ValueError, match="Download"):
        await runtime.switch_engine("whisper", "whisper-small")
    assert runtime.cfg.WHISPER_MODEL_SIZE == "base"


@pytest.mark.anyio
async def test_start_stop_is_idempotent_and_keeps_setup_service_available(runtime, monkeypatch):
    runtime.cfg.DISCORD_TOKEN = "test-token"
    monkeypatch.setattr("diswhisper.runtime.is_downloaded", lambda *args: True)
    monkeypatch.setattr("diswhisper.runtime.create_stt_engine", lambda *args: MagicMock())
    started = asyncio.Event()
    finished = asyncio.Event()
    fake = MagicMock()
    fake.is_ready.return_value = False
    fake.user = None
    fake.active_vc = None

    async def start(token):
        assert token == "test-token"
        fake.is_ready.return_value = True
        started.set()
        await finished.wait()

    async def close():
        fake.is_ready.return_value = False
        finished.set()

    fake.start = start
    fake.close = AsyncMock(side_effect=close)
    constructor = MagicMock(return_value=fake)
    monkeypatch.setattr("diswhisper.runtime.DisWhisperBot", constructor)
    await runtime.start_bot()
    await runtime.start_bot()
    await asyncio.wait_for(started.wait(), timeout=3)
    assert runtime.state == "online"
    with pytest.raises(ValueError, match="Stop the bot"):
        await runtime.update_configuration({"GUILD_ID": 123})
    await runtime.stop_bot()
    await runtime.stop_bot()
    assert runtime.state == "idle"
    assert not runtime.engine_loaded
    assert not runtime.shutdown_requested.is_set()
    constructor.assert_called_once()
    assert constructor.call_args.kwargs["managed"] is True


@pytest.mark.anyio
async def test_start_failure_redacts_token_and_allows_retry(runtime, monkeypatch):
    runtime.cfg.DISCORD_TOKEN = "test-private-token"
    monkeypatch.setattr("diswhisper.runtime.is_downloaded", lambda *args: True)
    monkeypatch.setattr("diswhisper.runtime.create_stt_engine", MagicMock(side_effect=RuntimeError("bad test-private-token")))
    await runtime.start_bot()
    await runtime._bot_task
    assert runtime.state == "error"
    assert "test-private-token" not in runtime.last_error
    assert "[credential]" in runtime.last_error
    await runtime.stop_bot()
    assert runtime.state == "idle"


@pytest.mark.anyio
async def test_stop_waits_for_background_model_initialization(runtime, monkeypatch):
    runtime.cfg.DISCORD_TOKEN = "test-token"
    monkeypatch.setattr("diswhisper.runtime.is_downloaded", lambda *args: True)
    entered, release = threading.Event(), threading.Event()

    def load(_):
        entered.set()
        release.wait(timeout=3)
        return MagicMock()

    factory = MagicMock(side_effect=load)
    constructor = MagicMock(side_effect=AssertionError("Cancelled startup cannot connect"))
    monkeypatch.setattr("diswhisper.runtime.create_stt_engine", factory)
    monkeypatch.setattr("diswhisper.runtime.DisWhisperBot", constructor)
    await runtime.start_bot()
    await asyncio.to_thread(entered.wait, 2)
    stop = asyncio.create_task(runtime.stop_bot())
    await asyncio.sleep(0.02)
    assert not stop.done()
    release.set()
    await asyncio.wait_for(stop, 3)
    constructor.assert_not_called()
    assert runtime.state == "idle"
