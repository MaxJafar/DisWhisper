"""Lightweight, offline CPU transcription with Vosk."""

from __future__ import annotations

import gc
import json
from pathlib import Path
from typing import Optional

import numpy as np

from diswhisper.transcriber.base import BaseSTTEngine


class VoskEngine(BaseSTTEngine):
    def __init__(
        self, model_path: str | Path, model_name: str, language: Optional[str] = None
    ):
        from vosk import Model

        self._model_name = model_name
        self.language = language
        path = Path(model_path)
        if not path.is_dir():
            raise ValueError(
                "Vosk model is not installed. Download it in the companion Models page first."
            )
        self.model = Model(str(path))

    @property
    def engine_name(self) -> str:
        return "Vosk (offline CPU)"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def active_device(self) -> str:
        return "cpu"

    @property
    def active_compute_type(self) -> str:
        return "float32"

    def transcribe(self, audio_data: np.ndarray) -> tuple[str, Optional[str]]:
        from vosk import KaldiRecognizer

        if not audio_data.size:
            return "", None
        recognizer = KaldiRecognizer(self.model, 16000)
        pcm = (np.clip(audio_data, -1, 1) * 32767).astype("<i2").tobytes()
        parts = []
        for offset in range(0, len(pcm), 8000):
            if recognizer.AcceptWaveform(pcm[offset : offset + 8000]):
                parts.append(json.loads(recognizer.Result()).get("text", ""))
        parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return " ".join(part.strip() for part in parts if part.strip()), self.language

    def purge_gpu_cache(self) -> None:
        gc.collect()
