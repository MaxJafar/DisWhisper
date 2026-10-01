import pytest

from diswhisper.config import Config


@pytest.fixture(autouse=True)
def isolate_personal_configuration(monkeypatch):
    """Tests must never read developer credentials or machine-specific settings."""
    monkeypatch.setattr("diswhisper.config.load_dotenv", lambda *args, **kwargs: None)
    for name in Config.model_fields:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def anyio_backend():
    # Discord and aiohttp require asyncio, even when Trio is installed locally.
    return "asyncio"
