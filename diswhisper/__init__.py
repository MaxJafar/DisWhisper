"""
DisWhisper: Free, Self-Hosted Discord Meeting Transcriber powered by Whisper Large-v3.
"""

__version__ = "0.2.1"
__author__ = "DisWhisper Contributors"

from diswhisper.config import Config, load_config

__all__ = ["Config", "load_config", "__version__"]
