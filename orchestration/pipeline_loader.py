"""
Oráculo — Pipeline Loader & Obsidian Vault Bridge (Real-Time Edition)
Gerencia playbooks declarativos (SOPs) em Markdown e persiste o ciclo de vida
completo dos projetos no Obsidian em TEMPO REAL (Única Fonte da Verdade).
"""

import os
import re
import yaml
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from config import settings
from models.project import Project, Task, DocumentArtifact

logger = logging.getLogger("pipeline_loader")

def get_vault_dirs() -> List[Path]:
    """Retorna a lista de diretórios do Vault Obsidian (primário no PC e espelho local no projeto)."""
    dirs = []
    
    # 1. Cofre Primário do Host (ex: C:\Users\Rodrigo\Documents\ObsidianVault)
    primary = settings.OBSIDIAN_VAULT_PATH
    if primary and str(primary).strip():
        primary_path = Path(primary)
        if primary_path.exists():
            dirs.append(primary_path)

    # Fallback para caminho padrão do Windows caso não configurado
    default_win = Path(r"C:\Users\Rodrigo\Documents\ObsidianVault")
    if default_win.exists() and default_win not in dirs:
        dirs.append(default_win)

    # 2. Cofre Espelho no repositório (para Docker na nuvem e deploy contínuo)
    repo_mirror = settings.DATA_DIR / "vault"
    repo_mirror.mkdir(parents=True, exist_ok=True)
    if repo_mirror not in dirs:
        dirs.append(repo_mirror)

    # Garante subpastas estruturadas em todos os cofres
    for v in dirs:
        (v / "04_Projetos_Ativos" / "Pipelines").mkdir(parents=True, exist_ok=True)
        (v / "04_Projetos_Ativos" / "Execucoes").mkdir(parents=True, exist_ok=True)

    return dirs

def get_primary_vault() -> Path:
    """Retorna o diretório principal para leitura prioritária do Vault."""
    vaults = get_vault_dirs()
    return vaults[0] if vaults else (settings.DATA_DIR / "vault")

def parse_pipeline_markdown(file_path: Path) -> Optional[Dict[str, Any]]:
    """Lê um arquivo .md de pipeline e extrai o YAML frontmatter e o conteúdo."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        
        frontmatter_str = parts[1].strip()
        body_str = parts[2].strip()
        
        data = yaml.safe_load(frontmatter_str) or {}
        data["file_path"] = str(file_path)
        data["markdown_body"] = body_str
        if "id" not in data:
            data["id"] = file_path.stem
        return data
    except Exception as e:
        logger.error(f"Erro ao parsear pipeline em {file_path}: {e}")
        return None

def list_available_pipelines() -> List[Dict[str, Any]]:
    """Lista todas as pipelines cadastradas no setor de Pipelines do Obsidian."""
    pipelines = []
    seen_ids = set()

    for v in get_vault_dirs():
        pipelines_dir = v / "04_Projetos_Ativos" / "Pipelines"
        if not pipelines_dir.exists():
            continue
        
        for f in pipelines_dir.glob("*.md"):
            p_data = parse_pipeline_markdown(f)
            if p_data and p_data.get("id") not in seen_ids:
                seen_ids.add(p_data["id"])
                pipelines.append(p_data)

    return pipelines

def get_pipeline_by_id(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """Localiza uma pipeline pelo ID exato."""
    clean_id = pipeline_id.strip().lower().replace(".md", "")
    for p in list_available_pipelines():
        if p.get("id", "").lower() == clean_id:
            return p
    return None

def find_pipeline_for_prompt(prompt: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Identifica se um comando/prompt aciona uma pipeline pré-definida.
    Retorna (pipeline_dict, tema_extraído).
    """
    cleaned = prompt.strip()
    words = cleaned.lower()

    all_pipelines = list_available_pipelines()

    # 1. Correspondência direta por comando explícito: /fluxo nome_pipeline tema
    for p in all_pipelines:
        p_id = p.get("id", "").lower()
        if words.startswith(f"/fluxo {p_id}") or words.startswith(f"/dev {p_id}"):
            remainder = cleaned[len(f"/fluxo {p_id}"):].strip() if words.startswith("/fluxo") else cleaned[len(f"/dev {p_id}"):].strip()
            return p, remainder or "Tema Geral"
        if words.startswith(f"{p_id} "):
            remainder = cleaned[len(f"{p_id} "):].strip()
            return p, remainder

    # 2. Correspondência por gatilhos (triggers) definidos no YAML
    for p in all_pipelines:
        triggers = p.get("triggers", [])
        matched_triggers = [t for t in triggers if t.lower() in words]
        if len(matched_triggers) >= 2 or (len(triggers) == 1 and len(matched_triggers) == 1):
            return p, cleaned

    return None, cleaned

def sanitize_filename(name: str) -> str:
    """Limpa string para nome de arquivo seguro."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.replace(" ", "_").strip("_")
    return clean[:50]

def get_project_vault_dir_name(project: Project) -> str:
    """Retorna o nome determinístico da pasta do projeto no Obsidian."""
    clean_title = sanitize_filename(project.title)
    return f"{project.id}_{clean_title}"

def update_moc_project(vault_path: Path, project: Project, folder_name: str, status_category: str):
    """
    Atualiza o MOC_Projetos.md movendo ou inserindo o projeto na seção correta.
    status_category pode ser: 'IN_PROGRESS' ou 'COMPLETED'
    """
    moc_path = vault_path / "04_Projetos_Ativos" / "MOC_Projetos.md"
    if not moc_path.exists():
        return
    try:
        text = moc_path.read_text(encoding="utf-8")
        link_target = f"Execucoes/{folder_name}/00_Overview"
        now_str = datetime.now().strftime("%d/%m/%Y")
        project_entry = f"- [[{link_target}|{project.title}]] — _{project.manager_agent_name} ({now_str})_\n"

        # Remove qualquer entrada anterior desse projeto
        lines = [line for line in text.splitlines(keepends=True) if link_target not in line]
        clean_text = "".join(lines)

        target_header = "## ✅ Concluídos\n" if status_category.upper() == "COMPLETED" else "## 🔥 Em Andamento\n"

        if target_header in clean_text:
            new_text = clean_text.replace(target_header, f"{target_header}{project_entry}")
            moc_path.write_text(new_text, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Erro ao atualizar MOC_Projetos em {vault_path}: {e}")


def _build_overview_content(project: Project, tasks: List[Task], docs: List[DocumentArtifact]) -> str:
    """Gera o Markdown vivo para a nota 00_Overview.md."""
    now = datetime.now()
    doc_map = {d.task_id: d for d in docs}

    task_table = "| # | Tarefa | Especialista | Status | Entregável |\n|---|---|---|---|---|\n"
    for idx, t in enumerate(tasks, 1):
        clean_t_title = sanitize_filename(t.title)
        file_stem = f"{idx:02d}_{clean_t_title}"
        doc_obj = doc_map.get(t.id)

        if t.status.value.lower() == "done" or doc_obj:
            status_badge = "CONCLUÍDO ✅"
            doc_link = f"[[{file_stem}]]"
        elif t.status.value.lower() == "in_progress":
            status_badge = "EM ANDAMENTO ⚙️"
            doc_link = "_produzindo..._"
        elif t.status.value.lower() == "failed":
            status_badge = "FALHOU ❌"
            doc_link = "_ver logs_"
        else:
            status_badge = "PENDENTE ⏳"
            doc_link = "_na fila_"

        task_table += f"| {idx} | {t.title} | {t.assigned_agent_name} | {status_badge} | {doc_link} |\n"

    status_str = project.status.value.upper()
    is_done = project.status.value.lower() == "completed"

    overview_content = f"""---
id: "{project.id}"
titulo: "{project.title}"
area: "{project.area_name}"
gestor: "{project.manager_agent_name}"
status: "{project.status.value}"
data_criacao: "{now.strftime('%d/%m/%Y %H:%M')}"
total_etapas: {len(tasks)}
tags:
  - projeto
  - {"concluido" if is_done else "ativo"}
  - oraculo
  - {project.area_id}
---

# 🚀 Projeto: {project.title}

> **Área**: {project.area_name}  
> **Gestor Responsável**: {project.manager_agent_name}  
> **Status**: {status_str} {"✅" if is_done else "⚙️"}  
> **Última Atualização**: {now.strftime('%d/%m/%Y às %H:%M:%S')}  

---

## 📌 Descrição & Objetivo
{project.description}

---

## 📋 Entregas & Tarefas (Atualização em Tempo Real)
{task_table}

---

## 🔗 Navegação do Segundo Cérebro
- **MOC Geral de Projetos**: [[MOC_Projetos]]
- **Home**: [[Home]]

_Orquestrado pelo Oráculo Harness & Sincronizado em Tempo Real no Obsidian._
"""
    return overview_content


def sync_project_created(project: Project, tasks: List[Task]) -> List[Path]:
    """
    Gatilho de Tempo Real: Disparado no momento em que um projeto é criado/planejado.
    Cria a pasta no Obsidian, gera 00_Overview.md com tarefas TODO e registra no MOC.
    """
    saved_paths = []
    folder_name = get_project_vault_dir_name(project)
    overview_text = _build_overview_content(project, tasks, [])

    for v in get_vault_dirs():
        try:
            proj_dir = v / "04_Projetos_Ativos" / "Execucoes" / folder_name
            proj_dir.mkdir(parents=True, exist_ok=True)

            overview_file = proj_dir / "00_Overview.md"
            overview_file.write_text(overview_text, encoding="utf-8")
            saved_paths.append(overview_file)

            update_moc_project(v, project, folder_name, "IN_PROGRESS")
        except Exception as err:
            logger.error(f"Erro no sync_project_created no vault {v}: {err}")

    logger.info(f"📁 [Obsidian Real-Time] Projeto '{project.title}' inicializado no Vault.")
    return saved_paths


def sync_task_completed(
    project: Project,
    task: Task,
    doc: Optional[DocumentArtifact],
    all_tasks: List[Task]
) -> List[Path]:
    """
    Gatilho de Tempo Real: Disparado imediatamente após uma tarefa ser concluída por um especialista.
    Grava o arquivo Markdown individual da entrega e atualiza o 00_Overview.md no mesmo instante!
    """
    saved_paths = []
    folder_name = get_project_vault_dir_name(project)
    now = datetime.now()

    # Localiza o índice da tarefa
    task_idx = 1
    for idx, t in enumerate(all_tasks, 1):
        if t.id == task.id:
            task_idx = idx
            break

    clean_title = sanitize_filename(task.title)
    file_name = f"{task_idx:02d}_{clean_title}.md"
    body_content = doc.content if doc else (task.result_summary or "Sem conteúdo.")

    task_note_text = f"""---
id: "{task.id}"
projeto: "[[00_Overview]]"
etapa: {task_idx}
especialista: "{task.assigned_agent_name}"
especialista_id: "{task.assigned_agent_id}"
status: "{task.status.value}"
data_entrega: "{now.strftime('%d/%m/%Y %H:%M')}"
tags:
  - oraculo
  - entrega
  - {project.area_id}
---

# 🎯 {task.title}

> **Especialista Responsável**: {task.assigned_agent_name}  
> **Status**: {task.status.value.upper()} ✅  
> **Voltar para o Projeto**: [[00_Overview]]

---

{body_content}

---
_Gerado e validado automaticamente pelo Oráculo Agent Harness em {now.strftime('%d/%m/%Y às %H:%M:%S')}._
"""

    for v in get_vault_dirs():
        try:
            proj_dir = v / "04_Projetos_Ativos" / "Execucoes" / folder_name
            proj_dir.mkdir(parents=True, exist_ok=True)

            # 1. Grava a nota individual da entrega
            doc_file = proj_dir / file_name
            doc_file.write_text(task_note_text, encoding="utf-8")
            saved_paths.append(doc_file)

            # 2. Atualiza imediatamente a nota viva 00_Overview.md
            # Carrega todos os docs conhecidos até agora
            overview_file = proj_dir / "00_Overview.md"
            active_docs = [doc] if doc else []
            updated_overview = _build_overview_content(project, all_tasks, active_docs)
            overview_file.write_text(updated_overview, encoding="utf-8")

        except Exception as err:
            logger.error(f"Erro no sync_task_completed no vault {v}: {err}")

    logger.info(f"📄 [Obsidian Real-Time] Tarefa [{task_idx}] '{task.title}' gravada no Vault.")
    return saved_paths


def sync_project_completed(
    project: Project,
    all_tasks: List[Task],
    all_docs: List[DocumentArtifact]
) -> List[Path]:
    """
    Gatilho de Tempo Real: Disparado quando todas as tarefas do projeto finalizam com sucesso.
    Finaliza o 00_Overview.md com status COMPLETED e move o projeto para Concluídos no MOC.
    """
    saved_paths = []
    folder_name = get_project_vault_dir_name(project)
    overview_text = _build_overview_content(project, all_tasks, all_docs)

    for v in get_vault_dirs():
        try:
            proj_dir = v / "04_Projetos_Ativos" / "Execucoes" / folder_name
            proj_dir.mkdir(parents=True, exist_ok=True)

            overview_file = proj_dir / "00_Overview.md"
            overview_file.write_text(overview_text, encoding="utf-8")
            saved_paths.append(overview_file)

            update_moc_project(v, project, folder_name, "COMPLETED")
        except Exception as err:
            logger.error(f"Erro no sync_project_completed no vault {v}: {err}")

    logger.info(f"🎉 [Obsidian Real-Time] Projeto '{project.title}' finalizado e arquivado no Vault.")
    return saved_paths


def save_project_to_vault(project: Project, tasks: List[Task], docs: List[DocumentArtifact]) -> List[Path]:
    """Compatibilidade reversa: finaliza o projeto no cofre."""
    return sync_project_completed(project, tasks, docs)


def list_vault_projects() -> Dict[str, List[Dict[str, Any]]]:
    """Lê todas as execuções de projetos arquivadas no Vault para visualização mobile/web."""
    active_projects = []
    completed_projects = []

    primary = get_primary_vault()
    exec_dir = primary / "04_Projetos_Ativos" / "Execucoes"

    if exec_dir.exists():
        for p_folder in exec_dir.iterdir():
            if not p_folder.is_dir():
                continue
            overview_file = p_folder / "00_Overview.md"
            if overview_file.exists():
                try:
                    content = overview_file.read_text(encoding="utf-8")
                    info = {}
                    if content.startswith("---"):
                        fm = content.split("---", 2)[1]
                        info = yaml.safe_load(fm) or {}
                    
                    p_entry = {
                        "id": info.get("id", p_folder.name),
                        "title": info.get("titulo", p_folder.name),
                        "gestor": info.get("gestor", "Gestor"),
                        "area": info.get("area", "Área"),
                        "status": info.get("status", "unknown"),
                        "folder": p_folder.name
                    }
                    if info.get("status", "").lower() == "completed":
                        completed_projects.append(p_entry)
                    else:
                        active_projects.append(p_entry)
                except Exception:
                    continue

    return {
        "active": active_projects,
        "completed": completed_projects
    }


def get_vault_project_overview(project_id: str) -> Optional[str]:
    """Retorna o conteúdo Markdown da nota 00_Overview.md de um projeto específico."""
    primary = get_primary_vault()
    exec_dir = primary / "04_Projetos_Ativos" / "Execucoes"
    if not exec_dir.exists():
        return None

    for p_folder in exec_dir.iterdir():
        if p_folder.is_dir() and project_id.lower() in p_folder.name.lower():
            overview_file = p_folder / "00_Overview.md"
            if overview_file.exists():
                return overview_file.read_text(encoding="utf-8")
    return None
