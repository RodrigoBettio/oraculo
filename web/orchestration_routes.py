from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from datetime import datetime, timezone

from models.project import (
    Project, Task, DocumentArtifact, ProjectStatus, TaskStatus,
    CreateProjectRequest, UpdateProjectRequest, CreateTaskRequest, CreateDocumentRequest,
    AutoDispatchProjectRequest
)
from orchestration.project_store import ProjectStore
from orchestration.harness import AgentHarness

router = APIRouter(prefix="/api", tags=["Orchestration"])
store = ProjectStore()
harness = AgentHarness()

# ----------------- PROJETOS -----------------

@router.post("/projects/auto-dispatch", response_model=Project)
def auto_dispatch_project(req: AutoDispatchProjectRequest, bg_tasks: BackgroundTasks):
    """Recebe um comando universal em linguagem natural e orquestra tudo automaticamente:
    escolhe área, gestor, tarefas técnicas e classifica o harness (Antigravity IDE vs Oráculo Cloud)."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt não pode estar vazio")
    
    project = harness.auto_dispatch(req.prompt.strip())
    return store.get_project(project.id)

@router.get("/projects", response_model=List[Project])
def list_projects():
    """Retorna todos os projetos cadastrados com suas tarefas e documentos."""
    return store.list_projects()

@router.post("/projects", response_model=Project)
def create_project(req: CreateProjectRequest):
    """Cria um novo projeto com objetivo estratégico."""
    # Encontra nome da área
    from config import settings
    import json
    area_name = "Geral"
    area_file = settings.AREAS_DIR / f"{req.area_id}.json"
    if area_file.exists():
        try:
            with open(area_file, "r", encoding="utf-8") as f:
                area_data = json.load(f)
                area_name = area_data.get("name", area_name)
        except Exception:
            pass

    # Nome do gestor
    manager_name = None
    if req.manager_agent_id:
        agent_file = settings.AGENTS_DIR / f"{req.manager_agent_id}.json"
        if agent_file.exists():
            try:
                with open(agent_file, "r", encoding="utf-8") as f:
                    ag = json.load(f)
                    manager_name = ag.get("name")
            except Exception:
                pass

    project = Project(
        title=req.title,
        description=req.description,
        area_id=req.area_id,
        area_name=area_name,
        manager_agent_id=req.manager_agent_id,
        manager_agent_name=manager_name,
        status=ProjectStatus.DRAFT
    )
    return store.save_project(project)

@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str):
    """Retorna um projeto detalhado pelo ID."""
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return proj

@router.put("/projects/{project_id}", response_model=Project)
def update_project(project_id: str, req: UpdateProjectRequest):
    """Atualiza dados cadastrais de um projeto."""
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    if req.title is not None:
        proj.title = req.title
    if req.description is not None:
        proj.description = req.description
    if req.manager_agent_id is not None:
        proj.manager_agent_id = req.manager_agent_id
    if req.status is not None:
        proj.status = req.status

    return store.save_project(proj)

@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Exclui um projeto e todas as suas tarefas e documentos."""
    success = store.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"message": f"Projeto {project_id} excluído com sucesso"}

@router.post("/projects/{project_id}/plan")
async def plan_project(project_id: str):
    """Dispara o Gestor de Área para analisar o projeto e decompor em tarefas técnicas."""
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    try:
        tasks = harness.plan_project(project_id)
        updated_proj = store.get_project(project_id)
        return {
            "message": f"Projeto planejado com sucesso pelo Gestor! {len(tasks)} tarefas criadas.",
            "project": updated_proj,
            "tasks": tasks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao planejar projeto: {str(e)}")

@router.post("/projects/{project_id}/tasks", response_model=Task)
def add_task_to_project(project_id: str, req: CreateTaskRequest):
    """Adiciona manualmente uma tarefa a um projeto existente."""
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    agent_name = "Especialista"
    if req.assigned_agent_id:
        from config import settings
        import json
        af = settings.AGENTS_DIR / f"{req.assigned_agent_id}.json"
        if af.exists():
            try:
                with open(af, "r", encoding="utf-8") as f:
                    agent_name = json.load(f).get("name", agent_name)
            except Exception:
                pass

    task = Task(
        project_id=project_id,
        title=req.title,
        instruction=req.instruction,
        assigned_agent_id=req.assigned_agent_id,
        assigned_agent_name=agent_name,
        status=TaskStatus.TODO
    )
    return store.save_task(task)

@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: str):
    """Executa uma tarefa individual no Agent Harness de forma síncrona/esperada."""
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    try:
        updated_task = await harness.execute_task(task_id)
        project = store.get_project(task.project_id)
        return {
            "message": "Tarefa executada com sucesso!",
            "task": updated_task,
            "project": project
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na execução da tarefa: {str(e)}")

@router.post("/projects/{project_id}/execute")
async def execute_project(project_id: str, bg_tasks: BackgroundTasks):
    """Dispara a execução de todas as tarefas pendentes do projeto em background."""
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    bg_tasks.add_task(harness.execute_project_all_tasks, project_id)
    return {"message": f"Execução do projeto '{proj.title}' iniciada em background!"}

# ----------------- DOCUMENTOS / ARTEFATOS -----------------

@router.get("/documents", response_model=List[DocumentArtifact])
def list_documents(project_id: Optional[str] = None):
    """Retorna todos os documentos/artefatos gerados pelos agentes."""
    return store.list_documents(project_id=project_id)

@router.get("/documents/{document_id}", response_model=DocumentArtifact)
def get_document(document_id: str):
    """Retorna o documento detalhado."""
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return doc

@router.delete("/documents/{document_id}")
def delete_document(document_id: str):
    """Exclui um documento do repositório."""
    success = store.delete_document(document_id)
    return {"message": f"Documento {document_id} excluído com sucesso"}

# ----------------- SKILL GAP ANALYSIS (GESTOR) -----------------

@router.post("/managers/{manager_id}/skill-gaps")
def run_manager_skill_gap_analysis(manager_id: str):
    """O Gestor de Área analisa o portfólio de habilidades dos seus especialistas,
    identifica defasagens (Skill Gaps) e emite pedidos de estudos ou contratação."""
    from orchestration.manager_sync import analyze_manager_skill_gaps
    result = analyze_manager_skill_gaps(manager_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/managers/{manager_id}/skill-gaps")
def get_manager_skill_gap_analysis(manager_id: str):
    """Retorna o último relatório de defasagens emitido pelo Gestor de Área."""
    from config import settings
    import json
    from orchestration.harness import load_agent_context

    ctx = load_agent_context(manager_id)
    if not ctx or ctx.get("agent_type") != "gestor":
        raise HTTPException(status_code=404, detail="Gestor não encontrado")

    area_id = ctx.get("area_id")
    gap_file = settings.AREAS_DIR / f"{area_id}_gap_analysis.json"
    if not gap_file.exists():
        # Executa na hora se não houver relatório prévio
        from orchestration.manager_sync import analyze_manager_skill_gaps
        return analyze_manager_skill_gaps(manager_id)

    try:
        with open(gap_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler relatório: {e}")
