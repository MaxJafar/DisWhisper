"""
Unit tests for configuration loading and validation.
"""

import json
from pathlib import Path

import pytest

from diswhisper.config import Config, load_config, public_config, save_config_updates


def test_default_config():
    cfg = Config()
    assert cfg.STT_ENGINE == "whisper"
    assert cfg.WHISPER_MODEL_SIZE == "base"
    assert cfg.DEVICE == "auto"
    assert cfg.COMPUTE_TYPE == "int8"
    assert cfg.CHUNKING_DURATION_SEC == 2.5
    assert cfg.SILENCE_THRESHOLD == 0.01
    assert cfg.TRANSCRIPT_CHANNEL_NAME == "live-transcript"
    assert cfg.LANGUAGE is None
    assert cfg.SUMMARIZER_PROVIDER == "local"
    assert not cfg.AUTO_CONNECT_BOT


def test_device_validation():
    cfg = Config(DEVICE="CPU")
    assert cfg.DEVICE == "cpu"

    with pytest.raises(ValueError):
        Config(DEVICE="invalid_device")


def test_language_validation():
    cfg1 = Config(LANGUAGE="")
    assert cfg1.LANGUAGE is None

    cfg2 = Config(LANGUAGE="auto")
    assert cfg2.LANGUAGE is None

    cfg3 = Config(LANGUAGE="ES")
    assert cfg3.LANGUAGE == "es"


def test_load_from_json(tmp_path: Path):
    json_file = tmp_path / "custom_config.json"
    custom_data = {
        "DISCORD_TOKEN": "test_token_123",
        "WHISPER_MODEL_SIZE": "medium",
        "DEVICE": "cpu",
        "COMPUTE_TYPE": "int8",
        "CHUNKING_DURATION_SEC": 3.0,
    }
    json_file.write_text(json.dumps(custom_data), encoding="utf-8")

    cfg = load_config(json_file)
    assert cfg.DISCORD_TOKEN == "test_token_123"
    assert cfg.WHISPER_MODEL_SIZE == "medium"
    assert cfg.DEVICE == "cpu"
    assert cfg.COMPUTE_TYPE == "int8"
    assert cfg.CHUNKING_DURATION_SEC == 3.0


@pytest.mark.parametrize(
    "values",
    [
        {"CHUNKING_DURATION_SEC": 0},
        {"CHUNKING_DURATION_SEC": float("nan")},
        {"SILENCE_THRESHOLD": -1},
        {"CONTINUOUS_SPEECH_TIMEOUT_SEC": 0},
        {"API_SERVER_PORT": 70000},
        {"AUTO_LEAVE_EMPTY_SEC": -1},
        {"STT_ENGINE": "typo"},
    ],
)
def test_invalid_runtime_settings_are_rejected(values):
    with pytest.raises(ValueError):
        Config(**values)


def test_custom_config_path_is_preserved_and_only_changes_are_written(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DISCORD_TOKEN", "environment-only-token")
    path = tmp_path / "custom.json"
    path.write_text('{"AUTO_SAVE_TRANSCRIPTS":true}', encoding="utf-8")
    config = load_config(path)
    updated = save_config_updates(config, {"AUTO_POST_TRANSCRIPTS": False})
    assert updated._config_path == path.resolve()
    assert updated.DISCORD_TOKEN == "environment-only-token"
    assert json.loads(path.read_text()) == {
        "AUTO_SAVE_TRANSCRIPTS": True,
        "AUTO_POST_TRANSCRIPTS": False,
    }
    assert "DISCORD_TOKEN" not in public_config(updated)


def test_local_provider_and_discord_options_have_environment_mappings(
    monkeypatch, tmp_path
):
    for key, value in {
        "VOSK_MODEL_ID": "vosk-model-small-ru-0.22",
        "LOCAL_MODEL_DIR": "custom-models",
        "LOCAL_SUMMARIZER_MODEL": "qwen2.5:3b",
        "AUTO_POST_TRANSCRIPTS": "false",
        "AUTO_CREATE_TRANSCRIPT_CHANNEL": "false",
        "AUTO_LEAVE_EMPTY_SEC": "45",
        "TRANSCRIPT_DIR": "custom-transcripts",
        "AUTO_CONNECT_BOT": "true",
        "CUDA_LIBRARY_DIR": "optional-cuda",
    }.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / "config.json"
    path.write_text("{}")
    config = load_config(path)
    assert config.VOSK_MODEL_ID == "vosk-model-small-ru-0.22"
    assert config.LOCAL_MODEL_DIR == "custom-models"
    assert config.LOCAL_SUMMARIZER_MODEL == "qwen2.5:3b"
    assert config.AUTO_LEAVE_EMPTY_SEC == 45
    assert not config.AUTO_POST_TRANSCRIPTS
    assert not config.AUTO_CREATE_TRANSCRIPT_CHANNEL
    assert config.TRANSCRIPT_DIR == "custom-transcripts"
    assert config.AUTO_CONNECT_BOT
    assert config.CUDA_LIBRARY_DIR == "optional-cuda"
