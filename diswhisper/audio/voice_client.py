"""DAVE receive support for discord-ext-voice-recv 0.5.2a179.

discord.py manages the MLS handshake. The upstream receiver decrypts only the
transport layer; our router decrypts the negotiated DAVE layer before buffering
Opus packets, including packets later used for forward error correction.
This adapter is scoped to DisWhisper clients and never patches installed modules.
"""

from __future__ import annotations

import logging

import davey
import discord
from discord.ext import voice_recv
from discord.ext.voice_recv.opus import PacketDecoder
from discord.ext.voice_recv.reader import AudioReader, PacketRouter

logger = logging.getLogger(__name__)


def decrypt_voice_payload(voice_client, packet) -> bool:
    connection = voice_client._connection
    session = getattr(connection, "dave_session", None)
    version = getattr(connection, "dave_protocol_version", 0)
    if not version and session is None:
        return True
    if session is None:
        return False
    user_id = voice_client._get_id_from_ssrc(packet.ssrc)
    if user_id is None:
        return False
    try:
        # Read the current session every packet: MLS epochs can change mid-call.
        decoded = session.decrypt(user_id, davey.MediaType.audio, packet.decrypted_data)
    except Exception:
        logger.debug(
            "DAVE packet unavailable for SSRC %s during voice transition", packet.ssrc
        )
        return False
    if not decoded:
        return False
    packet.decrypted_data = decoded
    return True


class _PacketDecoder(PacketDecoder):
    def _decode_packet(self, packet):
        try:
            return super()._decode_packet(packet)
        except discord.opus.OpusError:
            # One malformed audio frame must not terminate every speaker's stream.
            logger.debug("Discarding invalid Opus frame for SSRC %s", self.ssrc)
            return packet, b""


class _PacketRouter(PacketRouter):
    def feed_rtp(self, packet) -> None:
        if decrypt_voice_payload(self.reader.voice_client, packet):
            super().feed_rtp(packet)

    def get_decoder(self, ssrc):
        with self._lock:
            if ssrc not in self.decoders:
                self.decoders[ssrc] = _PacketDecoder(self, ssrc)
            return self.decoders[ssrc]


class DisWhisperVoiceClient(voice_recv.VoiceRecvClient):
    def listen(self, sink, *, after=None) -> None:
        if not self.is_connected():
            raise discord.ClientException("Not connected to voice")
        if not isinstance(sink, voice_recv.AudioSink):
            raise TypeError("sink must be a voice-recv AudioSink")
        if self.is_listening():
            raise discord.ClientException("Already receiving audio")
        reader = AudioReader(sink, self, after=after)
        reader.packet_router = _PacketRouter(sink, reader)
        self._reader = reader
        reader.start()
