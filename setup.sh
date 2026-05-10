#!/usr/bin/env bash
# One-shot system bootstrap for a fresh Linux box.
# Installs python3, python3-venv, python3-pip (and optionally node) via the
# distro package manager. Then run ./run.sh — that handles the rest in user space.
set -euo pipefail

WANT_NODE="${WANT_NODE:-0}"   # set 1 if you plan to modify frontend src
SUDO="${SUDO:-sudo}"

if [ "$EUID" -eq 0 ]; then SUDO=""; fi

if command -v apt-get >/dev/null 2>&1; then
  echo "[apt] installing python3 python3-venv python3-pip docker.io docker-compose-plugin"
  $SUDO apt-get update -y
  $SUDO apt-get install -y python3 python3-venv python3-pip ca-certificates curl
  if [ "$WANT_NODE" = "1" ]; then
    if ! command -v node >/dev/null 2>&1; then
      echo "[apt] installing node 20.x via NodeSource"
      curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
      $SUDO apt-get install -y nodejs
    fi
  fi
elif command -v dnf >/dev/null 2>&1; then
  echo "[dnf] installing python3 python3-pip"
  $SUDO dnf install -y python3 python3-pip ca-certificates curl
  if [ "$WANT_NODE" = "1" ] && ! command -v node >/dev/null 2>&1; then
    $SUDO dnf module install -y nodejs:20
  fi
elif command -v pacman >/dev/null 2>&1; then
  echo "[pacman] installing python python-pip"
  $SUDO pacman -Sy --noconfirm python python-pip ca-certificates curl
  if [ "$WANT_NODE" = "1" ] && ! command -v node >/dev/null 2>&1; then
    $SUDO pacman -Sy --noconfirm nodejs npm
  fi
else
  echo "[WARN] unknown package manager — please install manually:"
  echo "       python3 (>=3.10), python3-venv, python3-pip"
  echo "       (optional, only for editing frontend) node >= 18"
  exit 0
fi

echo
echo "✓ system packages installed."
echo "  next: ./run.sh"
echo
echo "  Optional integrations (clone next to 6bq5/):"
echo "    git clone https://github.com/mrgrit/6v6      # docker-compose infra"
echo "    git clone https://github.com/mrgrit/bastion  # KG-aware agent"
echo "    INFRA_DIR=\$PWD/../6v6 BASTION_URL=http://localhost:9100 ./run.sh"
