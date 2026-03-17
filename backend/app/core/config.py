import os


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/invest")
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "true").lower() not in {"0", "false", "no"}
    auth_role_header: str = os.getenv("AUTH_ROLE_HEADER", "x-dev-role")
    auth_client_id_header: str = os.getenv("AUTH_CLIENT_ID_HEADER", "x-client-id")
    auth_operator_header: str = os.getenv("AUTH_OPERATOR_HEADER", "x-operator-id")
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() not in {"0", "false", "no"}
    scheduler_timezone: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Singapore")
    scheduler_fx_day_of_week: str = os.getenv("SCHEDULER_FX_DAY_OF_WEEK", "mon")
    scheduler_fx_hour: int = int(os.getenv("SCHEDULER_FX_HOUR", "6"))
    scheduler_fx_minute: int = int(os.getenv("SCHEDULER_FX_MINUTE", "0"))
    scheduler_fx_pairs: str = os.getenv("SCHEDULER_FX_PAIRS", "HKD:USD,SGD:USD,CNY:USD")


settings = Settings()
