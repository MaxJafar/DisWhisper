"""Prefer the packaged macOS Opus decoder over a developer's Homebrew library."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import discord.opus


def ensure_opus_loaded() -> None:
    if discord.opus.is_loaded() or sys.platform != "darwin":
        return
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.extend(Path(sys._MEIPASS).glob("libopus*.dylib"))
    spec = importlib.util.find_spec("av")
    if spec and spec.origin:
        candidates.extend((Path(spec.origin).parent / ".dylibs").glob("libopus*.dylib"))
    for candidate in candidates:
        try:
            discord.opus.load_opus(str(candidate))
            return
        except OSError:
            continue
    # Source builds may use a system Opus installation. Discord reports an actionable
    # OpusNotLoaded error if neither its own loader nor the bundled wheel can load it.
    discord.opus.Decoder()
