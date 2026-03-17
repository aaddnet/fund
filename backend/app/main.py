import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
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


@app.middleware("http")
async def csrf_protect_cookie_auth(request: Request, call_next):
    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path not in {"/auth/login"}:
        if request.headers.get("authorization"):
            return await call_next(request)
        access_cookie = request.cookies.get(settings.auth_access_cookie_name)
        refresh_cookie = request.cookies.get(settings.auth_refresh_cookie_name)
        if settings.auth_cookie_enabled and (access_cookie or refresh_cookie):
            csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name)
            csrf_header = request.headers.get(settings.auth_csrf_header_name)
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(status_code=403, content={"detail": "csrf token missing or invalid"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000", "http://127.0.0.1:3001", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
