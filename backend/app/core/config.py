import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/invest")
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "true").lower() not in {"0", "false", "no"}
    auth_mode: str = os.getenv("AUTH_MODE", "hybrid").strip().lower()
    auth_allow_dev_fallback: bool = os.getenv("AUTH_ALLOW_DEV_FALLBACK", "true").lower() not in {"0", "false", "no"}
    auth_secret_key: str = os.getenv("AUTH_SECRET_KEY", "change-me-invest-dev-secret")
    auth_token_ttl_hours: int = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
    auth_role_header: str = os.getenv("AUTH_ROLE_HEADER", "x-dev-role")
    auth_client_id_header: str = os.getenv("AUTH_CLIENT_ID_HEADER", "x-client-id")
    auth_operator_header: str = os.getenv("AUTH_OPERATOR_HEADER", "x-operator-id")
    auth_bootstrap_users: Any = None
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() not in {"0", "false", "no"}
    scheduler_timezone: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Singapore")
    scheduler_fx_day_of_week: str = os.getenv("SCHEDULER_FX_DAY_OF_WEEK", "mon")
    scheduler_fx_hour: int = int(os.getenv("SCHEDULER_FX_HOUR", "6"))
    scheduler_fx_minute: int = int(os.getenv("SCHEDULER_FX_MINUTE", "0"))
    scheduler_fx_pairs: str = os.getenv("SCHEDULER_FX_PAIRS", "HKD:USD,SGD:USD,CNY:USD")

    def __post_init__(self) -> None:
        raw_bootstrap = os.getenv(
            "AUTH_BOOTSTRAP_USERS_JSON",
            '[{"username":"admin","password":"admin123","role":"admin","display_name":"Admin User"},'
            '{"username":"ops","password":"ops123","role":"ops","display_name":"Operations User"},'
            '{"username":"client1","password":"client123","role":"client-readonly","client_scope_id":1,"display_name":"Client Demo"}]',
        )
        try:
            self.auth_bootstrap_users = json.loads(raw_bootstrap)
        except json.JSONDecodeError:
            self.auth_bootstrap_users = []


settings = Settings()
