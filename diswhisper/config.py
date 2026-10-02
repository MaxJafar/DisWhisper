"""
Configuration loader and validation module for DisWhisper.
Supports loading from config.json and .env environment variables.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from diswhisper.secrets import MACOS_PREFIX, forget, protect, unprotect


class Config(BaseModel):
    """DisWhisper application configuration model."""

    model_config = ConfigDict(validate_assignment=True, allow_inf_nan=False)
    _config_path: Path = PrivateAttr(default_factory=lambda: Path("config.json"))

    DISCORD_TOKEN: str = Field(
        default="",
        description="Discord Bot Token from Discord Developer Portal",
    )
    GUILD_ID: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional Guild ID for instant slash command registration",
    )
    TRANSCRIPT_CHANNEL_NAME: str = Field(
        default="live-transcript",
        description="Discord text channel name where live transcripts are sent",
    )
    STT_ENGINE: str = Field(
        default="whisper",
        description="Speech-to-text engine: sensevoice, whisper, vosk, cloud, groq, or openai",
    )
    LOCAL_MODEL_DIR: str = Field(default="models", min_length=1)
    VOSK_MODEL_ID: str = Field(default="vosk-model-small-en-us-0.15", min_length=1)
    AUTO_CREATE_TRANSCRIPT_CHANNEL: bool = Field(default=True)
    AUTO_POST_TRANSCRIPTS: bool = Field(default=True)
    AUTO_LEAVE_EMPTY_SEC: float = Field(
        default=60.0,
        ge=0,
        le=3600,
        description="Leave an empty voice channel after this many seconds; 0 disables",
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
        default="base",
        description="Whisper model size: tiny, base, small, medium, large-v3, large-v3-turbo",
    )
    DEVICE: str = Field(
        default="auto",
        description="Inference device: 'cuda' or 'cpu'",
    )
    COMPUTE_TYPE: str = Field(
        default="int8",
        description="Quantization/Precision: 'float16', 'int8_float16', 'int8', 'float32'",
    )
    CUDA_LIBRARY_DIR: Optional[str] = Field(default=None, description="Optional folder containing CUDA/cuDNN DLLs or NVIDIA package bin folders")
    LANGUAGE: Optional[str] = Field(
        default=None,
        description="Language code (e.g. 'en', 'es') or None for auto-detection",
    )
    CHUNKING_DURATION_SEC: float = Field(
        default=2.5,
        ge=0.5,
        le=30,
        description="Duration of audio chunk in seconds passed to transcriber",
    )
    SILENCE_THRESHOLD: float = Field(
        default=0.01,
        ge=0,
        le=1,
        description="RMS amplitude below which chunk is discarded as silence",
    )
    CONTINUOUS_SPEECH_TIMEOUT_SEC: float = Field(
        default=5.0,
        gt=0,
        le=60,
        description="Seconds to append to same user message before creating new block",
    )
    AUTO_SAVE_TRANSCRIPTS: bool = Field(
        default=True,
        description="Save markdown transcripts to transcripts/ folder",
    )
    TRANSCRIPT_DIR: str = Field(default="transcripts", min_length=1)
    AUTO_CONNECT_BOT: bool = Field(default=False)
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
        ge=1,
        le=65535,
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
        default="local",
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
    LOCAL_SUMMARIZER_MODEL: str = Field(default="llama3.2:3b", min_length=1)

    @field_validator("STT_ENGINE")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        value = v.strip().lower()
        value = {
            "sense_voice": "sensevoice",
            "sense-voice": "sensevoice",
            "faster-whisper": "whisper",
            "faster_whisper": "whisper",
        }.get(value, value)
        if value not in ("sensevoice", "whisper", "vosk", "cloud", "groq", "openai"):
            raise ValueError("Unsupported speech-to-text engine")
        return value

    @field_validator("CLOUD_STT_PROVIDER", "SUMMARIZER_PROVIDER")
    @classmethod
    def validate_provider(cls, v: str, info) -> str:
        value = v.strip().lower()
        choices = (
            ("groq", "openai")
            if info.field_name == "CLOUD_STT_PROVIDER"
            else ("cloud", "local")
        )
        if value not in choices:
            raise ValueError(f"Provider must be one of {choices}")
        return value

    @field_validator("TRANSCRIPT_CHANNEL_NAME")
    @classmethod
    def validate_channel_name(cls, v: str) -> str:
        value = re.sub(r"\s+", "-", v.strip().lower())
        if not value or len(value) > 100 or any(c in value for c in "/\\#@"):
            raise ValueError(
                "Channel name must contain 1–100 characters without /, \\, #, or @"
            )
        return value

    @field_validator("LOCAL_LLM_URL")
    @classmethod
    def validate_local_url(cls, v: str) -> str:
        from urllib.parse import urlparse

        value = v.rstrip("/")
        parsed = urlparse(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "Ollama URL must be an HTTP(S) base URL without credentials"
            )
        return value

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

    @field_validator("DISCORD_TOKEN")
    @classmethod
    def normalize_bot_token(cls, value: str) -> str:
        value = value.strip()
        return value[4:].strip() if value.lower().startswith("bot ") else value

    @field_validator("API_SERVER_HOST")
    @classmethod
    def validate_local_host(cls, value: str) -> str:
        if value not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("The desktop service must listen on a loopback address.")
        return value


def load_config(config_path: Optional[str | Path] = None) -> Config:
    """
    Load configuration with the following priority:
    1. System environment variables (.env file)
    2. config.json file
    3. Default values
    """
    # Load .env if present
    load_dotenv(Path.cwd() / ".env")

    data: dict = {}
    selected_path = Path(config_path) if config_path else Path("config.json")

    # Check for config.json
    candidates = [config_path] if config_path else [
        Path("config.json"), Path(__file__).parent.parent / "config.json"
    ]

    for p in candidates:
        if p and Path(p).is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    if isinstance(json_data, dict):
                        data.update(json_data)
                        selected_path = Path(p)
                break
            except Exception as e:
                print(f"[Warning] Failed to read configuration from {p}: {e}")

    # Environment variables override config.json
    env_mappings = {
        "DISCORD_TOKEN": str,
        "GUILD_ID": lambda x: int(x) if x and x.strip() else None,
        "TRANSCRIPT_CHANNEL_NAME": str,
        "STT_ENGINE": str,
        "LOCAL_MODEL_DIR": str,
        "VOSK_MODEL_ID": str,
        "AUTO_CREATE_TRANSCRIPT_CHANNEL": lambda x: x.lower() in ("true", "1", "yes"),
        "AUTO_POST_TRANSCRIPTS": lambda x: x.lower() in ("true", "1", "yes"),
        "AUTO_LEAVE_EMPTY_SEC": float,
        "SENSEVOICE_MODEL_ID": str,
        "ENABLE_RICH_EVENTS": lambda x: str(x).lower() in ("true", "1", "yes"),
        "WHISPER_MODEL_SIZE": str,
        "DEVICE": str,
        "COMPUTE_TYPE": str,
        "CUDA_LIBRARY_DIR": str,
        "LANGUAGE": str,
        "CHUNKING_DURATION_SEC": float,
        "SILENCE_THRESHOLD": float,
        "CONTINUOUS_SPEECH_TIMEOUT_SEC": float,
        "AUTO_SAVE_TRANSCRIPTS": lambda x: str(x).lower() in ("true", "1", "yes"),
        "TRANSCRIPT_DIR": str,
        "AUTO_CONNECT_BOT": lambda x: str(x).lower() in ("true", "1", "yes"),
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
        "LOCAL_SUMMARIZER_MODEL": str,
    }

    for key, converter in env_mappings.items():
        val = os.getenv(key)
        if val is not None and val != "":
            try:
                data[key] = converter(val)
            except Exception:
                print(f"[Warning] Failed to convert environment variable {key}")

    for key in SECRET_FIELDS:
        if isinstance(data.get(key), str):
            try:
                data[key] = unprotect(data[key])
            except ValueError:
                # The API must remain available so a restored/moved profile can be repaired.
                print(f"[Warning] Could not unlock {key}. Enter it again in the companion.")
                data[key] = "" if key == "DISCORD_TOKEN" else None
    cfg = Config(**data)
    cfg._config_path = selected_path.resolve()
    return cfg


SECRET_FIELDS = frozenset(
    {"DISCORD_TOKEN", "GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"}
)


def public_config(config: Config) -> dict:
    """Expose credential presence, never credential values, to the companion."""
    result = config.model_dump(exclude=SECRET_FIELDS)
    for key in SECRET_FIELDS:
        result[f"{key}_CONFIGURED"] = bool(getattr(config, key))
    return result


def save_config_updates(config: Config, updates: dict) -> Config:
    """Validate and atomically persist only edited fields, preserving env-only secrets."""
    unknown = set(updates) - Config.model_fields.keys()
    if unknown:
        raise ValueError(f"Unknown configuration fields: {', '.join(sorted(unknown))}")
    candidate = Config.model_validate({**config.model_dump(), **updates})
    candidate._config_path = config._config_path
    path = config._config_path.resolve()
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(existing, dict):
        raise ValueError("Configuration file must contain a JSON object")
    normalized = candidate.model_dump()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    replaced = [existing.get(key) for key in updates if key in SECRET_FIELDS]
    created = []
    try:
        for key in updates:
            value = normalized[key]
            saved = protect(value) if key in SECRET_FIELDS and value else value
            existing[key] = saved
            if key in SECRET_FIELDS and isinstance(saved, str) and saved.startswith(MACOS_PREFIX):
                created.append(saved)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".diswhisper-config-",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(existing, file, indent=2)
            file.write("\n")
        if os.name != "nt":
            temp_path.chmod(0o600)
        os.replace(temp_path, path)
    except Exception:
        for value in created:
            forget(value)
        raise
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    for value in replaced:
        if value not in created:
            forget(value)
    return candidate
