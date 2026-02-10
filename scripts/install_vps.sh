#!/bin/bash
#
# ZapAssist — Instalador no VPS Linux (instalação do zero)
# Uso: sudo bash install_vps.sh
#
# Faz: remove TUDO do VPS (pasta de instalação) → atualiza o sistema → pede chaves e senha god-mode → instala e arranca.
#
set -e

INSTALL_DIR="${ZAPASSIST_INSTALL_DIR:-/opt/zapassist}"
DATA_DIR="${INSTALL_DIR}/data"
REPO_URL="${ZAPASSIST_REPO_URL:-https://github.com/rafaelrogel/lembretezap.git}"

echo ""
echo "=============================================="
echo "  ZapAssist — Instalador no VPS (do zero)"
echo "=============================================="
echo ""
echo "Este script vai:"
echo "  1. Parar contentores e APAGAR toda a instalação anterior em $INSTALL_DIR"
echo "  2. Atualizar o sistema (apt update + upgrade)"
echo "  3. Pedir as chaves de API (DeepSeek e Xiaomi MiMo)"
echo "  4. Pedir a senha de god-mode (comandos admin no chat)"
echo "  5. Instalar Docker (se precisar), clonar o código e arrancar tudo"
echo ""

# --- 1. Verificar root/sudo ---
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script deve ser executado com sudo."
  echo "Exemplo: sudo bash install_vps.sh"
  exit 1
fi

# --- 2. Parar contentores e apagar toda a instalação ---
echo "[Passo 1/7] A parar contentores e a remover toda a instalação em $INSTALL_DIR ..."
if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR"
  if [ -f "docker-compose.yml" ]; then
    docker compose -f docker-compose.yml -f docker-compose.vps.yml down 2>/dev/null || true
    docker compose down 2>/dev/null || true
  fi
  cd - > /dev/null
  rm -rf "$INSTALL_DIR"
  echo "    Pasta removida. Instalação anterior apagada."
else
  echo "    Nenhuma instalação anterior encontrada."
fi
echo ""

# --- 3. Atualizar o sistema ---
echo "[Passo 2/7] A atualizar o sistema (pode demorar um pouco)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl git ca-certificates
echo "    Sistema atualizado."
echo ""

# --- 4. Pedir chaves API ---
echo "[Passo 3/7] Chaves de API"
echo "    (As chaves ficam só no servidor, no ficheiro .env — não são enviadas para lado nenhum.)"
echo ""

if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "  DeepSeek — para o agente (lembretes, listas, conversa)."
  echo "  Obtém em: https://platform.deepseek.com"
  read -r -s -p "  Cola aqui a chave DeepSeek: " DEEPSEEK_API_KEY
  echo ""
  if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "  Erro: a chave DeepSeek é obrigatória."
    exit 1
  fi
fi

if [ -z "$XIAOMI_API_KEY" ]; then
  echo "  Xiaomi MiMo — para respostas rápidas e análises."
  echo "  Obtém em: https://platform.xiaomimimo.com"
  read -r -s -p "  Cola aqui a chave Xiaomi MiMo: " XIAOMI_API_KEY
  echo ""
  if [ -z "$XIAOMI_API_KEY" ]; then
    echo "  Erro: a chave Xiaomi MiMo é obrigatória."
    exit 1
  fi
fi
echo "    Chaves guardadas (só no .env)."
echo ""

# --- 5. Senha de god-mode ---
echo "[Passo 4/7] Senha de god-mode (comandos admin)"
echo "    Qualquer pessoa pode falar com o bot. Para rodar comandos admin (#status, #users, etc.),"
echo "    o administrador envia no chat: #<esta_senha> — isso ativa o god-mode e depois pode usar #status, #cron, etc."
echo "    Se alguém enviar # com senha errada, o bot não responde (silêncio)."
echo ""
if [ -z "$GOD_MODE_PASSWORD" ]; then
  read -r -s -p "  Define a senha de god-mode: " GOD_MODE_PASSWORD
  echo ""
  if [ -z "$GOD_MODE_PASSWORD" ]; then
    echo "  Aviso: senha vazia — god-mode ficará desativado (qualquer # será ignorado em silêncio)."
  else
    echo "    Senha guardada no .env (só no servidor)."
  fi
fi
echo ""

# --- 6. Docker e Docker Compose ---
echo "[Passo 5/7] Docker..."
if ! command -v docker &> /dev/null; then
  echo "    A instalar Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  echo "    Docker já está instalado."
fi
if ! command -v docker compose &> /dev/null 2>&1; then
  echo "    A instalar Docker Compose..."
  apt-get install -y -qq docker-compose-plugin
else
  echo "    Docker Compose já está instalado."
fi
echo ""

# --- 7. Clonar repositório (sempre do zero) ---
echo "[Passo 6/7] A clonar o código do ZapAssist em ${INSTALL_DIR}..."
mkdir -p "$(dirname "$INSTALL_DIR")"
git clone "$REPO_URL" "$INSTALL_DIR"
echo "    Repositório clonado (main)."
echo ""

# --- 8. Dados, config.json (com allow_from) e .env ---
echo "[Passo 7/7] Configuração e arranque..."
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/whatsapp-auth"

# config.json: allow_from vazio = qualquer pessoa pode falar com o bot
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

_esc() { echo "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'; }
cat > "$INSTALL_DIR/.env" << ENV_EOF
# Gerado por install_vps.sh — não commitar
NANOBOT_PROVIDERS__DEEPSEEK__API_KEY="$( _esc "$DEEPSEEK_API_KEY" )"
NANOBOT_PROVIDERS__XIAOMI__API_KEY="$( _esc "$XIAOMI_API_KEY" )"
HEALTH_CHECK_TOKEN=health-$(openssl rand -hex 8)
API_SECRET_KEY=api-$(openssl rand -hex 12)
CORS_ORIGINS=*
GOD_MODE_PASSWORD="$( _esc "$GOD_MODE_PASSWORD" )"
ENV_EOF
chmod 600 "$INSTALL_DIR/.env"

cat > "$INSTALL_DIR/docker-compose.vps.yml" << EOF
# Override para VPS: dados em pasta local e .env (chaves)
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

cd "$INSTALL_DIR"
echo "    A construir imagens e a iniciar os serviços (alguns minutos)..."
docker compose -f docker-compose.yml -f docker-compose.vps.yml build --no-cache 2>/dev/null || docker compose -f docker-compose.yml -f docker-compose.vps.yml build
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d

echo ""
echo "=============================================="
echo "  Instalação concluída"
echo "=============================================="
echo ""
echo "Próximo passo OBRIGATÓRIO — ligar o WhatsApp (QR code):"
echo ""
echo "  1. Executa:"
echo "     cd $INSTALL_DIR"
echo "     docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f bridge"
echo ""
echo "  2. Quando aparecer o QR no ecrã:"
echo "     • Abre o WhatsApp no telemóvel"
echo "     • Menu (⋮) → Aparelhos ligados → Ligar um aparelho"
echo "     • Escaneia o QR"
echo ""
echo "  3. Quando aparecer 'Connected', sai dos logs com Ctrl+C (os serviços continuam a correr)."
echo ""
echo "Dados e config: $DATA_DIR"
echo ""
