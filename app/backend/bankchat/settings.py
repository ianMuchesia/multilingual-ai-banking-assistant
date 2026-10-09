"""All backend configuration, read from the environment (and app/.env when present).

Nothing else in the backend hardcodes these values: they are passed in from a
`Settings` instance, which the app keeps on `app.state.settings`.
"""

from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR.parent
DEFAULT_INTENT_ROUTER_DIR = APP_DIR.parent / "intent-router"
DATA_DIR = Path(__file__).resolve().parent / "data"

RouterMode = Literal["stub", "gemma"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=APP_DIR / ".env", extra="ignore")

    # --- infrastructure -------------------------------------------------------
    database_url: str
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    log_level: str = "INFO"

    # --- auth -------------------------------------------------------------------
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=60, gt=0)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # --- intent router ------------------------------------------------------------
    router_mode: RouterMode = "stub"
    intent_router_dir: Path = DEFAULT_INTENT_ROUTER_DIR
    gemma_backend: str = "gemma"
    gemma_local_only: bool = True

    # --- banking behaviour ------------------------------------------------------
    currency: str = "KES"
    bank_utc_offset_hours: int = 3  # Africa/Nairobi, no DST
    pending_action_ttl_seconds: int = Field(default=300, gt=0)
    max_transfer_amount: float = Field(default=1_000_000, gt=0)
    mini_statement_limit: int = Field(default=10, gt=0)
    transactions_default_limit: int = Field(default=10, gt=0)
    transactions_max_limit: int = Field(default=200, gt=0)
    full_statement_default_months: int = Field(default=3, gt=0)
    full_statement_max_rows: int = Field(default=500, gt=0)
    find_transaction_limit: int = Field(default=10, gt=0)
    find_transaction_window_days: int = Field(default=180, gt=0)
    receipt_candidates_limit: int = Field(default=5, gt=0)
    reference_prefix: str = "BY"

    # --- seed (DEV ONLY) --------------------------------------------------------
    seed_dev_password: str = "password123"
    seed_history_months: int = Field(default=6, gt=0)
    seed_random_seed: str = "benki-yetu-demo"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def bank_config_path(self) -> Path:
        return self.intent_router_dir / "config" / "bank.json"

    @property
    def intents_path(self) -> Path:
        return self.intent_router_dir / "data" / "intents.json"

    @property
    def transfer_faq_path(self) -> Path:
        return DATA_DIR / "transfer_faq.json"

    @property
    def bank_timezone(self) -> timezone:
        return timezone(timedelta(hours=self.bank_utc_offset_hours))

    @property
    def pending_action_ttl(self) -> timedelta:
        return timedelta(seconds=self.pending_action_ttl_seconds)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
