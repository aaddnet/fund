from fastapi import FastAPI

from app.db import healthcheck

app = FastAPI(title="Fund Management System API", version="0.1.0")


@app.get("/health")
def read_health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def read_db_health() -> dict:
    return {"db": healthcheck()}
