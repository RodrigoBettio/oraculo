import sqlite3
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from config import settings
from models.project import Project, Task, DocumentArtifact, ProjectStatus, TaskStatus, DocumentType

class ProjectStore:
    """Gerenciador de persistência SQLite para Projetos, Tarefas e Documentos/Artefatos."""
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProjectStore, cls).__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _get_conn(self) -> sqlite3.Connection:
        db_path = settings.DATA_DIR / "oraculo.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._lock, self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    area_id TEXT NOT NULL,
                    area_name TEXT,
                    manager_agent_id TEXT,
                    manager_agent_name TEXT,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT,
                    updated_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instruction TEXT,
                    assigned_agent_id TEXT,
                    assigned_agent_name TEXT,
                    harness_type TEXT DEFAULT 'oraculo_cloud',
                    ide_handoff_prompt TEXT,
                    status TEXT DEFAULT 'todo',
                    result_summary TEXT,
                    execution_logs TEXT,
                    document_ids TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    task_id TEXT,
                    created_by_agent_id TEXT,
                    created_by_agent_name TEXT,
                    title TEXT NOT NULL,
                    content TEXT,
                    doc_type TEXT DEFAULT 'report',
                    version INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
            """)
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN harness_type TEXT DEFAULT 'oraculo_cloud'")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN ide_handoff_prompt TEXT")
            except Exception:
                pass

    # ------------------- PROJETOS -------------------
    def save_project(self, project: Project) -> Project:
        project.updated_at = datetime.now(timezone.utc)
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                INSERT INTO projects (
                    id, title, description, area_id, area_name, manager_agent_id,
                    manager_agent_name, status, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    area_id=excluded.area_id,
                    area_name=excluded.area_name,
                    manager_agent_id=excluded.manager_agent_id,
                    manager_agent_name=excluded.manager_agent_name,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at
            """, (
                project.id,
                project.title,
                project.description,
                project.area_id,
                project.area_name,
                project.manager_agent_id,
                project.manager_agent_name,
                project.status.value if isinstance(project.status, ProjectStatus) else str(project.status),
                project.created_at.isoformat() if project.created_at else None,
                project.updated_at.isoformat() if project.updated_at else None,
                project.completed_at.isoformat() if project.completed_at else None
            ))
        return project

    def get_project(self, project_id: str, include_children: bool = True) -> Optional[Project]:
        with self._lock, self._get_conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            
            proj_data = dict(row)
            if include_children:
                proj_data["tasks"] = self.list_tasks(project_id=project_id)
                proj_data["documents"] = self.list_documents(project_id=project_id)
            else:
                proj_data["tasks"] = []
                proj_data["documents"] = []
            
            return Project(**proj_data)

    def list_projects(self) -> List[Project]:
        with self._lock, self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            projects = []
            for r in rows:
                proj_data = dict(r)
                proj_data["tasks"] = self.list_tasks(project_id=r["id"])
                proj_data["documents"] = self.list_documents(project_id=r["id"])
                projects.append(Project(**proj_data))
            return projects

    def delete_project(self, project_id: str) -> bool:
        with self._lock, self._get_conn() as conn:
            conn.execute("DELETE FROM documents WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            res = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return res.rowcount > 0

    # ------------------- TAREFAS -------------------
    def save_task(self, task: Task) -> Task:
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    id, project_id, title, instruction, assigned_agent_id, assigned_agent_name,
                    harness_type, ide_handoff_prompt,
                    status, result_summary, execution_logs, document_ids, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    instruction=excluded.instruction,
                    assigned_agent_id=excluded.assigned_agent_id,
                    assigned_agent_name=excluded.assigned_agent_name,
                    harness_type=excluded.harness_type,
                    ide_handoff_prompt=excluded.ide_handoff_prompt,
                    status=excluded.status,
                    result_summary=excluded.result_summary,
                    execution_logs=excluded.execution_logs,
                    document_ids=excluded.document_ids,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at
            """, (
                task.id,
                task.project_id,
                task.title,
                task.instruction,
                task.assigned_agent_id,
                task.assigned_agent_name,
                task.harness_type,
                task.ide_handoff_prompt,
                task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                task.result_summary,
                json.dumps(task.execution_logs, ensure_ascii=False),
                json.dumps(task.document_ids, ensure_ascii=False),
                task.created_at.isoformat() if task.created_at else None,
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None
            ))
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock, self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["execution_logs"] = json.loads(data["execution_logs"] or "[]")
            data["document_ids"] = json.loads(data["document_ids"] or "[]")
            return Task(**data)

    def list_tasks(self, project_id: Optional[str] = None) -> List[Task]:
        with self._lock, self._get_conn() as conn:
            if project_id:
                rows = conn.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
            
            tasks = []
            for r in rows:
                data = dict(r)
                data["execution_logs"] = json.loads(data["execution_logs"] or "[]")
                data["document_ids"] = json.loads(data["document_ids"] or "[]")
                tasks.append(Task(**data))
            return tasks

    def delete_task(self, task_id: str) -> bool:
        with self._lock, self._get_conn() as conn:
            res = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return res.rowcount > 0

    # ------------------- DOCUMENTOS / ARTEFATOS -------------------
    def save_document(self, doc: DocumentArtifact) -> DocumentArtifact:
        doc.updated_at = datetime.now(timezone.utc)
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                INSERT INTO documents (
                    id, project_id, task_id, created_by_agent_id, created_by_agent_name,
                    title, content, doc_type, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    doc_type=excluded.doc_type,
                    version=excluded.version,
                    updated_at=excluded.updated_at
            """, (
                doc.id,
                doc.project_id,
                doc.task_id,
                doc.created_by_agent_id,
                doc.created_by_agent_name,
                doc.title,
                doc.content,
                doc.doc_type.value if isinstance(doc.doc_type, DocumentType) else str(doc.doc_type),
                doc.version,
                doc.created_at.isoformat() if doc.created_at else None,
                doc.updated_at.isoformat() if doc.updated_at else None
            ))
        return doc

    def get_document(self, doc_id: str) -> Optional[DocumentArtifact]:
        with self._lock, self._get_conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            return DocumentArtifact(**dict(row))

    def list_documents(self, project_id: Optional[str] = None) -> List[DocumentArtifact]:
        with self._lock, self._get_conn() as conn:
            if project_id:
                rows = conn.execute("SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
            return [DocumentArtifact(**dict(r)) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        with self._lock, self._get_conn() as conn:
            res = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return res.rowcount > 0
