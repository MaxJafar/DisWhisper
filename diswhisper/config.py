"""
Configuration loader and validation module for DisWhisper.
Supports loading from config.json and .env environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """DisWhisper application configuration model."""

    DISCORD_TOKEN: str = Field(
        default="",
        description="Discord Bot Token from Discord Developer Portal",
    )
    GUILD_ID: Optional[int] = Field(
        default=None,
        description="Optional Guild ID for instant slash command registration",
    )
    TRANSCRIPT_CHANNEL_NAME: str = Field(
        default="live-transcript",
        description="Discord text channel name where live transcripts are sent",
    )
    WHISPER_MODEL_SIZE: str = Field(
        default="large-v3",
        description="Whisper model size: tiny, base, small, medium, large-v3, large-v3-turbo",
    )
    DEVICE: str = Field(
        default="cuda",
        description="Inference device: 'cuda' or 'cpu'",
    )
    COMPUTE_TYPE: str = Field(
        default="float16",
        description="Quantization/Precision: 'float16', 'int8_float16', 'int8', 'float32'",
    )
    LANGUAGE: Optional[str] = Field(
        default="en",
        description="Language code (e.g. 'en', 'es') or None for auto-detection",
    )
    CHUNKING_DURATION_SEC: float = Field(
        default=2.5,
        description="Duration of audio chunk in seconds passed to transcriber",
    )
    SILENCE_THRESHOLD: float = Field(
        default=0.01,
        description="RMS amplitude below which chunk is discarded as silence",
    )
    CONTINUOUS_SPEECH_TIMEOUT_SEC: float = Field(
        default=5.0,
        description="Seconds to append to same user message before creating new block",
    )
    AUTO_SAVE_TRANSCRIPTS: bool = Field(
        default=True,
        description="Save markdown transcripts to transcripts/ folder",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )

    @field_validator("DEVICE")
    @classmethod
    def validate_device(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in ("cuda", "cpu", "auto"):
            raise ValueError(f"Invalid device '{v}'. Must be 'cuda', 'cpu', or 'auto'.")
        return v_lower

    @field_validator("LANGUAGE")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "" or v.lower() == "auto":
            return None
        return v.strip().lower()


def load_config(config_path: Optional[str | Path] = None) -> Config:
    """
    Load configuration with the following priority:
    1. System environment variables (.env file)
    2. config.json file
    3. Default values
    """
    # Load .env if present
    load_dotenv()

    data: dict = {}

    # Check for config.json
    candidates = [
        config_path,
        Path("config.json"),
        Path(__file__).parent.parent / "config.json",
    ]

    for p in candidates:
        if p and Path(p).is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    if isinstance(json_data, dict):
                        data.update(json_data)
                break
            except Exception as e:
                print(f"[Warning] Failed to read configuration from {p}: {e}")

    # Environment variables override config.json
    env_mappings = {
        "DISCORD_TOKEN": str,
        "GUILD_ID": lambda x: int(x) if x and x.strip() else None,
        "TRANSCRIPT_CHANNEL_NAME": str,
        "WHISPER_MODEL_SIZE": str,
        "DEVICE": str,
        "COMPUTE_TYPE": str,
        "LANGUAGE": str,
        "CHUNKING_DURATION_SEC": float,
        "SILENCE_THRESHOLD": float,
        "CONTINUOUS_SPEECH_TIMEOUT_SEC": float,
        "AUTO_SAVE_TRANSCRIPTS": lambda x: str(x).lower() in ("true", "1", "yes"),
        "LOG_LEVEL": str,
    }

    for key, converter in env_mappings.items():
        val = os.getenv(key)
        if val is not None and val != "":
            try:
                data[key] = converter(val)
            except Exception as e:
                print(f"[Warning] Failed to convert environment variable {key}={val}: {e}")

    return Config(**data)
