from sqlalchemy import text
from fastapi import FastAPI
from app.api.routes import router
from app.db import Base, engine

app = FastAPI(title="Fund Management System V1")
Base.metadata.create_all(bind=engine)
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
