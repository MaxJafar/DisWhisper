"""Discord meeting lifecycle, dedicated channel setup, and slash commands."""

from __future__ import annotations

import asyncio
import datetime
import io
import logging
from contextlib import closing
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from diswhisper.api.server import DisWhisperApiServer
from diswhisper.audio.buffer import AudioBufferManager
from diswhisper.audio.receiver import DisWhisperSink
from diswhisper.audio.voice_client import DisWhisperVoiceClient
from diswhisper.config import Config, save_config_updates
from diswhisper.exporter.file_logger import TranscriptFileLogger
from diswhisper.models import activation_updates, get_model, is_downloaded
from diswhisper.summarizer.engine import MeetingSummarizer
from diswhisper.transcriber.base import BaseSTTEngine
from diswhisper.transcriber.factory import create_stt_engine
from diswhisper.transcriber.worker import TranscriptionWorker
from diswhisper.ui.reporter import TranscriptReporter

logger = logging.getLogger(__name__)


class DisWhisperBot(commands.Bot):
    def __init__(self, config: Config, engine: BaseSTTEngine, *, managed: bool = False):
        intents = discord.Intents.default()
        intents.voice_states = True
        # Slash commands and voice capture do not require privileged message/member intents.
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.cfg = config
        self.engine = engine
        # One inference pipeline per process. Never let another guild steal its session.
        self.active_vc = None
        self.buffer_manager = None
        self.worker = None
        self.queue = None
        self._session_lock = asyncio.Lock()
        self._configuration_lock = asyncio.Lock()
        self._idle_audio_task = None
        self._empty_channel_task = None
        self.last_transcript_channel = None
        self.reporter = TranscriptReporter(
            self, config.TRANSCRIPT_CHANNEL_NAME, config.CONTINUOUS_SPEECH_TIMEOUT_SEC
        )
        self.file_logger = TranscriptFileLogger(config.TRANSCRIPT_DIR)
        self._owns_api_server = not managed
        self.start_time = datetime.datetime.now(datetime.timezone.utc)
        self.api_server = (
            DisWhisperApiServer(self, config.API_SERVER_HOST, config.API_SERVER_PORT)
            if config.ENABLE_API_SERVER and not managed
            else None
        )

    async def setup_hook(self) -> None:
        self._register_commands()
        if self.cfg.GUILD_ID:
            guild = discord.Object(id=self.cfg.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        if self.api_server and self._owns_api_server:
            await self.api_server.start()

    async def close(self) -> None:
        try:
            await self._cleanup_voice_session(reason="Bot shutting down")
        finally:
            if self.api_server and self._owns_api_server:
                await self.api_server.stop()
            await super().close()

    async def _provision_guild(self, guild: discord.Guild) -> None:
        if not self.cfg.AUTO_CREATE_TRANSCRIPT_CHANNEL:
            return
        try:
            await self.reporter.ensure_transcript_channel(guild)
        except (discord.HTTPException, RuntimeError):
            logger.warning(
                "Cannot provision the transcript channel in guild %s. "
                "Check Manage Channels, View Channel, and Send Messages permissions.",
                guild.id,
            )

    async def on_ready(self) -> None:
        logger.info(
            "Logged in as %s; engine=%s model=%s",
            self.user,
            self.engine.engine_name,
            self.engine.model_name,
        )
        for guild in self.guilds:
            await self._provision_guild(guild)
        if self.api_server:
            await self.api_server.broadcast_event("bot_status", {"status": "online"})

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self._provision_guild(guild)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        target = self.reporter.target_channel
        expected_vc = self.active_vc
        was_target = bool(target and target.id == channel.id)
        self.reporter.forget_channel(channel.guild.id, channel.id)
        if (
            was_target
            and self.active_vc
            and self.active_vc.guild.id == channel.guild.id
        ):
            try:
                destination = await self.reporter.ensure_transcript_channel(
                    channel.guild
                )
                if self.active_vc is expected_vc:
                    self.reporter.set_target_channel(destination)
            except (discord.HTTPException, RuntimeError):
                logger.warning(
                    "Transcript channel was deleted; local recording continues"
                )

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if self.active_vc and self.active_vc.guild.id == guild.id:
            await self._cleanup_voice_session(
                reason="Bot removed from server", publish=False
            )

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        vc = self.active_vc
        if not vc or member.guild.id != vc.guild.id:
            return
        if (
            self.user
            and member.id == self.user.id
            and before.channel
            and after.channel is None
        ):
            await self._cleanup_voice_session(reason="Disconnected from voice")
            return
        self._schedule_empty_channel_check()

    def _schedule_empty_channel_check(self) -> None:
        vc = self.active_vc
        empty = bool(
            vc
            and vc.channel
            and not any(not member.bot for member in vc.channel.members)
        )
        if not empty or self.cfg.AUTO_LEAVE_EMPTY_SEC == 0:
            if self._empty_channel_task:
                self._empty_channel_task.cancel()
                self._empty_channel_task = None
        elif self._empty_channel_task is None or self._empty_channel_task.done():
            self._empty_channel_task = asyncio.create_task(
                self._leave_empty_channel(vc)
            )

    async def _leave_empty_channel(self, expected_vc) -> None:
        try:
            await asyncio.sleep(self.cfg.AUTO_LEAVE_EMPTY_SEC)
            async with self._session_lock:
                if (
                    self.active_vc is expected_vc
                    and expected_vc.channel
                    and not any(
                        not member.bot for member in expected_vc.channel.members
                    )
                ):
                    await self._finish_voice_session(
                        reason="Everyone left the voice channel"
                    )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Could not finish an empty voice session")
        finally:
            if self._empty_channel_task is asyncio.current_task():
                self._empty_channel_task = None

    async def _flush_idle_audio(self) -> None:
        while self.buffer_manager:
            self.buffer_manager.flush_idle()
            await asyncio.sleep(0.25)

    async def _receiver_stopped(self, expected_vc, error) -> None:
        async with self._session_lock:
            if self.active_vc is expected_vc:
                if error:
                    logger.error(
                        "Voice receive failed",
                        exc_info=(type(error), error, error.__traceback__),
                    )
                await self._finish_voice_session(
                    "Voice stream stopped; meeting transcript preserved"
                )

    async def _handle_transcript(
        self, user_id: int, display_name: str, text: str, timestamp: float
    ) -> None:
        # Save first so Discord delivery failures cannot erase recognized speech.
        if self.file_logger.file_path:
            self.file_logger.log_utterance(display_name, text, timestamp)
        await self.reporter.post_transcript(user_id, display_name, text, timestamp)
        if self.api_server:
            await self.api_server.broadcast_event(
                "transcript_snippet",
                {
                    "user_id": user_id,
                    "speaker": display_name,
                    "text": text,
                    "timestamp": timestamp,
                },
            )

    async def update_configuration(self, updates: dict) -> None:
        async with self._configuration_lock:
            unknown = set(updates) - Config.model_fields.keys()
            if unknown:
                raise ValueError(
                    f"Unknown configuration fields: {', '.join(sorted(unknown))}"
                )
            candidate = Config.model_validate({**self.cfg.model_dump(), **updates})
            changed = {
                key
                for key in updates
                if getattr(candidate, key) != getattr(self.cfg, key)
            }
            engine_fields = {
                "STT_ENGINE",
                "WHISPER_MODEL_SIZE",
                "SENSEVOICE_MODEL_ID",
                "VOSK_MODEL_ID",
                "DEVICE",
                "COMPUTE_TYPE",
                "CUDA_LIBRARY_DIR",
                "LANGUAGE",
                "ENABLE_RICH_EVENTS",
                "CLOUD_STT_PROVIDER",
                "LOCAL_MODEL_DIR",
            }
            if candidate.STT_ENGINE in ("cloud", "groq", "openai"):
                engine_fields.update({"GROQ_API_KEY", "OPENAI_API_KEY"})
            # Model loading must not block Discord heartbeats or the companion API.
            new_engine = (
                await asyncio.to_thread(create_stt_engine, candidate)
                if engine_fields & changed
                else None
            )
            self.cfg = await asyncio.to_thread(save_config_updates, self.cfg, updates)
            self.reporter.channel_name = self.cfg.TRANSCRIPT_CHANNEL_NAME
            self.reporter.continuous_speech_timeout = (
                self.cfg.CONTINUOUS_SPEECH_TIMEOUT_SEC
            )
            if self.buffer_manager:
                self.buffer_manager.update_settings(
                    self.cfg.CHUNKING_DURATION_SEC, self.cfg.SILENCE_THRESHOLD
                )
            if new_engine:
                self.engine = new_engine
                if self.worker:
                    self.worker.engine = new_engine
                if self.api_server:
                    await self.api_server.broadcast_event(
                        "engine_switched",
                        {
                            "engine_name": new_engine.engine_name,
                            "model_name": new_engine.model_name,
                            "device": new_engine.active_device,
                        },
                    )
            if "AUTO_LEAVE_EMPTY_SEC" in changed and self._empty_channel_task:
                self._empty_channel_task.cancel()
                self._empty_channel_task = None
            self._schedule_empty_channel_check()

    async def switch_engine(self, engine: str, model_id: Optional[str] = None) -> None:
        if model_id:
            model = get_model(model_id)
            if model.category == "local_stt" and not await asyncio.to_thread(
                is_downloaded, self.cfg, model
            ):
                raise ValueError(
                    "Download this model in the companion before activating it"
                )
            updates = activation_updates(self.cfg, model)
        else:
            updates = {"STT_ENGINE": engine}
            if engine in ("groq", "openai"):
                updates["CLOUD_STT_PROVIDER"] = engine
        await self.update_configuration(updates)

    async def _cleanup_voice_session(
        self, reason: str = "Meeting finished", publish: bool = True
    ) -> Optional[Path]:
        async with self._session_lock:
            return await self._finish_voice_session(reason, publish)

    async def _finish_voice_session(
        self, reason: str, publish: bool = True
    ) -> Optional[Path]:
        vc = self.active_vc
        if vc is None and self.worker is None and self.file_logger.file_path is None:
            self.reporter.set_target_channel(None)
            return None
        self.active_vc = None  # Prevent disconnect events from finalizing this session a second time.
        self.last_transcript_channel = None
        for task in (self._idle_audio_task, self._empty_channel_task):
            if task and task is not asyncio.current_task():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self._idle_audio_task = None
        self._empty_channel_task = None
        if self.buffer_manager:
            self.buffer_manager.close()
        if vc and vc.is_listening():
            vc.stop_listening()
        # Allow thread-safe flush callbacks to enter the queue before its drain.
        await asyncio.sleep(0)
        if self.worker:
            await self.worker.stop()
            self.worker = None
        self.buffer_manager = None
        self.queue = None
        path = self.file_logger.end_session()
        try:
            if vc and vc.is_connected():
                await vc.disconnect(force=True)
        except discord.DiscordException:
            logger.exception("Voice disconnect failed after transcript finalization")
        if publish and self.cfg.AUTO_POST_TRANSCRIPTS and vc:
            try:
                channel = self.reporter.target_channel
                if channel is None or channel.guild.id != vc.guild.id:
                    channel = await self.reporter.ensure_transcript_channel(vc.guild)
                await self._publish_transcript(channel, path, reason)
                self.last_transcript_channel = channel
            except (discord.HTTPException, RuntimeError, OSError):
                logger.exception(
                    "Could not publish completed transcript; the local file is preserved"
                )
        self.reporter.set_target_channel(None)
        if self.api_server:
            await self.api_server.broadcast_event(
                "session_finished",
                {"reason": reason, "filename": path.name if path else None},
            )
        return path

    async def _publish_transcript(
        self, channel: discord.TextChannel, path: Optional[Path], reason: str
    ) -> None:
        embed = discord.Embed(
            title="📄 Meeting transcript",
            description=reason,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Recognized utterances", value=str(self.file_logger.total_utterances)
        )
        if path and path.is_file():
            # Freeze snapshots; the active log may keep growing while Discord uploads.
            content = (
                path.read_bytes()
                if path.stat().st_size <= channel.guild.filesize_limit
                else None
            )
            if content is not None and len(content) <= channel.guild.filesize_limit:
                with closing(
                    discord.File(io.BytesIO(content), filename=path.name)
                ) as file:
                    await channel.send(
                        embed=embed,
                        file=file,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                return
            embed.add_field(
                name="Export",
                value="The transcript exceeds this server's upload limit. "
                "It is saved locally and available in the companion.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Export",
                value="Live messages are retained above. Enable automatic saving "
                "in the companion to attach a Markdown file.",
                inline=False,
            )
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    def _can_control_session(self, interaction: discord.Interaction) -> bool:
        vc = self.active_vc
        if not interaction.guild or not vc or vc.guild.id != interaction.guild.id:
            return False
        voice = getattr(interaction.user, "voice", None)
        return bool(
            interaction.user.guild_permissions.manage_guild
            or (
                voice
                and voice.channel
                and vc.channel
                and voice.channel.id == vc.channel.id
            )
        )

    async def _require_session(self, interaction: discord.Interaction) -> bool:
        if self._can_control_session(interaction):
            return True
        await interaction.followup.send(
            "Join my active voice channel to control this meeting, "
            "or ask a member with Manage Server permission.",
            ephemeral=True,
        )
        return False

    def _register_commands(self) -> None:
        @self.tree.error
        async def command_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ):
            logger.error(
                "Slash command failed",
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "I couldn't complete that command. Check my channel permissions and the bot log."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

        @self.tree.command(
            name="join",
            description="Join your voice channel and start a meeting transcript",
        )
        @app_commands.guild_only()
        async def join_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            voice = getattr(interaction.user, "voice", None)
            if not voice or not isinstance(voice.channel, discord.VoiceChannel):
                await interaction.followup.send(
                    "Join a regular voice channel first, then use `/join`.",
                    ephemeral=True,
                )
                return
            channel = voice.channel
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.view_channel or not permissions.connect:
                await interaction.followup.send(
                    "I need View Channel and Connect permissions in your voice channel.",
                    ephemeral=True,
                )
                return
            async with self._session_lock:
                if self.active_vc or self.worker:
                    await interaction.followup.send(
                        "I'm already transcribing a meeting. Finish it with `/leave` before starting another.",
                        ephemeral=True,
                    )
                    return
                try:
                    destination = await self.reporter.ensure_transcript_channel(
                        interaction.guild
                    )
                    self.reporter.set_target_channel(destination)
                    vc = await channel.connect(
                        cls=DisWhisperVoiceClient, self_deaf=False
                    )
                    self.active_vc = vc
                    self.queue = asyncio.Queue(maxsize=128)
                    self.buffer_manager = AudioBufferManager(
                        self.queue,
                        asyncio.get_running_loop(),
                        self.cfg.CHUNKING_DURATION_SEC,
                        self.cfg.SILENCE_THRESHOLD,
                    )
                    self.worker = TranscriptionWorker(
                        self.queue, self.engine, self._handle_transcript
                    )
                    if self.cfg.AUTO_SAVE_TRANSCRIPTS:
                        self.file_logger.start_session(
                            channel.name, self.engine.engine_name
                        )
                    self.worker.start()
                    loop = asyncio.get_running_loop()

                    def receiver_stopped(error):
                        if not loop.is_closed():
                            loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(
                                    self._receiver_stopped(vc, error)
                                )
                            )

                    vc.listen(
                        DisWhisperSink(self.buffer_manager), after=receiver_stopped
                    )
                    self._idle_audio_task = asyncio.create_task(
                        self._flush_idle_audio()
                    )
                    await destination.send(
                        f"🎙️ **Meeting started in {channel.mention}**\n"
                        f"Transcribing with **{self.engine.engine_name}**. Live speech and the completed "
                        "transcript will appear here. Use `/leave` to finish.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    await interaction.followup.send(
                        f"Listening in {channel.mention}. Transcripts: {destination.mention}",
                        ephemeral=True,
                    )
                    self._schedule_empty_channel_check()
                except (RuntimeError, discord.Forbidden) as error:
                    await self._finish_voice_session("Meeting could not start")
                    await interaction.followup.send(str(error), ephemeral=True)
                except Exception:
                    logger.exception("Could not start voice transcription")
                    await self._finish_voice_session("Meeting could not start")
                    await interaction.followup.send(
                        "Could not start transcription. Check voice permissions, "
                        "the active model, and the bot log.",
                        ephemeral=True,
                    )

        @self.tree.command(
            name="leave",
            description="Finish the meeting and share its transcript in the dedicated channel",
        )
        @app_commands.guild_only()
        async def leave_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self._session_lock:
                if not await self._require_session(interaction):
                    return
                path = await self._finish_voice_session("Meeting finished with /leave")
                posted = self.last_transcript_channel
            if posted:
                message = f"Meeting finished. Transcript shared in {posted.mention}."
            elif not self.cfg.AUTO_POST_TRANSCRIPTS:
                message = "Meeting finished. Automatic transcript posting is disabled."
            elif path and path.is_file():
                message = "Meeting finished and saved locally. I couldn't post the export; check my channel and attachment permissions."
            else:
                message = (
                    "Meeting finished. Check the bot log if an export was expected."
                )
            await interaction.followup.send(message, ephemeral=True)

        @self.tree.command(
            name="export",
            description="Share a snapshot of the current transcript in the dedicated channel",
        )
        @app_commands.guild_only()
        async def export_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self._session_lock:
                if not await self._require_session(interaction):
                    return
                path = self.file_logger.file_path
                if not path or not path.is_file():
                    await interaction.followup.send(
                        "Enable automatic transcript saving before starting the meeting.",
                        ephemeral=True,
                    )
                    return
                destination = await self.reporter.ensure_transcript_channel(
                    interaction.guild
                )
                await self._publish_transcript(
                    destination, path, "Snapshot of the current meeting"
                )
            await interaction.followup.send(
                f"Snapshot shared in {destination.mention}.", ephemeral=True
            )

        @self.tree.command(
            name="status",
            description="Show the active transcription engine and meeting health",
        )
        @app_commands.guild_only()
        async def status_command(interaction: discord.Interaction):
            embed = discord.Embed(title="DisWhisper status", color=discord.Color.blue())
            embed.add_field(name="Engine", value=self.engine.engine_name)
            embed.add_field(name="Model", value=self.engine.model_name)
            embed.add_field(
                name="Device",
                value=f"{self.engine.active_device} ({self.engine.active_compute_type})",
            )
            vc = self.active_vc
            if vc and vc.guild.id == interaction.guild.id:
                embed.add_field(
                    name="Meeting",
                    value=vc.channel.mention if vc.channel else "Disconnecting",
                )
                embed.add_field(
                    name="Queued audio",
                    value=str(self.queue.qsize() if self.queue else 0),
                )
            else:
                embed.add_field(
                    name="Meeting",
                    value="Busy in another server" if vc else "Ready — use /join",
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(
            name="engine",
            description="View or switch the speech provider: SenseVoice, Whisper, Vosk, or cloud",
        )
        @app_commands.guild_only()
        @app_commands.choices(
            target_engine=[
                app_commands.Choice(name="SenseVoice", value="sensevoice"),
                app_commands.Choice(name="Whisper", value="whisper"),
                app_commands.Choice(name="Vosk (offline CPU)", value="vosk"),
                app_commands.Choice(name="Groq Cloud", value="groq"),
                app_commands.Choice(name="OpenAI Cloud", value="openai"),
            ]
        )
        async def engine_command(
            interaction: discord.Interaction, target_engine: Optional[str] = None
        ):
            await interaction.response.defer(ephemeral=True)
            if target_engine:
                if self.active_vc:
                    if not await self._require_session(interaction):
                        return
                elif not interaction.user.guild_permissions.manage_guild:
                    await interaction.followup.send(
                        "Manage Server permission is required to change providers before a meeting.",
                        ephemeral=True,
                    )
                    return
                try:
                    await self.switch_engine(target_engine)
                except ValueError as error:
                    await interaction.followup.send(str(error), ephemeral=True)
                    return
            await interaction.followup.send(
                f"Active provider: **{self.engine.engine_name}** · `{self.engine.model_name}` · "
                f"`{self.engine.active_device}`. Choose and download specific models in the companion.",
                ephemeral=True,
            )

        @self.tree.command(
            name="summarize",
            description="Share AI meeting notes in the dedicated transcript channel",
        )
        @app_commands.guild_only()
        async def summarize_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self._session_lock:
                if not await self._require_session(interaction):
                    return
                path = self.file_logger.file_path
                if (
                    not path
                    or not path.is_file()
                    or self.file_logger.total_utterances == 0
                ):
                    await interaction.followup.send(
                        "No recognized speech to summarize yet. Enable automatic saving and start speaking.",
                        ephemeral=True,
                    )
                    return
                text = path.read_text(encoding="utf-8")
                destination = await self.reporter.ensure_transcript_channel(
                    interaction.guild
                )
                cfg = self.cfg.model_copy(deep=True)
            summarizer = MeetingSummarizer(
                provider=cfg.SUMMARIZER_PROVIDER,
                cloud_platform=cfg.CLOUD_STT_PROVIDER,
                api_key=cfg.GROQ_API_KEY
                if cfg.CLOUD_STT_PROVIDER == "groq"
                else cfg.OPENAI_API_KEY,
                model_name=cfg.LOCAL_SUMMARIZER_MODEL
                if cfg.SUMMARIZER_PROVIDER == "local"
                else cfg.SUMMARIZER_MODEL,
                local_llm_url=cfg.LOCAL_LLM_URL,
            )
            summary = await summarizer.summarize_transcript(text)
            if summary.startswith(("❌", "⚠️")):
                await interaction.followup.send(summary, ephemeral=True)
                return
            with closing(
                discord.File(
                    io.BytesIO(summary.encode("utf-8")), filename=f"summary_{path.name}"
                )
            ) as file:
                await destination.send(
                    "📝 **AI meeting notes**",
                    file=file,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            await interaction.followup.send(
                f"Meeting notes shared in {destination.mention}.", ephemeral=True
            )
