# Fund Management System (V1 Scaffold)

This directory contains an initial scaffold for a Fund Management System V1:

- **PostgreSQL schema** in `db/schema.sql`
- **FastAPI backend** in `backend/app`
- **Next.js frontend** in `frontend`
- **Project notes/docs** in `docs`

## Quick start

### 1) Start database

```bash
docker compose up -d db
```

### 2) Run backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) Run frontend

```bash
cd frontend
npm install
npm run dev
```

## Scope

This is an initialization scaffold intended to match the requested project tree and V1 direction.
