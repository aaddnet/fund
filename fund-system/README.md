# Fund Management System (V1 Scaffold)

This directory contains an initial scaffold for a Fund Management System V1:

- **PostgreSQL schema** in `db/schema.sql`
- **FastAPI backend** in `backend/app`
- **Next.js frontend** in `frontend`
- **Project notes/docs** in `docs`

## Quick start

## Prerequisites

- Docker + Docker Compose plugin (you already confirmed Docker is installed locally)
- Python 3.10+
- Node.js 18+

### 1) Start database

```bash
docker compose up -d db

# optional: confirm DB container is healthy
docker compose ps
```

### 2) Run backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> If your backend is not running on the same host as PostgreSQL, set `DATABASE_URL` explicitly before starting uvicorn.

### 3) Run frontend

```bash
cd frontend
npm install
npm run dev
```

## End-to-end local test flow (recommended)

Use three terminals to start dependencies first, then verify from a fourth terminal:

1. `docker compose up -d db`
2. `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. `cd frontend && npm install && npm run dev`
4. Verification terminal:

```bash
curl -s http://127.0.0.1:8000/health && echo
curl -s http://127.0.0.1:8000/health/db && echo
curl -I http://127.0.0.1:3000
```

Expected:

- `{"status":"ok"}` from `/health`
- `{"db":"ok"}` from `/health/db`
- `HTTP/1.1 200` (or `307` redirect then `200`) for frontend homepage

## Local verification checklist

After both backend and frontend are running, you can validate core V1 scaffold behavior with the following checks.

### Backend checks

```bash
curl -s http://127.0.0.1:8000/health
# expected: {"status":"ok"}

curl -s http://127.0.0.1:8000/health/db
# expected: {"db":"ok"}
```

### Frontend checks

Open: <http://127.0.0.1:3000>

Expected page content:

- Title: `Fund Management System`
- Description: `V1 scaffold is ready.`

## Common issues

- **`/health` ok but `/health/db` fails**:
  - ensure database container is up: `docker compose ps`
  - inspect DB logs: `docker compose logs db --tail=100`
- **frontend cannot connect**:
  - verify Next dev server is on `127.0.0.1:3000`
  - check if another process occupies port 3000

### Optional one-command smoke sequence (manual)

In three terminals:

1. `docker compose up -d db`
2. `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. `cd frontend && npm run dev`

Then run:

```bash
curl -s http://127.0.0.1:8000/health && echo
curl -s http://127.0.0.1:8000/health/db && echo
```

If both interfaces return `ok` and the homepage renders the text above, local scaffold functionality is complete for the current V1 scope.

## Scope

This is an initialization scaffold intended to match the requested project tree and V1 direction.
