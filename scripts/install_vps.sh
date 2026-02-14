#!/bin/bash
#
# Zapista — Instalador 1: VPS novinho em folha
# Uso: sudo bash install_vps.sh
#
# Para: VPS limpo, sem instalação anterior.
# Faz: atualiza o sistema Linux → instala Docker, Node (via Docker), ffmpeg, etc. →
#      pede chaves API e senha god-mode → clona o código → configura → constrói e arranca
#      bridge, gateway, API, Redis, STT → pronto para escanear QR e conectar ao WhatsApp.
# Se existir instalação anterior em $INSTALL_DIR, remove primeiro (com opção de backup).
#
set -e

INSTALL_DIR="${ZAPISTA_INSTALL_DIR:-/opt/zapista}"
DATA_DIR="${INSTALL_DIR}/data"
REPO_URL="${ZAPISTA_REPO_URL:-https://github.com/rafaelrogel/lembretezap.git}"

# Guardar se o utilizador escolheu fazer backup (será usado mais tarde para restaurar)
DO_BACKUP_RESTORE=""
BACKUP_TEMP=""

echo ""
echo "=============================================="
echo "  Zapista — Instalador no VPS (do zero)"
echo "=============================================="
echo ""
echo "Este script vai:"
echo "  1. Parar contentores e APAGAR toda a instalação anterior em $INSTALL_DIR"
echo "  2. Atualizar o sistema (apt update + upgrade)"
echo "  3. Pedir as chaves de API (DeepSeek, Xiaomi MiMo, OpenAI e Perplexity)"
echo "  4. Pedir a senha de god-mode (comandos admin no chat)"
echo "  5. Instalar Docker (se precisar), clonar o código e arrancar tudo"
echo ""

# --- 1. Verificar root/sudo ---
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script deve ser executado com sudo."
  echo "Exemplo: sudo bash install_vps.sh"
  exit 1
fi

# --- 2. Perguntar backup ou instalação do zero (se existir instalação anterior) ---
if [ -d "$INSTALL_DIR" ] && [ -d "$DATA_DIR" ]; then
  echo "[Passo 1/8] Existe uma instalação anterior em $INSTALL_DIR"
  echo "    Desejas fazer backup dos dados (organizer.db, whatsapp-auth, sessões, etc.)"
  echo "    antes de reinstalar, para restaurar tudo no final?"
  echo ""
  echo "  [b] Backup — guarda os dados e restaura após a instalação"
  echo "  [z] Zero  — instalação do zero (apaga tudo, sem backup)"
  echo ""
  while true; do
    read -r -p "  Escolhe (b/z): " choice
    case "$(echo "$choice" | tr '[:upper:]' '[:lower:]')" in
      b)
        DO_BACKUP_RESTORE="1"
        echo "    Backup selecionado. Os dados serão guardados e restaurados no final."
        break
        ;;
      z)
        echo "    Instalação do zero selecionada."
        break
        ;;
      *)
        echo "    Opção inválida. Escreve 'b' ou 'z'."
        ;;
    esac
  done
  echo ""
fi

# --- 3. Parar contentores, fazer backup (se escolhido) e apagar instalação ---
echo "[Passo 2/8] A parar contentores e a remover a instalação em $INSTALL_DIR ..."
if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR"
  if [ -f "docker-compose.yml" ]; then
    docker compose -f docker-compose.yml -f docker-compose.vps.yml down 2>/dev/null || true
    docker compose down 2>/dev/null || true
  fi
  cd - > /dev/null

  if [ -n "$DO_BACKUP_RESTORE" ] && [ -d "$DATA_DIR" ]; then
    BACKUP_TEMP="/root/zapista-reinstall-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_TEMP"
    echo "    A fazer backup de $DATA_DIR para $BACKUP_TEMP ..."
    cp -a "$DATA_DIR"/. "$BACKUP_TEMP"/
    echo "    Backup guardado em $BACKUP_TEMP"
  fi

  rm -rf "$INSTALL_DIR"
  echo "    Pasta removida. Instalação anterior apagada."
else
  echo "    Nenhuma instalação anterior encontrada."
fi
echo ""

# --- 4. Atualizar o sistema ---
echo "[Passo 3/8] A atualizar o sistema (pode demorar um pouco)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl git ca-certificates ffmpeg jq
echo "    Sistema atualizado (curl, git, ffmpeg, jq)."
echo ""

# --- 5. Pedir chaves API ---
echo "[Passo 4/8] Chaves de API"
echo "    (As chaves ficam só no servidor, no ficheiro .env — não são enviadas para lado nenhum.)"
echo ""

if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "  DeepSeek — para o agente (lembretes, listas, conversa)."
  echo "  Obtém em: https://platform.deepseek.com"
  read -r -p "  Cola aqui a chave DeepSeek: " DEEPSEEK_API_KEY
  echo ""
  if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "  Erro: a chave DeepSeek é obrigatória."
    exit 1
  fi
fi

if [ -z "$XIAOMI_API_KEY" ]; then
  echo "  Xiaomi MiMo — para respostas rápidas e análises."
  echo "  Obtém em: https://platform.xiaomimimo.com"
  read -r -p "  Cola aqui a chave Xiaomi MiMo: " XIAOMI_API_KEY
  echo ""
  if [ -z "$XIAOMI_API_KEY" ]; then
    echo "  Erro: a chave Xiaomi MiMo é obrigatória."
    exit 1
  fi
fi

echo "  OpenAI — para transcrição de mensagens de voz (fallback quando whisper local falha). Opcional."
echo "  Obtém em: https://platform.openai.com/api-keys"
read -r -p "  Cola aqui a chave OpenAI (ou Enter para omitir): " OPENAI_API_KEY
echo ""
if [ -n "$OPENAI_API_KEY" ]; then
  echo "    Chave OpenAI guardada (só no .env)."
fi

echo "  Perplexity — para busca na web (pesquisas, informações em tempo real). Opcional."
echo "  Obtém em: https://www.perplexity.ai/settings/api"
read -r -p "  Cola aqui a chave Perplexity (ou Enter para omitir): " PERPLEXITY_API_KEY
echo ""
if [ -n "$PERPLEXITY_API_KEY" ]; then
  echo "    Chave Perplexity guardada (só no .env)."
fi

echo "    Chaves guardadas (só no .env)."
echo ""

# --- 6. Senha de god-mode ---
echo "[Passo 5/8] Senha de god-mode (comandos admin)"
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

# --- 7. Docker e Docker Compose ---
echo "[Passo 6/8] Docker..."
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

# --- 8. Clonar repositório (sempre do zero) ---
echo "[Passo 7/8] A clonar o código do Zapista em ${INSTALL_DIR}..."
mkdir -p "$(dirname "$INSTALL_DIR")"
if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
  echo ""
  echo "  ERRO: Falha ao clonar o repositório. Verifica:"
  echo "    - Ligação à internet"
  echo "    - URL: $REPO_URL"
  echo "    - Repositório público e acessível"
  exit 1
fi
echo "    Repositório clonado (main)."

# Validar estrutura essencial (evita erros silenciosos no build)
for f in docker-compose.yml Dockerfile pyproject.toml; do
  if [ ! -f "$INSTALL_DIR/$f" ]; then
    echo ""
    echo "  ERRO: Ficheiro obrigatório em falta: $f"
    echo "  O repositório pode ter estrutura diferente do esperado."
    exit 1
  fi
done
for d in zapista backend bridge prompts; do
  if [ ! -d "$INSTALL_DIR/$d" ]; then
    echo ""
    echo "  ERRO: Pasta obrigatória em falta: $d/"
    echo "  O repositório pode ter estrutura diferente do esperado."
    exit 1
  fi
done
echo ""

# --- 9. Dados, config e arranque ---
echo "[Passo 8/8] Configuração e arranque..."
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/whatsapp-auth"

if [ -n "$DO_BACKUP_RESTORE" ] && [ -d "${BACKUP_TEMP:-}" ]; then
  echo "    A restaurar dados do backup em $BACKUP_TEMP ..."
  cp -a "${BACKUP_TEMP}"/. "$DATA_DIR"/
  mkdir -p "$DATA_DIR/whatsapp-auth"
  [ -f "$DATA_DIR/config.json" ] && chmod 600 "$DATA_DIR/config.json"
  echo "    Dados restaurados: organizer.db, whatsapp-auth, sessões, cron, etc."
else
  # config.json: allow_from vazio = qualquer pessoa pode falar com o bot
  cat > "$DATA_DIR/config.json" << 'CONFIG_EOF'
{
  "agents": {
    "defaults": {
      "workspace": "~/.zapista/workspace",
      "model": "deepseek/deepseek-chat",
      "scopeModel": "xiaomi_mimo/mimo-v2-flash",
      "max_tokens": 2048,
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
    "xiaomi": { "api_key": "" },
    "perplexity": { "api_key": "" }
  }
}
CONFIG_EOF
  chmod 600 "$DATA_DIR/config.json"
fi

# Piper TTS: binário + 4 vozes (pt_BR cadu, pt_PT tugão, es_ES davefx, en_US amy)
# Links do VOICES.md: https://github.com/rhasspy/piper/blob/master/VOICES.md
# Base: https://huggingface.co/rhasspy/piper-voices/resolve/main/
PIPER_RELEASE="2023.11.14-2"
PIPER_ARCH=$(uname -m)
case "$PIPER_ARCH" in
  x86_64)   PIPER_TGZ="piper_linux_x86_64.tar.gz" ;;
  aarch64)  PIPER_TGZ="piper_linux_aarch64.tar.gz" ;;
  armv7l)   PIPER_TGZ="piper_linux_armv7l.tar.gz" ;;
  *)        PIPER_TGZ="" ;;
esac
HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"
# tugão: URL-encoded tug%C3%A3o (HuggingFace)
PIPER_VOICES="pt/pt_BR/cadu/medium:pt_BR-cadu-medium
pt/pt_PT/tug%C3%A3o/medium:pt_PT-tug%C3%A3o-medium
es/es_ES/davefx/medium:es_ES-davefx-medium
en/en_US/amy/medium:en_US-amy-medium"
if [ -n "$PIPER_TGZ" ]; then
  echo "    A instalar Piper TTS (binário + 4 vozes: pt_BR, pt_PT, es_ES, en_US)..."
  mkdir -p "$DATA_DIR/bin"
  PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_RELEASE}/${PIPER_TGZ}"
  if [ ! -f "$DATA_DIR/bin/piper" ]; then
    _piper_tmp=$(mktemp -d)
    if curl -fsSL "$PIPER_URL" -o "$_piper_tmp/piper.tar.gz"; then
      tar -xzf "$_piper_tmp/piper.tar.gz" -C "$_piper_tmp"
      # Piper tarball pode extrair para piper/, piper_linux_*/, etc. Procurar binário
      _piper_bin=$(find "$_piper_tmp" -name "piper" -type f 2>/dev/null | head -1)
      if [ -n "$_piper_bin" ]; then
        cp "$_piper_bin" "$DATA_DIR/bin/piper"
        chmod +x "$DATA_DIR/bin/piper"
      fi
    else
      echo "    Aviso: não foi possível descarregar Piper de $PIPER_URL"
    fi
    rm -rf "$_piper_tmp"
  fi
  _piper_ok=0
  while IFS=: read -r rel_path base_name; do
    [ -z "$rel_path" ] && continue
    dir="$DATA_DIR/models/piper/$rel_path"
    mkdir -p "$dir"
    for ext in onnx onnx.json; do
      f="${base_name}.${ext}"
      if [ ! -f "$dir/$f" ]; then
        curl -fsSL "$HF_BASE/$rel_path/$f" -o "$dir/$f" 2>/dev/null || true
      fi
      [ -f "$dir/$f" ] && _piper_ok=1
    done
  done << EOF
$PIPER_VOICES
EOF
  if [ -f "$DATA_DIR/bin/piper" ] && [ "$_piper_ok" = "1" ]; then
    echo "    Piper TTS instalado (TTS_ENABLED=1 no .env)."
  else
    echo "    Aviso: Piper incompleto; /audio usará texto até configurar manualmente."
  fi
else
  echo "    Piper: arquitetura $PIPER_ARCH não suportada; /audio usará texto."
fi

_esc() { echo "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'; }

# TTS: ativar se Piper instalado (múltiplas vozes em models/piper/)
TTS_ENV=""
if [ -f "$DATA_DIR/bin/piper" ] && [ -d "$DATA_DIR/models/piper" ]; then
  TTS_ENV="
TTS_ENABLED=1
PIPER_BIN=/root/.zapista/bin/piper
TTS_MODELS_BASE=/root/.zapista/models/piper
"
fi

cat > "$INSTALL_DIR/.env" << ENV_EOF
# Gerado por install_vps.sh — não commitar
ZAPISTA_PROVIDERS__DEEPSEEK__API_KEY="$( _esc "$DEEPSEEK_API_KEY" )"
ZAPISTA_PROVIDERS__XIAOMI__API_KEY="$( _esc "$XIAOMI_API_KEY" )"
OPENAI_API_KEY="$( _esc "${OPENAI_API_KEY:-}" )"
ZAPISTA_PROVIDERS__PERPLEXITY__API_KEY="$( _esc "${PERPLEXITY_API_KEY:-}" )"
HEALTH_CHECK_TOKEN=health-$(openssl rand -hex 8)
API_SECRET_KEY=api-$(openssl rand -hex 12)
CORS_ORIGINS=*
GOD_MODE_PASSWORD="$( _esc "$GOD_MODE_PASSWORD" )"
$TTS_ENV
ENV_EOF
chmod 600 "$INSTALL_DIR/.env"

cat > "$INSTALL_DIR/docker-compose.vps.yml" << EOF
# Override para VPS: dados persistidos em pasta local (config, BD organizer.db, sessões, whatsapp-auth)
# O volume ZAPISTA_data monta em /root/.zapista nos containers; organizer.db fica em DATA_DIR/organizer.db
volumes:
  ZAPISTA_data:
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
echo "    A construir imagens (alguns minutos — os erros aparecem abaixo)..."
if ! docker compose -f docker-compose.yml -f docker-compose.vps.yml build --no-cache; then
  echo ""
  echo "  ERRO: Falha ao construir imagens Docker. Verifica:"
  echo "    - Logs acima para ver o erro exato"
  echo "    - Docker em execução: systemctl status docker"
  echo "    - Espaço em disco: df -h"
  exit 1
fi
echo "    A iniciar os serviços..."
if ! docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d; then
  echo ""
  echo "  ERRO: Falha ao iniciar os contentores."
  echo "  Verifica os logs: docker compose -f docker-compose.yml -f docker-compose.vps.yml logs"
  exit 1
fi

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
echo "  - config.json, organizer.db (BD), sessões, whatsapp-auth"
echo "  - Piper TTS: models/piper/, bin/piper (comando /audio em PTT)"
echo "  - O volume ZAPISTA_data persiste tudo; reinício dos containers não apaga dados."
if [ -n "$DO_BACKUP_RESTORE" ] && [ -d "${BACKUP_TEMP:-}" ]; then
  echo ""
  echo "Backup restaurado com sucesso. A pasta $BACKUP_TEMP contém a cópia de segurança."
  echo "Podes eliminá-la após verificar que tudo está a funcionar: rm -rf $BACKUP_TEMP"
fi
echo ""
