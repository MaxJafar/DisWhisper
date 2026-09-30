"""
Alibaba SenseVoice Inference Engine powered by sherpa-onnx.
Non-autoregressive streaming architecture with <100ms latency,
native rich emotion and audio event detection, and multi-language support.
"""

from __future__ import annotations

import gc
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from diswhisper.transcriber.base import BaseSTTEngine

logger = logging.getLogger(__name__)

# Default Hugging Face repository for pre-exported SenseVoice ONNX models
DEFAULT_SENSEVOICE_REPO = "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

# Emotion tag mapping to emojis
EMOTION_MAP = {
    "<|HAPPY|>": "😄 ",
    "<|SAD|>": "😢 ",
    "<|ANGRY|>": "😠 ",
    "<|NEUTRAL|>": "",
    "<|EMO_UNKNOWN|>": "",
}

# Audio event tag mapping
EVENT_MAP = {
    "<|LAUGHTER|>": " 😂 [laughter]",
    "<|APPLAUSE|>": " 👏 [applause]",
    "<|BGM|>": " 🎵 [music]",
    "<|CRY|>": " 😭 [crying]",
    "<|SNEEZE|>": " 🤧 [sneeze]",
    "<|COUGH|>": " 😷 [cough]",
    "<|BREATH|>": "",
}

# Language token detection
LANG_TAG_PATTERN = re.compile(r"<\|(zh|en|ja|ko|yue)\|>")


class SenseVoiceEngine(BaseSTTEngine):
    """
    SenseVoice inference engine using sherpa-onnx.
    Features sub-100ms non-autoregressive decoding, int8 CPU/GPU execution,
    and automatic audio event/emotion detection.
    """

    def __init__(
        self,
        repo_id: str = DEFAULT_SENSEVOICE_REPO,
        model_filename: str = "model.int8.onnx",
        tokens_filename: str = "tokens.txt",
        device: str = "cuda",
        language: Optional[str] = "auto",
        num_threads: int = 4,
        use_itn: bool = True,
        enable_rich_events: bool = True,
    ):
        self.repo_id = repo_id
        self.model_filename = model_filename
        self.tokens_filename = tokens_filename
        self.requested_device = device
        self.language = language or "auto"
        self.num_threads = num_threads
        self.use_itn = use_itn
        self.enable_rich_events = enable_rich_events

        self.recognizer = None
        self._active_device = "cpu"
        self._active_compute_type = "int8" if "int8" in model_filename else "fp32"

        self._initialize_recognizer()

    @property
    def engine_name(self) -> str:
        return "SenseVoice (Alibaba / sherpa-onnx)"

    @property
    def model_name(self) -> str:
        return f"SenseVoiceSmall ({self._active_compute_type})"

    @property
    def active_device(self) -> str:
        return self._active_device

    @property
    def active_compute_type(self) -> str:
        return self._active_compute_type

    def _resolve_model_files(self) -> Tuple[str, str]:
        """Download or locate ONNX model and tokens files."""
        # Check if local files exist directly
        if os.path.isfile(self.model_filename) and os.path.isfile(self.tokens_filename):
            return self.model_filename, self.tokens_filename

        logger.info(f"Resolving SenseVoice model files from Hugging Face repository '{self.repo_id}'...")
        try:
            from huggingface_hub import hf_hub_download

            model_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.model_filename,
            )
            tokens_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.tokens_filename,
            )
            logger.info("SenseVoice model and tokens downloaded/cached successfully.")
            return model_path, tokens_path
        except Exception as e:
            logger.error(f"Failed to fetch SenseVoice model files from Hugging Face: {e}")
            raise

    def _initialize_recognizer(self) -> None:
        """Initialize the sherpa-onnx OfflineRecognizer for SenseVoice."""
        import sherpa_onnx

        model_path, tokens_path = self._resolve_model_files()

        provider = "cuda" if self.requested_device.lower() == "cuda" else "cpu"
        logger.info(
            f"Loading SenseVoice model with provider='{provider}' (num_threads={self.num_threads})..."
        )

        try:
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=self.num_threads,
                provider=provider,
                language=self.language if self.language in ("zh", "en", "ja", "ko", "yue") else "auto",
                use_itn=self.use_itn,
            )
            # Check if sherpa-onnx fell back to CPU
            self._active_device = provider
            logger.info("SenseVoice recognizer initialized successfully.")
        except Exception as e:
            logger.warning(f"SenseVoice initialization on '{provider}' failed ({e}). Falling back to CPU...")
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=self.num_threads,
                provider="cpu",
                language=self.language if self.language in ("zh", "en", "ja", "ko", "yue") else "auto",
                use_itn=self.use_itn,
            )
            self._active_device = "cpu"
            logger.info("SenseVoice CPU fallback initialized successfully.")

    def format_rich_transcription(self, raw_text: str) -> Tuple[str, Optional[str]]:
        """
        Parse SenseVoice raw tokens:
        - Detects language token (e.g. <|en|>, <|zh|>)
        - Replaces emotion tokens with emojis (e.g. <|HAPPY|> -> 😄)
        - Replaces audio event tokens with formatted badges (e.g. <|LAUGHTER|> -> 😂 [laughter])
        - Cleans up internal tokens (<|nospeech|>, <|withitn|>, etc.)
        """
        if not raw_text:
            return "", None

        text = raw_text

        # 1. Detect language
        detected_lang = None
        lang_match = LANG_TAG_PATTERN.search(text)
        if lang_match:
            detected_lang = lang_match.group(1)

        # 2. Process Emotion and Event Tags
        if self.enable_rich_events:
            for tag, emoji in EMOTION_MAP.items():
                text = text.replace(tag, emoji)
            for tag, badge in EVENT_MAP.items():
                text = text.replace(tag, badge)
        else:
            for tag in list(EMOTION_MAP.keys()) + list(EVENT_MAP.keys()):
                text = text.replace(tag, "")

        # 3. Clean up remaining special tokens (e.g. <|nospeech|>, <|woitn|>, <|withitn|>, etc.)
        cleaned = re.sub(r"<\|.*?\|>", "", text)

        # 4. Normalize excess whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned, detected_lang

    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, Optional[str]]:
        """
        Transcribe audio using SenseVoice non-autoregressive stream decoding.
        """
        if self.recognizer is None or audio_data.size == 0:
            return "", None

        try:
            stream = self.recognizer.create_stream()
            stream.accept_waveform(sample_rate=16000, waveform=audio_data)
            self.recognizer.decode_stream(stream)

            raw_text = stream.result.text
            if not raw_text:
                return "", None

            return self.format_rich_transcription(raw_text)

        except Exception as e:
            logger.error(f"Error during SenseVoice transcription: {e}", exc_info=True)
            return "", None

    def purge_gpu_cache(self) -> None:
        """Purge system memory / garbage collection."""
        gc.collect()
