import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import router
from app.db import SessionLocal, engine
from app.services.auth import bootstrap_auth_users
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    bootstrap_default_auth_users()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Fund Management System V1", lifespan=lifespan)
app.include_router(router)


def run_migrations() -> None:
    # 统一用 Alembic 收敛 schema 变化，减少启动时偷偷补表补列的行为。
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(config, "head")


def bootstrap_default_auth_users() -> None:
    db = SessionLocal()
    try:
        bootstrap_auth_users(db)
    finally:
        db.close()


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
