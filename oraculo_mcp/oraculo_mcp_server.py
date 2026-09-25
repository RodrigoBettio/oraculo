"""
Oráculo MCP Server — Expõe ferramentas do Oráculo para o Antigravity via MCP SSE.

Implementação usando o SDK `mcp` (Model Context Protocol) com transporte SSE
montado como sub-aplicação dentro do FastAPI existente.

Ferramentas expostas:
- oraculo_search_knowledge: Busca na base de conhecimento processada
- oraculo_consult_specialist: Consulta um especialista sobre um tema
- oraculo_list_agents: Lista agentes com competências
- oraculo_get_agent_skill: Retorna SKILL.md completo de um agente
- oraculo_auto_dispatch: Decompõe problema em tarefas via gestor
- oraculo_list_projects: Lista projetos com status
- oraculo_study_status: Status da fila de estudos
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("oraculo.mcp")


def _search_knowledge(query: str, group_filter: Optional[str] = None, limit: int = 5) -> dict:
    """Busca na base de conhecimento processada (cursos, aulas, PDFs)."""
    from config import settings
    
    processed_dir = settings.PROCESSED_DIR
    if not processed_dir.exists():
        return {"error": f"Diretório de conhecimento não encontrado em {processed_dir}", "results": []}

    results = []
    query_terms = query.lower().split()

    for json_file in processed_dir.glob("**/*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)

            group_name = doc.get("group_name", "")
            if group_filter and group_filter.lower() not in group_name.lower():
                continue

            doc_text = f"{doc.get('title', '')} {doc.get('summary', '')} {' '.join(doc.get('topics', []))}".lower()
            score = sum(2 for term in query_terms if term in doc_text)

            matching_segments = []
            for seg in doc.get("segments", []):
                seg_text = (seg.get("text", "") + " " + (seg.get("visual_description") or "")).lower()
                seg_score = sum(1 for term in query_terms if term in seg_text)
                if seg_score > 0:
                    matching_segments.append({
                        "start_time": seg.get("start_time"),
                        "end_time": seg.get("end_time"),
                        "text": seg.get("text", "")[:400],
                        "visual": seg.get("visual_description"),
                        "code_snippets": seg.get("code_snippets", [])
                    })

            if score > 0 or matching_segments:
                results.append({
                    "video_id": doc.get("video_id"),
                    "title": doc.get("title"),
                    "group_name": group_name,
                    "summary": doc.get("summary"),
                    "topics": doc.get("topics"),
                    "matching_segments": matching_segments[:5],
                    "extracted_codes": doc.get("extracted_codes", [])[:3],
                    "score": score + len(matching_segments)
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"query": query, "total_matches": len(results), "results": results[:limit]}


def _list_agents() -> list:
    """Lista todos os agentes com competências e horas estudadas."""
    from config import settings
    
    agents = []
    if settings.AGENTS_DIR.exists():
        for f in settings.AGENTS_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    agents.append({
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "role": data.get("role"),
                        "avatar": data.get("avatar"),
                        "area_id": data.get("area_id"),
                        "agent_type": data.get("agent_type"),
                        "topics_mastered": data.get("topics_mastered", []),
                        "total_hours_studied": data.get("total_hours_studied", 0),
                        "total_videos_studied": data.get("total_videos_studied", 0),
                        "status": data.get("status", "ativo"),
                    })
            except Exception:
                continue
    return agents


def _get_agent_skill(agent_id: str) -> dict:
    """Retorna o SKILL.md completo de um agente."""
    from config import settings
    
    skill_path = settings.DATA_DIR / "skills" / agent_id / "SKILL.md"
    profile_path = settings.AGENTS_DIR / f"{agent_id}.json"
    
    result = {"agent_id": agent_id, "skill_md": "", "profile": {}}
    
    if skill_path.exists():
        result["skill_md"] = skill_path.read_text(encoding="utf-8")
    
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                result["profile"] = json.load(f)
        except Exception:
            pass
    
    if not result["skill_md"] and not result["profile"]:
        result["error"] = f"Agente '{agent_id}' não encontrado."
    
    return result


def _consult_specialist(agent_id: str, question: str) -> dict:
    """Consulta um especialista sobre um tema usando seu contexto SKILL.md."""
    from orchestration.harness import AgentHarness, load_agent_context
    
    agent_ctx = load_agent_context(agent_id)
    if not agent_ctx.get("skill_md") and not agent_ctx.get("topics"):
        return {"error": f"Agente '{agent_id}' não possui conhecimento registrado (SKILL.md vazio)."}
    
    harness = AgentHarness()
    
    system_instruction = f"""Você é {agent_ctx['name']} ({agent_ctx['role']}), um especialista técnico.
Responda à pergunta usando EXCLUSIVAMENTE seu conhecimento absorvido dos cursos.
Cite aulas, timestamps e código quando aplicável.

SEU CONHECIMENTO (SKILL.MD):
{agent_ctx.get('skill_md', '')[:8000]}
"""
    
    try:
        response = harness._call_gemini_raw(question, system_instruction=system_instruction)
        return {
            "agent_id": agent_id,
            "agent_name": agent_ctx["name"],
            "agent_role": agent_ctx["role"],
            "question": question,
            "response": response,
        }
    except Exception as e:
        return {"error": f"Erro ao consultar {agent_ctx['name']}: {str(e)}"}


def _auto_dispatch(prompt: str) -> dict:
    """Recebe um problema e o Oráculo decompõe em tarefas via gestor de área."""
    from orchestration.harness import AgentHarness
    
    harness = AgentHarness()
    try:
        project = harness.auto_dispatch(prompt)
        return {
            "project_id": project.id,
            "title": project.title,
            "description": project.description,
            "area_id": project.area_id,
            "area_name": project.area_name,
            "manager": project.manager_agent_name,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "instruction": t.instruction,
                    "assigned_agent_id": t.assigned_agent_id,
                    "assigned_agent_name": t.assigned_agent_name,
                    "harness_type": t.harness_type,
                    "ide_handoff_prompt": t.ide_handoff_prompt,
                }
                for t in (project.tasks or [])
            ]
        }
    except Exception as e:
        return {"error": f"Erro no auto-dispatch: {str(e)}"}


def _list_projects() -> list:
    """Lista projetos existentes com status."""
    from orchestration.project_store import ProjectStore
    
    store = ProjectStore()
    projects = store.list_projects()
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description[:200],
            "area_id": p.area_id,
            "area_name": p.area_name,
            "manager": p.manager_agent_name,
            "status": p.status.value,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in projects
    ]


def _study_status() -> dict:
    """Retorna o status da fila de estudos."""
    from ingestion.study_queue import StudyQueueManager
    
    try:
        sqm = StudyQueueManager()
        status = sqm.get_queue_status()
        return {
            "is_busy": status.get("is_busy", False),
            "active_count": status.get("active_count", 0),
            "max_workers": status.get("max_workers", 0),
            "queue_count": status.get("queue_count", 0),
            "completed_count": status.get("completed_count", 0),
            "error_count": status.get("error_count", 0),
            "total_items": status.get("total_items", 0),
            "estimated_time_text": status.get("estimated_time_text", "N/A"),
            "safety_paused": status.get("safety_paused", False),
        }
    except Exception as e:
        return {"error": f"Erro ao obter status: {str(e)}"}


# ─────────────────────────────────────────────────────────────
# MCP Server Setup (usando SDK `mcp` se disponível,
# caso contrário expõe como REST endpoints puros)
# ─────────────────────────────────────────────────────────────

_MCP_AVAILABLE = False
MCPServerClass = None

try:
    from mcp.server.mcpserver import MCPServer
    MCPServerClass = MCPServer
    _MCP_AVAILABLE = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        MCPServerClass = FastMCP
        _MCP_AVAILABLE = True
    except ImportError:
        logger.warning("SDK 'mcp' não encontrado. MCP Server será exposto apenas como REST endpoints.")


def create_mcp_server():
    """Cria e configura o MCP Server com todas as ferramentas."""
    if not _MCP_AVAILABLE or MCPServerClass is None:
        return None
    
    mcp = MCPServerClass(
        "Oráculo",
        instructions="""O Oráculo é um sistema de agentes inteligentes que absorvem conhecimento de cursos, vídeos e PDFs.
Use as ferramentas para consultar especialistas, buscar conhecimento processado, listar agentes e suas competências,
decompor problemas em tarefas e monitorar a fila de estudos."""
    )

    @mcp.tool()
    def oraculo_search_knowledge(query: str, group_filter: str = "", limit: int = 5) -> str:
        """Busca na base de conhecimento processada do Oráculo (cursos, aulas, PDFs).
        Retorna trechos relevantes com timestamps, resumos e código extraído via OCR.
        
        Args:
            query: Termo de busca ou pergunta (ex: "autenticação JWT", "microserviços", "hooks Claude Code")
            group_filter: Filtro opcional por grupo/curso específico
            limit: Número máximo de resultados (padrão: 5)
        """
        result = _search_knowledge(query, group_filter or None, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_consult_specialist(agent_id: str, question: str) -> str:
        """Consulta um especialista do Oráculo sobre um tema técnico.
        O especialista responde usando EXCLUSIVAMENTE o conhecimento absorvido dos cursos estudados.
        
        Args:
            agent_id: ID do agente (ex: "agent_alex_vance", "agent_claude_code", "agent_jordan_belford_5567")
            question: Pergunta ou problema técnico para o especialista resolver
        """
        result = _consult_specialist(agent_id, question)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_list_agents() -> str:
        """Lista todos os agentes do Oráculo com suas competências, horas estudadas e áreas de atuação.
        Inclui tanto gestores executivos quanto especialistas técnicos.
        """
        agents = _list_agents()
        return json.dumps(agents, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_get_agent_skill(agent_id: str) -> str:
        """Retorna o SKILL.md completo de um agente — todo o conhecimento absorvido dos cursos, 
        regras determinísticas, padrões de código e timestamps das aulas.
        
        Args:
            agent_id: ID do agente (ex: "agent_alex_vance")
        """
        result = _get_agent_skill(agent_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_auto_dispatch(prompt: str) -> str:
        """Recebe um problema ou objetivo em linguagem natural e o Oráculo automaticamente:
        1. Identifica a área de negócio mais adequada
        2. Seleciona o gestor da área
        3. Decompõe em tarefas técnicas
        4. Atribui cada tarefa ao especialista mais qualificado
        5. Classifica se a tarefa é de código (antigravity_ide) ou consultiva (oraculo_cloud)
        
        Args:
            prompt: Descrição do problema ou objetivo (ex: "Criar um sistema de autenticação multi-tenant")
        """
        result = _auto_dispatch(prompt)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_list_projects() -> str:
        """Lista todos os projetos criados no Oráculo com status, área, gestor e datas."""
        projects = _list_projects()
        return json.dumps(projects, ensure_ascii=False, indent=2)

    @mcp.tool()
    def oraculo_study_status() -> str:
        """Retorna o status em tempo real da fila de estudos do Oráculo:
        quantos agentes estão estudando, quantas aulas foram concluídas, erros e estimativa de tempo.
        """
        result = _study_status()
        return json.dumps(result, ensure_ascii=False, indent=2)

    return mcp


def mount_mcp_on_app(app):
    """Monta o MCP Server SSE no FastAPI existente em /mcp/."""
    mcp = create_mcp_server()
    
    if mcp is not None:
        # Monta o MCP SSE transport como sub-aplicação
        try:
            mcp_app = mcp.sse_app()
            app.mount("/mcp", mcp_app)
            logger.info("✅ MCP Server montado em /mcp/ (SSE transport)")
            return True
        except Exception as e:
            logger.error(f"Erro ao montar MCP SSE: {e}")
    
    # Fallback: Expõe como REST endpoints puros
    _mount_rest_fallback(app)
    return False


def _mount_rest_fallback(app):
    """Fallback: expõe as ferramentas como REST endpoints caso o SDK MCP não esteja disponível."""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/mcp", tags=["MCP Fallback REST"])
    
    @router.get("/tools")
    def list_tools():
        """Lista ferramentas disponíveis do MCP."""
        return {
            "tools": [
                {"name": "oraculo_search_knowledge", "description": "Busca na base de conhecimento"},
                {"name": "oraculo_consult_specialist", "description": "Consulta especialista sobre um tema"},
                {"name": "oraculo_list_agents", "description": "Lista agentes com competências"},
                {"name": "oraculo_get_agent_skill", "description": "Retorna SKILL.md completo"},
                {"name": "oraculo_auto_dispatch", "description": "Decompõe problema em tarefas"},
                {"name": "oraculo_list_projects", "description": "Lista projetos com status"},
                {"name": "oraculo_study_status", "description": "Status da fila de estudos"},
            ]
        }
    
    @router.post("/call/{tool_name}")
    def call_tool(tool_name: str, params: dict = {}):
        """Chama uma ferramenta MCP diretamente via REST."""
        dispatch = {
            "oraculo_search_knowledge": lambda p: _search_knowledge(p.get("query", ""), p.get("group_filter"), p.get("limit", 5)),
            "oraculo_consult_specialist": lambda p: _consult_specialist(p.get("agent_id", ""), p.get("question", "")),
            "oraculo_list_agents": lambda p: _list_agents(),
            "oraculo_get_agent_skill": lambda p: _get_agent_skill(p.get("agent_id", "")),
            "oraculo_auto_dispatch": lambda p: _auto_dispatch(p.get("prompt", "")),
            "oraculo_list_projects": lambda p: _list_projects(),
            "oraculo_study_status": lambda p: _study_status(),
        }
        
        if tool_name not in dispatch:
            return {"error": f"Ferramenta '{tool_name}' não encontrada"}
        
        return dispatch[tool_name](params)
    
    app.include_router(router)
    logger.info("⚡ MCP REST fallback montado em /mcp/ (sem SDK MCP)")
