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
    STT_ENGINE: str = Field(
        default="sensevoice",
        description="Speech-to-text engine: 'sensevoice' (<100ms, emotion detection) or 'whisper' (large-v3, 99+ languages)",
    )
    SENSEVOICE_MODEL_ID: str = Field(
        default="csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        description="Hugging Face repository ID for SenseVoice ONNX model",
    )
    ENABLE_RICH_EVENTS: bool = Field(
        default=True,
        description="Render SenseVoice emotion and audio event tags with emojis (e.g. laughter, applause)",
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

    # Local REST IPC Server for Companion App
    ENABLE_API_SERVER: bool = Field(
        default=True,
        description="Run local HTTP/WebSocket IPC server for Companion App",
    )
    API_SERVER_HOST: str = Field(
        default="127.0.0.1",
        description="Host interface for Companion App IPC server",
    )
    API_SERVER_PORT: int = Field(
        default=8765,
        description="Port for Companion App IPC server",
    )

    # Cloud Provider API Keys
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq Cloud API Key for ultra-fast Cloud Whisper and LLM summaries",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API Key for Whisper-1 and GPT-4o summaries",
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API Key for meeting summaries",
    )
    CLOUD_STT_PROVIDER: str = Field(
        default="groq",
        description="Default cloud STT provider: 'groq' or 'openai'",
    )

    # Meeting Summarizer Configuration
    SUMMARIZER_PROVIDER: str = Field(
        default="cloud",
        description="Summarizer provider: 'cloud' (Groq/OpenAI) or 'local' (Ollama)",
    )
    SUMMARIZER_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Model identifier for meeting summarizer",
    )
    LOCAL_LLM_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama instance",
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
        "STT_ENGINE": str,
        "SENSEVOICE_MODEL_ID": str,
        "ENABLE_RICH_EVENTS": lambda x: str(x).lower() in ("true", "1", "yes"),
        "WHISPER_MODEL_SIZE": str,
        "DEVICE": str,
        "COMPUTE_TYPE": str,
        "LANGUAGE": str,
        "CHUNKING_DURATION_SEC": float,
        "SILENCE_THRESHOLD": float,
        "CONTINUOUS_SPEECH_TIMEOUT_SEC": float,
        "AUTO_SAVE_TRANSCRIPTS": lambda x: str(x).lower() in ("true", "1", "yes"),
        "LOG_LEVEL": str,
        "ENABLE_API_SERVER": lambda x: str(x).lower() in ("true", "1", "yes"),
        "API_SERVER_HOST": str,
        "API_SERVER_PORT": int,
        "GROQ_API_KEY": str,
        "OPENAI_API_KEY": str,
        "GEMINI_API_KEY": str,
        "CLOUD_STT_PROVIDER": str,
        "SUMMARIZER_PROVIDER": str,
        "SUMMARIZER_MODEL": str,
        "LOCAL_LLM_URL": str,
    }

    for key, converter in env_mappings.items():
        val = os.getenv(key)
        if val is not None and val != "":
            try:
                data[key] = converter(val)
            except Exception as e:
                print(f"[Warning] Failed to convert environment variable {key}={val}: {e}")

    return Config(**data)
