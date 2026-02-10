#!/bin/bash
#
# ZapAssist — Atualizar instalação no VPS (código + reiniciar serviços)
# Uso: sudo bash update_vps.sh
#
# Faz: git pull em /opt/zapassist → rebuild imagens → docker compose up -d
# Não altera .env nem config.json (mantém chaves e senha de god-mode).
#
set -e

INSTALL_DIR="${ZAPASSIST_INSTALL_DIR:-/opt/zapassist}"

echo ""
echo "=============================================="
echo "  ZapAssist — Atualizar no VPS"
echo "=============================================="
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
  echo "Erro: pasta de instalação não encontrada: $INSTALL_DIR"
  echo "Se instalaste noutro sítio, usa: ZAPASSIST_INSTALL_DIR=/caminho sudo bash update_vps.sh"
  exit 1
fi

if [ ! -d "${INSTALL_DIR}/.git" ]; then
  echo "Erro: $INSTALL_DIR não é um repositório git. Usa o instalador completo: scripts/install_vps.sh"
  exit 1
fi

# Opcional: exigir sudo para garantir que docker funciona
if [ "$(id -u)" -ne 0 ]; then
  echo "Aviso: recomenda-se executar com sudo para garantir acesso ao Docker."
  echo "Exemplo: sudo bash update_vps.sh"
  read -r -p "Continuar assim mesmo? [y/N] " r
  case "$r" in
    [yY][eE][sS]|[yY]) ;;
    *) exit 1 ;;
  esac
fi

echo "[1/3] A atualizar o código em $INSTALL_DIR ..."
cd "$INSTALL_DIR"
git fetch origin
git reset --hard origin/main
git pull --ff-only origin main || true
echo "    Código atualizado (main)."
echo ""

echo "[2/3] A reconstruir imagens e reiniciar os serviços..."
COMPOSE_FILES="-f docker-compose.yml"
if [ -f "docker-compose.vps.yml" ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.vps.yml"
fi
docker compose $COMPOSE_FILES build --no-cache 2>/dev/null || docker compose $COMPOSE_FILES build
docker compose $COMPOSE_FILES up -d
echo "    Serviços em execução."
echo ""

echo "[3/3] Concluído."
echo ""
echo "Ver logs: cd $INSTALL_DIR && docker compose $COMPOSE_FILES logs -f"
echo ""
