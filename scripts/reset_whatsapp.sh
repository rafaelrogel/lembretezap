#!/bin/bash
# Zapista — utilitário para resetar WhatsApp (Gerar Novo QR Code)
set -e

# Detectar pasta (mesma lógica do update_vps)
INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "=============================================="
echo "  Zapista — Reset de WhatsApp"
echo "=============================================="
echo ""
echo "Esta ação irá desconectar o bot atual e gerar um NOVO QR Code."
echo ""

read -p "Deseja continuar? [y/N] " confirm
if [[ ! "$confirm" =~ ^[yY]$ ]]; then
    echo "Cancelado."
    exit 0
fi

echo "1. Parando o bridge..."
docker compose stop bridge

echo "2. Limpando dados de autenticação..."
# Usamos o próprio bridge para limpar o seu volume
docker compose run --rm --entrypoint "rm -rf /root/.zapista/whatsapp-auth" bridge

echo "3. Reiniciando o bridge..."
docker compose up -d bridge

echo ""
echo "✅ Pronto! O bridge foi reiniciado."
echo "O novo QR Code aparecerá nos logs abaixo em alguns segundos."
echo "Use Ctrl+C para sair dos logs após escanear."
echo ""
sleep 3
docker compose logs -f bridge
