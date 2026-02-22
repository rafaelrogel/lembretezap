#!/bin/bash
#
# Zapista — Instalador 3: Updater (atualizar e reiniciar)
# Uso: sudo bash update_vps.sh
#
# Faz: puxa o código mais recente do git → reconstrói imagens → reinicia
#      todos os serviços (bridge, gateway, API) → WhatsApp reconecta automaticamente.
# Não altera .env nem config.json (mantém chaves e senha de god-mode).
#
set -e

# Auto-detectar pasta de instalação (procurar em /opt, /root, /home)
_detect_install_dir() {
  if [ -n "${ZAPISTA_INSTALL_DIR}" ] && [ -d "${ZAPISTA_INSTALL_DIR}" ]; then
    echo "${ZAPISTA_INSTALL_DIR}"
    return
  fi
  _found=$(find /opt /root /home -maxdepth 5 -name "docker-compose.vps.yml" -type f 2>/dev/null | head -1)
  if [ -n "$_found" ]; then
    dirname "$_found"
    return
  fi
  for _cand in /opt/zapista /opt/Zapista /root/zapista; do
    if [ -d "$_cand" ] && [ -f "$_cand/docker-compose.yml" ] && [ -d "$_cand/zapista" ] && [ -d "$_cand/backend" ]; then
      echo "$_cand"
      return
    fi
  done
  while IFS= read -r _f; do
    [ -z "$_f" ] && continue
    _p=$(dirname "$_f")
    if [ -d "$_p/zapista" ] && [ -d "$_p/backend" ] 2>/dev/null; then
      echo "$_p"
      return
    fi
  done < <(find /opt /root /home -maxdepth 4 -name "docker-compose.yml" -type f 2>/dev/null)
  echo "/opt/zapista"
}

INSTALL_DIR="${ZAPISTA_INSTALL_DIR:-$(_detect_install_dir)}"

echo ""
echo "=============================================="
echo "  Zapista — Updater (git + reiniciar + reconectar)"
echo "=============================================="
echo ""
echo "Pasta detectada: $INSTALL_DIR"
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
  echo "Erro: pasta de instalação não encontrada."
  echo "  Procurou em: /opt, /root, /home"
  echo "  Esperava: $INSTALL_DIR (ou ZAPISTA_INSTALL_DIR=/caminho)"
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
if ! docker compose $COMPOSE_FILES build --no-cache; then
  echo ""
  echo "  ERRO: Falha ao construir imagens. Verifica os logs acima."
  exit 1
fi
if ! docker compose $COMPOSE_FILES up -d; then
  echo ""
  echo "  ERRO: Falha ao iniciar os contentores."
  exit 1
fi
echo "    Serviços em execução."
echo ""

echo "[3/3] Verificação de saúde do sistema (TTS)..."
DATA_DIR="${INSTALL_DIR}/data"
if [ -f ".env" ]; then
  CUR_PIPER=$(grep "PIPER_BIN=" .env | cut -d'=' -f2)
  if [ -n "$CUR_PIPER" ] && [ ! -f "$CUR_PIPER" ]; then
    echo "    ⚠️ Aviso: PIPER_BIN no .env aponta para um caminho inexistente: $CUR_PIPER"
    NEW_PIPER="${DATA_DIR}/bin/piper"
    if [ -f "$NEW_PIPER" ]; then
      echo "    ✅ Encontrado Piper em: $NEW_PIPER"
      echo "    A atualizar .env com o caminho correto..."
      sed -i "s|PIPER_BIN=.*|PIPER_BIN=$NEW_PIPER|" .env
      sed -i "s|TTS_MODELS_BASE=.*|TTS_MODELS_BASE=${DATA_DIR}/models/piper|" .env
      echo "    Caminhos de TTS atualizados no .env."
    fi
  else
    # Validar se falta o espeak-ng-data (causa erro de síntese)
    _espeak_path="${DATA_DIR}/bin/espeak-ng-data"
    if [ ! -d "$_espeak_path" ] && [ -f "${DATA_DIR}/bin/piper" ]; then
      echo "    ⚠️ Aviso: Pasta espeak-ng-data não encontrada em: $_espeak_path"
      echo "    A tentar reparação automática do motor de áudio..."
      
      PIPER_RELEASE="2023.11.14-2"
      PIPER_ARCH=$(uname -m)
      case "$PIPER_ARCH" in
        x86_64)   PIPER_TGZ="piper_linux_x86_64.tar.gz" ;;
        aarch64)  PIPER_TGZ="piper_linux_aarch64.tar.gz" ;;
        armv7l)   PIPER_TGZ="piper_linux_armv7l.tar.gz" ;;
        *)        PIPER_TGZ="" ;;
      esac
      
      if [ -n "$PIPER_TGZ" ]; then
        _piper_tmp=$(mktemp -d)
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_RELEASE}/${PIPER_TGZ}"
        if curl -fsSL "$PIPER_URL" -o "$_piper_tmp/piper.tar.gz"; then
          tar -xzf "$_piper_tmp/piper.tar.gz" -C "$_piper_tmp"
          _espeak_src=$(find "$_piper_tmp" -name "espeak-ng-data" -type d 2>/dev/null | head -1)
          if [ -n "$_espeak_src" ]; then
            cp -a "$_espeak_src" "${DATA_DIR}/bin/"
            echo "    ✅ Pasta espeak-ng-data restaurada com sucesso."
          fi
        fi
        rm -rf "$_piper_tmp"
      fi
    fi
    echo "    ✅ Configuração de TTS parece correta."
  fi
fi
echo ""

echo "Concluído."
echo ""
echo "Serviços reiniciados. O bridge reconecta automaticamente ao WhatsApp."
echo ""
echo "Ver logs: cd $INSTALL_DIR && docker compose $COMPOSE_FILES logs -f"
echo "  (bridge = logs do WhatsApp; gateway = processamento de mensagens)"
echo ""
