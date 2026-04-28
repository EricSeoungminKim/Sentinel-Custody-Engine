import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/sentinel")
    monkeypatch.setenv("WEB3_RPC_URL", "https://sepolia.infura.io/v3/test")
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg")
    assert "sepolia" in s.web3_rpc_url
    assert s.daily_withdrawal_limit == 10000


def test_settings_fail_without_required_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WEB3_RPC_URL", raising=False)
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_load_daily_limit_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/sentinel")
    monkeypatch.setenv("WEB3_RPC_URL", "https://sepolia.infura.io/v3/test")
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    monkeypatch.setenv("DAILY_WITHDRAWAL_LIMIT", "25000")
    s = Settings()
    assert s.daily_withdrawal_limit == 25000
