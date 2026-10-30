#!/bin/sh
# ==============================================================================
# Oraculo Kindle Hub - Script de Autodiagnóstico e Validação de Hardware
# ==============================================================================

EXT_DIR="/mnt/us/extensions/painel_b3_crm"
if [ -f "$EXT_DIR/env.conf" ]; then
    . "$EXT_DIR/env.conf"
fi

# 1. Detecção do Binário FBInk
if command -v fbink >/dev/null 2>&1; then
    FBINK_BIN="fbink"
elif [ -x /usr/bin/fbink ]; then
    FBINK_BIN="/usr/bin/fbink"
elif [ -x /mnt/us/extensions/fbink/bin/fbink ]; then
    FBINK_BIN="/mnt/us/extensions/fbink/bin/fbink"
elif [ -x /mnt/us/extensions/MRInstaller/bin/fbink ]; then
    FBINK_BIN="/mnt/us/extensions/MRInstaller/bin/fbink"
else
    FBINK_BIN=""
fi

# 2. Detecção do Dispositivo de Toque
TOUCH_DEV_PATH="${TOUCH_DEVICE:-/dev/input/event0}"
if [ ! -e "$TOUCH_DEV_PATH" ]; then
    FOUND_DEV=$(grep -B 1 -E -i "touch|cyttsp|mxt|zforce" /proc/bus/input/devices 2>/dev/null | grep -o 'event[0-9]' | head -n 1)
    if [ -n "$FOUND_DEV" ] && [ -e "/dev/input/$FOUND_DEV" ]; then
        TOUCH_DEV_PATH="/dev/input/$FOUND_DEV"
    fi
fi

if [ -e "$TOUCH_DEV_PATH" ]; then
    TOUCH_STATUS="OK ($TOUCH_DEV_PATH)"
else
    TOUCH_STATUS="FALHA: Nao encontrado"
fi

# 3. Teste de Rede e API Oráculo
TARGET_URL="${API_BASE_URL:-http://34.46.39.111/api/v1/kindle}/manifest"
HTTP_RES=$(curl -s -m 8 -w "\n%{http_code}" "$TARGET_URL" 2>/dev/null)
HTTP_CODE=$(echo "$HTTP_RES" | tail -n 1)

if [ "$HTTP_CODE" = "200" ]; then
    API_STATUS="OK (HTTP 200 - Conectado)"
else
    API_STATUS="FALHA (HTTP $HTTP_CODE - Verifique Wi-Fi)"
fi

# 4. Exibição Visual
if [ -n "$FBINK_BIN" ]; then
    "$FBINK_BIN" -q -c -f
    "$FBINK_BIN" -q -pm -y 4  "========================================"
    "$FBINK_BIN" -q -pm -y 6  "   DIAGNOSTICO: PAINEL B3 & CRM HUB    "
    "$FBINK_BIN" -q -pm -y 8  "========================================"
    "$FBINK_BIN" -q -pm -y 11 "1. FBInk Driver : OK ($FBINK_BIN)"
    "$FBINK_BIN" -q -pm -y 13 "2. Painel Touch : $TOUCH_STATUS"
    "$FBINK_BIN" -q -pm -y 15 "3. API Oraculo  : $API_STATUS"
    "$FBINK_BIN" -q -pm -y 17 "4. Servidor     : ${API_BASE_URL}"
    "$FBINK_BIN" -q -pm -y 20 "========================================"
    "$FBINK_BIN" -q -pm -y 22 "Retornando ao menu em 8 segundos..."
else
    echo "FBInk nao encontrado no PATH."
fi

sleep 8
if [ -n "$FBINK_BIN" ]; then
    "$FBINK_BIN" -q -c -f
fi
exit 0
