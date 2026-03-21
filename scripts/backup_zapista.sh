#!/bin/bash
#
# Zapista — Backup da memória e dados (para uso com cron diário)
# Uso: sudo bash backup_zapista.sh
#
# Faz backup de:
# - Memória do agente (workspace/memory/)
# - Sessões (sessions/*.jsonl)
# - Base de dados (organizer.db)
# - Cron jobs (cron/jobs.json)
# - Auth WhatsApp (whatsapp-auth/)
#
# Variáveis de ambiente:
#   ZAPISTA_INSTALL_DIR   — pasta do projeto (default: /opt/zapista)
#   ZAPISTA_BACKUP_DIR      — pasta dos backups (default: /backups/zapista)
#   RETENTION_DAYS          — dias a manter (default: 7)
#
set -e

INSTALL_DIR="${ZAPISTA_INSTALL_DIR:-/opt/zapista}"
BACKUP_DIR="${ZAPISTA_BACKUP_DIR:-/backups/zapista}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

echo ""
echo "=============================================="
echo "  Zapista — Backup de dados"
echo "=============================================="
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
  echo "Erro: pasta de instalação não encontrada: $INSTALL_DIR"
  echo "Se instalaste noutro sítio, usa: ZAPISTA_INSTALL_DIR=/caminho bash backup_zapista.sh"
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
BACKUP_FILE="${BACKUP_DIR}/zapista-${TIMESTAMP}.tar.gz"

echo "[1/2] A criar backup em $BACKUP_FILE ..."
# Corre um container efémero com o volume ZAPISTA_data e comprime o conteúdo.
# Com docker-compose.vps.yml o volume monta em $DATA_DIR (ex.: /opt/zapista/data); senão em /root/.zapista.
# Usar ZAPISTA_DATA se definido no container, senão /root/.zapista.
docker compose $COMPOSE_FILES run --rm --entrypoint sh \
  -v "${BACKUP_DIR}:/backup:rw" \
  -e BACKUP_TS="${TIMESTAMP}" \
  gateway \
  -c 'DATA_PATH="${ZAPISTA_DATA:-/root/.zapista}"; tar -czf /backup/zapista-${BACKUP_TS}.tar.gz -C "$DATA_PATH" . 2>/dev/null || true'

if [ -f "$BACKUP_FILE" ]; then
  SIZE_BYTES=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
  SIZE_HUMAN=$(du -h "$BACKUP_FILE" | cut -f1)
  
  # Verificar se backup não está vazio/corrompido (mínimo 1KB)
  if [ "$SIZE_BYTES" -lt 1024 ]; then
    echo "    ERRO: Backup parece vazio ou incompleto ($SIZE_BYTES bytes)"
    echo "    Possíveis causas:"
    echo "      - Volume não montado corretamente"
    echo "      - Pasta de dados vazia ou inacessível"
    echo "      - Disco cheio"
    rm -f "$BACKUP_FILE"
    exit 1
  fi
  
  # Verificar integridade do tar.gz
  if ! tar -tzf "$BACKUP_FILE" >/dev/null 2>&1; then
    echo "    ERRO: Backup corrompido (tar.gz inválido)"
    rm -f "$BACKUP_FILE"
    exit 1
  fi
  
  # Verificar se contém arquivos essenciais
  if ! tar -tzf "$BACKUP_FILE" 2>/dev/null | grep -qE "(organizer\.db|config\.json)"; then
    echo "    AVISO: Backup não contém organizer.db ou config.json"
    echo "    O backup pode estar incompleto."
  fi
  
  echo "    Backup criado: $SIZE_HUMAN ($SIZE_BYTES bytes)"
else
  echo "    ERRO: Ficheiro de backup não foi criado."
  echo "    Verifique se os serviços estão a correr: docker compose ps"
  exit 1
fi

echo ""
echo "[2/2] A limpar backups com mais de ${RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -name "zapista-*.tar.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
echo "    Concluído."
echo ""
echo "Backups atuais em $BACKUP_DIR:"
ls -la "${BACKUP_DIR}"/zapista-*.tar.gz 2>/dev/null || echo "  (nenhum)"
echo ""
