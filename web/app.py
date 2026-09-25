import os
import re
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from models.agent import AgentProfile, AgentStatus, AgentRank, SourceStudy, StudiedLesson
from models.area import AreaProfile
from models.knowledge import ProcessingTier, VideoDocument
from ingestion.telegram_client import TelegramManager
from ingestion.video_processor import VideoProcessor
from orchestration.manager_sync import sync_all_managers_mappings

app = FastAPI(title="Oráculo", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from web.auth_routes import router as auth_router
app.include_router(auth_router)

from web.orchestration_routes import router as orchestration_router
app.include_router(orchestration_router)

from web.guardian_routes import router as guardian_router
app.include_router(guardian_router)

@app.on_event("startup")
async def startup_guardian():
    from orchestration.guardian import guardian
    guardian.start()

@app.on_event("shutdown")
async def shutdown_guardian():
    from orchestration.guardian import guardian
    guardian.stop()

# MCP Server — Expõe ferramentas do Oráculo para o Antigravity via SSE
try:
    from oraculo_mcp.oraculo_mcp_server import mount_mcp_on_app
    mount_mcp_on_app(app)
except Exception as e:
    logging.getLogger("oraculo").warning(f"MCP Server não inicializado: {e}")

@app.get('/health')
def health_check():
    return {
        'status': 'healthy',
        'version': '1.0.0',
        'environment': settings.ENVIRONMENT
    }

@app.post('/api/telegram/session/upload')
async def upload_telegram_session(file: UploadFile = File(...)):
    session_file = settings.DATA_DIR / f"{settings.TELEGRAM_SESSION_NAME}.session"
    content = await file.read()
    with open(session_file, "wb") as f:
        f.write(content)
    try:
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        await tm._force_reconnect()
    except Exception:
        pass
    return {"success": True, "message": "Sessão do Telegram instalada com sucesso!", "size": len(content)}

# Gerenciador global de progresso de estudo em background
study_state: Dict[str, Any] = {
    "is_studying": False,
    "agent_id": None,
    "video_title": None,
    "step": "idle",       # "downloading", "processing", "completed", "error"
    "progress_pct": 0.0,
    "error_message": None
}

settings.ensure_directories()
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ----------------- MODELOS DE REQUISIÇÃO -----------------

class CreateAgentRequest(BaseModel):
    id: str
    name: str
    role: str
    avatar: str = "👨‍💻"
    area_id: Optional[str] = None
    agent_type: str = "tecnico"
    initial_topics: List[str] = []
    capabilities: List[str] = ["answer_questions", "generate_specs", "write_code"]

class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None
    area_id: Optional[str] = None
    agent_type: Optional[str] = None
    status: Optional[str] = None
    topics_mastered: Optional[List[str]] = None
    total_hours_studied: Optional[float] = None
    capabilities: Optional[List[str]] = None

class UpdateAgentSpecRequest(BaseModel):
    skill_md: Optional[str] = None
    agent_md: Optional[str] = None

class CreateAreaRequest(BaseModel):
    id: Optional[str] = None
    name: str
    icon: str = "📁"
    color: str = "#10b981"
    description: str = ""
    manager_agent_id: Optional[str] = None
    health_score: int = 95
    routines_count: int = 0
    projects_count: int = 0
    meetings_count: int = 0

class UpdateAreaRequest(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    manager_agent_id: Optional[str] = None
    health_score: Optional[int] = None
    routines_count: Optional[int] = None
    projects_count: Optional[int] = None
    meetings_count: Optional[int] = None

class AssignAreaAgentRequest(BaseModel):
    agent_id: str
    agent_type: str = "tecnico" # "gestor" ou "tecnico"

class UpdateTopicsRequest(BaseModel):
    topics: List[str]

class UpdateHoursRequest(BaseModel):
    hours: float

from utils.token_tracker import get_token_stats, record_tokens, set_daily_budget
from ingestion.study_queue import StudyQueueManager, QueueItem

class EnqueueStudyRequest(BaseModel):
    agent_id: str
    group_id: int
    group_name: str
    message_id: int
    file_name: str
    tier: str = "audio_only"

class EnqueueGroupRequest(BaseModel):
    agent_id: str
    group_id: int
    group_name: str
    tier: str = "audio_only"
    only_pending: bool = True

class EnqueueBatchGroupsRequest(BaseModel):
    agent_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    group_ids: List[int]
    tier: str = "audio_only"
    only_pending: bool = True

class EnqueueDriveFileRequest(BaseModel):
    agent_id: str
    drive_file_id: str
    file_name: str
    course_name: str
    theme_name: Optional[str] = None
    support_files: Optional[List[Dict[str, Any]]] = None
    tier: str = "audio_only"

class EnqueueDriveThemeRequest(BaseModel):
    agent_id: str
    folder_id: str
    course_name: str
    theme_name: str
    support_files: Optional[List[Dict[str, Any]]] = None
    tier: str = "audio_only"
    only_pending: bool = True

class EnqueueDriveCourseRequest(BaseModel):
    agent_id: str
    folder_id: str
    course_name: str
    tier: str = "audio_only"
    only_pending: bool = True

class UpdateDriveConfigRequest(BaseModel):
    folder_id: Optional[str] = None
    service_account_json: Optional[str] = None

class SetBudgetRequest(BaseModel):
    daily_budget: int

class StartStudyRequest(BaseModel):
    agent_id: str
    group_id: int
    group_name: str
    message_id: int
    file_name: str
    tier: ProcessingTier = ProcessingTier.AUDIO_ONLY

class OracleChatRequest(BaseModel):
    query: str
    agent_id: Optional[str] = None         # Se preenchido, fala direto com esse agente
    mode: str = "debate"                   # "single" ou "debate" (mesa redonda multi-agente)

# ----------------- AUXILIARES DE AGENTES -----------------

def load_all_agents() -> List[Dict[str, Any]]:
    agents = []
    for f in settings.AGENTS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                profile = AgentProfile(**data)
                agent_dict = profile.model_dump()
                agent_dict["seniority"] = profile.get_seniority_info()
                agents.append(agent_dict)
        except Exception:
            continue
    return agents

def get_agent_profile(agent_id: str) -> Optional[AgentProfile]:
    agent_file = settings.AGENTS_DIR / f"{agent_id}.json"
    if not agent_file.exists():
        return None
    with open(agent_file, "r", encoding="utf-8") as f:
        return AgentProfile(**json.load(f))

def save_agent(profile: AgentProfile):
    out_file = settings.AGENTS_DIR / f"{profile.id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))

def get_area_raw(area_id: str) -> Optional[Dict[str, Any]]:
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    if not area_file.exists():
        return None
    try:
        with open(area_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_area_raw(area_id: str, data: Dict[str, Any]):
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    with open(area_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_area_profile(area_id: str) -> Optional[Dict[str, Any]]:
    return get_area_raw(area_id)

# ----------------- PIPELINE DE ESTUDO EM BACKGROUND -----------------

async def run_study_pipeline(req: StartStudyRequest):
    global study_state
    study_state["is_studying"] = True
    study_state["agent_id"] = req.agent_id
    study_state["video_title"] = req.file_name
    study_state["step"] = "downloading"
    study_state["progress_pct"] = 0.0
    study_state["error_message"] = None

    agent_profile = get_agent_profile(req.agent_id)
    if agent_profile:
        agent_profile.status = AgentStatus.STUDYING
        agent_profile.current_task = f"Baixando aula: {req.file_name}"
        save_agent(agent_profile)

    try:
        tg = TelegramManager()
        vp = VideoProcessor()

        def download_progress(current, total):
            if total > 0:
                study_state["progress_pct"] = round((current / total) * 50.0, 1)

        # 1. Download
        video_path = await tg.download_video(
            group_id=req.group_id,
            message_id=req.message_id,
            progress_callback=download_progress
        )

        study_state["step"] = "processing"
        study_state["progress_pct"] = 55.0
        if agent_profile:
            agent_profile.current_task = f"Analisando áudio e frames de código com Gemini..."
            save_agent(agent_profile)

        # 2. Processamento multimodal
        video_id = f"video_{req.message_id}"
        doc = await asyncio.to_thread(
            vp.process_video,
            video_path=video_path,
            group_name=req.group_name,
            video_id=video_id,
            tier=req.tier,
            telegram_message_id=req.message_id
        )

        study_state["progress_pct"] = 90.0

        # 3. Atualiza o Agente com a duração REAL do vídeo
        duration_hours = round(doc.duration_seconds / 3600.0, 3)
        if duration_hours == 0.0:
            # Se for muito curta, registra ao menos o tempo medido em minutos
            duration_hours = max(0.04, round(doc.duration_seconds / 3600.0, 2))

        if agent_profile:
            agent_profile.add_studied_content(
                group_name=req.group_name,
                hours=duration_hours,
                topics=doc.topics,
                lesson_id=video_id,
                lesson_title=doc.title,
                duration_seconds=doc.duration_seconds
            )
            agent_profile.status = AgentStatus.ACTIVE
            agent_profile.current_task = None
            save_agent(agent_profile)

        study_state["step"] = "completed"
        study_state["progress_pct"] = 100.0

    except Exception as e:
        study_state["step"] = "error"
        study_state["error_message"] = str(e)
        if agent_profile:
            agent_profile.status = AgentStatus.ACTIVE
            agent_profile.current_task = None
            save_agent(agent_profile)
    finally:
        study_state["is_studying"] = False

@app.get("/api/study/status")
def get_study_status():
    global study_state
    return study_state

# ----------------- ROTAS DE AGENTES & SENIORIDADE -----------------

@app.get("/api/agents")
def get_agents():
    return load_all_agents()

@app.get("/api/agents/{agent_id}")
def get_agent_detail(agent_id: str):
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    res = profile.model_dump()
    res["seniority"] = profile.get_seniority_info()
    return res

@app.post("/api/agents")
def create_agent(req: CreateAgentRequest):
    out_file = settings.AGENTS_DIR / f"{req.id}.json"
    if out_file.exists():
        raise HTTPException(status_code=400, detail="Já existe um agente com este ID")
    
    profile = AgentProfile(
        id=req.id,
        name=req.name,
        role=req.role,
        avatar=req.avatar,
        area_id=req.area_id,
        agent_type=req.agent_type,
        topics_mastered=req.initial_topics,
        capabilities=req.capabilities
    )
    save_agent(profile)

    if req.area_id:
        area = get_area_raw(req.area_id)
        if area:
            sub_ids = area.get("subagent_ids", [])
            if req.agent_type == "gestor":
                area["manager_agent_id"] = req.id
                if req.id in sub_ids:
                    sub_ids.remove(req.id)
            elif req.id not in sub_ids:
                sub_ids.append(req.id)
            area["subagent_ids"] = sub_ids
            save_area_raw(req.area_id, area)

    # Cria arquivo skill.md inicial se não existir
    skill_dir = settings.DATA_DIR / "skills" / req.id
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        initial_topics_str = "\n".join([f"- `{t}`" for t in req.initial_topics]) or "- `Conhecimentos Gerais do Domínio`"
        content = f"""# Skill: {req.name}
**ID**: `{req.id}`  
**Papel**: {req.role}  
**Hierarquia**: {req.agent_type.upper()}  

## Diretrizes
Agente corporativo do Oráculo. Focado em resultados e excelência operacional.

## Competências
{initial_topics_str}
"""
        with open(skill_file, "w", encoding="utf-8") as sf:
            sf.write(content)

    # Sincroniza automaticamente mapeamentos dos gestores
    try:
        sync_all_managers_mappings()
    except Exception as e:
        pass

    res = profile.model_dump()
    res["seniority"] = profile.get_seniority_info()
    return res

@app.post("/api/managers/sync")
def sync_managers_endpoint():
    """Sincroniza todos os gestores com seus especialistas atuais, competências e protocolos de delegação."""
    try:
        result = sync_all_managers_mappings()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar gestores: {str(e)}")

@app.put("/api/agents/{agent_id}")
def update_agent(agent_id: str, req: UpdateAgentRequest):
    """Atualização completa de cadastro do funcionário/agente (CRUD Corporativo)."""
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    old_area_id = profile.area_id
    old_agent_type = profile.agent_type

    if req.name is not None:
        profile.name = req.name
    if req.role is not None:
        profile.role = req.role
    if req.avatar is not None:
        profile.avatar = req.avatar
    if req.status is not None:
        try:
            profile.status = AgentStatus(req.status)
        except Exception:
            pass
    if req.topics_mastered is not None:
        profile.topics_mastered = req.topics_mastered
    if req.total_hours_studied is not None:
        profile.total_hours_studied = req.total_hours_studied
    if req.capabilities is not None:
        profile.capabilities = req.capabilities

    area_changed = req.area_id is not None and req.area_id != old_area_id
    type_changed = req.agent_type is not None and req.agent_type != old_agent_type

    if req.area_id is not None:
        profile.area_id = req.area_id if req.area_id != "" else None
    if req.agent_type is not None:
        profile.agent_type = req.agent_type

    save_agent(profile)

    # Atualiza vínculos em áreas
    if area_changed or type_changed:
        if old_area_id:
            old_area = get_area_raw(old_area_id)
            if old_area:
                if old_area.get("manager_agent_id") == agent_id:
                    old_area["manager_agent_id"] = None
                sub_ids = old_area.get("subagent_ids", [])
                if agent_id in sub_ids:
                    sub_ids.remove(agent_id)
                    old_area["subagent_ids"] = sub_ids
                save_area_raw(old_area_id, old_area)

        if profile.area_id:
            new_area = get_area_raw(profile.area_id)
            if new_area:
                sub_ids = new_area.get("subagent_ids", [])
                if profile.agent_type == "gestor":
                    new_area["manager_agent_id"] = agent_id
                    if agent_id in sub_ids:
                        sub_ids.remove(agent_id)
                else:
                    if new_area.get("manager_agent_id") == agent_id:
                        new_area["manager_agent_id"] = None
                    if agent_id not in sub_ids:
                        sub_ids.append(agent_id)
                new_area["subagent_ids"] = sub_ids
                save_area_raw(profile.area_id, new_area)

    # Sincroniza automaticamente mapeamentos dos gestores
    try:
        sync_all_managers_mappings()
    except Exception as e:
        pass

    res = profile.model_dump()
    res["seniority"] = profile.get_seniority_info()
    return res

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Demite/remove o agente do sistema, desvinculando de áreas e removendo arquivos."""
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    if profile.area_id:
        area = get_area_raw(profile.area_id)
        if area:
            if area.get("manager_agent_id") == agent_id:
                area["manager_agent_id"] = None
            sub_ids = area.get("subagent_ids", [])
            if agent_id in sub_ids:
                sub_ids.remove(agent_id)
                area["subagent_ids"] = sub_ids
            save_area_raw(profile.area_id, area)

    agent_file = settings.AGENTS_DIR / f"{agent_id}.json"
    if agent_file.exists():
        agent_file.unlink(missing_ok=True)

    skill_file = settings.DATA_DIR / "skills" / agent_id / "SKILL.md"
    if skill_file.exists():
        try:
            skill_file.unlink(missing_ok=True)
            skill_file.parent.rmdir()
        except Exception:
            pass

    # Sincroniza automaticamente mapeamentos dos gestores
    try:
        sync_all_managers_mappings()
    except Exception as e:
        pass

    return {"message": f"Agente {agent_id} excluído com sucesso"}

def compile_agent_rich_skill(agent_id: str) -> str:
    """Compila o arquivo SKILL.md oficial do agente com todo o conhecimento técnico profundo,
    códigos OCR extraídos das telas, regras determinísticas de arquitetura e timestamps
    das aulas que ele já estudou."""
    profile = get_agent_profile(agent_id)
    if not profile:
        return ""

    studied_lessons = []
    code_blocks = []

    agent_group_names = {s.group_name.strip().lower() for s in profile.sources if s.group_name}
    studied_lesson_ids = set()
    for s in profile.sources:
        for l in s.lessons:
            lid = str(l.lesson_id).strip().lower()
            if lid:
                studied_lesson_ids.add(lid)

    for p_file in settings.PROCESSED_DIR.rglob("*.json"):
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                gname = (doc.get("group_name") or "").strip().lower()
                vid = (doc.get("video_id") or "").strip().lower()
                vtitle = doc.get("title") or doc.get("file_name") or "Aula Técnica"

                if (gname and any(ag in gname or gname in ag for ag in agent_group_names)) or (vid in studied_lesson_ids):
                    studied_lessons.append(doc)
                    for snippet in doc.get("extracted_codes", []):
                        code_blocks.append({
                            "lesson_title": vtitle,
                            "timestamp": snippet.get("timestamp", "00:00"),
                            "language": snippet.get("language", "text"),
                            "code": snippet.get("code", ""),
                            "description": snippet.get("description", "")
                        })
                    for seg in doc.get("segments", []):
                        for snip in seg.get("code_snippets", []):
                            if not any(cb["code"] == snip.get("code") for cb in code_blocks):
                                code_blocks.append({
                                    "lesson_title": vtitle,
                                    "timestamp": snip.get("timestamp", seg.get("start_time", "00:00")),
                                    "language": snip.get("language", "text"),
                                    "code": snip.get("code", ""),
                                    "description": snip.get("description", "")
                                })
        except Exception:
            continue

    clean_name = re.sub(r'[^\w\s-]', '', profile.name).strip().lower().replace(" ", "-")
    skill_slug = f"oraculo-{clean_name}"
    topics_list = profile.topics_mastered or ["Automação Determinística", "Arquitetura de Software"]
    courses_str = ", ".join([s.group_name for s in profile.sources]) if profile.sources else "Cursos Técnicos do Oráculo"
    total_hours = profile.total_hours_studied
    agent_type = profile.agent_type
    role = profile.role
    avatar = profile.avatar
    seniority = profile.get_seniority_info()

    skill_md = f"""---
name: {skill_slug}
description: Especialista {profile.name} ({role}). Domina: {', '.join(topics_list[:6])}. Use para orientação técnica, regras determinísticas de código, arquitetura e automações aprendidas no curso {courses_str}.
---

# Skill: {profile.name} - {role}

> [!NOTE]
> Esta skill foi sintetizada e enriquecida automaticamente pelo **Oráculo Engine** a partir de **{total_hours:.2f} horas** de aulas reais e frames de código capturados via OCR e transcrição multimodal.

## 1. Ficha Técnica & Identidade Operacional
- **ID do Agente**: `{profile.id}`
- **Especialista**: {profile.name} ({avatar})
- **Cargo / Papel**: {role}
- **Hierarquia Corporativa**: {'👑 Gestor Executivo de Domínio' if agent_type == 'gestor' else '⚡ Especialista Técnico'}
- **Nível de Senioridade**: {seniority.get('rank', 'Pleno')} ({seniority.get('badge', '🥈')})
- **Horas Reais Absorvidas**: `{total_hours:.2f}h` ({profile.total_videos_studied} aulas indexadas)
- **Base de Cursos**: {courses_str}

## 2. Habilidades & Tópicos Dominados
"""
    for top in topics_list:
        skill_md += f"- `{top}`\n"

    skill_md += f"""
## 3. Diretrizes de Execução & Arquitetura Determinística
- Agir com autoridade técnica no domínio de {role}.
- Aplicar automações determinísticas sempre que possível, priorizando consistência e repetibilidade.
- Seguir os padrões arquiteturais ensinados nas aulas, incluindo controle rigoroso de contexto de IA, estrutura `/docs` e automação com hooks.
"""

    if studied_lessons:
        skill_md += "\n## 4. Base de Conhecimento Aprofundada (Cursos, Módulos & Aulas)\n"
        
        # Agrupa aulas por Curso e por Tema/Módulo
        from collections import defaultdict
        courses_map = defaultdict(lambda: defaultdict(list))
        for doc in studied_lessons:
            c_name = doc.get("group_name") or "Curso Técnico"
            t_name = doc.get("theme_name") or "Aulas Gerais"
            courses_map[c_name][t_name].append(doc)

        for c_name, themes_dict in courses_map.items():
            skill_md += f"\n### 🎓 Curso: {c_name}\n"
            for t_name, docs_list in themes_dict.items():
                if t_name != "Aulas Gerais":
                    skill_md += f"\n#### 📁 Tema / Módulo: {t_name}\n"
                for doc in docs_list:
                    title = doc.get("title") or doc.get("file_name") or "Aula"
                    summary = doc.get("summary") or ""
                    comp_files = doc.get("companion_files") or []
                    
                    skill_md += f"\n##### 📘 {title}\n"
                    if comp_files:
                        files_str = ", ".join([f"`{cf}`" for cf in comp_files])
                        skill_md += f"**Materiais de Apoio**: {files_str}\n\n"
                    if summary:
                        skill_md += f"**Síntese da Aula**: {summary}\n\n"
                    
                    topics = doc.get("topics", [])
                    if topics:
                        skill_md += "**Conceitos Chave**:\n"
                        for tp in topics:
                            skill_md += f"- {tp}\n"
                        skill_md += "\n"

                    segments = doc.get("segments", [])
                    if segments:
                        skill_md += "**Linha do Tempo & Tópicos Práticos**:\n"
                        for seg in segments:
                            st = seg.get("start_time", "00:00")
                            et = seg.get("end_time", "")
                            time_lbl = f"{st} - {et}" if et else st
                            skill_md += f"- **[{time_lbl}]**: {seg.get('text', '')}\n"
                        skill_md += "\n"

    if code_blocks:
        skill_md += "\n## 5. Implementações de Código & Configurações da Tela (OCR)\n"
        for cb in code_blocks:
            lang = cb.get("language") or "json"
            skill_md += f"\n#### 💻 {cb['lesson_title']} (Timestamp `{cb['timestamp']}`)\n"
            if cb.get("description"):
                skill_md += f"*{cb['description']}*\n\n"
            code_text = cb.get("code", "").strip()
            skill_md += f"```{lang}\n{code_text}\n```\n"

    skill_md += f"""
## 6. Critérios de Ativação & Uso
Consulte ou acione este especialista quando:
1. For necessário aplicar regras técnicas de {', '.join(topics_list[:3])}.
2. Houver dúvidas sobre configurações e estruturas ensinadas em {courses_str}.
3. O usuário ou outro agente solicitar arquitetura determinística no domínio de {role}.
"""
    return skill_md

@app.get("/api/agents/{agent_id}/spec")
def get_agent_spec(agent_id: str):
    """Retorna as especificações em markdown (skill.md e agent.md) do funcionário."""
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    skill_file = settings.DATA_DIR / "skills" / agent_id / "SKILL.md"
    agent_file = settings.DATA_DIR / "skills" / agent_id / "AGENT.md"

    # Se a skill não existir ou tiver menos de 1000 bytes e o agente tiver fontes estudadas, recompila rica
    if not skill_file.exists() or (skill_file.stat().st_size < 1000 and profile.sources):
        compiled_skill = compile_agent_rich_skill(agent_id)
        if compiled_skill:
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(compiled_skill)

    skill_content = ""
    if skill_file.exists():
        with open(skill_file, "r", encoding="utf-8") as f:
            skill_content = f.read()

    agent_content = ""
    if agent_file.exists():
        with open(agent_file, "r", encoding="utf-8") as f:
            agent_content = f.read()
    else:
        seniority = profile.get_seniority_info()
        topics_str = "\n".join([f"- `{t}`" for t in (profile.topics_mastered or [])])
        agent_content = f"""# Persona: {profile.name}
**Cargo**: {profile.role}
**Hierarquia**: {profile.agent_type.upper()}
**Nível**: {seniority.get('rank', 'Pleno')} ({seniority.get('badge', '🥈')})

## Contexto de Negócio
Atua como referência técnica e consultiva no domínio de sua área. 
Conecta-se aos gestores executivos para receber metas e reportar entregas de alta confiabilidade.

## Competências Principais
{topics_str}
"""

    return {
        "skill_md": skill_content,
        "agent_md": agent_content
    }

@app.put("/api/agents/{agent_id}/spec")
def update_agent_spec(agent_id: str, req: UpdateAgentSpecRequest):
    """Permite ao usuário editar diretamente os arquivos skill.md e agent.md do funcionário."""
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    agent_skills_dir = settings.DATA_DIR / "skills" / agent_id
    agent_skills_dir.mkdir(parents=True, exist_ok=True)

    if req.skill_md is not None:
        skill_file = agent_skills_dir / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(req.skill_md)

    if req.agent_md is not None:
        agent_file = agent_skills_dir / "AGENT.md"
        with open(agent_file, "w", encoding="utf-8") as f:
            f.write(req.agent_md)

    return {"message": "Especificações e skill.md atualizados com sucesso"}

@app.put("/api/agents/{agent_id}/topics")
def update_agent_topics(agent_id: str, req: UpdateTopicsRequest):
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    profile.set_topics(req.topics)
    save_agent(profile)
    return {"message": "Tópicos atualizados com sucesso", "topics": profile.topics_mastered}

@app.put("/api/agents/{agent_id}/hours")
def update_agent_hours(agent_id: str, req: UpdateHoursRequest):
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    profile.set_total_hours(req.hours)
    save_agent(profile)
    return {"message": "Horas atualizadas com sucesso", "total_hours": profile.total_hours_studied}

@app.post("/api/agents/{agent_id}/export-skill")
def export_agent_skill(agent_id: str):
    """Exporta o conhecimento do agente diretamente como uma Skill global do Antigravity."""
    profile = get_agent_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    home_dir = Path.home()
    global_skills_dir = home_dir / ".gemini" / "config" / "skills"
    
    clean_name = re.sub(r'[^\w\s-]', '', profile.name).strip().lower().replace(" ", "-")
    skill_slug = f"oraculo-{clean_name}"
    target_skill_dir = global_skills_dir / skill_slug
    target_skill_dir.mkdir(parents=True, exist_ok=True)
    
    studied_lessons = []
    code_blocks = []
    
    agent_group_names = {s.group_name for s in profile.sources}
    for p_file in settings.PROCESSED_DIR.rglob("*.json"):
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                gname = doc.get("group_name", "")
                vtitle = doc.get("title", "")
                if gname in agent_group_names or not agent_group_names:
                    studied_lessons.append(doc)
                    for seg in doc.get("segments", []):
                        for snip in seg.get("code_snippets", []):
                            code_blocks.append({
                                "lesson_title": vtitle,
                                "timestamp": snip.get("timestamp", ""),
                                "language": snip.get("language", "text"),
                                "code": snip.get("code", ""),
                                "description": snip.get("description", "")
                            })
        except Exception:
            continue

    topics_list = profile.topics_mastered or ["Arquitetura de Software", "Boas Práticas", "Automação"]
    topics_str = ", ".join(topics_list)
    courses_str = ", ".join([s.group_name for s in profile.sources]) if profile.sources else "Cursos do Oráculo"

    skill_md = f"""---
name: {skill_slug}
description: Especialista {profile.name} ({profile.role}). Domina: {topics_str}. Use para orientação técnica, regras determinísticas de código, arquitetura e boas práticas aprendidas no curso {courses_str}.
---

# Especialista {profile.name} - {profile.role}

> [!NOTE]
> Esta skill foi gerada automaticamente pelo **Oráculo** a partir de **{profile.total_hours_studied} horas** de aulas reais absorvidas no Telegram.

## 1. Visão Geral & Escopo de Atuação
- **Especialista**: {profile.name} ({profile.avatar})
- **Cargo**: {profile.role}
- **Senioridade**: {profile.get_seniority_info().get('rank', 'Especialista')} ({profile.total_hours_studied}h estudadas)
- **Cursos Base**: {courses_str}

## 2. Habilidades & Tópicos Dominados
"""
    for top in topics_list:
        skill_md += f"- **{top}**\n"

    skill_md += "\n## 3. Regras & Padrões Determinísticos Ensinados nas Aulas\n"
    if studied_lessons:
        for doc in studied_lessons[:6]:
            title = doc.get("title", "Aula")
            summary = doc.get("summary", "")
            skill_md += f"\n### Padrão: {title}\n"
            skill_md += f"{summary}\n"
    else:
        skill_md += f"- Seguir rigorosamente as convenções estabelecidas nas aulas de {topics_str}.\n"

    if code_blocks:
        skill_md += "\n## 4. Snippets de Código & Configurações da Tela\n"
        for cb in code_blocks[:8]:
            lang = cb["language"] or "text"
            skill_md += f"\n#### {cb['lesson_title']} (Timestamp: {cb['timestamp']})\n"
            if cb["description"]:
                skill_md += f"*{cb['description']}*\n\n"
            skill_md += f"```{lang}\n{cb['code']}\n```\n"

    skill_md += f"""
## 5. Quando Ativar esta Skill no Antigravity
Ative ou consulte esta skill sempre que o usuário solicitar:
- Melhores práticas de {topics_str}
- Configuração de ferramentas e automações ensinadas por {profile.name}
- Revisão de código e arquitetura de acordo com os cursos de {courses_str}
"""

    skill_file = target_skill_dir / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as sf:
        sf.write(skill_md)

    return {
        "success": True,
        "skill_name": skill_slug,
        "skill_path": str(skill_file),
        "message": f"Skill '{skill_slug}' gerada e instalada com sucesso em {skill_file}!"
    }

# ----------------- ROTAS DO GOOGLE DRIVE COMPARTILHADO -----------------

@app.get("/api/drive/status")
def get_drive_status():
    """Retorna o status de conexão, autenticação e acessibilidade da pasta compartilhada do Google Drive."""
    from ingestion.drive_client import GoogleDriveManager
    dm = GoogleDriveManager()
    return dm.get_status()

@app.get("/api/drive/tree")
def get_drive_tree():
    """Retorna a árvore completa de Áreas, Cursos e Aulas mapeadas no Google Drive."""
    from ingestion.drive_client import GoogleDriveManager
    dm = GoogleDriveManager()
    return dm.get_full_hierarchy()

@app.get("/api/drive/course-details")
def get_drive_course_details(folder_id: str, course_name: Optional[str] = None):
    """Inspeciona os temas, aulas e arquivos de apoio de um curso do Drive sob demanda."""
    from ingestion.drive_client import GoogleDriveManager
    dm = GoogleDriveManager()
    return dm._inspect_course_folder(folder_id, course_name or "Curso")

@app.get("/api/drive/shared-with-me")
def get_drive_shared_with_me():
    """Retorna a lista de pastas privadas compartilhadas diretamente com a conta pessoal do usuário."""
    from ingestion.drive_client import GoogleDriveManager
    dm = GoogleDriveManager()
    return dm.list_shared_with_me_folders()

@app.post("/api/drive/enqueue")
async def enqueue_drive_file(req: EnqueueDriveFileRequest):
    """Adiciona uma aula individual do Google Drive à esteira de estudos."""
    qm = StudyQueueManager()
    item = await qm.enqueue_drive_file(
        agent_id=req.agent_id,
        drive_file_id=req.drive_file_id,
        file_name=req.file_name,
        course_name=req.course_name,
        theme_name=req.theme_name,
        support_files=req.support_files,
        tier=req.tier
    )
    return {"message": "Aula do Google Drive adicionada à fila", "item": item}

@app.post("/api/drive/enqueue-theme")
async def enqueue_drive_theme(req: EnqueueDriveThemeRequest):
    """Enfileira todas as aulas de um tema/módulo específico do Google Drive."""
    qm = StudyQueueManager()
    enqueued = await qm.enqueue_drive_theme(
        agent_id=req.agent_id,
        folder_id=req.folder_id,
        course_name=req.course_name,
        theme_name=req.theme_name,
        support_files=req.support_files,
        tier=req.tier,
        only_pending=req.only_pending
    )
    return {
        "message": f"{len(enqueued)} aulas do tema '{req.theme_name}' ({req.course_name}) enfileiradas do Google Drive",
        "count": len(enqueued)
    }

@app.post("/api/drive/enqueue-course")
async def enqueue_drive_course(req: EnqueueDriveCourseRequest):
    """Enfileira todas as aulas pendentes de uma pasta/curso do Google Drive."""
    qm = StudyQueueManager()
    enqueued = await qm.enqueue_drive_course(
        agent_id=req.agent_id,
        folder_id=req.folder_id,
        course_name=req.course_name,
        tier=req.tier,
        only_pending=req.only_pending
    )
    return {
        "message": f"{len(enqueued)} aulas do curso '{req.course_name}' enfileiradas do Google Drive",
        "count": len(enqueued)
    }

@app.post("/api/drive/config")
def update_drive_config(req: UpdateDriveConfigRequest):
    """Permite configurar o GOOGLE_DRIVE_FOLDER_ID ou enviar o JSON da Service Account diretamente pelo frontend."""
    try:
        env_path = getattr(settings, 'BASE_DIR', Path(__file__).resolve().parent.parent) / ".env"
        env_lines = []
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        if req.service_account_json:
            try:
                parsed = json.loads(req.service_account_json)
                settings.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
                if "installed" in parsed or "web" in parsed:
                    target_file = settings.GOOGLE_DRIVE_OAUTH_FILE
                else:
                    target_file = settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE
                with open(target_file, "w", encoding="utf-8") as sf:
                    json.dump(parsed, sf, indent=2)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"JSON de credenciais inválido: {e}")

        if req.folder_id is not None:
            raw_fid = req.folder_id.strip()
            # Extrator resiliente de ID do Drive (suporta /folders/, ?id=, /d/, ou ID puro)
            if "/folders/" in raw_fid:
                clean_fid = raw_fid.split("/folders/")[1].split("?")[0].split("/")[0].split("&")[0].strip()
            elif "id=" in raw_fid:
                clean_fid = raw_fid.split("id=")[1].split("&")[0].split("#")[0].strip()
            elif "/d/" in raw_fid:
                clean_fid = raw_fid.split("/d/")[1].split("/")[0].split("?")[0].strip()
            else:
                clean_fid = raw_fid.strip()

            os.environ["GOOGLE_DRIVE_FOLDER_ID"] = clean_fid
            settings.GOOGLE_DRIVE_FOLDER_ID = clean_fid

            found = False
            new_lines = []
            for line in env_lines:
                if line.startswith("GOOGLE_DRIVE_FOLDER_ID="):
                    new_lines.append(f"GOOGLE_DRIVE_FOLDER_ID={clean_fid}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"GOOGLE_DRIVE_FOLDER_ID={clean_fid}\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        from ingestion.drive_client import GoogleDriveManager
        GoogleDriveManager._course_cache.clear()
        dm = GoogleDriveManager()
        return {
            "success": True,
            "message": "Configurações do Google Drive salvas com sucesso!",
            "status": dm.get_status()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao salvar configurações do Drive: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")

# ----------------- ROTAS DO TELEGRAM & ESTUDOS -----------------

@app.get("/api/telegram/folders")
async def get_folders():
    tg = TelegramManager()
    return await tg.list_folders()

@app.get("/api/telegram/groups")
async def get_groups(folder: Optional[str] = None):
    target = folder or settings.TELEGRAM_TARGET_FOLDER
    tg = TelegramManager()
    try:
        return await tg.list_groups_in_folder(target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/telegram/groups/summary")
async def get_groups_summary(folder: Optional[str] = None):
    """Retorna os canais com contagem de aulas, pendências, horas e breakdown por agente."""
    target = folder or settings.TELEGRAM_TARGET_FOLDER
    tg = TelegramManager()
    try:
        groups = await tg.list_groups_in_folder(target)
        
        # Carrega agentes para mapear IDs e nomes
        agents_map = {}
        for f in settings.AGENTS_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as file:
                    adata = json.load(file)
                    agents_map[adata["id"]] = adata
            except Exception:
                continue

        summaries = []
        for g in groups:
            gid = g["id"]
            gtitle = g.get("title", "")
            try:
                videos = await tg.list_videos_in_group(gid, limit=150)
                total = len(videos)
                studied = sum(1 for v in videos if v.get("is_studied"))
                pending = total - studied
                total_duration_sec = sum(v.get("duration_seconds", 0) for v in videos)
                total_size_bytes = sum(v.get("file_size_bytes", 0) for v in videos)

                # Breakdown por agente com contagem precisa e porcentagem
                agents_breakdown = {}
                gt_clean = gtitle.strip().lower()

                for aid, adata in agents_map.items():
                    aname = adata.get("name", "Especialista")
                    avatar = adata.get("avatar", "👨‍💻")

                    # Coleta aulas únicas que este agente estudou deste canal
                    studied_lessons_for_agent = set()

                    # 1. A partir das sources do perfil do agente
                    for src in adata.get("sources", []):
                        src_gname = (src.get("group_name") or "").strip().lower()
                        if src_gname and (src_gname in gt_clean or gt_clean in src_gname):
                            for les in src.get("lessons", []):
                                lid = str(les.get("lesson_id", "")).strip().lower()
                                clean_lid = lid.replace("video_", "").replace("aula_", "")
                                if clean_lid:
                                    studied_lessons_for_agent.add(clean_lid)
                            if not src.get("lessons") and src.get("videos_count", 0) > 0:
                                for i in range(src.get("videos_count", 0)):
                                    studied_lessons_for_agent.add(f"count_{i}")

                    # 2. A partir dos vídeos listados com studied_by
                    for v in videos:
                        if v.get("is_studied") and v.get("studied_by"):
                            if v["studied_by"] == aname or v["studied_by"] == aid:
                                mid = str(v.get("message_id", ""))
                                fname = str(v.get("file_name", "")).strip().lower()
                                if mid:
                                    studied_lessons_for_agent.add(mid)
                                elif fname:
                                    studied_lessons_for_agent.add(fname)

                    # Garante que não exceda o total de vídeos do canal nem o total estudado no canal
                    count = min(len(studied_lessons_for_agent), total)
                    if studied > 0:
                        count = min(count, studied)
                    pct = round((count / total * 100)) if total > 0 else 0

                    agents_breakdown[aid] = {
                        "agent_id": aid,
                        "agent_name": aname,
                        "avatar": avatar,
                        "studied_count": count,
                        "percent": pct
                    }

                summaries.append({
                    **g,
                    "total_videos": total,
                    "studied_videos": studied,
                    "pending_videos": pending,
                    "duration_hours": round(total_duration_sec / 3600.0, 1),
                    "size_gb": round(total_size_bytes / (1024 * 1024 * 1024), 2),
                    "agents_studied": agents_breakdown,
                    "studied_agents_list": [ab["agent_name"] for ab in agents_breakdown.values() if ab["studied_count"] > 0]
                })
            except Exception:
                summaries.append({
                    **g,
                    "total_videos": 0,
                    "studied_videos": 0,
                    "pending_videos": 0,
                    "duration_hours": 0.0,
                    "size_gb": 0.0,
                    "agents_studied": {},
                    "studied_agents_list": []
                })
        return summaries
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/telegram/groups/{group_id}/videos")
async def get_videos(group_id: int):
    tg = TelegramManager()
    try:
        return await tg.list_videos_in_group(group_id, limit=50)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/study/start")
def start_study(req: StartStudyRequest, background_tasks: BackgroundTasks):
    global study_state
    if study_state["is_studying"]:
        raise HTTPException(status_code=409, detail="Já existe um estudo em andamento!")
    
    background_tasks.add_task(run_study_pipeline, req)
    return {"message": f"Estudo iniciado para o agente '{req.agent_id}' na aula '{req.file_name}'"}

@app.get("/api/study/status")
def get_study_status():
    qm = StudyQueueManager()
    queue_state = qm.get_status()
    # Compatibilidade com interface anterior e integração com nova fila
    if queue_state["is_busy"] and queue_state["active_item"]:
        act = queue_state["active_item"]
        return {
            "is_studying": True,
            "agent_id": act.get("agent_id"),
            "video_title": act.get("file_name"),
            "step": act.get("status"),
            "progress_pct": act.get("progress_pct", 0.0),
            "error_message": act.get("error_message"),
            "current_step_text": act.get("current_step_text")
        }
# ----------------- ÁREAS DA VIDA & GESTORES (CRUD & COCKPIT) -----------------

def load_all_areas() -> List[Dict[str, Any]]:
    areas = []
    agents = load_all_agents()
    agent_map = {a["id"]: a for a in agents}

    for f in settings.AREAS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
            area_id = data.get("id")
            
            # Agentes associados a esta área da vida
            area_agents = [
                a for a in agents 
                if a.get("area_id") == area_id 
                or a["id"] in data.get("subagent_ids", []) 
                or a["id"] == data.get("manager_agent_id")
            ]
            
            manager_id = data.get("manager_agent_id")
            manager_agent = agent_map.get(manager_id) if manager_id else None
            
            total_hours = sum(a.get("total_hours_studied", 0.0) for a in area_agents)
            unique_topics = set()
            total_lessons = 0
            for a in area_agents:
                for t in a.get("topics_mastered", []):
                    unique_topics.add(t)
                for s in a.get("sources", []):
                    total_lessons += len(s.get("lessons", []))

            enriched = {
                **data,
                "manager": manager_agent,
                "agents_count": len(area_agents),
                "agents": area_agents,
                "total_hours_studied": round(total_hours, 2),
                "skills_count": len(unique_topics),
                "lessons_count": total_lessons,
                "memory_concepts_count": len(unique_topics) * 8 + total_lessons * 12
            }
            areas.append(enriched)
        except Exception:
            continue

    areas.sort(key=lambda x: x.get("name", ""))
    return areas

def get_area_profile(area_id: str) -> Optional[Dict[str, Any]]:
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    if not area_file.exists():
        return None
    try:
        with open(area_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

@app.get("/api/areas")
def get_areas():
    """Retorna todas as Áreas da Vida com métricas consolidadas e gestores vinculados."""
    return load_all_areas()

@app.post("/api/areas")
def create_area(req: CreateAreaRequest):
    """Cria uma nova Área da Vida."""
    area_id = req.id or re.sub(r'[^a-zA-Z0-9_]', '_', req.name.lower()).strip('_')
    out_file = settings.AREAS_DIR / f"{area_id}.json"
    if out_file.exists():
        raise HTTPException(status_code=400, detail="Já existe uma área com este identificador")

    area = AreaProfile(
        id=area_id,
        name=req.name,
        icon=req.icon,
        color=req.color,
        description=req.description,
        manager_agent_id=req.manager_agent_id,
        subagent_ids=[req.manager_agent_id] if req.manager_agent_id else [],
        health_score=req.health_score,
        routines_count=req.routines_count,
        projects_count=req.projects_count,
        meetings_count=req.meetings_count
    )
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(area.model_dump(), f, indent=2, ensure_ascii=False, default=str)

    if req.manager_agent_id:
        agent = get_agent_profile(req.manager_agent_id)
        if agent:
            agent.area_id = area_id
            agent.agent_type = "gestor"
            save_agent(agent)

    return area

@app.get("/api/areas/{area_id}")
def get_area_detail(area_id: str):
    """Retorna detalhes de uma Área da Vida incluindo seu Gestor e Especialistas Técnicos."""
    area_data = get_area_profile(area_id)
    if not area_data:
        raise HTTPException(status_code=404, detail="Área da vida não encontrada")

    agents = load_all_agents()
    agent_map = {a["id"]: a for a in agents}
    area_agents = [
        a for a in agents 
        if a.get("area_id") == area_id 
        or a["id"] in area_data.get("subagent_ids", []) 
        or a["id"] == area_data.get("manager_agent_id")
    ]
    manager_agent = agent_map.get(area_data.get("manager_agent_id"))

    return {
        **area_data,
        "manager": manager_agent,
        "agents": area_agents,
        "agents_count": len(area_agents)
    }

@app.put("/api/areas/{area_id}")
def update_area(area_id: str, req: UpdateAreaRequest):
    """Atualiza dados e métricas de uma Área da Vida."""
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    if not area_file.exists():
        raise HTTPException(status_code=404, detail="Área da vida não encontrada")

    with open(area_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    for k, v in req.model_dump(exclude_unset=True).items():
        if v is not None:
            data[k] = v

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(area_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if req.manager_agent_id:
        agent = get_agent_profile(req.manager_agent_id)
        if agent:
            agent.area_id = area_id
            agent.agent_type = "gestor"
            save_agent(agent)

    return data

@app.delete("/api/areas/{area_id}")
def delete_area(area_id: str):
    """Remove uma Área da Vida e desvincula os agentes."""
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    if not area_file.exists():
        raise HTTPException(status_code=404, detail="Área da vida não encontrada")

    os.remove(area_file)
    for f in settings.AGENTS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                adata = json.load(fp)
            if adata.get("area_id") == area_id:
                adata["area_id"] = None
                with open(f, "w", encoding="utf-8") as fp:
                    json.dump(adata, fp, indent=2, ensure_ascii=False)
        except Exception:
            pass
    return {"success": True, "message": f"Área '{area_id}' removida com sucesso"}

@app.post("/api/areas/{area_id}/assign-agent")
def assign_agent_to_area(area_id: str, req: AssignAreaAgentRequest):
    """Vincula um agente a uma área da vida, definindo seu papel (Gestor ou Técnico)."""
    area_file = settings.AREAS_DIR / f"{area_id}.json"
    if not area_file.exists():
        raise HTTPException(status_code=404, detail="Área não encontrada")
    agent = get_agent_profile(req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    agent.area_id = area_id
    agent.agent_type = req.agent_type
    save_agent(agent)

    with open(area_file, "r", encoding="utf-8") as f:
        area_data = json.load(f)
    if req.agent_type == "gestor":
        area_data["manager_agent_id"] = agent.id
    if agent.id not in area_data.get("subagent_ids", []):
        area_data.setdefault("subagent_ids", []).append(agent.id)
    with open(area_file, "w", encoding="utf-8") as f:
        json.dump(area_data, f, indent=2, ensure_ascii=False)

    return {"success": True, "message": f"Agente '{agent.name}' vinculado como {req.agent_type} da área!"}

@app.get("/api/areas/{area_id}/graph")
def get_area_knowledge_graph(area_id: str):
    """Retorna o grafo estelar de conhecimento (constelação) específico da Área da Vida.
    Estrutura: Área (Super Hub) -> Gestores & Especialistas -> Cursos -> Aulas & Habilidades."""
    area_data = get_area_profile(area_id)
    if not area_data:
        raise HTTPException(status_code=404, detail="Área não encontrada")

    all_agents = load_all_agents()
    area_agents = [
        a for a in all_agents 
        if a.get("area_id") == area_id 
        or a.get("id") == area_data.get("manager_agent_id") 
        or a.get("id") in area_data.get("subagent_ids", [])
    ]

    nodes = []
    links = []
    node_ids = set()
    area_color = area_data.get("color", "#06b6d4")

    # 1. Super Hub da Área (Sol Central da Constelação)
    hub_id = f"hub_{area_id}"
    nodes.append({
        "id": hub_id,
        "label": area_data.get("name", "Área"),
        "type": "area_hub",
        "icon": area_data.get("icon", "🎯"),
        "color": area_color,
        "size": 30,
        "health": area_data.get("health_score", 90),
        "agents_count": len(area_agents)
    })
    node_ids.add(hub_id)

    # 2. Agentes da Área (Planetas Principais)
    for ag in area_agents:
        aid = ag["id"]
        is_mgr = (aid == area_data.get("manager_agent_id"))
        ag_color = "#f59e0b" if is_mgr else area_color

        nodes.append({
            "id": aid,
            "label": ag.get("name", aid),
            "type": "agent",
            "role": ag.get("role", "Especialista"),
            "avatar": ag.get("avatar", "👨‍💻"),
            "color": ag_color,
            "size": 22 if is_mgr else 18,
            "is_manager": is_mgr,
            "hours": ag.get("total_hours_studied", 0),
            "videos_count": ag.get("total_videos_studied", 0),
            "status": ag.get("status", "ativo")
        })
        node_ids.add(aid)

        # Conexão da Área para o Agente
        links.append({
            "source": hub_id,
            "target": aid,
            "color": area_color,
            "distance": 95,
            "width": 2.5 if is_mgr else 1.5
        })

        # 3. Cursos e Aulas Estudadas pelo Agente
        course_nodes = {}
        for src in ag.get("sources", []):
            g_name = src.get("group_name") or f"Curso {src.get('group_id')}"
            cid = f"course_{abs(hash(g_name)) % 1000000}"
            if cid not in course_nodes:
                course_nodes[cid] = {
                    "id": cid,
                    "label": g_name,
                    "type": "course",
                    "color": "#818cf8",
                    "size": 14,
                    "agent_id": aid,
                    "lessons_count": len(src.get("lessons", []))
                }
                nodes.append(course_nodes[cid])
                node_ids.add(cid)

            links.append({
                "source": aid,
                "target": cid,
                "color": "rgba(129, 140, 248, 0.6)",
                "distance": 68
            })

            # Aulas Estudadas
            for les in src.get("lessons", []):
                lid = f"les_{aid}_{les.get('lesson_id')}"
                if lid not in node_ids:
                    nodes.append({
                        "id": lid,
                        "label": les.get("title") or f"Aula {les.get('lesson_id')}",
                        "type": "lesson",
                        "status": "completed",
                        "color": "#22c55e",
                        "size": 7,
                        "course_id": cid,
                        "agent_id": aid,
                        "duration_seconds": les.get("duration_seconds", 0)
                    })
                    node_ids.add(lid)
                    links.append({
                        "source": cid,
                        "target": lid,
                        "color": "rgba(34, 197, 94, 0.45)",
                        "distance": 36
                    })

        # 4. Habilidades / Tópicos dominados
        for top in ag.get("topics_mastered", []):
            top_clean = top.strip()
            if not top_clean:
                continue
            tid = f"top_{aid}_{abs(hash(top_clean.lower())) % 1000000}"
            if tid not in node_ids:
                nodes.append({
                    "id": tid,
                    "label": top_clean,
                    "type": "topic",
                    "color": "#38bdf8",
                    "size": 8,
                    "agent_id": aid
                })
                node_ids.add(tid)
                links.append({
                    "source": aid,
                    "target": tid,
                    "color": "rgba(56, 189, 248, 0.4)",
                    "distance": 50
                })

    return {
        "area": area_data,
        "nodes": nodes,
        "links": links
    }

@app.get("/api/agents/{agent_id}/spec")
def get_agent_spec(agent_id: str):
    """Gera a especificação formal de agent.md e modular skill.md para o especialista."""
    agent = get_agent_profile(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    area = None
    if agent.area_id:
        area_file = settings.AREAS_DIR / f"{agent.area_id}.json"
        if area_file.exists():
            with open(area_file, "r", encoding="utf-8") as f:
                area = json.load(f)

    agent_type_label = "Gestor Executivo & Orquestrador" if agent.agent_type == "gestor" else "Especialista Técnico de Execução"
    area_name = area.get("name") if area else "Geral"
    seniority = agent.get_seniority_info()

    agent_md = f"""# Agente: {agent.name}
**ID**: `{agent.id}`  
**Papel**: {agent.role}  
**Hierarquia**: {agent_type_label}  
**Área da Vida**: {area_name}  
**Senioridade**: {seniority.get('rank')} ({agent.total_hours_studied}h estudadas)

---

## 🎯 Contexto e Diretrizes de Negócio
- Responsável estratégico pela área de **{area_name}**.
- Tom de voz: Assertivo, analítico, focado em resultados tangíveis e métricas.
- Alinhado aos objetivos de alta performance e automação da organização.

## 🔄 Protocolo de Escalação & Delegação
1. **Comunicação Inter-Gestores**:
   - Este agente pode debater diretamente na Mesa Redonda do Oráculo com os demais gestores de área.
2. **Delegação Técnica**:
   - Para execução de tarefas operacionais profundas, consulta suas ferramentas e aciona os subagentes técnicos especializados.
3. **Escalação para Decisão Humana (Human-in-the-Loop)**:
   - Despesas financeiras, limites de verba de tráfego pago ou alterações estruturais exigem confirmação do Usuário.

## 💡 Habilidades & Tópicos Dominados ({len(agent.topics_mastered)})
"""
    for top in agent.topics_mastered:
        agent_md += f"- `{top}`\n"

    skills = []
    for top in agent.topics_mastered[:15]:
        slug = re.sub(r'[^a-zA-Z0-9_]', '_', top.lower()).strip('_')
        skill_md = f"""# Skill: {top}
**Agente Responsável**: {agent.name}  
**Status**: Dominado via Absorção de Cursos  

### 📋 Descrição e Escopo
Aplica o conhecimento estruturado de **{top}** para resolução de problemas reais, geração de código ou recomendações táticas.

### ⚙️ Entradas Requeridas
- Contexto da solicitação ou parâmetros da tarefa
- Dados do projeto ou código pré-existente

### 📤 Artefatos de Saída
- Código limpo, documento `.md`, arquitetura técnica ou plano de ação.
"""
        skills.append({
            "name": slug,
            "title": top,
            "markdown": skill_md
        })

    # Carrega arquivo skill.md real se existir
    real_skill_file = settings.DATA_DIR / "skills" / agent_id / "SKILL.md"
    real_skill_content = ""
    if real_skill_file.exists():
        try:
            with open(real_skill_file, "r", encoding="utf-8") as sf:
                real_skill_content = sf.read()
        except Exception:
            pass

    if not real_skill_content:
        # Fallback concatenando as skills dos tópicos
        real_skill_content = f"# Skill: {agent.name}\n**ID**: `{agent.id}`\n**Papel**: {agent.role}\n**Hierarquia**: {agent_type_label}\n\n" + "\n\n---\n\n".join([s["markdown"] for s in skills])

    return {
        "agent": agent.model_dump(),
        "area": area,
        "agent_md": agent_md,
        "skill_md": real_skill_content,
        "skills": skills
    }

@app.put("/api/agents/{agent_id}/spec")
def update_agent_spec(agent_id: str, req: UpdateAgentSpecRequest):
    """Permite editar diretamente o skill.md e agent.md do funcionário."""
    agent = get_agent_profile(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    skill_dir = settings.DATA_DIR / "skills" / agent_id
    skill_dir.mkdir(parents=True, exist_ok=True)

    if req.skill_md is not None:
        skill_file = skill_dir / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as sf:
            sf.write(req.skill_md)

    if req.agent_md is not None:
        agent_file = skill_dir / "AGENT.md"
        with open(agent_file, "w", encoding="utf-8") as af:
            af.write(req.agent_md)

    return {"message": f"Especificação de {agent.name} salva com sucesso!", "agent_id": agent_id}

# ----------------- GRAFO DE CONHECIMENTO (OBSIDIAN GRAPH VIEW) -----------------

@app.get("/api/knowledge/graph")
async def get_knowledge_graph():
    """Retorna os nós e conexões da base de conhecimento (estilo Obsidian Graph View)
    conectando Especialistas -> Cursos -> Aulas (concluídas e pendentes) -> Habilidades."""
    agents = load_all_agents()
    qm = StudyQueueManager()
    queue_status = qm.get_status()

    nodes = []
    links = []
    node_ids = set()

    agent_colors = {
        "agent_claude_code": "#10b981",
        "agent_jim_kwik": "#a855f7",
        "agent_jordan_belfort": "#f59e0b"
    }

    course_nodes = {}
    topic_nodes = {}

    # 1. Nós dos Especialistas (Hubs Centrais)
    for a in agents:
        aid = a["id"]
        area_id = a.get("area_id")
        is_gestor = a.get("agent_type") == "gestor"
        color = "#f59e0b" if is_gestor else agent_colors.get(aid, "#818cf8")
        nodes.append({
            "id": aid,
            "label": a["name"],
            "type": "agent",
            "role": a.get("role", "Especialista"),
            "avatar": a.get("avatar", "👨‍💻"),
            "color": color,
            "size": 24 if is_gestor else 18,
            "hours": a.get("total_hours_studied", 0),
            "status": a.get("status", "ativo"),
            "area_id": area_id,
            "agent_type": a.get("agent_type", "tecnico")
        })
        node_ids.add(aid)

        # Cursos estudados deste agente
        for src in a.get("sources", []):
            g_name = src.get("group_name", "Curso")
            cid = f"course_{abs(hash(g_name)) % 1000000}"
            if cid not in course_nodes:
                course_nodes[cid] = {
                    "id": cid,
                    "label": g_name,
                    "type": "course",
                    "color": "#818cf8",
                    "size": 15,
                    "agent_id": aid,
                    "area_id": area_id,
                    "lessons_count": len(src.get("lessons", []))
                }
                nodes.append(course_nodes[cid])
                node_ids.add(cid)

            links.append({
                "source": aid,
                "target": cid,
                "color": color,
                "distance": 85
            })

            # Aulas já estudadas deste curso
            for les in src.get("lessons", []):
                lid = f"lesson_{les.get('lesson_id')}"
                if lid not in node_ids:
                    nodes.append({
                        "id": lid,
                        "label": les.get("title") or les.get("lesson_id"),
                        "type": "lesson",
                        "status": "completed",
                        "color": "#22c55e",
                        "size": 7,
                        "course_id": cid,
                        "agent_id": aid,
                        "area_id": area_id,
                        "duration_seconds": les.get("duration_seconds", 0)
                    })
                    node_ids.add(lid)
                    links.append({
                        "source": cid,
                        "target": lid,
                        "color": "rgba(34, 197, 94, 0.45)",
                        "distance": 45
                    })

        # Habilidades/Tópicos dominados
        for top in a.get("topics_mastered", []):
            top_clean = top.strip()
            if not top_clean:
                continue
            tid = f"topic_{abs(hash(top_clean.lower())) % 1000000}"
            if tid not in topic_nodes:
                topic_nodes[tid] = {
                    "id": tid,
                    "label": top_clean,
                    "type": "topic",
                    "color": "#38bdf8",
                    "size": 9,
                    "area_id": area_id,
                    "source_agent_id": aid
                }
                nodes.append(topic_nodes[tid])
                node_ids.add(tid)
            links.append({
                "source": aid,
                "target": tid,
                "color": "rgba(56, 189, 248, 0.35)",
                "distance": 90
            })

    agent_area_map = {a["id"]: a.get("area_id") for a in agents}

    # 2. Cursos atribuídos na fila ativa (para que o assunto maior já exista no grafo)
    active_items_list = queue_status.get("active_items", [])
    active_ids = {it.get("id"): it for it in active_items_list}

    for it in qm.queue:
        g_name = it.group_name or f"Canal {it.group_id}"
        cid = f"course_{abs(hash(g_name)) % 1000000}"
        if cid not in node_ids:
            course_nodes[cid] = {
                "id": cid,
                "label": g_name,
                "type": "course",
                "color": "#818cf8",
                "size": 16,
                "agent_id": it.agent_id,
                "area_id": agent_area_map.get(it.agent_id),
                "lessons_count": sum(1 for q in qm.queue if q.group_id == it.group_id)
            }
            nodes.append(course_nodes[cid])
            node_ids.add(cid)
            if it.agent_id in node_ids:
                links.append({
                    "source": it.agent_id,
                    "target": cid,
                    "color": agent_colors.get(it.agent_id, "#818cf8"),
                    "distance": 90
                })

    # 3. Apenas as aulas em processamento ativo acendem no grafo (máx 8 workers)
    # Aulas pendentes aguardam na esteira e acendem assim que concluídas!
    for act in active_items_list:
        vid = f"active_{act.get('id')}"
        if vid in node_ids:
            continue
        g_name = act.get("group_name") or f"Canal {act.get('group_id')}"
        cid = f"course_{abs(hash(g_name)) % 1000000}"
        act_agent_id = act.get("agent_id")
        if cid in node_ids:
            nodes.append({
                "id": vid,
                "label": act.get("file_name", "Aula"),
                "type": "lesson",
                "status": "processing",
                "color": "#f59e0b",
                "size": 8,
                "course_id": cid,
                "agent_id": act_agent_id,
                "area_id": agent_area_map.get(act_agent_id),
                "progress_pct": act.get("progress_pct", 5.0)
            })
            node_ids.add(vid)
            links.append({
                "source": cid,
                "target": vid,
                "color": "rgba(245, 158, 11, 0.7)",
                "distance": 35
            })

    total_completed = len([n for n in nodes if n["type"] == "lesson" and n.get("status") == "completed"])
    total_processing = len([n for n in nodes if n["type"] == "lesson" and n.get("status") == "processing"])

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "agents_count": len(agents),
            "courses_count": len(course_nodes),
            "nodes_count": len(nodes),
            "links_count": len(links),
            "completed_lessons": total_completed,
            "active_lessons": total_processing,
            "pending_lessons": queue_status.get("pending_count", len(qm.queue))
        }
    }

# ----------------- ROTAS DA FILA DE ESTUDOS & GRUPOS -----------------

@app.get("/api/study/queue")
async def get_study_queue():
    return StudyQueueManager().get_status()

@app.post("/api/study/queue")
async def enqueue_study(req: EnqueueStudyRequest):
    qm = StudyQueueManager()
    item = await qm.enqueue(
        agent_id=req.agent_id,
        group_id=req.group_id,
        group_name=req.group_name,
        message_id=req.message_id,
        file_name=req.file_name,
        tier=req.tier
    )
    return {"message": "Aula adicionada à fila de estudos", "item": item.model_dump()}

@app.post("/api/study/group")
async def enqueue_group_study(req: EnqueueGroupRequest):
    qm = StudyQueueManager()
    items = await qm.enqueue_group(
        agent_id=req.agent_id,
        group_id=req.group_id,
        group_name=req.group_name,
        tier=req.tier,
        only_pending=req.only_pending
    )
    # Atualiza sessão salva para recuperação rápida
    try:
        session_file = settings.DATA_DIR / "last_study_session.json"
        data = {}
        if session_file.exists():
            with open(session_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        assignments = data.get("assignments", [])
        assignments = [a for a in assignments if a.get("agent_id") != req.agent_id]
        assignments.append({
            "agent_id": req.agent_id,
            "group_id": req.group_id,
            "group_name": req.group_name,
            "tier": req.tier
        })
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["tier"] = req.tier
        data["assignments"] = assignments
        with open(session_file, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
    except Exception:
        pass

    return {
        "message": f"{len(items)} aulas adicionadas à fila de estudos com sucesso!",
        "count": len(items)
    }

@app.post("/api/study/groups/batch")
async def enqueue_groups_batch_route(req: EnqueueBatchGroupsRequest):
    """Enfileira todas as aulas pendentes de múltiplos canais selecionados de uma só vez para um ou mais especialistas."""
    tg = TelegramManager()
    all_groups = await tg.list_groups_in_folder(settings.TELEGRAM_TARGET_FOLDER)
    selected_groups = [g for g in all_groups if g["id"] in req.group_ids]
    
    if not selected_groups:
        raise HTTPException(status_code=400, detail="Nenhum canal válido selecionado")

    target_agents = []
    if req.agent_ids and len(req.agent_ids) > 0:
        target_agents = req.agent_ids
    elif req.agent_id:
        target_agents = [req.agent_id]
    else:
        raise HTTPException(status_code=400, detail="Nenhum especialista foi selecionado para o estudo")

    qm = StudyQueueManager()
    total_enqueued = []
    for aid in target_agents:
        items = await qm.enqueue_multiple_groups(
            agent_id=aid,
            groups=selected_groups,
            tier=req.tier,
            only_pending=req.only_pending,
            start_worker=False
        )
        total_enqueued.extend(items)

    qm.interleave_queued_items()
    qm.ensure_worker()

    # Salva os parâmetros da sessão para permitir recuperação rápida em caso de suspensão/reinício
    try:
        session_file = settings.DATA_DIR / "last_study_session.json"
        with open(session_file, "w", encoding="utf-8") as fp:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_ids": target_agents,
                "group_ids": [g["id"] for g in selected_groups],
                "tier": req.tier,
                "only_pending": req.only_pending
            }, fp, indent=2)
    except Exception:
        pass

    return {
        "message": f"{len(total_enqueued)} aulas de {len(selected_groups)} canais adicionadas à fila para {len(target_agents)} especialista(s)!",
        "count": len(total_enqueued),
        "channels_count": len(selected_groups),
        "agents_count": len(target_agents)
    }

@app.post("/api/study/queue/pause")
def pause_study_queue_route():
    """Pausa imediatamente a fila de estudos."""
    qm = StudyQueueManager()
    qm.pause()
    return {
        "status": "paused",
        "message": "Fila de estudos pausada com sucesso. Nenhum novo vídeo será baixado ou processado."
    }

@app.post("/api/study/queue/resume")
async def resume_study_queue_route():
    """Retoma os estudos interrompidos (ex: fechamento de tampa do notebook ou queda de conexão)."""
    qm = StudyQueueManager()
    qm.resume()

    # 1. Se há itens com erro ou pendentes na fila em memória, reativa-os imediatamente
    resumed_items = 0
    existing_ids = {it.id for it in qm.queue}

    for it in qm.queue:
        if it.status in ["error", "downloading", "processing"]:
            it.status = "queued"
            it.error_message = None
            it.current_step_text = "Retomando estudo..."
            it.progress_pct = 0.0
            qm._db_update(it)
            resumed_items += 1

    # Recupera também itens com erro que estejam persistidos no banco de dados SQLite
    for db_it in qm._db_get_all():
        if db_it.id not in existing_ids and db_it.status == "error":
            db_it.status = "queued"
            db_it.error_message = None
            db_it.current_step_text = "Retomando estudo..."
            db_it.progress_pct = 0.0
            qm.queue.append(db_it)
            qm._db_update(db_it)
            existing_ids.add(db_it.id)
            resumed_items += 1

    if resumed_items > 0:
        qm.interleave_queued_items()
        qm.ensure_worker()
        return {
            "status": "resumed",
            "count": resumed_items,
            "message": f"Retomando {resumed_items} aulas interrompidas de onde pararam!"
        }

    # Se há aulas que já estavam como 'queued' na fila aguardando processamento
    queued_pending = [it for it in qm.queue if it.status == "queued"]
    if queued_pending:
        qm.interleave_queued_items()
        qm.ensure_worker()
        return {
            "status": "resumed",
            "count": len(queued_pending),
            "message": f"Iniciando estudo de {len(queued_pending)} aulas pendentes na fila!"
        }

    # 2. Se a fila estava vazia ou zerada, busca a última sessão salva em disco
    session_file = settings.DATA_DIR / "last_study_session.json"
    if session_file.exists():
        try:
            with open(session_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            total_enqueued = []
            if "assignments" in data and isinstance(data["assignments"], list):
                for asg in data["assignments"]:
                    items = await qm.enqueue_group(
                        agent_id=asg["agent_id"],
                        group_id=asg["group_id"],
                        group_name=asg.get("group_name") or f"Canal {asg['group_id']}",
                        tier=asg.get("tier") or data.get("tier", "audio_only"),
                        only_pending=True,
                        start_worker=False
                    )
                    total_enqueued.extend(items)
            else:
                tg = TelegramManager()
                all_groups = await tg.list_groups_in_folder(settings.TELEGRAM_TARGET_FOLDER)
                selected_groups = [g for g in all_groups if g["id"] in data.get("group_ids", [])]
                target_agents = data.get("agent_ids", [])
                for aid in target_agents:
                    items = await qm.enqueue_multiple_groups(
                        agent_id=aid,
                        groups=selected_groups,
                        tier=data.get("tier", "audio_only"),
                        only_pending=True,
                        start_worker=False
                    )
                    total_enqueued.extend(items)
            qm.interleave_queued_items()
            qm.ensure_worker()
            return {
                "status": "resumed",
                "count": len(total_enqueued),
                "message": f"Última sessão recuperada com sucesso! {len(total_enqueued)} aulas pendentes enviadas para os especialistas."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao recuperar sessão: {str(e)}")

    return {
        "status": "empty",
        "count": 0,
        "message": "Nenhum estudo interrompido encontrado para retomar."
    }

@app.delete("/api/study/queue/{item_id}")
def delete_queue_item(item_id: str):
    qm = StudyQueueManager()
    ok = qm.remove(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item não encontrado ou já em processamento")
    return {"message": "Item removido da fila"}

@app.post("/api/study/queue/clear")
def clear_queue_finished():
    StudyQueueManager().clear_finished()
    return {"message": "Itens concluídos limpos da fila"}

# ----------------- ROTAS DE TELEMETRIA DE TOKENS -----------------

@app.get("/api/tokens/stats")
def get_tokens_stats_route():
    return get_token_stats()

@app.post("/api/tokens/budget")
def set_tokens_budget_route(req: SetBudgetRequest):
    set_daily_budget(req.daily_budget)
    return {"message": "Orçamento diário atualizado", "stats": get_token_stats()}

class SetPlanTierRequest(BaseModel):
    plan_tier: str  # "free_tier" ou "paid_tier"

@app.post("/api/tokens/plan")
def set_tokens_plan_route(req: SetPlanTierRequest):
    from utils.token_tracker import set_plan_tier
    set_plan_tier(req.plan_tier)
    return {"message": "Plano de cota atualizado com sucesso", "stats": get_token_stats()}

@app.get("/api/knowledge")
def get_knowledge(agent_id: Optional[str] = None):
    """Lista as aulas estudadas. Se filtrado por agente, mostra apenas o que aquele agente aprendeu."""
    studied_lesson_ids = set()
    if agent_id:
        profile = get_agent_profile(agent_id)
        if profile:
            for s in profile.sources:
                for l in s.lessons:
                    studied_lesson_ids.add(l.lesson_id)

    knowledge_list = []
    for json_file in settings.PROCESSED_DIR.glob("**/*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                v_id = doc.get("video_id")
                if agent_id and v_id not in studied_lesson_ids:
                    continue

                duration_sec = doc.get("duration_seconds", 0)
                dur_min = round(duration_sec / 60, 1)
                knowledge_list.append({
                    "video_id": v_id,
                    "title": doc.get("title"),
                    "group_name": doc.get("group_name"),
                    "summary": doc.get("summary"),
                    "topics": doc.get("topics", []),
                    "duration_minutes": dur_min,
                    "segments_count": len(doc.get("segments", [])),
                    "codes_count": len(doc.get("extracted_codes", []))
                })
        except Exception:
            continue
    return knowledge_list

def call_gemini_chat_resilient(prompt: str, config: Optional[Any] = None) -> Any:
    """Chama a API do Gemini com rotação de chaves e fallback resiliente de modelos em caso de 503/429."""
    from google import genai
    keys = settings.GEMINI_API_KEYS or [settings.GEMINI_API_KEY]
    models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]
    last_err = None

    for attempt in range(len(keys) * 2):
        key = keys[attempt % len(keys)]
        cl = genai.Client(api_key=key)
        for model_name in models_to_try:
            try:
                if config:
                    return cl.models.generate_content(model=model_name, contents=prompt, config=config)
                return cl.models.generate_content(model=model_name, contents=prompt)
            except Exception as err:
                last_err = err
                err_msg = str(err).upper()
                if any(x in err_msg for x in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "HIGH DEMAND"]):
                    import time
                    time.sleep(1.0)
                    continue
                else:
                    break

    raise RuntimeError(f"Falha ao consultar o Gemini após múltiplas tentativas: {last_err}")

# ----------------- SALA DO ORÁCULO (DEBATE & 1-ON-1) -----------------

@app.post("/api/oracle/chat")
async def oracle_chat(req: OracleChatRequest):
    try:
        from google import genai
        from google.genai import types

        agents = load_all_agents()

        # 1. Modo de conversa com 1 Agente Específico
        if req.agent_id:
            target_agent = next((a for a in agents if a["id"] == req.agent_id), None)
            if not target_agent:
                raise HTTPException(status_code=404, detail="Agente não encontrado")

            # Coleta fontes apenas dos cursos/grupos desse agente
            agent_groups = [s["group_name"].lower() for s in target_agent.get("sources", [])]
            relevant_context = []
            extracted_codes = []
            citations = []

            for json_file in settings.PROCESSED_DIR.glob("**/*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    if doc.get("group_name", "").lower() in agent_groups:
                        citations.append({
                            "title": doc.get("title"),
                            "group": doc.get("group_name"),
                            "timestamps": [f"{s.get('start_time')} - {s.get('end_time')}" for s in doc.get("segments", [])[:2]]
                        })
                        for c in doc.get("extracted_codes", []):
                            extracted_codes.append(c)
                        relevant_context.append(f"Aula '{doc.get('title')}': {doc.get('summary')}")
                except Exception:
                    continue

            prompt = f"""
Você é {target_agent['name']} ({target_agent['role']}), um agente especialista.
Você estudou profundamente os cursos: {', '.join(agent_groups) if agent_groups else 'geral'}.
Tópicos que você domina: {', '.join(target_agent.get('topics_mastered', []))}.

Diretrizes de resposta:
- Responda em primeira pessoa mantendo seu tom técnico e especialista.
- Seja DIRETO, CONCISO e OBJETIVO. Vá direto ao ponto sem enrolações ou introduções desnecessárias.
- Use negrito de forma natural e limpa para destacar conceitos essenciais. Evite poluição de asteriscos redundantes.
- Se relevante, cite a aula e o minuto exato de onde extraiu a solução.

Pergunta do usuário: "{req.query}"

Suas fontes de estudo:
{chr(10).join(relevant_context)}
"""
            res = call_gemini_chat_resilient(prompt)
            
            # Registra telemetria de tokens
            if hasattr(res, "usage_metadata") and res.usage_metadata:
                try:
                    record_tokens(
                        source="oracle_chat",
                        details=f"1-on-1: {target_agent['name']}",
                        prompt_tokens=getattr(res.usage_metadata, "prompt_token_count", 0) or 0,
                        output_tokens=getattr(res.usage_metadata, "candidates_token_count", 0) or 0,
                        total_tokens=getattr(res.usage_metadata, "total_token_count", 0) or 0,
                        model="gemini-3.6-flash"
                    )
                except Exception:
                    pass

            return {
                "mode": "single",
                "speaker": target_agent["name"],
                "avatar": target_agent["avatar"],
                "role": target_agent["role"],
                "answer": res.text.strip(),
                "citations": citations,
                "extracted_codes": extracted_codes[:4]
            }

        # 2. Modo Oráculo (Mesa Redonda / Debate Multi-Agente)
        # Identifica os especialistas disponíveis
        active_agents = [a for a in agents if a.get("status") == "ativo"]
        if not active_agents:
            active_agents = agents[:3]

        agents_summary = "\n".join([
            f"- Agente: {a['name']} ({a['role']}, Avatar: {a['avatar']}). Cursos que estudou: {[s['group_name'] for s in a.get('sources', [])]}. Tópicos: {a.get('topics_mastered', [])}"
            for a in active_agents
        ])

        # Coleta todas as fontes estudadas
        knowledge_snippets = []
        citations = []
        extracted_codes = []
        for json_file in settings.PROCESSED_DIR.glob("**/*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    citations.append({
                        "title": doc.get("title"),
                        "group": doc.get("group_name"),
                        "timestamps": [f"{s.get('start_time')} - {s.get('end_time')}" for s in doc.get("segments", [])[:2]]
                    })
                    for c in doc.get("extracted_codes", []):
                        extracted_codes.append(c)
                    knowledge_snippets.append(f"Aula '{doc.get('title')}' do curso '{doc.get('group_name')}': {doc.get('summary')}")
            except Exception:
                continue

        debate_prompt = f"""
Você é o ORÁCULO, o agente orquestrador supremo.
O usuário enviou uma pergunta: "{req.query}"

Sua equipe de especialistas disponíveis:
{agents_summary}

Conhecimento acumulado nas aulas:
{chr(10).join(knowledge_snippets)}

INSTRUÇÃO IMPORTANTE:
Gere uma discussão/mesa-redonda dinâmica, fluida e CONCISA.
1. O Oráculo introduz o tema de forma rápida e convoca 2 especialistas relevantes.
2. Cada especialista expõe sua visão com objetividade (máximo 1 a 2 parágrafos concisos), citando conceitos ou timestamps das aulas.
3. Os especialistas podem interagir, debater, complementar ou discordar construtivamente de abordagens.
4. O Oráculo conclui com uma recomendação prática e direta.

DIRETRIZES DE FORMATAÇÃO:
- Escreva de forma limpa, direta e elegante.
- Use negrito para destacar pontos-chave de forma limpa. Não use asteriscos soltos nem poluição visual.
- Evite prolixidade ou discursos longos.

Retorne estritamente um JSON no seguinte formato:
{{
  "debate": [
    {{
      "speaker": "Oráculo",
      "avatar": "🔮",
      "role": "Orquestrador",
      "text": "Fala do Oráculo..."
    }},
    {{
      "speaker": "Nome do Agente",
      "avatar": "Emoji do Agente",
      "role": "Cargo do Agente",
      "text": "Fala do especialista..."
    }}
  ],
  "final_summary": "Resumo final objetivo do Oráculo para o usuário"
}}
"""
        response = call_gemini_chat_resilient(
            prompt=debate_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3)
        )

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            try:
                record_tokens(
                    source="oracle_chat",
                    details="Mesa Redonda (Debate)",
                    prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                    total_tokens=getattr(response.usage_metadata, "total_token_count", 0) or 0,
                    model="gemini-3.6-flash"
                )
            except Exception:
                pass

        clean_text = response.text.strip()
        if clean_text.startswith("```json"): clean_text = clean_text[7:]
        if clean_text.startswith("```"): clean_text = clean_text[3:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            data = json.loads(clean_text, strict=False)
        except Exception:
            sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', lambda m: ' ' if m.group(0) in '\n\r\t' else '', clean_text)
            data = json.loads(sanitized, strict=False)

        return {
            "mode": "debate",
            "debate": data.get("debate", []),
            "final_summary": data.get("final_summary", ""),
            "citations": citations,
            "extracted_codes": extracted_codes[:4]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar consulta no chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no processamento da consulta: {str(e)}")

# Servindo o Frontend SPA
@app.get("/")
def get_index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
