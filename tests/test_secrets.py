import json
import sys

import pytest

from diswhisper.config import Config, load_config, save_config_updates
from diswhisper.secrets import PREFIX, protect, unprotect


def test_plaintext_compatibility_and_credential_roundtrip():
    assert unprotect("legacy-test-token") == "legacy-test-token"
    assert protect("") == ""
    encrypted = protect("fake-token-русский")
    assert unprotect(encrypted) == "fake-token-русский"
    if sys.platform == "win32":
        assert encrypted.startswith(PREFIX)
        assert "fake-token" not in encrypted
        assert protect(encrypted) == encrypted


def test_saved_credentials_are_usable_without_exposing_them(tmp_path):
    config = Config()
    path = tmp_path / "config.json"
    config._config_path = path
    save_config_updates(config, {"DISCORD_TOKEN": "test-secret"})
    saved = json.loads(path.read_text())
    assert load_config(path).DISCORD_TOKEN == "test-secret"
    if sys.platform == "win32":
        assert saved["DISCORD_TOKEN"].startswith(PREFIX)
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
