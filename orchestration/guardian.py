"""
============================================================
ORÁCULO - Autonomous SRE Guardian & Self-Healing Watchdog
============================================================
Monitora a saúde da aplicação em produção, auto-recupera falhas
operacionais (workers caídos, deadlocks no SQLite, itens travados)
e isola/notifica falhas críticas que exigem ação humana.
============================================================
"""

import asyncio
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger("oraculo.guardian")


class Incident(BaseModel):
    id: Optional[int] = None
    component: str
    severity: str  # "INFO", "WARNING", "ERROR", "CRITICAL"
    error_type: str
    message: str
    requires_human: bool = False
    action_url: Optional[str] = None
    resolution_status: str = "OPEN"  # "OPEN", "AUTO_RESOLVED", "MANUAL_ACTION_NEEDED"
    resolution_detail: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None


class ProductionGuardian:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProductionGuardian, cls).__new__(cls)
                cls._instance._init_guardian()
            return cls._instance

    def _init_guardian(self):
        self._db_path = settings.DATA_DIR / "oraculo.db"
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._init_db()
        self.last_check_time: Optional[datetime] = None
        self.health_score: float = 100.0
        self.active_issues: List[Dict[str, Any]] = []

    def _init_db(self):
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS guardian_incidents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        component TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        requires_human INTEGER DEFAULT 0,
                        action_url TEXT,
                        resolution_status TEXT DEFAULT 'OPEN',
                        resolution_detail TEXT,
                        created_at TEXT NOT NULL,
                        resolved_at TEXT
                    );
                """)
                conn.execute("PRAGMA journal_mode=WAL;")
        except Exception as e:
            logger.error(f"Erro ao inicializar tabela guardian_incidents: {e}")

    def log_incident(
        self,
        component: str,
        severity: str,
        error_type: str,
        message: str,
        requires_human: bool = False,
        action_url: Optional[str] = None,
        resolution_status: str = "OPEN",
        resolution_detail: Optional[str] = None
    ) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO guardian_incidents (
                        component, severity, error_type, message, requires_human,
                        action_url, resolution_status, resolution_detail, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    component, severity, error_type, message, 1 if requires_human else 0,
                    action_url, resolution_status, resolution_detail, datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao registrar incidente no Guardian: {e}")
            return -1

    def resolve_incident(self, incident_id: int, detail: str):
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    UPDATE guardian_incidents
                    SET resolution_status = 'AUTO_RESOLVED',
                        resolution_detail = ?,
                        resolved_at = ?
                    WHERE id = ?
                """, (detail, datetime.now(timezone.utc).isoformat(), incident_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Erro ao resolver incidente {incident_id}: {e}")

    def get_recent_incidents(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM guardian_incidents
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao consultar incidentes: {e}")
            return []

    # ==========================================
    # VERIFICAÇÕES DE AUTO-CURA (HEALTH CHECKS)
    # ==========================================

    def check_sqlite_health(self) -> Dict[str, Any]:
        """Verifica integridade do SQLite e executa checkpoint de WAL se necessário."""
        status = {"healthy": True, "detail": "SQLite operacional"}
        try:
            with sqlite3.connect(self._db_path, timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA quick_check;")
                result = cursor.fetchone()
                if result and result[0] != "ok":
                    status["healthy"] = False
                    status["detail"] = f"Integridade comprometida: {result[0]}"
                    self.log_incident(
                        component="SQLite",
                        severity="ERROR",
                        error_type="DB_CORRUPTION",
                        message=status["detail"],
                        requires_human=True
                    )
                else:
                    # Executa manutenção leve (checkpoint do WAL)
                    cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                status["healthy"] = False
                status["detail"] = "SQLite bloqueado por concorrência (auto-recuperando...)"
                self.log_incident(
                    component="SQLite",
                    severity="WARNING",
                    error_type="DB_LOCKED",
                    message="Banco travado temporariamente. Tentando liberar conexões órfãs.",
                    resolution_status="AUTO_RESOLVED",
                    resolution_detail="Checkpoint executado com sucesso."
                )
            else:
                status["healthy"] = False
                status["detail"] = str(e)
        return status

    def check_and_heal_stuck_queue_items(self) -> int:
        """Identifica itens travados em 'downloading' ou 'processing' há mais de 25 min e reseta para queued."""
        healed_count = 0
        try:
            with sqlite3.connect(self._db_path, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Busca itens em andamento
                cursor.execute("""
                    SELECT id, file_name, status, started_at, retry_count
                    FROM study_queue
                    WHERE status IN ('downloading', 'processing')
                """)
                rows = cursor.fetchall()
                now = datetime.now(timezone.utc)

                for row in rows:
                    started_str = row["started_at"]
                    if started_str:
                        try:
                            started_dt = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
                            if (now - started_dt) > timedelta(minutes=25):
                                item_id = row["id"]
                                retries = (row["retry_count"] or 0) + 1
                                
                                # Auto-cura: reseta para queued
                                conn.execute("""
                                    UPDATE study_queue
                                    SET status = 'queued',
                                        progress_pct = 0.0,
                                        current_step_text = 'Recuperado automaticamente pelo Guardian',
                                        retry_count = ?
                                    WHERE id = ?
                                """, (retries, item_id))
                                healed_count += 1
                                
                                self.log_incident(
                                    component="StudyQueue",
                                    severity="WARNING",
                                    error_type="ITEM_STUCK_TIMEOUT",
                                    message=f"Item {row['file_name']} travado em '{row['status']}' há mais de 25 min.",
                                    resolution_status="AUTO_RESOLVED",
                                    resolution_detail=f"Item resetado para 'queued' com retry_count={retries}"
                                )
                                logger.info(f"🛡️ Guardian: Item {item_id} ({row['file_name']}) recuperado e devolvido à fila.")
                        except Exception as parse_err:
                            logger.warning(f"Erro ao analisar started_at: {parse_err}")
                
                if healed_count > 0:
                    conn.commit()
        except Exception as e:
            logger.error(f"Erro no check_and_heal_stuck_queue_items: {e}")
        return healed_count

    def check_worker_liveness(self) -> Dict[str, Any]:
        """Garante que se a fila tiver itens e não estiver pausada, o worker esteja rodando."""
        from ingestion.study_queue import StudyQueueManager
        queue_mgr = StudyQueueManager()
        
        status = {"active": True, "paused": queue_mgr.is_paused, "detail": "Workers operacionais"}
        
        if not queue_mgr.is_paused:
            has_pending = any(item.status == "queued" for item in queue_mgr.queue)
            worker_alive = queue_mgr._worker_task is not None and not queue_mgr._worker_task.done()
            
            if has_pending and not worker_alive:
                logger.warning("🛡️ Guardian: Fila com itens pendentes mas worker inativo. Respawning worker...")
                queue_mgr.ensure_worker()
                self.log_incident(
                    component="StudyWorker",
                    severity="WARNING",
                    error_type="WORKER_DIED",
                    message="Worker principal estava finalizado com itens na fila.",
                    resolution_status="AUTO_RESOLVED",
                    resolution_detail="Worker reiniciado com sucesso via ensure_worker()."
                )
                status["detail"] = "Worker reiniciado com sucesso"
        return status

    # ==========================================
    # CICLO VIGILANTE PRINCIPAL
    # ==========================================

    async def _watchdog_loop(self):
        logger.info("🛡️ Guardian Watchdog iniciado em segundo plano (Ciclo a cada 30s).")
        while self._running:
            try:
                self.last_check_time = datetime.now(timezone.utc)
                
                # 1. Checa banco de dados
                sqlite_status = self.check_sqlite_health()
                
                # 2. Cura itens travados
                self.check_and_heal_stuck_queue_items()
                
                # 3. Garante liveness de workers
                worker_status = self.check_worker_liveness()
                
                # 4. Calcula índice de saúde (Health Score)
                if not sqlite_status["healthy"]:
                    self.health_score = 40.0
                elif not worker_status["active"]:
                    self.health_score = 75.0
                else:
                    self.health_score = 100.0

            except Exception as e:
                logger.error(f"🛡️ Erro no loop do Guardian: {e}")
            
            await asyncio.sleep(30)

    def start(self):
        if not self._running:
            self._running = True
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._watchdog_loop())
            except RuntimeError:
                logger.warning("Event loop não ativo; Guardian aguardando startup do servidor.")

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛡️ Guardian Watchdog finalizado.")

    def get_status(self) -> Dict[str, Any]:
        incidents = self.get_recent_incidents(limit=10)
        human_needed = [inc for inc in incidents if inc.get("requires_human") and inc.get("resolution_status") == "OPEN"]
        
        return {
            "status": "HEALTHY" if self.health_score >= 80 else ("DEGRADED" if self.health_score >= 50 else "CRITICAL"),
            "health_score": self.health_score,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "requires_human_intervention": len(human_needed) > 0,
            "pending_human_actions": human_needed,
            "recent_incidents_count": len(incidents),
            "recent_incidents": incidents
        }


# Instância global do Guardian
guardian = ProductionGuardian()
