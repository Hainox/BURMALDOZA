from __future__ import annotations

import pytest

from apps.bot.app.main import BotConfig, load_config


def test_missing_bot_configuration_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    monkeypatch.delenv("MINIAPP_URL", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        load_config()


@pytest.mark.parametrize("missing", ["MINIAPP_URL", "API_BASE_URL"])
def test_missing_url_is_rejected(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    values = {
        "BOT_TOKEN": "TEST_BOT_TOKEN",
        "INTERNAL_API_TOKEN": "TEST_INTERNAL_TOKEN",
        "MINIAPP_URL": "https://miniapp.example.test",
        "API_BASE_URL": "https://api.example.test",
    }
    values[missing] = ""
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(RuntimeError, match=missing):
        load_config()


def test_valid_development_config_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "TEST_BOT_TOKEN")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
    monkeypatch.setenv("MINIAPP_URL", "http://localhost:4173")
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("ENVIRONMENT", "development")

    config = load_config()

    assert config == BotConfig(
        token="TEST_BOT_TOKEN",
        internal_api_token="TEST_INTERNAL_TOKEN",
        miniapp_url="http://localhost:4173",
        api_base_url="http://localhost:8000",
        environment="development",
    )


def test_production_rejects_placeholder_or_insecure_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "TEST_BOT_TOKEN")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
    monkeypatch.setenv("MINIAPP_URL", "https://example.invalid")
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="MINIAPP_URL"):
        load_config()


def test_production_allows_only_the_fixed_internal_api_http_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "TEST_BOT_TOKEN")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
    monkeypatch.setenv("MINIAPP_URL", "https://burmaldoza.example.test")
    monkeypatch.setenv("API_BASE_URL", "http://api:8000")
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert load_config().api_base_url == "http://api:8000"


@pytest.mark.parametrize(
    "api_url",
    [
        "http://api:8001",
        "http://api.internal:8000",
        "http://api:8000/",
        "http://user@api:8000",
        "http://localhost:8000",
    ],
)
def test_production_rejects_other_http_api_urls(
    monkeypatch: pytest.MonkeyPatch, api_url: str
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "TEST_BOT_TOKEN")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
    monkeypatch.setenv("MINIAPP_URL", "https://burmaldoza.example.test")
    monkeypatch.setenv("API_BASE_URL", api_url)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="API_BASE_URL must use HTTPS in production"):
        load_config()


def test_missing_or_reused_internal_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "TEST_BOT_TOKEN")
    monkeypatch.setenv("MINIAPP_URL", "http://localhost:4173")
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        load_config()

    monkeypatch.setenv("INTERNAL_API_TOKEN", "TEST_BOT_TOKEN")
    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        load_config()

    for invalid in (" ", "é"):
        monkeypatch.setenv("INTERNAL_API_TOKEN", invalid)
        with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
            load_config()
