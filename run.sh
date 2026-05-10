#!/usr/bin/env bash
# 6bq5 launcher — Python-only on a fresh Linux box.
#
# Auto-installs:
#   - Python deps into a venv at .venv/
# Skips frontend build (frontend/dist/ is committed to the repo).
# If you modify frontend/src/ you need node 18+ and `cd frontend && npm i && npm run build`.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8500}"
HOST="${HOST:-0.0.0.0}"
VENV="${VENV:-.venv}"

# ── 1. Python ────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo "[FATAL] python3 not installed. Run ./setup.sh first (sudo) or"
  echo "        sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

# ── 2. venv + deps ───────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo "[1/3] creating Python venv at $VENV…"
  if ! python3 -m venv "$VENV" 2>/dev/null; then
    echo "[FATAL] python3-venv missing. sudo apt install python3-venv"
    exit 1
  fi
fi
# shellcheck disable=SC1090
. "$VENV/bin/activate"

if ! python -c "import fastapi, uvicorn, networkx, httpx, pydantic" 2>/dev/null; then
  echo "[2/3] installing Python deps into $VENV…"
  pip install --quiet --upgrade pip
  pip install --quiet -r backend/requirements.txt
fi

# ── 3. KG (already in repo, but allow re-import via SRC_KG) ──
if [ ! -f data/kg.db ]; then
  echo "[+]   data/kg.db missing — running import_kg.py"
  python scripts/import_kg.py
fi

# CCC SKILLS dict (33) + playbook YAML 을 한 번 더 KG 로 sync
# (존재하는 CCC repo 가 있을 때만 — 없으면 silently skip)
if [ -d "$HOME/ccc" ] || [ -n "${CCC_HOME:-}" ]; then
  if python -c "import sys; sys.exit(0)" 2>/dev/null; then
    python scripts/sync_ccc_skills_playbooks.py 2>/dev/null | tail -3 || true
  fi
fi

# ── 4. frontend ──────────────────────────────────────────────
if [ ! -d frontend/dist ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[+]   building frontend (npm)…"
    pushd frontend >/dev/null
    npm install --silent
    npm run build --silent
    popd >/dev/null
  else
    echo "[WARN] frontend/dist missing AND npm unavailable — UI will return"
    echo "       a JSON ping at /. The API at /api/* still works fully."
    echo "       Install node 18+ then \`cd frontend && npm i && npm run build\`."
  fi
fi

# ── 5. boot ──────────────────────────────────────────────────
echo "[3/3] starting backend on http://${HOST}:${PORT}/"
exec env PYTHONPATH=. python -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}"
