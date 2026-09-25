#!/usr/bin/env python3
"""
Oráculo Zero-Touch Auto-Sync Daemon
Executa em background na máquina local e mantém as Skills do Antigravity
rigorosamente atualizadas com a VM a cada 5 minutos, sem nenhuma ação manual.
"""

import time
import sys
import logging
from pathlib import Path

# Configura encoding UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auto_sync_daemon")

from scripts.sync_skills_from_vm import sync_knowledge

def run_loop(interval_seconds: int = 300):
    logger.info(f"🚀 Oráculo Zero-Touch Auto-Sync iniciado (ciclo: {interval_seconds}s)")
    while True:
        try:
            logger.info("🔄 Verificando atualizações de conhecimento na VM...")
            sync_knowledge()
            logger.info(f"💤 Aguardando {interval_seconds}s até a próxima checagem...")
        except Exception as e:
            logger.warning(f"Erro transitório no auto-sync: {e}")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    run_loop(interval)
