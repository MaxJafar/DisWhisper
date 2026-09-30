"""
Unit tests for configuration loading and validation.
"""

import json
from pathlib import Path
import pytest
from diswhisper.config import Config, load_config


def test_default_config():
    cfg = Config()
    assert cfg.WHISPER_MODEL_SIZE == "large-v3"
    assert cfg.DEVICE == "cuda"
    assert cfg.COMPUTE_TYPE == "float16"
    assert cfg.CHUNKING_DURATION_SEC == 2.5
    assert cfg.SILENCE_THRESHOLD == 0.01
    assert cfg.TRANSCRIPT_CHANNEL_NAME == "live-transcript"
    assert cfg.LANGUAGE == "en"


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
