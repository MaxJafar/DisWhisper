"""
Real-Time Output Interface for Discord.
Streams live transcripts to a designated text channel (#live-transcript)
with continuous speech debouncing to eliminate channel spam.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import discord

logger = logging.getLogger(__name__)

DISCORD_MAX_MESSAGE_LENGTH = 2000
SAFE_MESSAGE_LENGTH_LIMIT = 1850


class TranscriptReporter:
    """
    Manages live transcript streaming and debounced message editing in Discord.
    """

    def __init__(
        self,
        bot: discord.Client,
        channel_name: str = "live-transcript",
        continuous_speech_timeout: float = 5.0,
    ):
        self.bot = bot
        self.channel_name = channel_name
        self.continuous_speech_timeout = continuous_speech_timeout

        self._target_channel: Optional[discord.TextChannel] = None
        self._last_speaker_id: Optional[int] = None
        self._last_speaker_name: Optional[str] = None
        self._last_message: Optional[discord.Message] = None
        self._last_speech_time: float = 0.0
        self._current_message_text: str = ""
        self._lock = asyncio.Lock()

    def set_target_channel(self, channel: discord.TextChannel) -> None:
        """Explicitly set the destination text channel."""
        self._target_channel = channel
        self.reset_state()
        logger.info(f"Target transcript channel set to #{channel.name} ({channel.id})")

    def reset_state(self) -> None:
        """Reset conversation continuity tracking."""
        self._last_speaker_id = None
        self._last_speaker_name = None
        self._last_message = None
        self._last_speech_time = 0.0
        self._current_message_text = ""

    async def ensure_transcript_channel(
        self, guild: discord.Guild, fallback_channel: Optional[discord.TextChannel] = None
    ) -> discord.TextChannel:
        """
        Locates existing transcript channel or creates one automatically.
        Falls back to provided channel if permissions are lacking.
        """
        if self._target_channel and self._target_channel.guild.id == guild.id:
            return self._target_channel

        # 1. Search existing channels
        for channel in guild.text_channels:
            if channel.name.lower() == self.channel_name.lower():
                self._target_channel = channel
                return channel

        # 2. Try to create the channel
        try:
            new_channel = await guild.create_text_channel(
                name=self.channel_name,
                topic="Real-time meeting transcript powered by DisWhisper (Whisper Large-v3)",
            )
            self._target_channel = new_channel
            logger.info(f"Created dedicated transcript channel #{new_channel.name}")
            return new_channel
        except discord.Forbidden:
            logger.warning(
                f"Missing permissions to create #{self.channel_name}. Using fallback channel."
            )
        except Exception as e:
            logger.error(f"Error creating #{self.channel_name}: {e}")

        # 3. Fallback
        if fallback_channel:
            self._target_channel = fallback_channel
            return fallback_channel

        # 4. First available writable channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                self._target_channel = channel
                return channel

        raise RuntimeError(f"No writable text channel found in guild {guild.name}")

    async def post_transcript(
        self,
        user_id: int,
        display_name: str,
        snippet: str,
        timestamp: float,
    ) -> None:
        """
        Post or append transcript snippet.
        If the same user spoke within continuous_speech_timeout seconds,
        appends to existing message. Otherwise, creates a new message block.
        """
        if not snippet or not snippet.strip():
            return

        clean_snippet = snippet.strip()

        async with self._lock:
            channel = self._target_channel
            if not channel:
                logger.warning("No transcript channel selected. Dropping snippet.")
                return

            now = time.time()
            time_since_last_speech = now - self._last_speech_time
            is_same_speaker = (self._last_speaker_id == user_id)
            within_timeout = (time_since_last_speech <= self.continuous_speech_timeout)

            # Check if we should append to the current active message
            should_append = (
                is_same_speaker
                and within_timeout
                and self._last_message is not None
            )

            if should_append:
                updated_text = f"{self._current_message_text} {clean_snippet}"
                new_content = f"**[{display_name}]:** {updated_text}"

                # Ensure we don't exceed Discord's 2000 character limit
                if len(new_content) <= SAFE_MESSAGE_LENGTH_LIMIT:
                    try:
                        await self._last_message.edit(content=new_content)
                        self._current_message_text = updated_text
                        self._last_speech_time = now
                        return
                    except discord.NotFound:
                        logger.debug("Previous transcript message was deleted; creating new message.")
                    except discord.HTTPException as e:
                        logger.warning(f"Failed to edit transcript message: {e}; creating new message.")

            # Otherwise, start a fresh message block
            new_content = f"**[{display_name}]:** {clean_snippet}"
            try:
                msg = await channel.send(new_content)
                self._last_message = msg
                self._last_speaker_id = user_id
                self._last_speaker_name = display_name
                self._current_message_text = clean_snippet
                self._last_speech_time = now
            except discord.HTTPException as e:
                logger.error(f"Failed to send transcript message to #{channel.name}: {e}")
