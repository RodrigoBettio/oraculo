#!/bin/bash
set -e

echo "============================================"
echo "🔮 ORÁCULO - Inicializando servidor..."
echo "============================================"

# Garante que diretórios de dados existem
mkdir -p /app/data/agents /app/data/areas /app/data/skills /app/data/processed /app/data/videos /app/data/temp /app/data/workspaces /app/data/vault_documents /app/credentials

# Verifica se o token do Google Drive existe e é válido
if [ -f "/app/credentials/token.json" ]; then
    echo "✅ Token do Google Drive encontrado."
else
    echo "ℹ️  Token do Google Drive não encontrado."
    echo "   Acesse o painel web e clique em 'Conectar com Google' para autenticar."
fi

# Limpeza de vídeos antigos (se configurado)
RETENTION=${VIDEO_RETENTION_HOURS:-24}
echo "🧹 Limpando vídeos com mais de ${RETENTION}h..."
find /app/data/videos -type f -mmin +$((RETENTION * 60)) -delete 2>/dev/null || true
find /app/data/temp -type f -mmin +60 -delete 2>/dev/null || true

echo "🚀 Iniciando Uvicorn..."
exec "$@"
