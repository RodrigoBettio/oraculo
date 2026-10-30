#!/bin/sh
# ==============================================================================
# Sincronizador Manual do Relatório de Fechamento de Vendas CRM via KUAL
# ==============================================================================

EXT_DIR="/mnt/us/extensions/painel_b3_crm"
if [ -f "$EXT_DIR/env.conf" ]; then
    . "$EXT_DIR/env.conf"
fi

if command -v fbink >/dev/null 2>&1; then
    FBINK_BIN="fbink"
elif [ -x /usr/bin/fbink ]; then
    FBINK_BIN="/usr/bin/fbink"
elif [ -x /mnt/us/extensions/fbink/bin/fbink ]; then
    FBINK_BIN="/mnt/us/extensions/fbink/bin/fbink"
elif [ -x /mnt/us/extensions/MRInstaller/bin/fbink ]; then
    FBINK_BIN="/mnt/us/extensions/MRInstaller/bin/fbink"
else
    FBINK_BIN="fbink"
fi

mkdir -p "$CRM_DOCS_DIR"
TODAY=$(date +%Y-%m-%d)
EPUB_PATH="$CRM_DOCS_DIR/CRM_Fechamento_${TODAY}.epub"

"$FBINK_BIN" -q -pm -y 12 "Conectando ao CRM e gerando relatorio de fechamento..."

HTTP_CODE=$(curl -s -w "%{http_code}" -m 25 "$API_BASE_URL/crm/latest.epub" -o "$EPUB_PATH.tmp")

if [ "$HTTP_CODE" = "200" ] && [ -s "$EPUB_PATH.tmp" ]; then
    mv "$EPUB_PATH.tmp" "$EPUB_PATH"
    find "$CRM_DOCS_DIR" -name "CRM_Fechamento_*.epub" -mtime +"${MAX_HISTORY_DAYS:-7}" -exec rm -f {} \; 2>/dev/null
    lipc-set-prop com.lab126.scanner startScan 1
    "$FBINK_BIN" -q -pm -y 14 "Sucesso! CRM_Fechamento_${TODAY}.epub disponivel na Biblioteca."
    sleep 3
else
    rm -f "$EPUB_PATH.tmp"
    "$FBINK_BIN" -q -pm -y 14 "Falha ao baixar fechamento (HTTP $HTTP_CODE). Verifique Wi-Fi."
    sleep 4
fi
