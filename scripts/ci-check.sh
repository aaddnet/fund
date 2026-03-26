#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[ci] backend pytest"
cd "$ROOT_DIR/backend"
if [ -x "$ROOT_DIR/backend/.venv312/bin/python" ]; then
  "$ROOT_DIR/backend/.venv312/bin/python" -m pytest
else
  python3 -m pytest
fi

echo "[ci] frontend type/build"
cd "$ROOT_DIR/frontend"
npm run build

echo "[ci] done"
