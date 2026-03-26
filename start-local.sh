#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.local.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running" >&2
  exit 1
fi

echo "[1/3] Building local images..."
docker compose -f "$COMPOSE_FILE" build

echo "[2/3] Starting db + backend + frontend..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[3/3] Waiting for backend and frontend readiness..."
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && curl -sf http://127.0.0.1:3000 >/dev/null 2>&1; then
    echo "Local stack is ready."
    echo "Frontend: http://127.0.0.1:3000"
    echo "Backend:  http://127.0.0.1:8000"
    echo
    echo "To inspect logs: docker compose -f $COMPOSE_FILE logs -f"
    exit 0
  fi
  sleep 2
done

echo "Local stack did not become ready in time." >&2
docker compose -f "$COMPOSE_FILE" logs --tail=100 >&2 || true
exit 1
