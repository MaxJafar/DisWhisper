"""Dedicated transcript channels and bounded, mention-free live messages."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord

logger = logging.getLogger(__name__)
SAFE_MESSAGE_LENGTH_LIMIT = 1850


class TranscriptReporter:
    def __init__(self, bot: discord.Client, channel_name: str = "live-transcript",
                 continuous_speech_timeout: float = 5.0):
        self.bot = bot
        self.channel_name = channel_name
        self.continuous_speech_timeout = continuous_speech_timeout
        self._target_channel: Optional[discord.TextChannel] = None
        self._channel_locks: dict[int, asyncio.Lock] = {}
        self._known_channels: dict[int, discord.TextChannel] = {}
        self._lock = asyncio.Lock()
        self.reset_state()

    @property
    def target_channel(self) -> Optional[discord.TextChannel]:
        return self._target_channel

    def set_target_channel(self, channel: Optional[discord.TextChannel]) -> None:
        self._target_channel = channel
        self.reset_state()

    def reset_state(self) -> None:
        self._last_speaker_id = None
        self._last_message = None
        self._last_speech_time = 0.0
        self._current_message_text = ""

    def forget_channel(self, guild_id: int, channel_id: int) -> None:
        channel = self._known_channels.get(guild_id)
        if channel and channel.id == channel_id:
            self._known_channels.pop(guild_id, None)
        if self._target_channel and self._target_channel.id == channel_id:
            self.set_target_channel(None)

    @staticmethod
    def _writable(channel: discord.TextChannel, guild: discord.Guild) -> bool:
        if guild.me is None:
            return False
        permissions = channel.permissions_for(guild.me)
        return permissions.view_channel and permissions.send_messages

    async def ensure_transcript_channel(self, guild: discord.Guild,
                                        fallback_channel: Optional[discord.TextChannel] = None) -> discord.TextChannel:
        # Provisioning another server must never redirect the active meeting.
        async with self._channel_locks.setdefault(guild.id, asyncio.Lock()):
            existing = next((channel for channel in guild.text_channels
                             if channel.name.casefold() == self.channel_name.casefold()), None)
            cached = self._known_channels.get(guild.id)
            if not existing and cached and cached.name.casefold() == self.channel_name.casefold():
                existing = cached
            if existing:
                if not self._writable(existing, guild):
                    raise RuntimeError(f"Grant me View Channel and Send Messages in #{self.channel_name}.")
                self._known_channels[guild.id] = existing
                return existing
            if guild.me is None or not guild.me.guild_permissions.manage_channels:
                raise RuntimeError(f"Grant me Manage Channels to create #{self.channel_name}, "
                                   "or create that channel and grant me View Channel and Send Messages.")
            # Read-only for normal members; server moderators retain their permissions.
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                    attach_files=True, embed_links=True, read_message_history=True),
            }
            channel = await guild.create_text_channel(name=self.channel_name, overwrites=overwrites,
                topic="DisWhisper live transcripts and meeting exports. /join to start, /leave to finish.",
                reason="Set up the dedicated DisWhisper transcript channel")
            self._known_channels[guild.id] = channel
            try:
                await channel.send(
                    "🎙️ **DisWhisper is ready**\nJoin a voice channel and use `/join` to start transcription. "
                    "Live speech appears here. Use `/export` for a snapshot, `/summarize` for meeting notes, "
                    "and `/leave` to finish. Completed transcripts are shared here automatically.\n"
                    "The bot also finishes the meeting when everyone leaves the voice channel.",
                    allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logger.warning("Could not send introduction in #%s", channel.name)
            return channel

    async def post_transcript(self, user_id: int, display_name: str, snippet: str, timestamp: float) -> None:
        if not snippet or not snippet.strip():
            return
        clean = snippet.strip()
        name = discord.utils.escape_markdown(display_name.replace("\n", " "))[:200]
        prefix = f"**[{name}]:** "
        limit = SAFE_MESSAGE_LENGTH_LIMIT - len(prefix)
        async with self._lock:
            channel = self._target_channel
            if not channel:
                return
            gap = timestamp - self._last_speech_time
            if (self._last_speaker_id == user_id and 0 <= gap <= self.continuous_speech_timeout
                    and self._last_message is not None):
                updated = f"{self._current_message_text} {clean}"
                if len(updated) <= limit:
                    try:
                        await self._last_message.edit(content=prefix + updated,
                                                     allowed_mentions=discord.AllowedMentions.none())
                        self._current_message_text = updated
                        self._last_speech_time = timestamp
                        return
                    except discord.HTTPException:
                        logger.debug("Previous live transcript message is unavailable; posting a new block")
            while clean:
                if len(clean) > limit:
                    split = clean.rfind(" ", 0, limit + 1)
                    if split < limit // 2:
                        split = limit
                else:
                    split = len(clean)
                part, clean = clean[:split], clean[split:].lstrip()
                try:
                    message = await channel.send(prefix + part, allowed_mentions=discord.AllowedMentions.none())
                except discord.HTTPException:
                    logger.exception("Could not send live transcript to #%s; local logging continues", channel.name)
                    self.reset_state()
                    return
                self._last_message = message
                self._last_speaker_id = user_id
                self._current_message_text = part
                self._last_speech_time = timestamp
