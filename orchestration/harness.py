import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from config import settings
from models.project import Project, Task, DocumentArtifact, ProjectStatus, TaskStatus, DocumentType
from orchestration.project_store import ProjectStore

logger = logging.getLogger("orchestrator")

def load_agent_context(agent_id: str) -> Dict[str, Any]:
    """Carrega perfil, AGENT.md e SKILL.md de um agente."""
    profile_path = settings.AGENTS_DIR / f"{agent_id}.json"
    profile = {}
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass

    skill_dir = settings.DATA_DIR / "skills" / agent_id
    agent_md = ""
    skill_md = ""
    if (skill_dir / "AGENT.md").exists():
        try:
            agent_md = (skill_dir / "AGENT.md").read_text(encoding="utf-8")
        except Exception:
            pass
    if (skill_dir / "SKILL.md").exists():
        try:
            skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        except Exception:
            pass

    return {
        "id": agent_id,
        "name": profile.get("name", "Especialista"),
        "role": profile.get("role", "Técnico"),
        "avatar": profile.get("avatar", "🤖"),
        "area_id": profile.get("area_id"),
        "agent_type": profile.get("agent_type", "tecnico"),
        "topics": profile.get("topics_mastered", []),
        "agent_md": agent_md,
        "skill_md": skill_md
    }

def get_all_agents() -> List[Dict[str, Any]]:
    """Carrega todos os agentes do sistema."""
    agents = []
    if settings.AGENTS_DIR.exists():
        for f in settings.AGENTS_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    agents.append(json.load(fp))
            except Exception:
                continue
    return agents

class AgentHarness:
    """Motor de execução e orquestração de agentes (Agent Harness)."""
    
    def __init__(self):
        self.store = ProjectStore()

    def _call_gemini_raw(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Executa chamada resiliente ao Gemini utilizando o pool de chaves."""
        from google import genai
        from google.genai import types

        keys = settings.GEMINI_API_KEYS or [settings.GEMINI_API_KEY]
        models_to_try = settings.ORCHESTRATION_MODELS
        last_err = None

        for attempt in range(len(keys) * 2):
            key = keys[attempt % len(keys)]
            client = genai.Client(api_key=key)
            for model_name in models_to_try:
                try:
                    config = None
                    if system_instruction:
                        config = types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.4
                        )
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    return res.text.strip() if res.text else ""
                except Exception as err:
                    last_err = err
                    err_str = str(err).upper()
                    if any(code in err_str for code in ["503", "429", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "HIGH DEMAND"]):
                        import time
                        time.sleep(1.0)
                        continue
                    # Se o modelo falhar (ex: 404), tenta o próximo modelo da lista
                    continue
        raise RuntimeError(f"Erro ao chamar Gemini no Harness: {last_err}")

    def plan_project(self, project_id: str) -> List[Task]:
        """O Gestor da Área decompõe a meta do projeto em um conjunto de tarefas técnicas."""
        project = self.store.get_project(project_id)
        if not project:
            raise ValueError(f"Projeto {project_id} não encontrado")

        # Localiza o Gestor encarregado
        manager_id = project.manager_agent_id
        all_agents = get_all_agents()

        if not manager_id:
            # Encontra o gestor da área
            area_managers = [a for a in all_agents if a.get("area_id") == project.area_id and a.get("agent_type") == "gestor"]
            if area_managers:
                manager_id = area_managers[0]["id"]
            elif all_agents:
                manager_id = all_agents[0]["id"]

        manager_ctx = load_agent_context(manager_id) if manager_id else {}
        project.manager_agent_id = manager_id
        project.manager_agent_name = manager_ctx.get("name", "Gestor de Área")

        # Lista de especialistas técnicos disponíveis para executar
        tech_specialists = [
            a for a in all_agents 
            if a.get("area_id") == project.area_id or a.get("agent_type") == "tecnico"
        ]
        specialists_summary = chr(10).join([
            f"- ID: `{a['id']}`, Nome: {a['name']} ({a['role']}), Especialidades: {', '.join(a.get('topics_mastered', [])[:6])}"
            for a in tech_specialists
        ])

        system_instruction = f"""Você é {manager_ctx.get('name', 'Gestor Executivo')}, um Gestor Sênior e Estrategista.
Sua missão é liderar e quebrar projetos estratégicos em tarefas acionáveis e técnicas para os especialistas da sua equipe.
Você tem visão de negócios, metodologia e exige rigor na execução.

Equipe de Especialistas Técnicos sob sua gestão:
{specialists_summary}
"""

        is_tech = project.area_id == "tech" or any(k in project.title.lower() or k in project.description.lower() for k in ["código", "software", "api", "sistema", "desenvolva", "app", "script", "endpoint"])
        tech_rule = ""
        if is_tech:
            tech_rule = """
DIRETRIZ OBRIGATÓRIA DE ENGENHARIA DE SOFTWARE (SDD + TDD):
Como este é um projeto de tecnologia/código, você DEVE estruturar o backlog sequencial seguindo:
- Tarefa 1 (SDD - Spec-Driven): Definir a Especificação Técnica, Contratos de API e Schemas (atribuir a Alex Vance).
- Tarefa 2 (TDD - Test-Driven): Criar a Suíte de Testes Unitários cobrindo caminho feliz, erros e casos de borda (atribuir a Bruno).
- Tarefa 3 (Execução): Implementar o código completo e validar no Sandbox até aprovação total (atribuir a Alex Vance ou Bruno).
"""

        prompt = f"""
PROJETO: "{project.title}"
OBJETIVO & DIRETRIZES:
{project.description}
{tech_rule}
Como gestor, analise o objetivo e elabore um plano de ação claro de 2 a 4 tarefas sequenciais e interdependentes para atingir o objetivo com perfeição.
Para cada tarefa, defina:
1. `title`: Um título claro e objetivo (ex: "Pesquisar e Estruturar as 3 Principais Pautas").
2. `instruction`: Instruções ricas e completas de como o especialista deve executar e o que deve entregar.
3. `assigned_agent_id`: O ID do especialista técnico mais qualificado para essa tarefa.

Responda ESTRITAMENTE em formato JSON (uma lista de objetos):
```json
[
  {{
    "title": "Nome da tarefa 1",
    "instruction": "Instruções completas para o técnico...",
    "assigned_agent_id": "agent_id_aqui"
  }},
  {{
    "title": "Nome da tarefa 2",
    "instruction": "Instruções completas...",
    "assigned_agent_id": "agent_id_aqui"
  }}
]
```
"""

        raw_response = self._call_gemini_raw(prompt, system_instruction=system_instruction)
        
        # Extrai JSON
        json_text = raw_response
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        try:
            tasks_data = json.loads(json_text)
        except Exception as e:
            logger.error(f"Erro ao parsear JSON das tarefas: {e} | Resposta: {raw_response}")
            tasks_data = [{
                "title": f"Execução técnica do projeto: {project.title}",
                "instruction": project.description,
                "assigned_agent_id": tech_specialists[0]["id"] if tech_specialists else manager_id
            }]

        created_tasks = []
        for t_info in tasks_data:
            assigned_id = t_info.get("assigned_agent_id")
            assigned_name = "Especialista"
            target_a = next((a for a in all_agents if a["id"] == assigned_id), None)
            if target_a:
                assigned_name = target_a.get("name", assigned_name)

            h_type = t_info.get("harness_type", "oraculo_cloud")
            if any(k in t_info.get("title", "").lower() or k in t_info.get("instruction", "").lower() for k in ["código", "codigo", "react", "frontend", "interface", "tailwind", "html", "css", "componente", "script", "api"]):
                h_type = "antigravity_ide"

            ide_prompt = None
            if h_type == "antigravity_ide":
                t_ctx = load_agent_context(assigned_id) if assigned_id else {}
                ide_prompt = f"""# TAREFA DO ORÁCULO PARA O ANTIGRAVITY IDE
PROJETO: {project.title}
ESPECIALISTA DESIGNADO: {assigned_name} ({t_ctx.get('role', 'Técnico')})
TAREFA: {t_info.get('title')}

DIRETRIZES TÉCNICAS ABSORVIDAS DOS CURSOS (SKILL.MD):
{t_ctx.get('skill_md', '')[:1200]}

INSTRUÇÕES DE IMPLEMENTAÇÃO:
{t_info.get('instruction')}

Por favor, implemente o código necessário no workspace atual, criando os arquivos e componentes com excelência técnica."""

            task = Task(
                project_id=project.id,
                title=t_info.get("title", "Tarefa sem título"),
                instruction=t_info.get("instruction", ""),
                assigned_agent_id=assigned_id,
                assigned_agent_name=assigned_name,
                harness_type=h_type,
                ide_handoff_prompt=ide_prompt,
                status=TaskStatus.TODO
            )
            saved_task = self.store.save_task(task)
            created_tasks.append(saved_task)

        project.status = ProjectStatus.PLANNING
        self.store.save_project(project)
        return created_tasks

    async def execute_task(self, task_id: str) -> Task:
        """Executa uma tarefa utilizando o Agent Harness com ReAct loop e geração de artefatos."""
        task = self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Tarefa {task_id} não encontrada")

        project = self.store.get_project(task.project_id)
        if not project:
            raise ValueError(f"Projeto {task.project_id} não encontrado")

        agent_id = task.assigned_agent_id or project.manager_agent_id
        agent_ctx = load_agent_context(agent_id)

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        task.execution_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "thought",
            "message": f"Agente {agent_ctx['name']} ({agent_ctx['role']}) assumiu a tarefa e carregou seu SKILL.md."
        })
        self.store.save_task(task)

        # Roteamento inteligente para Execução de Código no Sandbox
        is_code_task = (
            task.harness_type == "antigravity_ide" or
            any(k in task.title.lower() or k in task.instruction.lower() 
                for k in ["código", "codigo", "script", "função", "funcao", "api", "classe", "test", "desenvolva", "implemente", "software", "endpoint"])
        )
        if is_code_task:
            return await self.execute_code_task(task, project, agent_ctx)

        prior_docs = self.store.list_documents(project_id=project.id)
        docs_context = ""
        if prior_docs:
            formatted_docs = []
            for d in prior_docs:
                formatted_docs.append(f"### {d.title} (ID: {d.id})" + chr(10) + f"{d.content[:800]}...")
            docs_context = "DOCUMENTOS JA CRIADOS NESTE PROJETO:" + chr(10) + chr(10).join(formatted_docs)

        system_prompt = f"""Você é {agent_ctx['name']} ({agent_ctx['role']}), um agente operador e técnico especialista.
Seu perfil e diretrizes:
{agent_ctx.get('agent_md') or 'Especialista focado em entregar trabalho técnico de altíssimo padrão.'}

SEU CONHECIMENTO PRÁTICO ABSORVIDO (SKILL.MD):
{agent_ctx.get('skill_md') or 'Tópicos dominados: ' + ', '.join(agent_ctx.get('topics', []))}

Você opera em um HARNESS AUTÔNOMO.
Sua missão é EXECUTAR a tarefa atribuída e produzir o(s) artefato(s) final(is) com excelência prática.
"""

        execution_prompt = f"""
PROJETO: "{project.title}"
OBJETIVO GERAL DO PROJETO:
{project.description}

{docs_context}

SUA TAREFA ATUAL:
"{task.title}"

INSTRUÇÕES ESPECÍFICAS DA TAREFA:
{task.instruction}

COMO VOCÊ DEVE ENTREGAR SEU TRABALHO:
1. Comece com um breve raciocínio (2 a 3 linhas) explicando sua estratégia técnica.
2. Em seguida, crie o documento / artefato de entrega completo, formatado e detalhado utilizando o bloco especial:
```artifact:tipo_de_documento
# Título do Documento
Conteúdo completo, sem resumos preguiçosos, código executável, roteiro cena a cena ou relatório completo...
```
(Onde tipo_de_documento pode ser: `script`, `report`, `code`, `summary`, `outline` ou `analysis`).

3. Conclua com um resumo de 1 parágrafo do resultado para o seu Gestor de Área.
"""

        try:
            task.execution_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "action",
                "message": "Executando raciocínio com a API Gemini utilizando contexto dos cursos estudados..."
            })
            self.store.save_task(task)

            # Executa a geração
            output = self._call_gemini_raw(execution_prompt, system_instruction=system_prompt)

            # Processa os blocos de artefato gerados
            created_docs = []
            if "```artifact:" in output:
                parts = output.split("```artifact:")
                for p in parts[1:]:
                    block_header = p.split(chr(10), 1)[0].strip()
                    doc_type_str = block_header.lower() if block_header else "report"
                    doc_body = p.split(chr(10), 1)[1].split("```")[0].strip()

                    # Determina título a partir da primeira linha
                    title = f"Entregável - {task.title}"
                    for line in doc_body.split(chr(10)):
                        clean_l = line.strip()
                        if clean_l.startswith("#"):
                            title = clean_l.replace("#", "").strip()
                            break

                    doc_type = DocumentType.REPORT
                    if doc_type_str in [dt.value for dt in DocumentType]:
                        doc_type = DocumentType(doc_type_str)

                    artifact = DocumentArtifact(
                        project_id=project.id,
                        task_id=task.id,
                        created_by_agent_id=agent_id,
                        created_by_agent_name=agent_ctx["name"],
                        title=title,
                        content=doc_body,
                        doc_type=doc_type
                    )
                    saved_doc = self.store.save_document(artifact)
                    created_docs.append(saved_doc)
                    task.document_ids.append(saved_doc.id)
            else:
                artifact = DocumentArtifact(
                    project_id=project.id,
                    task_id=task.id,
                    created_by_agent_id=agent_id,
                    created_by_agent_name=agent_ctx["name"],
                    title=f"Resultado: {task.title}",
                    content=output,
                    doc_type=DocumentType.REPORT
                )
                saved_doc = self.store.save_document(artifact)
                created_docs.append(saved_doc)
                task.document_ids.append(saved_doc.id)

            task.status = TaskStatus.DONE
            task.completed_at = datetime.now(timezone.utc)
            task.result_summary = f"Tarefa concluída com sucesso. {len(created_docs)} documento(s) gerado(s) e arquivado(s)."
            task.execution_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "completion",
                "message": f"Entrega finalizada com sucesso. Artefatos: {[d.title for d in created_docs]}."
            })
            self.store.save_task(task)

            # Verifica se todas as tarefas do projeto foram concluídas
            all_proj_tasks = self.store.list_tasks(project_id=project.id)
            if all(t.status == TaskStatus.DONE for t in all_proj_tasks):
                project.status = ProjectStatus.COMPLETED
                project.completed_at = datetime.now(timezone.utc)
            else:
                project.status = ProjectStatus.IN_PROGRESS
            self.store.save_project(project)

            return task

        except Exception as e:
            logger.error(f"Erro na execução da tarefa {task.id}: {e}")
            task.status = TaskStatus.FAILED
            task.result_summary = f"Erro durante a execução: {str(e)}"
            task.execution_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "error",
                "message": f"Falha na execução: {str(e)}"
            })
            self.store.save_task(task)
            raise e

    async def execute_code_task(self, task: Task, project: Project, agent_ctx: Dict[str, Any]) -> Task:
        """Executa uma tarefa de desenvolvimento de software em sandbox com ReAct loop de auto-correção."""
        from orchestration.sandbox import extract_code_files, write_workspace_files, execute_in_sandbox

        workspace_dir = settings.WORKSPACES_DIR / project.id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        task.execution_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "thought",
            "message": f"Iniciando ciclo autônomo de engenharia de software com {agent_ctx['name']}. Workspace: {workspace_dir.name}"
        })
        self.store.save_task(task)

        system_prompt = f"""Você é {agent_ctx['name']} ({agent_ctx['role']}), um Engenheiro e Arquiteto de Software sênior.
Seu conhecimento técnico dos cursos e referências:
{agent_ctx.get('skill_md') or 'Tópicos dominados: ' + ', '.join(agent_ctx.get('topics', []))}

DIRETRIZES DE ENGENHARIA DE SOFTWARE:
1. Você gera código funcional, limpo, modular e de nível de produção.
2. Sempre forneça testes unitários abrangentes cobrindo os casos de uso.
3. Formate cada arquivo usando estritamente o bloco:
```code:caminho/do/arquivo.ext
// ou # código completo do arquivo aqui
```
4. Se o projeto for Python, sempre crie um arquivo de testes (ex: `test_main.py`) com unittest para validação automática no sandbox.
"""

        code_prompt = f"""PROJETO: "{project.title}"
OBJETIVO DO PROJETO:
{project.description}

SUA TAREFA DE DESENVOLVIMENTO:
"{task.title}"

INSTRUÇÕES:
{task.instruction}

Crie a implementação completa com os arquivos necessários e a suite de testes unitários para validar a execução.
"""

        max_iterations = 3
        current_prompt = code_prompt
        last_sandbox_res = None
        created_files = []

        for attempt in range(1, max_iterations + 1):
            task.execution_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "action",
                "message": f"Gerando/refinando código (tentativa {attempt}/{max_iterations}) com {agent_ctx['name']}..."
            })
            self.store.save_task(task)

            raw_code = self._call_gemini_raw(current_prompt, system_instruction=system_prompt)
            files = extract_code_files(raw_code)

            if not files:
                task.execution_logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "thought",
                    "message": "Nenhum arquivo de código explícito detectado; gerando script padrão main.py..."
                })
                files = {"main.py": raw_code}

            created_files = write_workspace_files(workspace_dir, files)

            task.execution_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "action",
                "message": f"Executando validação e testes no sandbox: {created_files}..."
            })
            self.store.save_task(task)

            last_sandbox_res = await execute_in_sandbox(workspace_dir, timeout_seconds=15)

            if last_sandbox_res.success:
                task.execution_logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "thought",
                    "message": f"✅ Validação no sandbox aprovada com sucesso! Saída: {last_sandbox_res.stdout or last_sandbox_res.stderr or 'OK'}"
                })
                break
            else:
                task.execution_logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "error",
                    "message": f"⚠️ Falha na execução ({last_sandbox_res.error_summary}). Ativando auto-correção ReAct..."
                })
                self.store.save_task(task)

                # Prompt de auto-cura para a próxima iteração
                current_prompt = f"""O código gerado anteriormente falhou nos testes do sandbox.
ERRO IDENTIFICADO:
{last_sandbox_res.error_summary}

STDOUT:
{last_sandbox_res.stdout}

STDERR / TRACEBACK:
{last_sandbox_res.stderr}

Por favor, corrija o código de todos os arquivos afetados mantendo a formatação ```code:caminho/arquivo.ext para que todos os testes passem com 100% de sucesso.
"""

        # Cria artefato de entrega do código
        summary_text = f"Software desenvolvido e validado por {agent_ctx['name']} no sandbox."
        if last_sandbox_res and not last_sandbox_res.success:
            summary_text = f"Código gerado com pendências de validação: {last_sandbox_res.error_summary}"

        combined_code_doc = f"# Entregável de Software: {task.title}\n\n"
        combined_code_doc += f"**Desenvolvido por**: {agent_ctx['name']} ({agent_ctx['role']})\n"
        combined_code_doc += f"**Workspace**: `{workspace_dir.resolve()}`\n"
        combined_code_doc += f"**Status do Sandbox**: {'Aprovado ✅' if (last_sandbox_res and last_sandbox_res.success) else 'Com alertas ⚠️'}\n\n"
        
        for fname in created_files:
            fpath = workspace_dir / fname
            if fpath.exists():
                ext = fpath.suffix.lstrip(".") or "txt"
                combined_code_doc += f"### Arquivo: `{fname}`\n```{ext}\n{fpath.read_text(encoding='utf-8', errors='replace')}\n```\n\n"

        artifact = DocumentArtifact(
            project_id=project.id,
            task_id=task.id,
            created_by_agent_id=agent_ctx["id"],
            created_by_agent_name=agent_ctx["name"],
            title=f"Código & Testes: {task.title}",
            content=combined_code_doc,
            doc_type=DocumentType.CODE
        )
        saved_doc = self.store.save_document(artifact)
        task.document_ids.append(saved_doc.id)

        task.status = TaskStatus.DONE if (last_sandbox_res and last_sandbox_res.success) else TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        task.result_summary = f"{'Código executado e validado com sucesso' if task.status == TaskStatus.DONE else 'Falha na validação do código'}. Arquivos: {', '.join(created_files)}."
        self.store.save_task(task)

        # Atualiza status do projeto
        all_proj_tasks = self.store.list_tasks(project_id=project.id)
        if all(t.status == TaskStatus.DONE for t in all_proj_tasks):
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.now(timezone.utc)
        else:
            project.status = ProjectStatus.IN_PROGRESS
        self.store.save_project(project)

        return task

    async def execute_project_all_tasks(self, project_id: str):
        """Executa em fila todas as tarefas pendentes de um projeto."""
        tasks = self.store.list_tasks(project_id=project_id)
        for t in tasks:
            if t.status in [TaskStatus.TODO, TaskStatus.FAILED]:
                await self.execute_task(t.id)


    def auto_dispatch(self, user_prompt: str) -> Project:
        """Recebe um prompt universal em linguagem natural, deduz a área, o gestor,
        cria o projeto e dispara a decomposição em tarefas com roteamento de harness."""
        all_agents = get_all_agents()
        areas = []
        if settings.AREAS_DIR.exists():
            for f in settings.AREAS_DIR.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        areas.append(json.load(fp))
                except Exception:
                    pass

        areas_desc = chr(10).join([
            f"- ID: '{a['id']}', Nome: '{a.get('name')}', Descrição: '{a.get('description', '')}'"
            for a in areas
        ])

        classify_prompt = f"""Você é o Orquestrador Central do Oráculo.
Um usuário enviou este comando ou objetivo de projeto:
\"{user_prompt}\"

Analise o objetivo e escolha a melhor Área da Vida / Negócio para assumir esse projeto entre as disponíveis:
{areas_desc}

Responda estritamente em formato JSON:
```json
{{
  \"title\": \"Um título curto e memorável para o projeto (máximo 6 palavras)\",
  \"description\": \"Uma descrição expandida e detalhada do objetivo e dos entregáveis esperados\",
  \"area_id\": \"o_id_da_area_escolhida\"
}}
```"""
        raw = self._call_gemini_raw(classify_prompt)
        json_text = raw
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        try:
            decision = json.loads(json_text)
        except Exception:
            decision = {
                "title": user_prompt[:40],
                "description": user_prompt,
                "area_id": "tech" if areas else "geral"
            }

        area_id = decision.get("area_id", "tech")
        area_obj = next((a for a in areas if a["id"] == area_id), None)
        area_name = area_obj.get("name") if area_obj else "Geral"

        # Acha o gestor da área
        area_managers = [a for a in all_agents if a.get("area_id") == area_id and a.get("agent_type") == "gestor"]
        manager_id = area_managers[0]["id"] if area_managers else (all_agents[0]["id"] if all_agents else None)
        manager_name = area_managers[0]["name"] if area_managers else (all_agents[0]["name"] if all_agents else "Gestor")

        project = Project(
            title=decision.get("title", user_prompt[:40]),
            description=decision.get("description", user_prompt),
            area_id=area_id,
            area_name=area_name,
            manager_agent_id=manager_id,
            manager_agent_name=manager_name,
            status=ProjectStatus.PLANNING
        )
        saved_proj = self.store.save_project(project)

        # Decompõe em tarefas com o Gestor
        tasks = self.plan_project(saved_proj.id)
        saved_proj.tasks = tasks
        return saved_proj
