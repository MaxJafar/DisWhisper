"""No-network regressions for Discord channel provisioning and meeting teardown."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from diswhisper.audio.buffer import AudioBufferManager
from diswhisper.bot import DisWhisperBot
from diswhisper.config import Config
from diswhisper.exporter.file_logger import TranscriptFileLogger
from diswhisper.transcriber.worker import TranscriptionWorker
from diswhisper.ui.reporter import TranscriptReporter


def guild_and_channel(guild_id=1):
    guild = MagicMock(id=guild_id)
    guild.me.guild_permissions.manage_channels = True
    channel = MagicMock(id=guild_id * 10, guild=guild)
    channel.name = "live-transcript"
    channel.send = AsyncMock()
    channel.permissions_for.return_value = SimpleNamespace(
        view_channel=True, send_messages=True
    )
    guild.text_channels = []
    guild.create_text_channel = AsyncMock(return_value=channel)
    guild.filesize_limit = 8 * 1024 * 1024
    return guild, channel


@pytest.fixture
async def bot(tmp_path):
    config = Config(ENABLE_API_SERVER=False)
    config._config_path = tmp_path / "config.json"
    engine = SimpleNamespace(
        engine_name="Test engine",
        model_name="test-model",
        active_device="cpu",
        active_compute_type="int8",
        transcribe=lambda audio: ("The final words", "en"),
    )
    instance = DisWhisperBot(config, engine)
    instance.file_logger = TranscriptFileLogger(tmp_path / "transcripts")
    instance._register_commands()
    yield instance
    await instance.close()


def start_fake_session(bot, guild, channel, members=None):
    voice = SimpleNamespace(
        id=111, name="Meeting", mention="<#111>", members=members or []
    )
    vc = SimpleNamespace(
        guild=guild,
        channel=voice,
        is_connected=MagicMock(return_value=True),
        is_listening=MagicMock(return_value=True),
        stop_listening=MagicMock(),
        disconnect=AsyncMock(),
    )
    bot.active_vc = vc
    bot.reporter.set_target_channel(channel)
    bot.file_logger.start_session(voice.name, bot.engine.engine_name)
    return vc


@pytest.mark.anyio
async def test_provisioning_is_idempotent_and_does_not_redirect_active_session():
    reporter = TranscriptReporter(MagicMock())
    guild, channel = guild_and_channel()
    a, b = await asyncio.gather(
        reporter.ensure_transcript_channel(guild),
        reporter.ensure_transcript_channel(guild),
    )
    assert a is b is channel
    assert guild.create_text_channel.await_count == 1
    assert channel.send.await_count == 1
    reporter.set_target_channel(channel)
    other_guild, other_channel = guild_and_channel(2)
    await reporter.ensure_transcript_channel(other_guild)
    assert reporter.target_channel is channel
    assert other_channel.send.await_count == 1


@pytest.mark.anyio
async def test_missing_manage_permission_never_posts_into_a_random_channel():
    reporter = TranscriptReporter(MagicMock())
    guild, unrelated = guild_and_channel()
    unrelated.name = "general"
    guild.text_channels = [unrelated]
    guild.me.guild_permissions.manage_channels = False
    with pytest.raises(RuntimeError, match="Manage Channels"):
        await reporter.ensure_transcript_channel(guild, fallback_channel=unrelated)
    unrelated.send.assert_not_awaited()
    assert reporter.target_channel is None


@pytest.mark.anyio
async def test_bot_provisions_on_invite_without_starting_voice(bot):
    guild, channel = guild_and_channel()
    await bot.on_guild_join(guild)
    guild.create_text_channel.assert_awaited_once()
    channel.send.assert_awaited_once()
    assert bot.active_vc is None


@pytest.mark.anyio
async def test_shutdown_drains_final_audio_before_sharing_exactly_one_export(bot):
    guild, channel = guild_and_channel()
    guild.text_channels = [channel]
    vc = start_fake_session(bot, guild, channel)
    bot.queue = asyncio.Queue()
    bot.buffer_manager = AudioBufferManager(bot.queue, asyncio.get_running_loop())
    stream = bot.buffer_manager.get_or_create_stream(123, "Alice")
    stream.feed_samples(np.full(8000, 0.2, dtype=np.float32))
    bot.worker = TranscriptionWorker(bot.queue, bot.engine, bot._handle_transcript)
    bot.worker.start()
    delivered = []

    async def send(*args, **kwargs):
        if "file" in kwargs:
            delivered.append(kwargs["file"].fp.read().decode("utf-8"))
        return MagicMock(edit=AsyncMock())

    channel.send.side_effect = send
    path = await bot._cleanup_voice_session()
    await bot._cleanup_voice_session()
    assert path.is_file()
    assert "The final words" in delivered[0]
    assert delivered[0].index("The final words") < delivered[0].index(
        "### Meeting Summary"
    )
    assert delivered[0].count("### Meeting Summary") == 1
    assert "Test engine" in delivered[0]
    assert len(delivered) == 1
    vc.stop_listening.assert_called_once()
    vc.disconnect.assert_awaited_once()
    assert bot.queue is bot.worker is bot.buffer_manager is bot.active_vc is None


@pytest.mark.anyio
async def test_commands_from_other_guild_cannot_finish_or_export_a_meeting(bot):
    guild, channel = guild_and_channel()
    vc = start_fake_session(bot, guild, channel)
    other, _ = guild_and_channel(2)
    interaction = MagicMock(guild=other)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.user.guild_permissions.manage_guild = True
    for name in ("leave", "export", "summarize"):
        await bot.tree.get_command(name).callback(interaction)
    assert bot.active_vc is vc
    vc.disconnect.assert_not_awaited()
    channel.send.assert_not_awaited()


@pytest.mark.anyio
async def test_empty_voice_channel_finishes_and_publishes_automatically(bot):
    bot.cfg.AUTO_LEAVE_EMPTY_SEC = 0.01
    guild, channel = guild_and_channel()
    guild.text_channels = [channel]
    start_fake_session(bot, guild, channel)
    bot._schedule_empty_channel_check()
    task = bot._empty_channel_task
    await asyncio.wait_for(task, timeout=1)
    assert bot.active_vc is None
    assert any("file" in call.kwargs for call in channel.send.call_args_list)


@pytest.mark.anyio
async def test_returning_member_cancels_automatic_leave(bot):
    bot.cfg.AUTO_LEAVE_EMPTY_SEC = 30
    guild, channel = guild_and_channel()
    vc = start_fake_session(bot, guild, channel)
    bot._schedule_empty_channel_check()
    task = bot._empty_channel_task
    vc.channel.members = [SimpleNamespace(bot=False)]
    bot._schedule_empty_channel_check()
    await asyncio.gather(task, return_exceptions=True)
    assert bot.active_vc is vc
    assert bot._empty_channel_task is None


@pytest.mark.anyio
async def test_long_transcripts_are_split_and_mentions_are_suppressed():
    reporter = TranscriptReporter(MagicMock())
    _, channel = guild_and_channel()
    channel.send.return_value = MagicMock(edit=AsyncMock())
    reporter.set_target_channel(channel)
    await reporter.post_transcript(1, "**Alice**", "@everyone " + "a" * 6000, 100)
    assert channel.send.await_count >= 4
    for call in channel.send.call_args_list:
        assert len(call.args[0]) <= 1850
        assert not call.kwargs["allowed_mentions"].everyone
    assert "\\*\\*Alice\\*\\*" in channel.send.call_args.args[0]


@pytest.mark.anyio
async def test_speech_continuity_uses_audio_timestamps_instead_of_inference_completion():
    reporter = TranscriptReporter(MagicMock(), continuous_speech_timeout=5)
    _, channel = guild_and_channel()
    message = MagicMock(edit=AsyncMock())
    channel.send.return_value = message
    reporter.set_target_channel(channel)
    await reporter.post_transcript(1, "Alice", "Hello", 100)
    await reporter.post_transcript(1, "Alice", "again", 102)
    message.edit.assert_awaited_once()
    await reporter.post_transcript(1, "Alice", "after a pause", 110)
    assert channel.send.await_count == 2
