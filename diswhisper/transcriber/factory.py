"""
Factory for creating STT engine instances (Whisper or SenseVoice).
"""

from __future__ import annotations

import logging
from typing import Optional

from diswhisper.config import Config
from diswhisper.models import get_model, model_path
from diswhisper.transcriber.base import BaseSTTEngine
from diswhisper.transcriber.cloud_engine import CloudWhisperEngine
from diswhisper.transcriber.engine import WhisperEngine
from diswhisper.transcriber.sensevoice_engine import SenseVoiceEngine
from diswhisper.transcriber.vosk_engine import VoskEngine

logger = logging.getLogger(__name__)


def create_stt_engine(
    config: Config, engine_type_override: Optional[str] = None
) -> BaseSTTEngine:
    """
    Instantiate the configured STT engine.

    Supported engines:
    - 'sensevoice': Alibaba SenseVoice via sherpa-onnx (emotion/event detection)
    - 'whisper': faster-whisper via CTranslate2 (99+ languages, deep accuracy)
    - 'cloud' / 'groq' / 'openai': Cloud Whisper API via Groq or OpenAI
    """
    engine_type = (engine_type_override or config.STT_ENGINE).lower().strip()

    if engine_type in ("sensevoice", "sense_voice", "sense-voice"):
        logger.info(
            "Initializing Alibaba SenseVoice STT Engine..."
        )
        return SenseVoiceEngine(
            repo_id=config.SENSEVOICE_MODEL_ID,
            device=config.DEVICE,
            language=config.LANGUAGE,
            enable_rich_events=config.ENABLE_RICH_EVENTS,
        )
    elif engine_type in ("whisper", "faster-whisper", "faster_whisper"):
        logger.info(
            f"Initializing faster-whisper Engine ({config.WHISPER_MODEL_SIZE})..."
        )
        try:
            local_path = model_path(config, get_model(config.WHISPER_MODEL_SIZE))
        except ValueError:
            local_path = None
        return WhisperEngine(
            model_size=config.WHISPER_MODEL_SIZE,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
            language=config.LANGUAGE,
            model_path=str(local_path)
            if local_path and (local_path / "model.bin").is_file()
            else None,
            cuda_library_dir=config.CUDA_LIBRARY_DIR,
        )
    elif engine_type == "vosk":
        model = get_model(config.VOSK_MODEL_ID)
        if model.engine != "vosk":
            raise ValueError("VOSK_MODEL_ID must identify a Vosk model")
        language = {"English": "en", "Russian": "ru", "German": "de", "Turkish": "tr"}[
            model.languages[0]
        ]
        return VoskEngine(model_path(config, model), model.model_name, language)
    elif engine_type in ("cloud", "groq", "openai"):
        provider = config.CLOUD_STT_PROVIDER if engine_type == "cloud" else engine_type
        api_key = config.GROQ_API_KEY if provider == "groq" else config.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                f"Configure a {provider.upper()} API key before activating this provider"
            )
        logger.info(f"Initializing Cloud Whisper Engine ({provider.upper()})...")
        return CloudWhisperEngine(
            provider=provider,
            api_key=api_key,
            language=config.LANGUAGE,
        )
    else:
        raise ValueError(f"Unknown speech-to-text engine: {engine_type}")
