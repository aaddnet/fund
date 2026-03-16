import os

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://fund_user:fund_pass@localhost:5432/fund_system",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def healthcheck() -> str:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return "ok"
