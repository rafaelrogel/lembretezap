#!/usr/bin/env bash
# Zapista – nuke: parar e remover containers, volumes e imagens do projeto
# Uso: bash scripts/install_vps_nuke.sh [--reinstall]
#   --reinstall  após nuke, corre install_vps.sh

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"
PROJECT_NAME="${PROJECT_NAME:-zapista}"
REINSTALL=""

for arg in "$@"; do
  case "$arg" in
    --reinstall) REINSTALL=1 ;;
  esac
done

echo "[Zapista Nuke] A parar e remover containers e volumes do projeto '$PROJECT_NAME'..."
docker compose down -v --remove-orphans 2>/dev/null || true

echo "[Zapista Nuke] A remover imagens do projeto..."
docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "zapista-api|zapista-gateway|zapista-bridge" | while read -r img; do
  docker rmi "$img" 2>/dev/null || true
done

echo "[Zapista Nuke] Nuke concluído."
if [ -n "$REINSTALL" ]; then
  echo "[Zapista Nuke] A correr instalação do zero..."
  bash "$SCRIPT_DIR/scripts/install_vps.sh"
fi
