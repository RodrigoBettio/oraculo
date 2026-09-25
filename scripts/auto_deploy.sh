#!/bin/bash
set -eo pipefail

cd /home/rodriguinhobettiojr/oraculo || exit 1

git fetch origin main >/dev/null 2>&1 || exit 0

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    mkdir -p /home/rodriguinhobettiojr/oraculo/data
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Novo commit detectado: $LOCAL -> $REMOTE. Aplicando atualizações..." >> /home/rodriguinhobettiojr/oraculo/data/deploy.log
    git reset --hard origin/main >> /home/rodriguinhobettiojr/oraculo/data/deploy.log 2>&1
    docker compose up -d >> /home/rodriguinhobettiojr/oraculo/data/deploy.log 2>&1 || docker restart oraculo-app >> /home/rodriguinhobettiojr/oraculo/data/deploy.log 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deploy concluído com sucesso!" >> /home/rodriguinhobettiojr/oraculo/data/deploy.log
fi
