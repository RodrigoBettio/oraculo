#!/bin/sh
# ==============================================================================
# Kindle Paperwhite 3 - Daemon Standby Ticker B3 & Sincronizador Silencioso CRM
# 5 Páginas x 6 Ativos = 30 Ativos Monitorados (FIIs, Ações, BDRs, Macro)
# ==============================================================================

EXT_DIR="/mnt/us/extensions/painel_b3_crm"
if [ -f "$EXT_DIR/env.conf" ]; then
    . "$EXT_DIR/env.conf"
fi

PID_FILE="/tmp/b3_ticker.pid"
echo $$ > "$PID_FILE"

# 1. Autodetecção do FBInk
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

# 2. Autodetecção do Dispositivo de Toque
if [ ! -e "$TOUCH_DEVICE" ]; then
    FOUND_DEV=$(grep -B 1 -E -i "touch|cyttsp|mxt|zforce" /proc/bus/input/devices 2>/dev/null | grep -o 'event[0-9]' | head -n 1)
    if [ -n "$FOUND_DEV" ] && [ -e "/dev/input/$FOUND_DEV" ]; then
        TOUCH_DEVICE="/dev/input/$FOUND_DEV"
    else
        TOUCH_DEVICE="/dev/input/event0"
    fi
fi

# 3. Gerenciamento de Energia e Iluminação
SAVED_BRIGHTNESS=$(lipc-get-prop com.lab126.powerd flIntensity 2>/dev/null || echo 10)
lipc-set-prop com.lab126.powerd preventScreenSaver 1
lipc-set-prop com.lab126.powerd flIntensity 0

# Pausa a interface nativa da Amazon para evitar colisão no framebuffer /dev/fb0
killall -STOP awesome 2>/dev/null || killall -STOP cvm 2>/dev/null

cleanup_and_exit() {
    killall -CONT awesome 2>/dev/null || killall -CONT cvm 2>/dev/null
    lipc-set-prop com.lab126.powerd flIntensity "$SAVED_BRIGHTNESS"
    lipc-set-prop com.lab126.powerd preventScreenSaver 0
    "$FBINK_BIN" -q -c -f
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup_and_exit INT TERM EXIT

# 4. Subprocesso Vigilante do Painel Touch (encerra imediatamente ao tocar)
(
    dd if="$TOUCH_DEVICE" bs=16 count=1 >/dev/null 2>&1
    kill -TERM $(cat "$PID_FILE" 2>/dev/null) 2>/dev/null
) &
WATCHER_PID=$!

CYCLE_COUNT=0
TODAY=$(date +%Y-%m-%d)

while [ -f "$PID_FILE" ]; do
    # --------------------------------------------------------------------------
    # Sincronização Matinal Silenciosa do Relatório de Fechamento de Vendas
    # --------------------------------------------------------------------------
    mkdir -p "$CRM_DOCS_DIR"
    EPUB_FILE="$CRM_DOCS_DIR/CRM_Fechamento_${TODAY}.epub"
    if [ ! -f "$EPUB_FILE" ]; then
        curl -s -m 15 "$API_BASE_URL/crm/latest.epub" -o "$EPUB_FILE.tmp"
        if [ -s "$EPUB_FILE.tmp" ]; then
            mv "$EPUB_FILE.tmp" "$EPUB_FILE"
            find "$CRM_DOCS_DIR" -name "CRM_Fechamento_*.epub" -mtime +"${MAX_HISTORY_DAYS:-7}" -exec rm -f {} \; 2>/dev/null
            lipc-set-prop com.lab126.scanner startScan 1
        else
            rm -f "$EPUB_FILE.tmp"
        fi
    fi

    # --------------------------------------------------------------------------
    # Verificação de Horário do Pregão (Economia de Bateria)
    # --------------------------------------------------------------------------
    DAY_OF_WEEK=$(date +%u) # 1=Segunda ... 7=Domingo
    HOUR_OF_DAY=$(date +%H) # 00..23

    if [ "$DAY_OF_WEEK" -ge 1 ] && [ "$DAY_OF_WEEK" -le 5 ] && [ "$HOUR_OF_DAY" -ge 10 ] && [ "$HOUR_OF_DAY" -lt 18 ]; then
        IS_MARKET_OPEN=1
    else
        IS_MARKET_OPEN=0
    fi

    # --------------------------------------------------------------------------
    # Download das 5 Imagens PNG (1072x1448) a cada N ciclos
    # --------------------------------------------------------------------------
    if [ $((CYCLE_COUNT % NET_REFRESH_CYCLES)) -eq 0 ]; then
        for PAGE in 1 2 3 4 5; do
            curl -s -m 12 "$API_BASE_URL/b3/ticker-page/${PAGE}.png" -o "/tmp/b3_page_${PAGE}.png.tmp"
            if [ -s "/tmp/b3_page_${PAGE}.png.tmp" ]; then
                mv "/tmp/b3_page_${PAGE}.png.tmp" "/tmp/b3_page_${PAGE}.png"
            fi
        done
    fi

    # --------------------------------------------------------------------------
    # Exibição no Painel E-Ink (30s por página)
    # --------------------------------------------------------------------------
    if [ "$IS_MARKET_OPEN" -eq 1 ]; then
        # Durante o pregão: alterna as 5 páginas a cada 30 segundos
        for PAGE in 1 2 3 4 5; do
            [ ! -f "$PID_FILE" ] && break

            if [ -s "/tmp/b3_page_${PAGE}.png" ]; then
                if [ "$PAGE" -eq 1 ]; then
                    "$FBINK_BIN" -q -c -f -g file="/tmp/b3_page_${PAGE}.png"
                else
                    "$FBINK_BIN" -q -g file="/tmp/b3_page_${PAGE}.png"
                fi
            else
                "$FBINK_BIN" -q -c -pm -y 15 "Aguardando conexao com o Servidor B3..."
            fi

            sleep "${PAGE_INTERVAL_SEC:-30}"
        done
    else
        # Fora do pregão: congela na Página 1 (FIIs) ou Página 5 (Macro) e dorme por 15 minutos
        if [ -s "/tmp/b3_page_1.png" ]; then
            "$FBINK_BIN" -q -c -f -g file="/tmp/b3_page_1.png"
        fi
        sleep 900
    fi

    CYCLE_COUNT=$((CYCLE_COUNT + 1))
done

kill -9 "$WATCHER_PID" 2>/dev/null
cleanup_and_exit
