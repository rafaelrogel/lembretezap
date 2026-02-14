#!/bin/bash
#
# Zapista — Instalador 2: Nuclear (apagar tudo e reinstalar)
# Uso: sudo bash install_vps_nuke.sh
#
# Para: quando queres desinstalar completamente o Docker e reinstalar tudo do zero.
# Faz: 1. Para contentores e remove pasta de instalação
#      2. DESINSTALA o Docker (containers, imagens, volumes, pacotes)
#      3. Chama o instalador 1 para reinstalar tudo limpo
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detectar pasta de instalação (procurar em /opt, /root, /home)
_detect_install_dir() {
  if [ -n "${ZAPISTA_INSTALL_DIR}" ] && [ -d "${ZAPISTA_INSTALL_DIR}" ]; then
    echo "${ZAPISTA_INSTALL_DIR}"
    return
  fi
  # 1. Procurar docker-compose.vps.yml (criado pelo nosso instalador)
  _found=$(find /opt /root /home -maxdepth 5 -name "docker-compose.vps.yml" -type f 2>/dev/null | head -1)
  if [ -n "$_found" ]; then
    dirname "$_found"
    return
  fi
  # 2. Procurar estrutura zapista (docker-compose.yml + zapista/ + backend/ + bridge/)
  for _cand in /opt/zapista /opt/Zapista /root/zapista; do
    if [ -d "$_cand" ] && [ -f "$_cand/docker-compose.yml" ] && [ -d "$_cand/zapista" ] && [ -d "$_cand/backend" ]; then
      echo "$_cand"
      return
    fi
  done
  # 3. Busca mais ampla: directorias com docker-compose.yml que referenciem bridge/gateway
  while IFS= read -r _dir; do
    [ -z "$_dir" ] && continue
    _parent=$(dirname "$_dir")
    if [ -d "$_parent/zapista" ] && [ -d "$_parent/backend" ] 2>/dev/null; then
      echo "$_parent"
      return
    fi
  done < <(find /opt /root /home -maxdepth 4 -name "docker-compose.yml" -type f 2>/dev/null)
  # 4. Fallback: pasta padrão (para nuke fresco)
  echo "/opt/zapista"
}

INSTALL_DIR=$(_detect_install_dir)
DATA_DIR="${INSTALL_DIR}/data"

# Serão exportadas para o install_vps.sh se fizer backup
export DO_BACKUP_RESTORE=""
export BACKUP_TEMP=""

echo ""
echo "=============================================="
echo "  Zapista — Instalador 2: NUCLEAR"
echo "=============================================="
echo ""
echo "ATENÇÃO: Este script vai:"
echo "  1. Parar todos os contentores Zapista"
echo "  2. APAGAR a pasta $INSTALL_DIR"
echo "  3. DESINSTALAR o Docker completamente (pacotes + dados)"
echo "  4. Reinstalar tudo do zero (sistema, Docker, código, etc.)"
echo ""
echo "Usa isto quando queres uma reinstalação limpa (ex.: Docker corrompido)."
echo ""
echo "Pasta detectada: $INSTALL_DIR"
echo ""
read -r -p "Continuar? Escreve 'sim' para confirmar: " confirm
if [ "$confirm" != "sim" ]; then
  echo "Cancelado."
  exit 0
fi
echo ""

# --- 1. Verificar root ---
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script deve ser executado com sudo."
  echo "Exemplo: sudo bash install_vps_nuke.sh"
  exit 1
fi

# --- 2. Backup opcional (sempre pergunta quando existe instalação) ---
echo "[Nuke 1/4] Backup dos dados"
if [ -d "$INSTALL_DIR" ] && [ -d "$DATA_DIR" ]; then
  echo "          Existe instalação em $INSTALL_DIR"
  echo "          Desejas fazer backup (organizer.db, whatsapp-auth, sessões) para restaurar no final?"
  echo ""
  echo "  [b] Backup — guarda e restaura no final"
  echo "  [z] Zero   — apaga tudo sem backup"
  echo ""
  while true; do
    read -r -p "  Escolhe (b/z): " choice
    case "$(echo "$choice" | tr '[:upper:]' '[:lower:]')" in
      b)
        export DO_BACKUP_RESTORE="1"
        export BACKUP_TEMP="/root/zapista-reinstall-backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_TEMP"
        echo "    A fazer backup de $DATA_DIR para $BACKUP_TEMP ..."
        cp -a "$DATA_DIR"/. "$BACKUP_TEMP"/
        echo "    Backup guardado."
        break
        ;;
      z)
        echo "    Sem backup."
        break
        ;;
      *)
        echo "    Opção inválida. Escreve 'b' ou 'z'."
        ;;
    esac
  done
else
  echo "          Nenhuma instalação anterior em $INSTALL_DIR — segue sem backup."
fi
echo ""

# --- 3. Parar contentores e remover pasta ---
echo "[Nuke 2/4] A parar contentores e a remover $INSTALL_DIR ..."
if [ -d "$INSTALL_DIR" ]; then
  (cd "$INSTALL_DIR" && [ -f "docker-compose.yml" ] && docker compose -f docker-compose.yml -f docker-compose.vps.yml down -v 2>/dev/null) || true
  (cd "$INSTALL_DIR" && [ -f "docker-compose.yml" ] && docker compose down -v 2>/dev/null) || true
  rm -rf "$INSTALL_DIR"
  echo "    Pasta removida."
else
  echo "    Nenhuma instalação encontrada."
fi
echo ""

# --- 4. Desinstalar Docker ---
echo "[Nuke 3/4] A desinstalar o Docker..."
systemctl stop docker 2>/dev/null || true
systemctl stop docker.socket 2>/dev/null || true

# Remover pacotes (nomes podem variar conforme a instalação)
apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>/dev/null || true
apt-get purge -y docker.io docker-doc docker-compose 2>/dev/null || true
apt-get autoremove -y -qq 2>/dev/null || true

# Remover dados do Docker
rm -rf /var/lib/docker /var/lib/containerd /etc/docker 2>/dev/null || true

echo "    Docker desinstalado."
echo ""

# --- 5. Chamar instalador 1 (reinstala tudo na mesma pasta) ---
echo "[Nuke 4/4] A chamar instalador do zero..."
echo "          Reinstalação em: $INSTALL_DIR"
echo ""
export ZAPISTA_INSTALL_DIR="$INSTALL_DIR"
exec bash "$SCRIPT_DIR/install_vps.sh"
