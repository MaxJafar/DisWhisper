"""
Factory for creating STT engine instances (Whisper or SenseVoice).
"""

from __future__ import annotations

import logging
from typing import Optional

from diswhisper.config import Config
from diswhisper.transcriber.base import BaseSTTEngine
from diswhisper.transcriber.engine import WhisperEngine
from diswhisper.transcriber.sensevoice_engine import SenseVoiceEngine

logger = logging.getLogger(__name__)


def create_stt_engine(config: Config, engine_type_override: Optional[str] = None) -> BaseSTTEngine:
    """
    Instantiate the configured STT engine.

    Supported engines:
    - 'sensevoice': Alibaba SenseVoice via sherpa-onnx (<100ms latency, emotion/event detection)
    - 'whisper': faster-whisper via CTranslate2 (99+ languages, deep accuracy)
    """
    engine_type = (engine_type_override or config.STT_ENGINE).lower().strip()

    if engine_type in ("sensevoice", "sense_voice", "sense-voice"):
        logger.info("Initializing Alibaba SenseVoice STT Engine (<100ms ultra-low latency)...")
        return SenseVoiceEngine(
            repo_id=config.SENSEVOICE_MODEL_ID,
            device=config.DEVICE,
            language=config.LANGUAGE,
            enable_rich_events=config.ENABLE_RICH_EVENTS,
        )
    elif engine_type in ("whisper", "faster-whisper", "faster_whisper"):
        logger.info(f"Initializing faster-whisper Engine ({config.WHISPER_MODEL_SIZE})...")
        return WhisperEngine(
            model_size=config.WHISPER_MODEL_SIZE,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
            language=config.LANGUAGE,
        )
    else:
        logger.warning(f"Unknown engine '{engine_type}'. Defaulting to 'sensevoice'.")
        return SenseVoiceEngine(
            repo_id=config.SENSEVOICE_MODEL_ID,
            device=config.DEVICE,
            language=config.LANGUAGE,
            enable_rich_events=config.ENABLE_RICH_EVENTS,
        )
