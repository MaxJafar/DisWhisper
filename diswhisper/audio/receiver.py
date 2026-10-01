"""
Discord Voice Receiver AudioSink Hook.
Intercepts decoded PCM voice frames per user and feeds them into the AudioBufferManager.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import voice_recv

from diswhisper.audio.buffer import AudioBufferManager

logger = logging.getLogger(__name__)


class DisWhisperSink(voice_recv.AudioSink):
    """
    Custom AudioSink that routes incoming voice packets from discord-ext-voice-recv
    to the per-user AudioBufferManager.
    """

    def __init__(self, buffer_manager: AudioBufferManager):
        super().__init__()
        self.buffer_manager = buffer_manager

    def wants_opus(self) -> bool:
        """Return False to request decoded PCM audio from voice_recv."""
        return False

    def write(self, user: Optional[discord.Member | discord.User], data: voice_recv.VoiceData) -> None:
        """
        Invoked for every incoming voice packet.
        Extracts user identity and PCM bytes.
        """
        # Determine user identity
        if user is not None and user.bot:
            return
        if user is not None:
            user_id = user.id
            display_name = getattr(user, "display_name", getattr(user, "name", f"User-{user.id}"))
        else:
            user_id = 0
            display_name = "Unknown Speaker"

        # Extract PCM bytes from VoiceData container
        pcm_bytes = None
        if hasattr(data, "pcm") and data.pcm:
            pcm_bytes = data.pcm
        elif isinstance(data, (bytes, bytearray)):
            pcm_bytes = bytes(data)

        if not pcm_bytes:
            return

        try:
            self.buffer_manager.process_pcm_packet(
                user_id=user_id,
                display_name=display_name,
                pcm_bytes=pcm_bytes,
            )
        except Exception as e:
            logger.error(f"Error processing voice packet from {display_name}: {e}", exc_info=True)

    def cleanup(self) -> None:
        """Called when the voice client disconnects or stops listening."""
        logger.info("DisWhisperSink cleanup called. Flushing buffered streams...")
        try:
            self.buffer_manager.close()
        except Exception as e:
            logger.error(f"Error during AudioSink cleanup: {e}")
