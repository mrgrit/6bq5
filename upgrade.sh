#!/usr/bin/env bash
# 6bq5 in-place upgrader.
#
# Pulls the latest main, preserves your local kg.db (실험 데이터·snapshots·notes
# 등), updates Python deps, and restarts the backend.
#
# What is preserved:
#   - data/kg.db (your live state including poison_log / experiments / notes)
#   - .venv/
#   - data/kg.db-wal / -shm
#
# What is overwritten:
#   - backend/*.py
#   - scripts/*.py
#   - frontend/dist/    (rebuilt asset bundle)
#   - run.sh / setup.sh / docs/*
#
# Usage:
#   ./upgrade.sh                    # standard upgrade, keep your kg.db
#   ./upgrade.sh --reset-kg         # also reset kg.db to repo baseline
#                                   # (drops your experiments — back them up first)
#   ./upgrade.sh --no-restart       # don't restart the uvicorn server
set -euo pipefail
cd "$(dirname "$0")"

RESET_KG=0
NO_RESTART=0
for a in "$@"; do
  case "$a" in
    --reset-kg)    RESET_KG=1 ;;
    --no-restart)  NO_RESTART=1 ;;
    *) echo "[warn] unknown arg: $a" ;;
  esac
done

ts=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=".upgrade_backups"
mkdir -p "$BACKUP_DIR"

echo "[1/6] backing up data/kg.db → $BACKUP_DIR/kg-${ts}.db"
if [ -f data/kg.db ]; then
  cp data/kg.db "$BACKUP_DIR/kg-${ts}.db"
fi

# stop systemd service if present
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet 6bq5 2>/dev/null; then
  echo "[2/6] stopping systemd 6bq5 service…"
  sudo systemctl stop 6bq5
  STARTED_AS_SERVICE=1
else
  echo "[2/6] systemd 6bq5 not active — skipping service stop"
  STARTED_AS_SERVICE=0
fi

# stash any user code changes (won't touch the DB since it's binary)
if [ -n "$(git status --porcelain | grep -v '^?? ')" ]; then
  echo "[3/6] stashing local changes…"
  git stash push -u -m "pre-upgrade-${ts}" || true
fi

echo "[4/6] git pull (origin main)…"
git fetch origin main
# protect kg.db from the pull when it's committed in the repo:
# checkout -- data/kg.db only if user did NOT pass --reset-kg
if [ "$RESET_KG" = "0" ] && [ -f data/kg.db ]; then
  # keep local DB; tell git to ignore changes to it during merge
  git update-index --skip-worktree data/kg.db 2>/dev/null || true
fi
git reset --hard origin/main
if [ "$RESET_KG" = "0" ] && [ -f data/kg.db ]; then
  # restore the user's DB (it was preserved on disk because of skip-worktree)
  cp "$BACKUP_DIR/kg-${ts}.db" data/kg.db
  git update-index --no-skip-worktree data/kg.db 2>/dev/null || true
fi

echo "[5/6] updating Python deps in .venv/…"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

# re-pop user changes (best-effort)
if git stash list | grep -q "pre-upgrade-${ts}"; then
  echo "[+]   re-applying stashed local changes…"
  git stash pop || echo "[warn] stash pop had conflicts — resolve manually with: git stash list/pop"
fi

if [ "$RESET_KG" = "1" ]; then
  echo "[+]   --reset-kg: data/kg.db replaced by repo baseline. Old DB at $BACKUP_DIR/kg-${ts}.db"
fi

# restart
if [ "$NO_RESTART" = "1" ]; then
  echo "[6/6] --no-restart: skipping service start"
  echo
  echo "✓ upgrade done.  Manual restart: ./run.sh"
  exit 0
fi

if [ "$STARTED_AS_SERVICE" = "1" ]; then
  echo "[6/6] restarting systemd 6bq5…"
  sudo systemctl start 6bq5
  sleep 2
  sudo systemctl --no-pager --lines=10 status 6bq5 | head -15 || true
else
  echo "[6/6] killing any old uvicorn and starting fresh in background…"
  pkill -f 'uvicorn backend.main' 2>/dev/null || true
  sleep 1
  nohup ./run.sh > /tmp/6bq5.log 2>&1 &
  disown
  sleep 3
  curl -s --max-time 3 http://127.0.0.1:8500/api/health | head -c 200 || echo "[warn] server not responding yet — check tail -f /tmp/6bq5.log"
  echo
fi

echo
echo "✓ upgrade done."
echo "  backup:   $BACKUP_DIR/kg-${ts}.db"
echo "  rollback: cp $BACKUP_DIR/kg-${ts}.db data/kg.db && ./run.sh"
