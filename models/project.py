from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field

class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"

class DocumentType(str, Enum):
    SCRIPT = "script"         # Roteiros de vídeo, podcasts, etc.
    REPORT = "report"         # Relatórios e pareceres
    CODE = "code"             # Códigos, automações e scripts
    SUMMARY = "summary"       # Resumos executivos e sínteses
    OUTLINE = "outline"       # Estruturas, pautas e planos
    ANALYSIS = "analysis"     # Análises aprofundadas e comparações
    REFERENCE = "reference"   # Padrões de design, manuais técnicos e especificações
    OTHER = "other"

class DocumentArtifact(BaseModel):
    id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:10]}")
    project_id: str
    task_id: Optional[str] = None
    created_by_agent_id: str
    created_by_agent_name: str = "Agente"
    title: str
    content: str
    doc_type: DocumentType = DocumentType.REPORT
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    project_id: str
    title: str
    instruction: str
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    harness_type: str = "oraculo_cloud"  # "oraculo_cloud", "antigravity_ide", "claude_code"
    ide_handoff_prompt: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    result_summary: Optional[str] = None
    execution_logs: List[Dict[str, Any]] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class Project(BaseModel):
    id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    area_id: str
    area_name: Optional[str] = None
    manager_agent_id: Optional[str] = None
    manager_agent_name: Optional[str] = None
    status: ProjectStatus = ProjectStatus.DRAFT
    tasks: List[Task] = Field(default_factory=list)
    documents: List[DocumentArtifact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

# Request / Input Schemas
class CreateProjectRequest(BaseModel):
    title: str
    description: str
    area_id: str
    manager_agent_id: Optional[str] = None

class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    manager_agent_id: Optional[str] = None
    status: Optional[ProjectStatus] = None

class CreateTaskRequest(BaseModel):
    title: str
    instruction: str
    assigned_agent_id: Optional[str] = None
    harness_type: Optional[str] = "oraculo_cloud"

class CreateDocumentRequest(BaseModel):
    project_id: str
    task_id: Optional[str] = None
    created_by_agent_id: str
    title: str
    content: str
    doc_type: DocumentType = DocumentType.REPORT

class AutoDispatchProjectRequest(BaseModel):
    prompt: str
    auto_execute: bool = True

