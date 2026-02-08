#!/bin/bash
#
# Instalação do ZapAssist (organizador WhatsApp) num VPS Linux.
# Uso: sudo bash install_vps.sh
# Ou: DEEPSEEK_API_KEY="sk-..." XIAOMI_API_KEY="sk-..." sudo -E bash install_vps.sh
#
set -e

INSTALL_DIR="${ZAPASSIST_INSTALL_DIR:-/opt/zapassist}"
DATA_DIR="${INSTALL_DIR}/data"
REPO_URL="${ZAPASSIST_REPO_URL:-https://github.com/rafaelrogel/lembretezap.git}"

echo "=============================================="
echo "  ZapAssist - Instalação no VPS"
echo "=============================================="
echo ""

# --- 1. Verificar root/sudo ---
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script deve ser executado como root (ou com sudo)."
  echo "Exemplo: sudo bash install_vps.sh"
  exit 1
fi

# --- 2. Pedir ou usar chaves DeepSeek e Xiaomi MiMo ---
if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "Chave DeepSeek (agente: lembretes, listas). Obtém em: https://platform.deepseek.com"
  read -r -s -p "Chave DeepSeek: " DEEPSEEK_API_KEY
  echo ""
  if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "Erro: é obrigatório indicar a chave DeepSeek."
    exit 1
  fi
fi
if [ -z "$XIAOMI_API_KEY" ]; then
  echo "Chave Xiaomi MiMo (scope + heartbeat). Obtém em: https://platform.xiaomimimo.com"
  read -r -s -p "Chave Xiaomi MiMo: " XIAOMI_API_KEY
  echo ""
  if [ -z "$XIAOMI_API_KEY" ]; then
    echo "Erro: é obrigatório indicar a chave Xiaomi MiMo."
    exit 1
  fi
fi
echo "Chaves recebidas (serão guardadas apenas no .env local)."

# --- 3. Instalar dependências (apt) ---
echo ""
echo "[1/6] A atualizar o sistema e a instalar dependências..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl git ca-certificates

# --- 4. Instalar Docker se não existir ---
if ! command -v docker &> /dev/null; then
  echo "[2/6] A instalar Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  echo "[2/6] Docker já está instalado."
fi

# --- 5. Instalar Docker Compose se não existir ---
if ! command -v docker compose &> /dev/null 2>&1; then
  echo "[3/6] A instalar Docker Compose plugin..."
  apt-get install -y -qq docker-compose-plugin
else
  echo "[3/6] Docker Compose já está instalado."
fi

# --- 6. Clonar ou atualizar o repositório ---
echo "[4/6] A preparar o código em ${INSTALL_DIR}..."
mkdir -p "$(dirname "$INSTALL_DIR")"
if [ -d "${INSTALL_DIR}/.git" ]; then
  cd "$INSTALL_DIR"
  git fetch origin
  git reset --hard origin/main
  git pull --ff-only origin main || true
  cd - > /dev/null
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# --- 7. Criar dados e config.json ---
echo "[5/6] A criar configuração e dados..."
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/whatsapp-auth"

# config.json: modelos DeepSeek (agente) + Xiaomi (scope/heartbeat); chaves ficam no .env
cat > "$DATA_DIR/config.json" << 'CONFIG_EOF'
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "deepseek/deepseek-chat",
      "scopeModel": "xiaomi_mimo/mimo-v2-flash",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  },
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridge_url": "ws://bridge:3001",
      "allow_from": []
    }
  },
  "providers": {
    "deepseek": { "api_key": "" },
    "xiaomi": { "api_key": "" }
  }
}
CONFIG_EOF
chmod 600 "$DATA_DIR/config.json"

# .env: chaves DeepSeek e Xiaomi (opção B - não colocar no config.json)
_esc() { echo "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'; }
cat > "$INSTALL_DIR/.env" << ENV_EOF
# Gerado por install_vps.sh - não commitar
NANOBOT_PROVIDERS__DEEPSEEK__API_KEY="$( _esc "$DEEPSEEK_API_KEY" )"
NANOBOT_PROVIDERS__XIAOMI__API_KEY="$( _esc "$XIAOMI_API_KEY" )"
HEALTH_CHECK_TOKEN=health-$(openssl rand -hex 8)
API_SECRET_KEY=api-$(openssl rand -hex 12)
CORS_ORIGINS=*
ENV_EOF
chmod 600 "$INSTALL_DIR/.env"

# docker-compose.vps.yml: dados em pasta local + .env para chaves
cat > "$INSTALL_DIR/docker-compose.vps.yml" << EOF
# Override para VPS: dados em pasta local e .env (DeepSeek + Xiaomi)
volumes:
  nanobot_data:
    driver: local
    driver_opts:
      type: none
      device: $DATA_DIR
      o: bind
services:
  gateway:
    env_file: .env
  api:
    env_file: .env
EOF

# O Compose carrega automaticamente o .env da pasta para substituir ${VAR}.

# --- 8. Build e arranque ---
echo "[6/6] A construir imagens e a iniciar os serviços (pode demorar alguns minutos)..."
cd "$INSTALL_DIR"
docker compose -f docker-compose.yml -f docker-compose.vps.yml build --no-cache 2>/dev/null || docker compose -f docker-compose.yml -f docker-compose.vps.yml build
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d

echo ""
echo "=============================================="
echo "  Instalação concluída"
echo "=============================================="
echo ""
echo "Próximo passo OBRIGATÓRIO: ligar o WhatsApp ao bridge (QR code)."
echo ""
echo "  cd $INSTALL_DIR"
echo "  docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge"
echo ""
echo "Quando aparecer o QR no terminal:"
echo "  1. Abre o WhatsApp no telemóvel"
echo "  2. Menu (⋮) → Aparelhos ligados → Ligar um aparelho"
echo "  3. Escaneia o QR"
echo "  4. Para sair dos logs: Ctrl+C (os contentores continuam a correr)"
echo ""
echo "Portas: bridge 3001, API 8000, gateway 18790."
echo "Dados e config: $DATA_DIR"
echo ""
