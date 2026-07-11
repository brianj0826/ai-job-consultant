import pytest

from backend.services.database import (
    DatabaseConfigurationError,
    validate_database_configuration,
)


def test_development_database_defaults_remain_available(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    validate_database_configuration()


def test_production_database_credentials_are_required(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DB_HOST", "mysql")
    monkeypatch.setenv("DB_USER", "aiagent")
    monkeypatch.setenv("DB_NAME", "ai_assistant")
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(DatabaseConfigurationError, match="DB_PASSWORD"):
        validate_database_configuration()


def test_production_rejects_root_as_the_application_user(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DB_HOST", "mysql")
    monkeypatch.setenv("DB_USER", "root")
    monkeypatch.setenv("DB_PASSWORD", "strong-secret")
    monkeypatch.setenv("DB_NAME", "ai_assistant")

    with pytest.raises(DatabaseConfigurationError, match="non-root"):
        validate_database_configuration()
