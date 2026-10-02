import json
import sys

import pytest

from diswhisper.config import Config, load_config, save_config_updates
from diswhisper.secrets import MACOS_PREFIX, PREFIX, protect, unprotect


def test_plaintext_compatibility_and_credential_roundtrip():
    assert unprotect("legacy-test-token") == "legacy-test-token"
    assert protect("") == ""
    encrypted = protect("fake-token-русский")
    assert unprotect(encrypted) == "fake-token-русский"
    if sys.platform in ("win32", "darwin"):
        assert encrypted.startswith(PREFIX if sys.platform == "win32" else MACOS_PREFIX)
        assert "fake-token" not in encrypted
        assert protect(encrypted) == encrypted


def test_saved_credentials_are_usable_without_exposing_them(tmp_path):
    config = Config()
    path = tmp_path / "config.json"
    config._config_path = path
    save_config_updates(config, {"DISCORD_TOKEN": "test-secret"})
    saved = json.loads(path.read_text())
    assert load_config(path).DISCORD_TOKEN == "test-secret"
    if sys.platform in ("win32", "darwin"):
        assert saved["DISCORD_TOKEN"].startswith(PREFIX if sys.platform == "win32" else MACOS_PREFIX)
        assert "test-secret" not in path.read_text()


def test_invalid_protected_credential_has_actionable_error():
    with pytest.raises(ValueError, match="credential|Windows user"):
        unprotect(PREFIX + "broken")


def test_unreadable_credential_keeps_setup_available(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"DISCORD_TOKEN": PREFIX + "broken"}))
    config = load_config(path)
    assert not config.DISCORD_TOKEN
    # Preserve the original file until the user replaces the credential.
    assert json.loads(path.read_text())["DISCORD_TOKEN"].startswith(PREFIX)


def test_macos_keychain_references_are_private_and_cross_platform_safe(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    reference = protect("test-keychain-credential")
    assert reference.startswith(MACOS_PREFIX)
    assert "test-keychain-credential" not in reference
    assert unprotect(reference) == "test-keychain-credential"
    assert protect(reference) == reference
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ValueError, match="Mac login Keychain"):
        unprotect(reference)


def test_replacing_macos_credential_removes_old_keychain_entry(tmp_path, monkeypatch, isolate_login_keychain):
    monkeypatch.setattr(sys, "platform", "darwin")
    config = Config()
    config._config_path = tmp_path / "config.json"
    config = save_config_updates(config, {"DISCORD_TOKEN": "first-test-token"})
    first = json.loads(config._config_path.read_text())["DISCORD_TOKEN"]
    config = save_config_updates(config, {"DISCORD_TOKEN": "replacement-test-token"})
    assert len(isolate_login_keychain) == 1
    with pytest.raises(ValueError, match="cannot be unlocked"):
        unprotect(first)
    assert load_config(config._config_path).DISCORD_TOKEN == "replacement-test-token"


def test_failed_config_write_rolls_back_new_keychain_entries(tmp_path, monkeypatch, isolate_login_keychain):
    monkeypatch.setattr(sys, "platform", "darwin")
    config = Config()
    config._config_path = tmp_path / "config.json"
    config = save_config_updates(config, {"DISCORD_TOKEN": "original-test-token"})
    original = config._config_path.read_text()

    def fail_replace(*args):
        raise OSError("Test disk failure")

    monkeypatch.setattr("diswhisper.config.os.replace", fail_replace)
    with pytest.raises(OSError, match="Test disk failure"):
        save_config_updates(config, {"DISCORD_TOKEN": "replacement-test-token"})
    assert config._config_path.read_text() == original
    assert len(isolate_login_keychain) == 1
    assert load_config(config._config_path).DISCORD_TOKEN == "original-test-token"
