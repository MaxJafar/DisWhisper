"""Transport/DAVE compatibility without contacting Discord."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import davey
import discord
import pytest

from diswhisper.audio.voice_client import (
    _PacketDecoder,
    _PacketRouter,
    decrypt_voice_payload,
)


def client_packet(version=1, session=None, user_id=123):
    session = session or MagicMock(decrypt=MagicMock(return_value=b"opus-audio"))
    client = SimpleNamespace(
        _connection=SimpleNamespace(
            dave_protocol_version=version, dave_session=session
        ),
        _get_id_from_ssrc=MagicMock(return_value=user_id),
    )
    return client, SimpleNamespace(ssrc=99, decrypted_data=b"encrypted"), session


def test_dave_decrypts_using_the_speaker_id():
    client, packet, session = client_packet()
    assert decrypt_voice_payload(client, packet)
    session.decrypt.assert_called_once_with(123, davey.MediaType.audio, b"encrypted")
    assert packet.decrypted_data == b"opus-audio"


@pytest.mark.parametrize(
    "case", ["unknown-user", "not-ready", "no-payload", "no-session"]
)
def test_unavailable_dave_packets_are_dropped(case):
    client, packet, session = client_packet()
    if case == "unknown-user":
        client._get_id_from_ssrc.return_value = None
    elif case == "not-ready":
        session.decrypt.side_effect = RuntimeError("NoDecryptorForUser")
    elif case == "no-payload":
        session.decrypt.return_value = b""
    else:
        client._connection.dave_session = None
    assert not decrypt_voice_payload(client, packet)
    assert packet.decrypted_data == b"encrypted"


def test_plain_voice_packets_keep_the_transport_payload():
    client, packet, _ = client_packet(version=0)
    client._connection.dave_session = None
    assert decrypt_voice_payload(client, packet)
    assert packet.decrypted_data == b"encrypted"


def test_dave_session_is_reloaded_after_an_epoch_transition():
    client, packet, _ = client_packet()
    assert decrypt_voice_payload(client, packet)
    replacement = MagicMock(decrypt=MagicMock(return_value=b"new-epoch-opus"))
    client._connection.dave_session = replacement
    assert decrypt_voice_payload(client, packet)
    assert packet.decrypted_data == b"new-epoch-opus"


def test_decryption_happens_before_jitter_buffering_and_fec():
    client, packet, session = client_packet()
    router = _PacketRouter.__new__(_PacketRouter)
    router.reader = SimpleNamespace(voice_client=client)
    with patch("discord.ext.voice_recv.reader.PacketRouter.feed_rtp") as feed:
        router.feed_rtp(packet)
        feed.assert_called_once_with(packet)
        assert feed.call_args.args[0].decrypted_data == b"opus-audio"
        session.decrypt.side_effect = RuntimeError("Transition")
        router.feed_rtp(packet)
        assert feed.call_count == 1


def test_corrupt_opus_frame_does_not_terminate_the_receive_thread():
    decoder = _PacketDecoder.__new__(_PacketDecoder)
    decoder.ssrc = 99
    packet = SimpleNamespace(sequence=1)
    with patch("discord.opus._lib") as lib:
        lib.opus_strerror.return_value = b"corrupt frame"
        error = discord.opus.OpusError(-4)
    with patch(
        "discord.ext.voice_recv.opus.PacketDecoder._decode_packet", side_effect=error
    ):
        assert decoder._decode_packet(packet) == (packet, b"")
