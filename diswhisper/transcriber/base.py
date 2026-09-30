"""
Abstract Base Class for Speech-to-Text Engines.
Defines the standard interface for Whisper, SenseVoice, and future STT providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np


class BaseSTTEngine(ABC):
    """Abstract interface that all DisWhisper STT backends must implement."""

    @abstractmethod
    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, Optional[str]]:
        """
        Transcribe a 1D float32 16kHz audio array normalized between [-1.0, 1.0].

        Returns:
            Tuple of (transcribed_text, detected_language).
        """
        raise NotImplementedError

    @abstractmethod
    def purge_gpu_cache(self) -> None:
        """Purge GPU memory cache or perform garbage collection."""
        raise NotImplementedError

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Name of the engine family (e.g. 'Whisper' or 'SenseVoice')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Specific model identifier (e.g. 'large-v3' or 'SenseVoiceSmall-int8')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def active_device(self) -> str:
        """Currently active execution device ('cuda' or 'cpu')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def active_compute_type(self) -> str:
        """Active compute precision (e.g. 'float16', 'int8', 'float32')."""
        raise NotImplementedError
