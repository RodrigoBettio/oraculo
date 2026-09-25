#!/bin/bash
# ============================================================
# ORÁCULO - Backup de Dados e Credenciais
# ============================================================
# Uso: bash scripts/backup.sh
# Cria um tar.gz com timestamp contendo:
#   - data/agents/ (perfis dos agentes)
#   - data/areas/  (áreas da vida)
#   - data/skills/ (skills geradas)
#   - data/processed/ (transcrições e OCR)
#   - data/oraculo.db (fila e histórico)
#   - credentials/token.json (sessão do Google Drive)
#   - .env (configurações)
# ============================================================

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_FILE="${BACKUP_DIR}/oraculo_backup_${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

echo "🔮 ORÁCULO - Criando backup..."
echo "   Destino: ${BACKUP_FILE}"

tar -czf "${BACKUP_FILE}" \
    --exclude='data/videos' \
    --exclude='data/temp' \
    --exclude='*.session' \
    --exclude='*.session-shm' \
    --exclude='*.session-wal' \
    data/ \
    credentials/token.json \
    .env \
    2>/dev/null || true

SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "✅ Backup criado: ${BACKUP_FILE} (${SIZE})"

# Remove backups com mais de 30 dias
find "${BACKUP_DIR}" -name "oraculo_backup_*.tar.gz" -mtime +30 -delete 2>/dev/null || true
echo "🧹 Backups antigos (>30 dias) removidos."
