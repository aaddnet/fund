import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.api.routes import router
from app.db import Base, engine
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Fund Management System V1", lifespan=lifespan)
app.include_router(router)


def ensure_runtime_columns() -> None:
    ensure_import_batch_columns()
    ensure_asset_snapshot_columns()
    ensure_fee_record_columns()
    ensure_audit_log_table()
    ensure_scheduler_job_run_table()


def ensure_import_batch_columns() -> None:
    inspector = inspect(engine)
    if "import_batch" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("import_batch")}
    statements: list[str] = []

    # 这段兼容逻辑用于无迁移场景，避免现有开发库因为旧表结构直接报错。
    if "account_id" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN account_id INTEGER")
    if "status" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN status VARCHAR(30) DEFAULT 'uploaded' NOT NULL")
    if "row_count" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN row_count INTEGER DEFAULT 0 NOT NULL")
    if "parsed_count" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN parsed_count INTEGER DEFAULT 0 NOT NULL")
    if "confirmed_count" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN confirmed_count INTEGER DEFAULT 0 NOT NULL")
    if "failed_reason" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN failed_reason TEXT")
    if "preview_json" not in columns:
        statements.append("ALTER TABLE import_batch ADD COLUMN preview_json TEXT DEFAULT '[]' NOT NULL")

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text("UPDATE import_batch SET status = COALESCE(status, 'uploaded')"))
        conn.execute(text("UPDATE import_batch SET row_count = COALESCE(row_count, 0)"))
        conn.execute(text("UPDATE import_batch SET parsed_count = COALESCE(parsed_count, 0)"))
        conn.execute(text("UPDATE import_batch SET confirmed_count = COALESCE(confirmed_count, 0)"))
        conn.execute(text("UPDATE import_batch SET preview_json = COALESCE(preview_json, '[]')"))
        conn.execute(text("UPDATE import_batch SET account_id = COALESCE(account_id, 1)"))


def ensure_asset_snapshot_columns() -> None:
    inspector = inspect(engine)
    if "asset_snapshot" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("asset_snapshot")}
    statements: list[str] = []
    if "currency" not in columns:
        statements.append("ALTER TABLE asset_snapshot ADD COLUMN currency VARCHAR(10)")
    if "price_native" not in columns:
        statements.append("ALTER TABLE asset_snapshot ADD COLUMN price_native NUMERIC(24,8)")
    if "value_native" not in columns:
        statements.append("ALTER TABLE asset_snapshot ADD COLUMN value_native NUMERIC(24,8)")
    if "fx_rate_to_usd" not in columns:
        statements.append("ALTER TABLE asset_snapshot ADD COLUMN fx_rate_to_usd NUMERIC(24,8)")
    if "account_ids" not in columns:
        statements.append("ALTER TABLE asset_snapshot ADD COLUMN account_ids TEXT")

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def ensure_fee_record_columns() -> None:
    inspector = inspect(engine)
    if "fee_record" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("fee_record")}
    statements: list[str] = []
    if "nav_start" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN nav_start NUMERIC(24,8)")
    if "nav_end_before_fee" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN nav_end_before_fee NUMERIC(24,8)")
    if "annual_return_pct" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN annual_return_pct NUMERIC(12,6)")
    if "excess_return_pct" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN excess_return_pct NUMERIC(12,6)")
    if "fee_base_usd" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN fee_base_usd NUMERIC(24,8)")
    if "nav_after_fee" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN nav_after_fee NUMERIC(24,8)")
    if "applied_date" not in columns:
        statements.append("ALTER TABLE fee_record ADD COLUMN applied_date DATE")

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def ensure_audit_log_table() -> None:
    inspector = inspect(engine)
    if "audit_log" in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE audit_log (
                    id INTEGER PRIMARY KEY,
                    actor_role VARCHAR(50) NOT NULL,
                    actor_id VARCHAR(100) NOT NULL,
                    client_scope_id INTEGER,
                    action VARCHAR(100) NOT NULL,
                    entity_type VARCHAR(100) NOT NULL,
                    entity_id VARCHAR(100),
                    status VARCHAR(30) NOT NULL DEFAULT 'success',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def ensure_scheduler_job_run_table() -> None:
    inspector = inspect(engine)
    if "scheduler_job_run" in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE scheduler_job_run (
                    id INTEGER PRIMARY KEY,
                    job_name VARCHAR(100) NOT NULL,
                    trigger_source VARCHAR(30) NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    message TEXT,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"db": "ok"}
