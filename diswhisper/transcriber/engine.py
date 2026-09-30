"""
Local Whisper Inference Engine utilizing faster-whisper and CTranslate2.
Supports CUDA acceleration, float16 precision, CPU fallback, and CUDA OOM recovery.
"""

from __future__ import annotations

import gc
import logging
from typing import Optional, Tuple

import numpy as np
from faster_whisper import WhisperModel

from diswhisper.transcriber.base import BaseSTTEngine

logger = logging.getLogger(__name__)


class WhisperEngine(BaseSTTEngine):
    """
    Wrapper for faster-whisper CTranslate2 model implementing BaseSTTEngine.
    Handles device selection, compute precision, and OOM exception handling.
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        language: Optional[str] = "en",
        beam_size: int = 1,
    ):
        self._model_size = model_size
        self.requested_device = device
        self.requested_compute_type = compute_type
        self.language = language
        self.beam_size = beam_size

        self.model: Optional[WhisperModel] = None
        self._active_device = device
        self._active_compute_type = compute_type

        self._load_model()

    @property
    def engine_name(self) -> str:
        return "Whisper (faster-whisper)"

    @property
    def model_name(self) -> str:
        return self._model_size

    @property
    def active_device(self) -> str:
        return self._active_device

    @property
    def active_compute_type(self) -> str:
        return self._active_compute_type

    def _load_model(self) -> None:
        """Load the faster-whisper model with automatic CPU fallback if CUDA fails."""
        device_to_try = self.requested_device
        compute_to_try = self.requested_compute_type

        logger.info(
            f"Loading Whisper model '{self._model_size}' on device='{device_to_try}' "
            f"with compute_type='{compute_to_try}'..."
        )

        try:
            self.model = WhisperModel(
                model_size_or_path=self._model_size,
                device=device_to_try,
                compute_type=compute_to_try,
            )
            self._active_device = device_to_try
            self._active_compute_type = compute_to_try
            logger.info(
                f"Whisper model '{self._model_size}' loaded successfully on {device_to_try} ({compute_to_try})."
            )
        except Exception as e:
            if device_to_try == "cuda":
                logger.warning(
                    f"Failed to load Whisper model on CUDA ({e}). Attempting CPU fallback (compute_type='int8')..."
                )
                try:
                    self.model = WhisperModel(
                        model_size_or_path=self._model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    self._active_device = "cpu"
                    self._active_compute_type = "int8"
                    logger.info(f"Fallback to CPU succeeded for model '{self._model_size}'.")
                except Exception as cpu_err:
                    logger.error(f"Fatal error loading Whisper model on CPU fallback: {cpu_err}")
                    raise
            else:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, Optional[str]]:
        """
        Transcribe a 1D float32 16kHz audio array.
        Returns a tuple of (transcribed_text, detected_language).
        Gracefully handles CUDA out-of-memory errors.
        """
        if self.model is None or audio_data.size == 0:
            return "", None

        try:
            segments, info = self.model.transcribe(
                audio_data,
                language=self.language,
                beam_size=self.beam_size,
                best_of=1,
                temperature=0.0,
                vad_filter=False,  # Silence filtering handled by RMS in buffer
            )

            # Accumulate segment text
            text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
            full_text = " ".join(text_parts).strip()
            detected_lang = getattr(info, "language", self.language)

            return full_text, detected_lang

        except RuntimeError as e:
            err_str = str(e).lower()
            if "out of memory" in err_str or "cuda" in err_str:
                logger.critical(
                    f"CUDA Out Of Memory (OOM) encountered during transcription! Purging memory cache... Error: {e}"
                )
                self.purge_gpu_cache()
                return "[Audio dropped due to GPU Out of Memory]", None
            else:
                logger.error(f"RuntimeError during transcription: {e}")
                return "", None
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}", exc_info=True)
            return "", None

    def purge_gpu_cache(self) -> None:
        """Attempt to free CUDA memory cache."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except ImportError:
            pass

        gc.collect()
        logger.info("Garbage collection and GPU cache purge complete.")
