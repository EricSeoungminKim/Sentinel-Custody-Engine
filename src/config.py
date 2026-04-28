from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    web3_rpc_url: str
    sentinel_api_key: str  # required — no default
    sepolia_test_private_key: str | None = None
    mpc_min_shares: int = 2
    mpc_total_shares: int = 3
    daily_withdrawal_limit: Decimal = Decimal("10000")


@lru_cache
def get_settings() -> Settings:
    return Settings()
