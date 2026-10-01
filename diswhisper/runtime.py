"""Keep the local companion service available before Discord or a model is ready."""

from __future__ import annotations

import asyncio
import datetime
import logging
from pathlib import Path

from diswhisper.api.server import DisWhisperApiServer
from diswhisper.bot import DisWhisperBot
from diswhisper.config import Config, save_config_updates
from diswhisper.exporter.file_logger import TranscriptFileLogger
from diswhisper.models import activation_updates, get_model, is_downloaded
from diswhisper.transcriber.factory import create_stt_engine

logger = logging.getLogger(__name__)


class UnloadedEngine:
    """Display the selected model without downloading or allocating it."""

    def __init__(self, config: Config):
        self.engine_name = {"whisper": "Whisper", "sensevoice": "SenseVoice", "vosk": "Vosk"}.get(config.STT_ENGINE, "Cloud Whisper")
        self.model_name = selected_model_id(config)
        self.active_device = "not_loaded"
        self.active_compute_type = config.COMPUTE_TYPE


def selected_model_id(config: Config) -> str:
    if config.STT_ENGINE == "whisper":
        return f"whisper-{config.WHISPER_MODEL_SIZE}"
    if config.STT_ENGINE == "vosk":
        return config.VOSK_MODEL_ID
    if config.STT_ENGINE == "sensevoice":
        return "sensevoice"
    provider = config.CLOUD_STT_PROVIDER if config.STT_ENGINE == "cloud" else config.STT_ENGINE
    return f"cloud-{provider}"


class CompanionRuntime:
    def __init__(self, config: Config, session_id: str = ""):
        self.cfg = config
        self.session_id = session_id
        self.start_time = datetime.datetime.now(datetime.timezone.utc)
        self.file_logger = TranscriptFileLogger(config.TRANSCRIPT_DIR)
        self._bot = None
        self._bot_task = None
        self._lock = asyncio.Lock()
        self._starting = False
        self.last_error = ""
        self.shutdown_requested = asyncio.Event()
        self.api_server = DisWhisperApiServer(self, config.API_SERVER_HOST, config.API_SERVER_PORT)

    @property
    def engine(self):
        return self._bot.engine if self._bot else UnloadedEngine(self.cfg)

    @property
    def engine_loaded(self) -> bool:
        return self._bot is not None

    @property
    def user(self):
        return self._bot.user if self._bot else None

    @property
    def active_vc(self):
        return self._bot.active_vc if self._bot else None

    @property
    def queue(self):
        return self._bot.queue if self._bot else None

    @property
    def buffer_manager(self):
        return self._bot.buffer_manager if self._bot else None

    @property
    def state(self) -> str:
        if self.is_ready():
            return "online"
        if self._starting:
            return "starting"
        if self.last_error:
            return "error"
        if self._bot_task and not self._bot_task.done():
            return "connecting"
        return "error" if self.last_error else "idle"

    def is_ready(self) -> bool:
        return bool(self._bot and self._bot.is_ready())

    async def update_configuration(self, updates: dict) -> None:
        async with self._lock:
            if self._starting:
                raise ValueError("Wait for the bot to finish starting before changing settings.")
            if self._bot:
                if set(updates) & {"DISCORD_TOKEN", "GUILD_ID", "TRANSCRIPT_DIR"}:
                    raise ValueError("Stop the bot before changing its account, server, or transcript folder.")
                await self._bot.update_configuration(updates)
                self.cfg = self._bot.cfg
            else:
                candidate = Config.model_validate({**self.cfg.model_dump(), **updates})
                # Creating the output folder can fail; do it before committing settings.
                Path(candidate.TRANSCRIPT_DIR).mkdir(parents=True, exist_ok=True)
                self.cfg = await asyncio.to_thread(save_config_updates, self.cfg, updates)
            self.file_logger.output_dir = Path(self.cfg.TRANSCRIPT_DIR)

    async def switch_engine(self, engine: str, model_id: str | None = None) -> None:
        if model_id:
            model = get_model(model_id)
            if model.category == "local_stt" and not await asyncio.to_thread(is_downloaded, self.cfg, model):
                raise ValueError("Download this model before using it.")
            updates = activation_updates(self.cfg, model)
        else:
            updates = {"STT_ENGINE": engine}
            if engine in ("groq", "openai"):
                updates["CLOUD_STT_PROVIDER"] = engine
        await self.update_configuration(updates)

    async def start_bot(self) -> None:
        async with self._lock:
            if self._bot_task and not self._bot_task.done():
                return
            if not self.cfg.DISCORD_TOKEN.strip():
                raise ValueError("Connect your Discord bot before starting.")
            model = get_model(selected_model_id(self.cfg))
            if not await asyncio.to_thread(is_downloaded, self.cfg, model):
                raise ValueError("Download your selected speech model, or configure this cloud provider's API key, before starting.")
            self.last_error = ""
            self._starting = True
            self._bot_task = asyncio.create_task(self._run_bot(self.cfg.model_copy(deep=True)), name="discord-bot")

    async def _run_bot(self, config: Config) -> None:
        bot = None
        load_task = asyncio.create_task(asyncio.to_thread(create_stt_engine, config))
        try:
            engine = await asyncio.shield(load_task)
            bot = DisWhisperBot(config, engine, managed=True)
            bot.api_server = self.api_server
            self._bot = bot
            self._starting = False
            await bot.start(config.DISCORD_TOKEN.strip())
        except asyncio.CancelledError:
            # Model initialization uses a worker thread. Let it finish before releasing it.
            await asyncio.gather(load_task, return_exceptions=True)
            raise
        except Exception as error:
            self.last_error = str(error).replace(config.DISCORD_TOKEN, "[credential]")
            logger.error("Bot could not start: %s", self.last_error)
        finally:
            if bot:
                await bot.close()
            self._bot = None
            self._starting = False
            await self.api_server.broadcast_event("bot_status", {"status": self.state, "error": self.last_error})

    async def stop_bot(self) -> None:
        async with self._lock:
            task = self._bot_task
            if self._bot:
                await self._bot.close()
            if task and not task.done():
                task.cancel()
            if task:
                await asyncio.gather(task, return_exceptions=True)
            self._bot_task = None
            self._bot = None
            self._starting = False
            self.last_error = ""

    async def run(self) -> None:
        await self.api_server.start()
        try:
            if self.cfg.AUTO_CONNECT_BOT and self.cfg.DISCORD_TOKEN:
                try:
                    await self.start_bot()
                except ValueError as error:
                    self.last_error = str(error)
            await self.shutdown_requested.wait()
        finally:
            await self.stop_bot()
            await self.api_server.stop()
