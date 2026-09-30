"""
Main Discord Bot Client and Slash Command Handlers for DisWhisper.
Manages voice lifecycle, connects VoiceRecvClient with DisWhisperSink,
and bridges audio ingestion with the transcription engine and UI reporter.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from diswhisper.audio.buffer import AudioBufferManager, AudioChunk
from diswhisper.audio.receiver import DisWhisperSink
from diswhisper.config import Config
from diswhisper.exporter.file_logger import TranscriptFileLogger
from diswhisper.transcriber.engine import WhisperEngine
from diswhisper.transcriber.worker import TranscriptionWorker
from diswhisper.ui.reporter import TranscriptReporter

logger = logging.getLogger(__name__)


class DisWhisperBot(commands.Bot):
    """
    Discord bot managing voice channel capture and local Whisper transcription.
    """

    def __init__(self, config: Config, engine: WhisperEngine):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.cfg = config
        self.engine = engine

        # State management per guild
        self.active_vc: Optional[voice_recv.VoiceRecvClient] = None
        self.buffer_manager: Optional[AudioBufferManager] = None
        self.worker: Optional[TranscriptionWorker] = None
        self.queue: Optional[asyncio.Queue[AudioChunk]] = None

        self.reporter = TranscriptReporter(
            bot=self,
            channel_name=config.TRANSCRIPT_CHANNEL_NAME,
            continuous_speech_timeout=config.CONTINUOUS_SPEECH_TIMEOUT_SEC,
        )
        self.file_logger = TranscriptFileLogger()
        self.start_time = datetime.datetime.now()

    async def setup_hook(self) -> None:
        """Register slash commands upon bot startup."""
        self._register_commands()
        if self.cfg.GUILD_ID:
            guild_obj = discord.Object(id=self.cfg.GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            logger.info(f"Slash commands synchronized to guild ID {self.cfg.GUILD_ID}.")
        else:
            await self.tree.sync()
            logger.info("Global slash commands synchronized.")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"DisWhisper ready with Whisper '{self.engine.model_size}' on '{self.engine.active_device}'.")

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-cleanup if bot is disconnected or kicked from voice."""
        if member.id == self.user.id and before.channel is not None and after.channel is None:
            logger.info("Bot was disconnected from voice channel. Cleaning up...")
            await self._cleanup_voice_session()

    async def _handle_transcript(
        self, user_id: int, display_name: str, text: str, timestamp: float
    ) -> None:
        """Callback invoked by transcription worker for new text."""
        # 1. Update live Discord channel
        await self.reporter.post_transcript(user_id, display_name, text, timestamp)

        # 2. Persist to markdown meeting file
        if self.cfg.AUTO_SAVE_TRANSCRIPTS:
            self.file_logger.log_utterance(display_name, text, timestamp)

    async def _cleanup_voice_session(self) -> Optional[Path]:
        """Tear down voice client, buffer manager, and finalize transcription worker."""
        if self.buffer_manager:
            self.buffer_manager.flush_all()

        if self.worker:
            await self.worker.stop()
            self.worker = None

        if self.active_vc and self.active_vc.is_connected():
            if self.active_vc.is_listening():
                self.active_vc.stop_listening()
            await self.active_vc.disconnect(force=True)
            self.active_vc = None

        self.buffer_manager = None
        self.reporter.reset_state()

        final_transcript_file = None
        if self.cfg.AUTO_SAVE_TRANSCRIPTS:
            final_transcript_file = self.file_logger.end_session()

        return final_transcript_file

    def _register_commands(self) -> None:
        """Define and attach slash commands."""

        @self.tree.command(name="join", description="Join your active voice channel and begin real-time transcription")
        async def join_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)

            # Check user voice state
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send(
                    "❌ You must be in a voice channel to use `/join`.", ephemeral=True
                )
                return

            voice_channel = interaction.user.voice.channel
            guild = interaction.guild

            # Check bot voice permissions
            perms = voice_channel.permissions_for(guild.me)
            if not perms.connect or not perms.speak:
                await interaction.followup.send(
                    f"❌ I lack permission to join or speak in **{voice_channel.name}**.", ephemeral=True
                )
                return

            # Clean existing session if any
            if self.active_vc and self.active_vc.is_connected():
                await self._cleanup_voice_session()

            try:
                # 1. Locate or create transcript channel
                transcript_channel = await self.reporter.ensure_transcript_channel(
                    guild=guild,
                    fallback_channel=interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None,
                )
                self.reporter.set_target_channel(transcript_channel)

                # 2. Connect via VoiceRecvClient
                vc = await voice_channel.connect(cls=voice_recv.VoiceRecvClient)
                self.active_vc = vc

                # 3. Initialize audio buffer and worker pipeline
                loop = asyncio.get_running_loop()
                self.queue = asyncio.Queue[AudioChunk]()
                self.buffer_manager = AudioBufferManager(
                    transcription_queue=self.queue,
                    loop=loop,
                    chunk_duration_sec=self.cfg.CHUNKING_DURATION_SEC,
                    silence_threshold=self.cfg.SILENCE_THRESHOLD,
                )

                self.worker = TranscriptionWorker(
                    queue=self.queue,
                    engine=self.engine,
                    on_transcript=self._handle_transcript,
                )
                self.worker.start()

                # 4. Start file logger session
                if self.cfg.AUTO_SAVE_TRANSCRIPTS:
                    self.file_logger.start_session(voice_channel.name)

                # 5. Attach AudioSink and start listening
                sink = DisWhisperSink(self.buffer_manager)
                vc.listen(sink)

                # Embed response
                embed = discord.Embed(
                    title="🎙️ DisWhisper Transcriber Active",
                    description=f"Joined **{voice_channel.name}** and listening for speech.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now(),
                )
                embed.add_field(name="Live Transcript Channel", value=f"{transcript_channel.mention}", inline=False)
                embed.add_field(name="Whisper Model", value=f"`{self.engine.model_size}`", inline=True)
                embed.add_field(name="Inference Device", value=f"`{self.engine.active_device} ({self.engine.active_compute_type})`", inline=True)
                embed.add_field(name="Chunk Interval", value=f"`{self.cfg.CHUNKING_DURATION_SEC}s`", inline=True)
                embed.set_footer(text="Speak naturally. Silence is automatically filtered.")

                await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Failed to join voice channel: {e}", exc_info=True)
                await self._cleanup_voice_session()
                await interaction.followup.send(f"❌ Failed to join voice channel: `{e}`")

        @self.tree.command(name="leave", description="Disconnect from voice channel and finalize transcript export")
        async def leave_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)

            if not self.active_vc or not self.active_vc.is_connected():
                await interaction.followup.send("⚠️ DisWhisper is not currently in any voice channel.", ephemeral=True)
                return

            channel_name = self.active_vc.channel.name if self.active_vc.channel else "Voice Channel"
            transcript_file = await self._cleanup_voice_session()

            embed = discord.Embed(
                title="⏹️ DisWhisper Disconnected",
                description=f"Left **{channel_name}** and completed transcription session.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(),
            )

            # If transcript file was generated, upload it
            if transcript_file and transcript_file.is_file():
                file_size = transcript_file.stat().st_size
                if file_size > 0:
                    discord_file = discord.File(str(transcript_file), filename=transcript_file.name)
                    embed.add_field(name="Session Transcript", value=f"Attached: `{transcript_file.name}`", inline=False)
                    await interaction.followup.send(embed=embed, file=discord_file)
                    return

            await interaction.followup.send(embed=embed)

        @self.tree.command(name="status", description="Display DisWhisper engine health, hardware usage, and metrics")
        async def status_command(interaction: discord.Interaction):
            uptime = datetime.datetime.now() - self.start_time
            uptime_str = str(uptime).split(".")[0]

            embed = discord.Embed(
                title="📊 DisWhisper System Status",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(),
            )
            embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
            embed.add_field(name="Model", value=f"`{self.engine.model_size}`", inline=True)
            embed.add_field(
                name="Hardware Device",
                value=f"`{self.engine.active_device}` (`{self.engine.active_compute_type}`)",
                inline=True,
            )

            vc_status = self.active_vc.channel.name if (self.active_vc and self.active_vc.is_connected()) else "Disconnected"
            embed.add_field(name="Voice Channel", value=f"`{vc_status}`", inline=True)

            q_size = self.queue.qsize() if self.queue else 0
            embed.add_field(name="Queue Depth", value=f"`{q_size} chunks`", inline=True)

            active_speakers = self.buffer_manager.active_user_count if self.buffer_manager else 0
            embed.add_field(name="Active Stream Buffers", value=f"`{active_speakers} users`", inline=True)

            # GPU Memory if CUDA
            if self.engine.active_device == "cuda":
                try:
                    import torch
                    if torch.cuda.is_available():
                        allocated = torch.cuda.memory_allocated() / (1024**2)
                        reserved = torch.cuda.memory_reserved() / (1024**2)
                        embed.add_field(name="GPU Memory", value=f"`{allocated:.0f}MB / {reserved:.0f}MB`", inline=True)
                except ImportError:
                    pass

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="export", description="Export the current meeting transcript without leaving")
        async def export_command(interaction: discord.Interaction):
            if not self.file_logger.file_path or not self.file_logger.file_path.is_file():
                await interaction.response.send_message(
                    "⚠️ No active transcript session to export.", ephemeral=True
                )
                return

            current_file = self.file_logger.file_path
            discord_file = discord.File(str(current_file), filename=f"live_{current_file.name}")
            await interaction.response.send_message(
                content="📄 Current session transcript snapshot:",
                file=discord_file,
                ephemeral=False,
            )
