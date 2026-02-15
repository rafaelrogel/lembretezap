#!/usr/bin/env bash
# Zapista – atualizador: git pull + rebuild e restart dos containers
# Uso: bash scripts/update_vps.sh
# Requer: estar na raiz do repo (ou ser chamado a partir de scripts/)

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"

echo "[Zapista Update] Diretório: $SCRIPT_DIR"
echo "[Zapista Update] A fazer git pull..."
git pull

echo "[Zapista Update] A reconstruir imagens e a reiniciar serviços..."
docker compose build
docker compose up -d

echo "[Zapista Update] Estado dos serviços:"
docker compose ps
echo ""
echo "Atualização concluída. Logs: docker compose logs -f"
