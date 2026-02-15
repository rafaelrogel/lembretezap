#!/usr/bin/env bash
# Zapista – instalação do zero no VPS (Linux)
# Uso: bash scripts/install_vps.sh
# Requer: Docker, Docker Compose, git (e opcionalmente .env na raiz do projeto)

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"
PROJECT_NAME="${PROJECT_NAME:-zapista}"

echo "[Zapista] Instalação do zero em: $SCRIPT_DIR"
echo ""

# 1) Ficheiro .env (opcional)
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "[Zapista] A copiar .env.example -> .env"
    cp .env.example .env
    echo "[Zapista] Edita .env com os teus valores e volta a correr este script se precisares."
  else
    echo "[Zapista] Aviso: não existe .env nem .env.example. Cria .env com as variáveis necessárias (ex.: chaves API)."
  fi
else
  echo "[Zapista] .env encontrado."
fi

# 2) Build e arranque
echo "[Zapista] A construir imagens e a levantar serviços..."
docker compose build --no-cache
docker compose up -d

echo ""
echo "[Zapista] Instalação concluída. Serviços:"
docker compose ps
echo ""
echo "Para ver logs: docker compose logs -f"
echo "Para parar:    docker compose down"
