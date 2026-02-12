#!/bin/bash
#
# ZapAssist — Backup da memória e dados (para uso com cron diário)
# Uso: sudo bash backup_nanobot.sh
#
# Faz backup de:
# - Memória do agente (workspace/memory/)
# - Sessões (sessions/*.jsonl)
# - Base de dados (organizer.db)
# - Cron jobs (cron/jobs.json)
# - Auth WhatsApp (whatsapp-auth/)
#
# Variáveis de ambiente:
#   ZAPASSIST_INSTALL_DIR   — pasta do projeto (default: /opt/zapassist)
#   NANOBOT_BACKUP_DIR      — pasta dos backups (default: /backups/nanobot)
#   RETENTION_DAYS          — dias a manter (default: 7)
#
set -e

INSTALL_DIR="${ZAPASSIST_INSTALL_DIR:-/opt/zapassist}"
BACKUP_DIR="${NANOBOT_BACKUP_DIR:-/backups/nanobot}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

echo ""
echo "=============================================="
echo "  ZapAssist — Backup de dados"
echo "=============================================="
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
  echo "Erro: pasta de instalação não encontrada: $INSTALL_DIR"
  echo "Se instalaste noutro sítio, usa: ZAPASSIST_INSTALL_DIR=/caminho bash backup_nanobot.sh"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

COMPOSE_FILES="-f docker-compose.yml"
if [ -f "${INSTALL_DIR}/docker-compose.vps.yml" ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.vps.yml"
fi

cd "$INSTALL_DIR"

# Nome do ficheiro com data e hora
TIMESTAMP=$(date +%Y%m%d-%H%M)
BACKUP_FILE="${BACKUP_DIR}/nanobot-${TIMESTAMP}.tar.gz"

echo "[1/2] A criar backup em $BACKUP_FILE ..."
# Corre um container efémero com o volume nanobot_data e comprime o conteúdo
docker compose $COMPOSE_FILES run --rm \
  -v "${BACKUP_DIR}:/backup:rw" \
  gateway \
  sh -c "tar -czf /backup/nanobot-${TIMESTAMP}.tar.gz -C /root/.nanobot . 2>/dev/null || true"

if [ -f "$BACKUP_FILE" ]; then
  SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
  echo "    Backup criado: $SIZE"
else
  echo "    Aviso: ficheiro de backup não foi criado. Verifique se os serviços estão a correr."
  exit 1
fi

echo ""
echo "[2/2] A limpar backups com mais de ${RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -name "nanobot-*.tar.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
echo "    Concluído."
echo ""
echo "Backups atuais em $BACKUP_DIR:"
ls -la "${BACKUP_DIR}"/nanobot-*.tar.gz 2>/dev/null || echo "  (nenhum)"
echo ""
