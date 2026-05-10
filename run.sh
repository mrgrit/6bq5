#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f data/kg.db ]; then
  echo "[1/3] data/kg.db missing — running import_kg.py…"
  python3 scripts/import_kg.py
else
  echo "[1/3] data/kg.db present (skipping import — pre-sanitized snapshot in repo)"
fi

if [ ! -d frontend/dist ]; then
  echo "[2/3] building frontend…"
  pushd frontend >/dev/null
  npm install
  npm run build
  popd >/dev/null
fi

PORT="${PORT:-8500}"
HOST="${HOST:-0.0.0.0}"
echo "[3/3] starting backend on ${HOST}:${PORT}…"
PYTHONPATH=. exec python3 -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}"
