import pytest

from diswhisper.config import Config


@pytest.fixture(autouse=True)
def isolate_personal_configuration(monkeypatch):
    """Tests must never read developer credentials or machine-specific settings."""
    monkeypatch.setattr("diswhisper.config.load_dotenv", lambda *args, **kwargs: None)
    for name in Config.model_fields:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def isolate_login_keychain(monkeypatch):
    """Never add test credentials to the developer's real login Keychain."""
    import diswhisper.macos_keychain as keychain

    entries = {}
    monkeypatch.setattr(keychain, "store", lambda account, value: entries.__setitem__(account, value))

    def read(account):
        if account not in entries:
            raise ValueError("Test credential not found")
        return entries[account]

    monkeypatch.setattr(keychain, "read", read)
    monkeypatch.setattr(keychain, "delete", lambda account: entries.pop(account, None))
    return entries


@pytest.fixture
def anyio_backend():
    # Discord and aiohttp require asyncio, even when Trio is installed locally.
    return "asyncio"
