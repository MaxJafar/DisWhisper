"""
DisWhisper: Local Discord voice transcription with native Windows and macOS apps.
"""

__version__ = "0.2.1"
__author__ = "DisWhisper Contributors"

from diswhisper.config import Config, load_config

__all__ = ["Config", "load_config", "__version__"]
