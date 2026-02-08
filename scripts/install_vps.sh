#!/bin/bash
#
# Instalação do ZapAssist (organizador WhatsApp) num VPS Linux.
# Uso: sudo bash install_vps.sh
# Ou: OPENROUTER_API_KEY="sk-or-v1-..." sudo -E bash install_vps.sh
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

# --- 2. Pedir ou usar chave OpenRouter ---
if [ -z "$OPENROUTER_API_KEY" ]; then
  echo "Introduz a tua chave da API OpenRouter (sk-or-v1-...)."
  echo "(Não partilhes esta chave com ninguém; o script usa-a só localmente.)"
  read -r -p "Chave OpenRouter: " OPENROUTER_API_KEY
  if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Erro: é obrigatório indicar a chave OpenRouter."
    exit 1
  fi
fi

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

# config.json com a chave OpenRouter (escape para JSON)
API_KEY_ESC=$(echo "$OPENROUTER_API_KEY" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
cat > "$DATA_DIR/config.json" << EOF
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "openrouter/anthropic/claude-sonnet-4",
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
    "openrouter": {
      "api_key": "$API_KEY_ESC"
    }
  }
}
EOF
chmod 600 "$DATA_DIR/config.json"

# .env para o Compose (chave também aqui para o gateway)
cat > "$INSTALL_DIR/.env" << EOF
# Gerado por install_vps.sh - não commitar
NANOBOT_PROVIDERS__OPENROUTER__API_KEY=$API_KEY_ESC
HEALTH_CHECK_TOKEN=health-$(openssl rand -hex 8)
API_SECRET_KEY=api-$(openssl rand -hex 12)
CORS_ORIGINS=*
EOF
chmod 600 "$INSTALL_DIR/.env"

# docker-compose.vps.yml: usar pasta local em vez de volume
cat > "$INSTALL_DIR/docker-compose.vps.yml" << EOF
# Override para VPS: dados em pasta local
volumes:
  nanobot_data:
    driver: local
    driver_opts:
      type: none
      device: $DATA_DIR
      o: bind
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
