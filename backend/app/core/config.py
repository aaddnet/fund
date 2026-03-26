import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/invest")
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "true").lower() not in {"0", "false", "no"}
    auth_mode: str = os.getenv("AUTH_MODE", "hybrid").strip().lower()
    # Default false; set AUTH_ALLOW_DEV_FALLBACK=true only for local dev / hybrid mode.
    auth_allow_dev_fallback: bool = os.getenv("AUTH_ALLOW_DEV_FALLBACK", "false").lower() not in {"0", "false", "no"}
    auth_secret_key: str = os.getenv("AUTH_SECRET_KEY", "change-me-invest-dev-secret")
    auth_token_ttl_hours: int = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
    auth_access_token_ttl_minutes: int = int(os.getenv("AUTH_ACCESS_TOKEN_TTL_MINUTES", str(int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12")) * 60)))
    auth_refresh_token_ttl_days: int = int(os.getenv("AUTH_REFRESH_TOKEN_TTL_DAYS", "14"))
    auth_session_idle_minutes: int = int(os.getenv("AUTH_SESSION_IDLE_MINUTES", "120"))
    auth_lockout_threshold: int = int(os.getenv("AUTH_LOCKOUT_THRESHOLD", "5"))
    auth_lockout_minutes: int = int(os.getenv("AUTH_LOCKOUT_MINUTES", "15"))
    auth_cookie_enabled: bool = os.getenv("AUTH_COOKIE_ENABLED", "true").lower() not in {"0", "false", "no"}
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() not in {"0", "false", "no"}
    auth_cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    auth_access_cookie_name: str = os.getenv("AUTH_ACCESS_COOKIE_NAME", "invest_access_token")
    auth_refresh_cookie_name: str = os.getenv("AUTH_REFRESH_COOKIE_NAME", "invest_refresh_token")
    auth_csrf_cookie_name: str = os.getenv("AUTH_CSRF_COOKIE_NAME", "invest_csrf_token")
    auth_csrf_header_name: str = os.getenv("AUTH_CSRF_HEADER_NAME", "x-csrf-token")
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
            '[{"username":"admin","password":"Admin12345","role":"admin","display_name":"Admin User"},'
            '{"username":"ops","password":"Ops1234567","role":"ops","display_name":"Operations User"},'
            '{"username":"client1","password":"Client12345","role":"client-readonly","client_scope_id":1,"display_name":"Client Demo"},'
            '{"username":"ops.viewer","password":"Viewer12345","role":"ops-readonly","display_name":"Operations Viewer"}]',
        )
        try:
            self.auth_bootstrap_users = json.loads(raw_bootstrap)
        except json.JSONDecodeError:
            self.auth_bootstrap_users = []


settings = Settings()
