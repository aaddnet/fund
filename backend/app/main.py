from sqlalchemy import inspect, text
from fastapi import FastAPI

from app.api.routes import router
from app.db import Base, engine

app = FastAPI(title="Fund Management System V1")
Base.metadata.create_all(bind=engine)


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


ensure_import_batch_columns()
ensure_asset_snapshot_columns()
app.include_router(router)


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
