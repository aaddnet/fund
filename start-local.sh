#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
COMPOSE_DIR="$ROOT/fund-system"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://fund_user:fund_pass@127.0.0.1:5432/fund_system}"

mkdir -p "$ROOT/.run"

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "[1/3] Starting PostgreSQL via Docker Compose..."
cd "$COMPOSE_DIR"
docker compose up -d db

echo "[2/3] Preparing backend virtualenv..."
cd "$BACKEND_DIR"
if [ ! -d .venv312 ]; then
  "$PYTHON_BIN" -m venv .venv312
fi
source .venv312/bin/activate
pip install -r requirements.txt >/tmp/invest-backend-pip.log
export DATABASE_URL
uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$ROOT/.run/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$ROOT/.run/backend.pid"

echo "[3/3] Starting frontend..."
cd "$FRONTEND_DIR"
npm install >/tmp/invest-frontend-npm.log
npm run dev > "$ROOT/.run/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$ROOT/.run/frontend.pid"

echo "Waiting for services..."
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && curl -sf http://127.0.0.1:3000 >/dev/null 2>&1; then
    echo "Local stack is ready."
    echo "Frontend: http://127.0.0.1:3000"
    echo "Backend:  http://127.0.0.1:8000"
    echo "Logs: $ROOT/.run/backend.log and $ROOT/.run/frontend.log"
    wait
    exit 0
  fi
  sleep 2
done

echo "Startup timed out. Check logs in $ROOT/.run/." >&2
exit 1
