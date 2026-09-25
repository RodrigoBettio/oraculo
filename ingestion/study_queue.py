import asyncio
import uuid
import logging
import threading
import sqlite3
import shutil
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from config import settings
from models.agent import AgentProfile, AgentStatus
from models.knowledge import ProcessingTier
from ingestion.telegram_client import TelegramManager
from ingestion.video_processor import VideoProcessor
from utils.token_tracker import record_tokens

logger = logging.getLogger("oraculo.study_queue")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


class QueueItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str
    agent_name: str = "Especialista"
    source_type: str = "telegram"  # "telegram" ou "google_drive"
    drive_file_id: Optional[str] = None
    group_id: int = 0
    group_name: str
    theme_name: Optional[str] = None
    support_files: List[Dict[str, Any]] = Field(default_factory=list)
    message_id: int = 0
    file_name: str
    tier: str = "audio_only"
    status: str = "queued"  # queued, downloading, processing, completed, error
    progress_pct: float = 0.0
    current_step_text: str = "Na fila de espera"
    error_message: Optional[str] = None
    retry_count: int = 0
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class StudyQueueManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StudyQueueManager, cls).__new__(cls)
            cls._instance._init_queue()
        return cls._instance

    def _init_queue(self):
        self.queue: List[QueueItem] = []
        self.active_items: Dict[str, QueueItem] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._agent_file_lock = threading.RLock()
        self._download_tg_semaphore = asyncio.Semaphore(getattr(settings, "MAX_TELEGRAM_WORKERS", 4))
        self._download_drive_semaphore = asyncio.Semaphore(getattr(settings, "MAX_DRIVE_WORKERS", 16))
        self._download_semaphore = self._download_tg_semaphore  # retrocompatibilidade
        self._analysis_semaphore = asyncio.Semaphore(16)
        self.is_paused: bool = False  # Ativo por padrão para iniciar processamento imediato ao enfileirar
        
        self._db_lock = threading.Lock()
        self._db_path = settings.DATA_DIR / 'oraculo.db'
        self._init_db()
        self._db_load_pending()

    def pause(self):
        """Pausa imediatamente o consumo de novos itens na fila."""
        self.is_paused = True
        logger.info("⏸️ Fila de estudos pausada com sucesso.")

    def resume(self):
        """Retoma o processamento da fila de estudos."""
        self.is_paused = False
        logger.info("▶️ Fila de estudos retomada com sucesso.")
        self.ensure_worker()
        
        self._reconcile_idle_agents()

    def _init_db(self):
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS study_queue (
                        id TEXT PRIMARY KEY,
                        agent_id TEXT,
                        agent_name TEXT,
                        source_type TEXT,
                        drive_file_id TEXT,
                        group_id INTEGER,
                        group_name TEXT,
                        theme_name TEXT,
                        support_files TEXT,
                        message_id INTEGER,
                        file_name TEXT,
                        tier TEXT,
                        status TEXT,
                        progress_pct REAL,
                        current_step_text TEXT,
                        error_message TEXT,
                        enqueued_at TEXT,
                        started_at TEXT,
                        completed_at TEXT
                    )
                ''')
                # Migração idempotente se tabela já existia sem as novas colunas
                cursor = conn.execute("PRAGMA table_info(study_queue)")
                cols = {row[1] for row in cursor.fetchall()}
                if "theme_name" not in cols:
                    conn.execute("ALTER TABLE study_queue ADD COLUMN theme_name TEXT")
                if "support_files" not in cols:
                    conn.execute("ALTER TABLE study_queue ADD COLUMN support_files TEXT")
                if "retry_count" not in cols:
                    conn.execute("ALTER TABLE study_queue ADD COLUMN retry_count INTEGER DEFAULT 0")

    def _db_insert(self, item: QueueItem):
        import json
        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT INTO study_queue (
                        id, agent_id, agent_name, source_type, drive_file_id,
                        group_id, group_name, theme_name, support_files, message_id, file_name, tier,
                        status, progress_pct, current_step_text, error_message, retry_count,
                        enqueued_at, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.id, item.agent_id, item.agent_name, item.source_type, item.drive_file_id,
                    item.group_id, item.group_name, item.theme_name, json.dumps(item.support_files or []),
                    item.message_id, item.file_name, item.tier,
                    item.status, item.progress_pct, item.current_step_text, item.error_message, item.retry_count,
                    item.enqueued_at.isoformat() if item.enqueued_at else None,
                    item.started_at.isoformat() if item.started_at else None,
                    item.completed_at.isoformat() if item.completed_at else None
                ))

    def _db_update(self, item: QueueItem):
        import json
        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    UPDATE study_queue SET
                        agent_id=?, agent_name=?, source_type=?, drive_file_id=?,
                        group_id=?, group_name=?, theme_name=?, support_files=?, message_id=?, file_name=?, tier=?,
                        status=?, progress_pct=?, current_step_text=?, error_message=?, retry_count=?,
                        enqueued_at=?, started_at=?, completed_at=?
                    WHERE id=?
                ''', (
                    item.agent_id, item.agent_name, item.source_type, item.drive_file_id,
                    item.group_id, item.group_name, item.theme_name, json.dumps(item.support_files or []),
                    item.message_id, item.file_name, item.tier,
                    item.status, item.progress_pct, item.current_step_text, item.error_message, item.retry_count,
                    item.enqueued_at.isoformat() if item.enqueued_at else None,
                    item.started_at.isoformat() if item.started_at else None,
                    item.completed_at.isoformat() if item.completed_at else None,
                    item.id
                ))

    def _db_get_all(self) -> List[QueueItem]:
        import json
        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM study_queue")
                rows = cursor.fetchall()
                
        items = []
        for row in rows:
            data = dict(row)
            data['retry_count'] = data.get('retry_count') or 0
            for field in ['enqueued_at', 'started_at', 'completed_at']:
                if data.get(field):
                    data[field] = datetime.fromisoformat(data[field])
            if isinstance(data.get('support_files'), str):
                try:
                    data['support_files'] = json.loads(data['support_files'])
                except Exception:
                    data['support_files'] = []
            elif not data.get('support_files'):
                data['support_files'] = []
            items.append(QueueItem(**data))
        return items

    def _db_load_pending(self):
        items = self._db_get_all()
        for item in items:
            if item.status in ['queued', 'downloading']:
                item.status = 'queued'
                item.current_step_text = 'Na fila de estudos'
                self.queue.append(item)
                self._db_update(item)

    @property
    def max_telegram_workers(self) -> int:
        return getattr(settings, "MAX_TELEGRAM_WORKERS", 4)

    @property
    def max_drive_workers(self) -> int:
        return getattr(settings, "MAX_DRIVE_WORKERS", 16)

    @property
    def max_workers(self) -> int:
        """Calcula o teto total de workers em paralelo combinando as fontes ativas."""
        return self.max_telegram_workers + self.max_drive_workers

    @max_workers.setter
    def max_workers(self, value: int):
        pass  # Permite compatibilidade caso algum método tente atribuir

    @property
    def active_item(self) -> Optional[QueueItem]:
        """Compatibilidade retroativa: retorna o primeiro item ativo."""
        if self.active_items:
            return next(iter(self.active_items.values()))
        return None

    def get_agent_profile(self, agent_id: str) -> Optional[AgentProfile]:
        agent_file = settings.AGENTS_DIR / f"{agent_id}.json"
        if not agent_file.exists():
            return None
        import json
        try:
            with open(agent_file, "r", encoding="utf-8") as f:
                return AgentProfile(**json.load(f))
        except Exception:
            return None

    def save_agent(self, agent: AgentProfile):
        agent_file = settings.AGENTS_DIR / f"{agent.id}.json"
        with self._agent_file_lock:
            with open(agent_file, "w", encoding="utf-8") as f:
                f.write(agent.model_dump_json(indent=2))

    async def enqueue(
        self,
        agent_id: str,
        group_id: int,
        group_name: str,
        message_id: int,
        file_name: str,
        tier: str = "audio_only",
        start_worker: bool = True
    ) -> QueueItem:
        """Adiciona uma aula na fila de estudos (isolada por especialista)."""
        agent = self.get_agent_profile(agent_id)
        agent_name = agent.name if agent else "Especialista"

        # Evita duplicar se já estiver na fila ou rodando para ESTE especialista
        for item in self.queue:
            if item.agent_id == agent_id and item.group_id == group_id and item.message_id == message_id and item.status in ["queued", "downloading", "processing"]:
                return item

        item = QueueItem(
            agent_id=agent_id,
            agent_name=agent_name,
            group_id=group_id,
            group_name=group_name,
            message_id=message_id,
            file_name=file_name,
            tier=tier or "audio_only",
            status="queued",
            current_step_text="Na fila de estudos"
        )
        self.queue.append(item)
        self._db_insert(item)
        if start_worker:
            self.ensure_worker()
        return item

    async def enqueue_group(
        self,
        agent_id: str,
        group_id: int,
        group_name: str,
        tier: str = "audio_only",
        only_pending: bool = True,
        start_worker: bool = True
    ) -> List[QueueItem]:
        """Adiciona todas as aulas (ou apenas as pendentes deste especialista) na fila de estudos."""
        tg = TelegramManager()
        videos = await tg.list_videos_in_group(group_id, limit=200)

        if only_pending:
            agent = self.get_agent_profile(agent_id)
            agent_studied_ids = set()
            if agent and agent.sources:
                gn_clean = group_name.lower().strip()
                for src in agent.sources:
                    s_name = (src.group_name or "").lower().strip()
                    if s_name and (s_name in gn_clean or gn_clean in s_name):
                        for les in (src.lessons or []):
                            raw_lid = getattr(les, "lesson_id", None) if hasattr(les, "lesson_id") else (les.get("lesson_id") if isinstance(les, dict) else "")
                            lid = str(raw_lid or "").replace("video_", "").replace("aula_", "").strip()
                            if lid:
                                agent_studied_ids.add(lid)
            videos = [v for v in videos if str(v.get("message_id", "")).strip() not in agent_studied_ids]

        # Inverte para estudar na ordem cronológica (aulas mais antigas primeiro)
        videos.reverse()

        enqueued = []
        for v in videos:
            msg_id = v.get("message_id")
            f_name = v.get("file_name") or f"aula_{msg_id}.mp4"
            item = await self.enqueue(
                agent_id=agent_id,
                group_id=group_id,
                group_name=group_name,
                message_id=msg_id,
                file_name=f_name,
                tier=tier,
                start_worker=start_worker
            )
            enqueued.append(item)

        if start_worker:
            self.ensure_worker()

        return enqueued

    async def enqueue_multiple_groups(
        self,
        agent_id: str,
        groups: List[Dict[str, Any]],
        tier: str = "audio_only",
        only_pending: bool = True,
        start_worker: bool = True
    ) -> List[QueueItem]:
        """Adiciona todas as aulas pendentes de múltiplos canais na fila sequencial de estudos."""
        all_enqueued = []
        for g in groups:
            gid = g.get("id")
            gtitle = g.get("title", f"Canal {gid}")
            enqueued = await self.enqueue_group(
                agent_id=agent_id,
                group_id=gid,
                group_name=gtitle,
                tier=tier,
                only_pending=only_pending,
                start_worker=start_worker
            )
            all_enqueued.extend(enqueued)
        if start_worker:
            self.ensure_worker()
        return all_enqueued

    async def enqueue_drive_file(
        self,
        agent_id: str,
        drive_file_id: str,
        file_name: str,
        course_name: str,
        theme_name: Optional[str] = None,
        support_files: Optional[List[Dict[str, Any]]] = None,
        tier: str = "audio_only",
        start_worker: bool = True
    ) -> QueueItem:
        """Adiciona uma aula do Google Drive na fila de estudos com contexto de tema e arquivos de apoio."""
        agent = self.get_agent_profile(agent_id)
        agent_name = agent.name if agent else "Especialista"

        # Evita duplicar se já estiver na fila ou rodando para ESTE especialista
        for item in self.queue:
            if item.agent_id == agent_id and item.drive_file_id == drive_file_id and item.status in ["queued", "downloading", "processing"]:
                return item

        item = QueueItem(
            agent_id=agent_id,
            agent_name=agent_name,
            source_type="google_drive",
            drive_file_id=drive_file_id,
            group_name=course_name,
            theme_name=theme_name,
            support_files=support_files or [],
            file_name=file_name,
            tier=tier
        )

        async with self._lock:
            self.queue.append(item)
            self._db_insert(item)

        if start_worker:
            self.ensure_worker()

        return item

    async def enqueue_drive_theme(
        self,
        agent_id: str,
        folder_id: str,
        course_name: str,
        theme_name: str,
        support_files: Optional[List[Dict[str, Any]]] = None,
        tier: str = "audio_only",
        only_pending: bool = True,
        start_worker: bool = True
    ) -> List[QueueItem]:
        """Adiciona todas as aulas de um tema/módulo específico do Drive na fila."""
        from ingestion.drive_client import GoogleDriveManager
        dm = GoogleDriveManager()
        contents = dm.list_folder_contents(folder_id, course_name=course_name, theme_name=theme_name)
        videos = contents["videos"]
        s_files = support_files or contents["support_files"]

        if only_pending:
            videos = [v for v in videos if not v.get("is_studied")]

        enqueued = []
        for v in videos:
            item = await self.enqueue_drive_file(
                agent_id=agent_id,
                drive_file_id=v["id"],
                file_name=v["file_name"],
                course_name=course_name,
                theme_name=theme_name,
                support_files=s_files,
                tier=tier,
                start_worker=False
            )
            enqueued.append(item)

        # Se não há vídeos neste módulo/tema, mas há arquivos de apoio (ex: PDFs/Ebooks)
        if not videos and s_files:
            for s in s_files:
                if only_pending and s.get("is_studied"):
                    continue
                item = await self.enqueue_drive_file(
                    agent_id=agent_id,
                    drive_file_id=s["id"],
                    file_name=s.get("file_name", s.get("name")),
                    course_name=course_name,
                    theme_name=theme_name,
                    support_files=[],
                    tier=tier,
                    start_worker=False
                )
                enqueued.append(item)

        if start_worker and enqueued:
            self.ensure_worker()

        return enqueued

    async def enqueue_drive_course(
        self,
        agent_id: str,
        folder_id: str,
        course_name: str,
        tier: str = "audio_only",
        only_pending: bool = True,
        start_worker: bool = True
    ) -> List[QueueItem]:
        """Adiciona todas as aulas de um curso do Drive na fila, preservando a divisão por temas e arquivos de apoio."""
        from ingestion.drive_client import GoogleDriveManager
        dm = GoogleDriveManager()
        course_node = dm._inspect_course_folder(folder_id, course_name)

        enqueued = []
        # 1. Se o curso possui temas/módulos, enfileira respeitando cada tema e seus respectivos arquivos de apoio
        for theme in course_node.get("themes", []):
            t_name = theme.get("name")
            t_files = theme.get("support_files", [])
            t_videos = theme.get("videos", [])
            if only_pending:
                t_videos = [v for v in t_videos if not v.get("is_studied")]

            for v in t_videos:
                item = await self.enqueue_drive_file(
                    agent_id=agent_id,
                    drive_file_id=v["id"],
                    file_name=v["file_name"],
                    course_name=course_name,
                    theme_name=t_name,
                    support_files=t_files,
                    tier=tier,
                    start_worker=False
                )
                enqueued.append(item)

            # Se o módulo/tema não possui vídeos, mas possui arquivos de apoio (ex: PDFs/Ebooks)
            if not t_videos and t_files:
                for s in t_files:
                    if only_pending and s.get("is_studied"):
                        continue
                    item = await self.enqueue_drive_file(
                        agent_id=agent_id,
                        drive_file_id=s["id"],
                        file_name=s.get("file_name", s.get("name")),
                        course_name=course_name,
                        theme_name=t_name,
                        support_files=[],
                        tier=tier,
                        start_worker=False
                    )
                    enqueued.append(item)

        # 2. Aulas diretas no curso (fora de módulos/temas específicos)
        direct_videos = course_node.get("direct_videos", [])
        direct_files = course_node.get("direct_support_files", [])
        if only_pending:
            direct_videos = [v for v in direct_videos if not v.get("is_studied")]

        for v in direct_videos:
            item = await self.enqueue_drive_file(
                agent_id=agent_id,
                drive_file_id=v["id"],
                file_name=v["file_name"],
                course_name=course_name,
                theme_name=None,
                support_files=direct_files,
                tier=tier,
                start_worker=False
            )
            enqueued.append(item)

        # Se não há vídeos diretos, mas há arquivos de apoio diretos (ex: PDFs/Ebooks avulsos)
        if not direct_videos and direct_files:
            for s in direct_files:
                if only_pending and s.get("is_studied"):
                    continue
                item = await self.enqueue_drive_file(
                    agent_id=agent_id,
                    drive_file_id=s["id"],
                    file_name=s.get("file_name", s.get("name")),
                    course_name=course_name,
                    theme_name=None,
                    support_files=[],
                    tier=tier,
                    start_worker=False
                )
                enqueued.append(item)

        if start_worker and enqueued:
            self.ensure_worker()

        return enqueued

    def remove(self, item_id: str) -> bool:
        """Remove um item da fila ou do histórico (qualquer status)."""
        removed = False
        for i, item in enumerate(self.queue):
            if item.id == item_id:
                self.queue.pop(i)
                removed = True
                break
        if item_id in self.active_items:
            del self.active_items[item_id]
            removed = True

        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("DELETE FROM study_queue WHERE id=?", (item_id,))
                if cursor.rowcount > 0:
                    removed = True
        return removed

    def retry_item(self, item_id: str) -> Optional[QueueItem]:
        """Reenfileira um item que estava com erro ou concluído para novo processamento."""
        all_items = self._db_get_all()
        target = None
        for it in all_items:
            if it.id == item_id:
                target = it
                break

        if not target:
            return None

        target.status = "queued"
        target.error_message = None
        target.progress_pct = 0.0
        target.current_step_text = "Reenfileirado pelo usuário"
        target.retry_count = getattr(target, "retry_count", 0) + 1
        target.started_at = None
        target.completed_at = None

        self._db_update(target)

        # Adiciona à fila em memória se não estiver
        in_memory = False
        for it in self.queue:
            if it.id == target.id:
                it.status = "queued"
                it.error_message = None
                it.progress_pct = 0.0
                it.current_step_text = target.current_step_text
                in_memory = True
                break
        if not in_memory:
            self.queue.append(target)

        self.ensure_worker()
        return target

    def retry_all_errors(self) -> int:
        """Reenfileira todos os itens com status 'error' de uma só vez."""
        all_items = self._db_get_all()
        retried = 0
        for it in all_items:
            if it.status == "error":
                self.retry_item(it.id)
                retried += 1
        return retried

    def clear_finished(self):
        """Remove itens completados ou com erro da lista."""
        items_to_remove = [item for item in self.queue if item.status not in ["queued", "downloading", "processing"]]
        self.queue = [item for item in self.queue if item.status in ["queued", "downloading", "processing"]]
        with self._db_lock:
            with sqlite3.connect(self._db_path) as conn:
                for item in items_to_remove:
                    conn.execute("DELETE FROM study_queue WHERE id=?", (item.id,))

    def interleave_queued_items(self):
        """Reordena os itens com status 'queued' alternando entre especialistas (Round-Robin)."""
        active_and_done = [item for item in self.queue if item.status != "queued"]
        queued = [item for item in self.queue if item.status == "queued"]

        from collections import defaultdict
        by_agent = defaultdict(list)
        for it in queued:
            by_agent[it.agent_id].append(it)

        interleaved = []
        while any(by_agent.values()):
            for aid in list(by_agent.keys()):
                if by_agent[aid]:
                    interleaved.append(by_agent[aid].pop(0))

        self.queue = active_and_done + interleaved

    def _reconcile_idle_agents(self):
        """Garante que nenhum especialista permaneça com status 'estudando' se não houver tarefas ativas para ele."""
        import json
        with self._agent_file_lock:
            active_agent_ids = {it.agent_id for it in self.active_items.values()}
            for f in settings.AGENTS_DIR.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    aid = data.get("id")
                    if data.get("status") == "estudando" and aid not in active_agent_ids:
                        data["status"] = "ativo"
                        data["current_task"] = None
                        with open(f, "w", encoding="utf-8") as fp:
                            json.dump(data, fp, indent=2)
                except Exception:
                    pass

    def get_status(self) -> Dict[str, Any]:
        """Retorna o estado atual da fila de estudos, histórico consolidado e workers paralelos."""
        all_db_items = self._db_get_all()
        active_list = [item.model_dump() for item in self.active_items.values()]
        active_ids = set(self.active_items.keys())

        queued_items = []
        error_items = []
        completed_items = []

        for item in all_db_items:
            if item.id in active_ids:
                continue
            dump = item.model_dump()
            if item.status in ["queued", "downloading"]:
                queued_items.append(dump)
            elif item.status == "error":
                error_items.append(dump)
            elif item.status == "completed":
                completed_items.append(dump)

        # Ordenações adequadas
        completed_items.sort(key=lambda x: str(x.get("completed_at") or ""), reverse=True)
        error_items.sort(key=lambda x: str(x.get("enqueued_at") or ""), reverse=True)

        all_items = active_list + error_items + queued_items + completed_items

        session_file = settings.DATA_DIR / "last_study_session.json"
        has_saved_session = session_file.exists()
        can_resume = (len(error_items) > 0) or (len(queued_items) > 0 and len(self.active_items) == 0) or (has_saved_session and len(self.active_items) == 0 and len(queued_items) == 0)
        pending_count = len(queued_items) + len(self.active_items)
        workers_count = max(1, self.max_workers)
        # Em média 40s por aula com áudio e tópicos estruturados divididos pelos workers simultâneos
        estimated_seconds = int((pending_count * 40) / workers_count) if pending_count > 0 else 0
        if pending_count == 0:
            estimated_time_text = "Concluído" if len(completed_items) > 0 else "0m"
        else:
            hours = estimated_seconds // 3600
            minutes = (estimated_seconds % 3600) // 60
            if hours > 0:
                estimated_time_text = f"~{hours}h {minutes:02d}m"
            else:
                estimated_time_text = f"~{max(1, minutes)}m"

        try:
            from utils.token_tracker import is_budget_exceeded
            safety_paused = is_budget_exceeded()
        except Exception:
            safety_paused = False

        return {
            "is_busy": len(self.active_items) > 0 and not getattr(self, "is_paused", False),
            "is_paused": getattr(self, "is_paused", False),
            "active_count": len(self.active_items) if not getattr(self, "is_paused", False) else 0,
            "max_workers": self.max_workers,
            "max_telegram_workers": self.max_telegram_workers,
            "max_drive_workers": self.max_drive_workers,
            "active_items": active_list,
            "active_item": active_list[0] if active_list else None,
            "queue_count": len(queued_items),
            "queued_items": queued_items,
            "completed_count": len(completed_items),
            "completed_items": completed_items[:50],
            "error_count": len(error_items),
            "error_items": error_items,
            "all_items": all_items[:150],
            "total_items": len(all_db_items),
            "pending_count": pending_count,
            "estimated_seconds": estimated_seconds,
            "estimated_time_text": estimated_time_text,
            "can_resume": can_resume,
            "interrupted_count": len(error_items),
            "safety_paused": safety_paused
        }


    def ensure_worker(self):
        """Garante que a rotina consumidora da fila está ativa."""
        try:
            if self._worker_task is None or self._worker_task.done():
                logger.info("🚀 Iniciando worker loop de processamento da fila de estudos...")
                self._worker_task = asyncio.create_task(self._process_queue_loop())
                logger.info(f"✅ Worker task criada: {self._worker_task}")
            else:
                logger.debug(f"Worker loop já ativo: {self._worker_task}")
        except RuntimeError as e:
            # Pode ocorrer se não houver event loop rodando
            logger.error(f"❌ Erro ao criar worker task (sem event loop?): {e}")
            import traceback
            traceback.print_exc()

    async def _process_queue_loop(self):
        """Loop contínuo que distribui aulas em paralelo entre múltiplos workers e chaves."""
        logger.info(f"📚 Worker loop iniciado! Max workers: {self.max_workers}, Itens na fila: {len(self.queue)}")
        keys = settings.GEMINI_API_KEYS or [settings.GEMINI_API_KEY]
        logger.info(f"🔑 Pool de chaves: {len(keys)} chaves disponíveis")
        worker_counter = 0

        async def run_worker(item: QueueItem, worker_id: int):
            self.active_items[item.id] = item
            assigned_key = keys[worker_id % len(keys)] if keys else None
            key_label = f"Key#{(worker_id % len(keys)) + 1}" if keys else "NoKey"
            logger.info(f"⚙️ Worker #{worker_id} ({key_label}) processando: {item.file_name} para {item.agent_name}")
            try:
                await self._process_single_item(item, api_key=assigned_key)
                logger.info(f"✅ Worker #{worker_id} concluiu: {item.file_name}")
            except Exception as e:
                logger.error(f"❌ Worker #{worker_id} falhou em {item.file_name}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.active_items.pop(item.id, None)

        try:
            while True:
                # Verifica se a fila foi pausada pelo usuário
                if getattr(self, "is_paused", False):
                    await asyncio.sleep(2)
                    continue

                # Verifica trava de segurança de tokens antes de despachar novos itens
                try:
                    from utils.token_tracker import is_budget_exceeded
                    if is_budget_exceeded():
                        logger.warning("🛡️ Trava de segurança de tokens ATIVA: Teto diário atingido. Estudos pausados para evitar custos indesejados.")
                        await asyncio.sleep(5)
                        continue
                except Exception:
                    pass

                # Pega itens enfileirados que ainda não estão ativos
                queued_items = [it for it in self.queue if it.status == "queued" and it.id not in self.active_items]

                if not queued_items and not self.active_items:
                    logger.info("📭 Fila vazia e nenhum worker ativo. Worker loop encerrando.")
                    self._reconcile_idle_agents()
                    break


                active_tg = sum(1 for it in self.active_items.values() if getattr(it, "source_type", "telegram") == "telegram")
                active_drive = sum(1 for it in self.active_items.values() if getattr(it, "source_type", "telegram") == "google_drive")

                avail_tg = max(0, self.max_telegram_workers - active_tg)
                avail_drive = max(0, self.max_drive_workers - active_drive)

                if (avail_tg > 0 or avail_drive > 0) and queued_items:
                    from collections import Counter
                    active_counts = Counter(it.agent_id for it in self.active_items.values())

                    # Agrupa itens pendentes por especialista
                    agent_queues = {}
                    for it in queued_items:
                        agent_queues.setdefault(it.agent_id, []).append(it)

                    to_process = []
                    tg_slots_left = avail_tg
                    drive_slots_left = avail_drive

                    while (tg_slots_left > 0 or drive_slots_left > 0) and any(agent_queues.values()):
                        sorted_agents = sorted(
                            [aid for aid, q in agent_queues.items() if q],
                            key=lambda aid: active_counts[aid]
                        )
                        if not sorted_agents:
                            break
                        progress_made = False
                        for aid in sorted_agents:
                            queue_for_agent = agent_queues[aid]
                            for i, candidate in enumerate(queue_for_agent):
                                is_drive = (getattr(candidate, "source_type", "telegram") == "google_drive")
                                if is_drive and drive_slots_left > 0:
                                    item = queue_for_agent.pop(i)
                                    to_process.append(item)
                                    drive_slots_left -= 1
                                    active_counts[aid] += 1
                                    progress_made = True
                                    break
                                elif not is_drive and tg_slots_left > 0:
                                    item = queue_for_agent.pop(i)
                                    to_process.append(item)
                                    tg_slots_left -= 1
                                    active_counts[aid] += 1
                                    progress_made = True
                                    break
                        if not progress_made:
                            break

                    if to_process:
                        logger.info(f"📤 Despachando {len(to_process)} aulas (Telegram: {avail_tg - tg_slots_left}/{self.max_telegram_workers}, Drive: {avail_drive - drive_slots_left}/{self.max_drive_workers})")
                        for item in to_process:
                            item.status = "downloading"
                            item.current_step_text = "Iniciando download..."
                            self._db_update(item)
                            self.active_items[item.id] = item
                            asyncio.create_task(run_worker(item, worker_counter))
                            worker_counter += 1

                await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"💥 ERRO FATAL no worker loop: {e}")
            import traceback
            traceback.print_exc()

    async def _process_single_item(self, item: QueueItem, api_key: Optional[str] = None):
        """Processa o download, extração, análise e registro de uma aula."""
        item.started_at = datetime.now(timezone.utc)
        
        with self._agent_file_lock:
            agent = self.get_agent_profile(item.agent_id)
            if agent:
                agent.status = AgentStatus.STUDYING
                agent.current_task = f"Estudando '{item.file_name}' ({item.group_name})"
                self.save_agent(agent)

        try:
            # 1. Download do vídeo com telemetria detalhada em MB
            item.status = "downloading"
            item.current_step_text = "Conectando ao Telegram..."
            item.progress_pct = 5.0
            self._db_update(item)

            def download_progress(current, total):
                if total > 0:
                    pct = min(45.0, 5.0 + (current / total) * 40.0)
                    item.progress_pct = round(pct, 1)
                    curr_mb = current / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    item.current_step_text = f"Baixando ({curr_mb:.1f} MB / {tot_mb:.1f} MB)..."

            if getattr(item, "source_type", "telegram") == "google_drive":
                item.current_step_text = "Conectando ao Google Drive..."
                self._db_update(item)
                from ingestion.drive_client import GoogleDriveManager
                dm = GoogleDriveManager()
                course_video_dir = settings.VIDEOS_DIR / item.group_name
                course_video_dir.mkdir(parents=True, exist_ok=True)
                target_file_path = course_video_dir / item.file_name

                async with self._download_drive_semaphore:
                    video_path = await asyncio.to_thread(
                        dm.download_file,
                        file_id=item.drive_file_id,
                        destination_path=target_file_path,
                        progress_callback=download_progress
                    )
            else:
                tg = TelegramManager()
                group_video_dir = settings.VIDEOS_DIR / item.group_name
                async with self._download_tg_semaphore:
                    video_path = await tg.download_video(
                        group_id=item.group_id,
                        message_id=item.message_id,
                        output_dir=group_video_dir,
                        progress_callback=download_progress
                    )

            item.progress_pct = 50.0
            item.status = "processing"
            is_pdf = item.file_name.lower().endswith(".pdf")
            if is_pdf:
                item.current_step_text = "Analisando material PDF com OCR Multimodal Gemini..."
            else:
                tier_label = "Modo Econômico (Áudio)" if item.tier == "audio_only" else "Modo Profundo (OCR)"
                item.current_step_text = f"Analisando aula com Gemini 3.6 Flash ({tier_label})..."
            self._db_update(item)

            # 2. Processamento do Vídeo ou PDF com chave dedicada do pool e semáforo para evitar 503
            processor = VideoProcessor(api_key=api_key)
            video_id = Path(item.file_name).stem
            tier_enum = ProcessingTier.AUDIO_ONLY if item.tier == "audio_only" else ProcessingTier.MULTIMODAL_OCR

            curation_result = None
            async with self._analysis_semaphore:
                if is_pdf:
                    doc, curation_result = await asyncio.to_thread(
                        processor.process_pdf,
                        pdf_path=video_path,
                        group_name=item.group_name,
                        pdf_id=video_id,
                        telegram_message_id=item.message_id or 0,
                        theme_name=item.theme_name
                    )
                else:
                    doc = await asyncio.to_thread(
                        processor.process_video,
                        video_path=video_path,
                        group_name=item.group_name,
                        telegram_message_id=item.message_id or 0,
                        tier=tier_enum,
                        video_id=video_id,
                        theme_name=item.theme_name,
                        companion_files=item.support_files
                    )
                import inspect
                if inspect.iscoroutine(doc):
                    doc = await doc

            # Curadoria inteligente de Cofre para PDFs
            if is_pdf and curation_result:
                if curation_result.get("is_valuable_for_vault"):
                    try:
                        from models.project import DocumentArtifact, DocumentType
                        from orchestration.project_store import ProjectStore
                        
                        # Salva cópia permanente do PDF no repositório do cofre
                        vault_dir = settings.DATA_DIR / "vault_documents"
                        vault_dir.mkdir(parents=True, exist_ok=True)
                        perm_pdf = vault_dir / f"{video_id}_{Path(video_path).name}"
                        shutil.copy2(video_path, perm_pdf)

                        cat = curation_result.get("vault_category", "Padrões & Arquitetura")
                        artifact = DocumentArtifact(
                            project_id="knowledge_vault",
                            created_by_agent_id=item.agent_id,
                            created_by_agent_name=item.agent_name,
                            title=f"📖 {doc.title} ({cat})",
                            content=doc.full_markdown,
                            doc_type=DocumentType.REFERENCE
                        )
                        ProjectStore().save_document(artifact)
                        logger.info(f"💎 Material PDF '{item.file_name}' classificado como PERMANENTE e arquivado no Cofre!")
                    except Exception as ve:
                        logger.warning(f"Erro ao salvar PDF no Cofre de Documentos: {ve}")
                else:
                    logger.info(f"🍃 Material PDF '{item.file_name}' classificado como EFÊMERO (resumo absorvido na mente do agente, arquivo bruto descartado).")

            item.progress_pct = 90.0
            self._db_update(item)

            # 3. Atualiza o perfil e a senioridade do agente (com lock para evitar race condition)
            with self._agent_file_lock:
                current_agent = self.get_agent_profile(item.agent_id)
                if current_agent:
                    duration_hours = round(doc.duration_seconds / 3600.0, 2)
                    comp_names = [cf.get("name") or cf.get("file_name") or str(cf) for cf in (item.support_files or [])]
                    current_agent.add_studied_content(
                        group_name=item.group_name,
                        hours=duration_hours,
                        topics=doc.topics,
                        lesson_id=video_id,
                        lesson_title=doc.title,
                        duration_seconds=doc.duration_seconds,
                        theme_name=item.theme_name,
                        companion_files=comp_names
                    )
                    has_other_active = any(
                        other.agent_id == item.agent_id and other.id != item.id 
                        for other in self.active_items.values()
                    )
                    if not has_other_active:
                        current_agent.status = AgentStatus.ACTIVE
                        current_agent.current_task = None
                    self.save_agent(current_agent)

                    # Recompilação contínua de SKILL.md enriquecido
                    try:
                        from web.app import compile_agent_rich_skill
                        compiled_md = compile_agent_rich_skill(item.agent_id)
                        if compiled_md:
                            skill_file = settings.DATA_DIR / "skills" / item.agent_id / "SKILL.md"
                            skill_file.parent.mkdir(parents=True, exist_ok=True)
                            with open(skill_file, "w", encoding="utf-8") as sf:
                                sf.write(compiled_md)
                            
                            # Auto-sync para o Antigravity (~/.gemini/config/skills/)
                            try:
                                agy_skill_dir = Path.home() / ".gemini" / "config" / "skills" / f"oraculo-{item.agent_id}"
                                agy_skill_dir.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(skill_file, agy_skill_dir / "SKILL.md")
                                logger.info(f"🔄 Skill de {item.agent_id} sincronizada com Antigravity")
                            except Exception as sync_err:
                                logger.warning(f"Falha no sync Antigravity de {item.agent_id}: {sync_err}")
                    except Exception as skill_err:
                        logger.warning(f"Não foi possível recompilar SKILL.md de {item.agent_id}: {skill_err}")

            item.status = "completed"
            item.progress_pct = 100.0
            item.current_step_text = "Estudo concluído com sucesso!"
            item.completed_at = datetime.now(timezone.utc)
            self._db_update(item)

        except Exception as e:
            err_str = str(e).upper()
            is_transient = any(k in err_str for k in [
                "503", "UNAVAILABLE", "HIGH DEMAND", "TEMPORARY", 
                "429", "RESOURCE_EXHAUSTED", "QUOTA", "RATE LIMIT",
                "DEADLINE", "TIMEOUT", "CONNECTION", "CONNECTERROR", "RETRY"
            ])
            item.retry_count = getattr(item, "retry_count", 0) + 1
            if is_transient and item.retry_count <= 5:
                logger.warning(f"⚠️ Erro temporário da API em '{item.file_name}' ({e}). Reenfileirando automaticamente ({item.retry_count}/5)...")
                item.status = "queued"
                item.error_message = None
                item.progress_pct = 0.0
                item.current_step_text = f"Reenfileirado após pico de demanda (tentativa {item.retry_count}/5)"
                item.started_at = None
                self._db_update(item)
                if item not in self.queue:
                    self.queue.append(item)
            else:
                item.status = "error"
                item.error_message = str(e)
                item.current_step_text = f"Erro no estudo: {str(e)}"
                self._db_update(item)

            with self._agent_file_lock:
                current_agent = self.get_agent_profile(item.agent_id)
                if current_agent:
                    has_other_active = any(
                        other.agent_id == item.agent_id and other.id != item.id 
                        for other in self.active_items.values()
                    )
                    if not has_other_active:
                        current_agent.status = AgentStatus.ACTIVE
                        current_agent.current_task = None
                        self.save_agent(current_agent)
        finally:
            # Auto-limpeza de vídeo MP4 bruto para evitar estourar disco (ex: AWS Free Tier 30GB)
            # Mantém em disco se ainda estiver na fila para retry imediato
            try:
                if 'video_path' in locals() and video_path and Path(video_path).exists():
                    if item.status != "queued":
                        Path(video_path).unlink(missing_ok=True)
            except Exception:
                pass
