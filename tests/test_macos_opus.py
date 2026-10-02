"""The portable Mac app must never depend on the packager's Homebrew Opus."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from diswhisper.audio.opus import ensure_opus_loaded


def test_frozen_macos_prefers_its_bundled_decoder(tmp_path, monkeypatch):
    library = tmp_path / "libopus.0.dylib"
    library.write_bytes(b"test-library")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr("discord.opus.is_loaded", lambda: False)
    monkeypatch.setattr("diswhisper.audio.opus.importlib.util.find_spec", lambda name: None)
    load = MagicMock()
    monkeypatch.setattr("discord.opus.load_opus", load)
    ensure_opus_loaded()
    load.assert_called_once_with(str(library))


def test_source_macos_uses_the_pyav_wheel_decoder(tmp_path, monkeypatch):
    package = tmp_path / "av"
    vendor = package / ".dylibs"
    vendor.mkdir(parents=True)
    library = vendor / "libopus.0.dylib"
    library.write_bytes(b"test-library")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr("discord.opus.is_loaded", lambda: False)
    monkeypatch.setattr("diswhisper.audio.opus.importlib.util.find_spec", lambda name: SimpleNamespace(origin=str(package / "__init__.py")))
    load = MagicMock()
    monkeypatch.setattr("discord.opus.load_opus", load)
    ensure_opus_loaded()
    load.assert_called_once_with(str(library))
