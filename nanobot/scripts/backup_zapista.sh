#!/usr/bin/env bash
# Zapista – backup de dados (volumes Docker e ficheiros do projeto)
# Uso: bash scripts/backup_zapista.sh [DIR_SAIDA]
#   DIR_SAIDA  pasta onde guardar o backup (default: ./backups)
# Gera: backup-zapista-YYYYMMDD-HHMMSS.tar.gz

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"
OUT_DIR="${1:-$SCRIPT_DIR/backups}"
STAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$OUT_DIR/backup-zapista-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"
echo "[Zapista Backup] A criar $ARCHIVE"

# Dados em volumes Docker (nome do projeto = zapista)
VOLUMES=$(docker volume ls -q --filter name=zapista) 2>/dev/null || true
TMP_DIR=$(mktemp -d)
trap "rm -rf '$TMP_DIR'" EXIT

if [ -n "$VOLUMES" ]; then
  for vol in $VOLUMES; do
    echo "[Zapista Backup] A exportar volume: $vol"
    docker run --rm -v "$vol":/data -v "$TMP_DIR":/out alpine tar czf "/out/$vol.tar.gz" -C /data . 2>/dev/null || true
  done
fi

# Ficheiros locais úteis (opcional)
[ -f .env ] && cp .env "$TMP_DIR/" 2>/dev/null || true
[ -d .zapista ] && cp -r .zapista "$TMP_DIR/" 2>/dev/null || true

tar czf "$ARCHIVE" -C "$TMP_DIR" .
echo "[Zapista Backup] Concluído: $ARCHIVE"
