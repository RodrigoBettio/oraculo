"""
Oráculo — Pipeline Loader & Obsidian Vault Bridge
Gerencia playbooks/SOPs declarativos em Markdown e persiste entregas de projetos no Obsidian.
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
        # Se todos os triggers obrigatórios estiverem presentes no texto
        matched_triggers = [t for t in triggers if t.lower() in words]
        if len(matched_triggers) >= 2 or (len(triggers) == 1 and len(matched_triggers) == 1):
            return p, cleaned

    return None, cleaned

def sanitize_filename(name: str) -> str:
    """Limpa string para nome de arquivo seguro."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.replace(" ", "_").strip("_")
    return clean[:60]

def save_project_to_vault(project: Project, tasks: List[Task], docs: List[DocumentArtifact]) -> List[Path]:
    """Salva todo o projeto concluído no setor 04_Projetos_Ativos/Execucoes do Obsidian."""
    saved_paths = []
    vaults = get_vault_dirs()
    if not vaults:
        return saved_paths

    now = datetime.now()
    folder_name = f"{now.strftime('%Y%m%d_%H%M')}_{sanitize_filename(project.title)}"

    # Monta os dados dos artefatos
    doc_map = {d.task_id: d for d in docs}

    for v in vaults:
        try:
            proj_dir = v / "04_Projetos_Ativos" / "Execucoes" / folder_name
            proj_dir.mkdir(parents=True, exist_ok=True)

            # 1. Cria cada documento de entrega
            created_notes = []
            for idx, task in enumerate(tasks, 1):
                clean_title = sanitize_filename(task.title)
                file_name = f"{idx:02d}_{clean_title}.md"
                doc_file = proj_dir / file_name

                doc_obj = doc_map.get(task.id)
                body_content = doc_obj.content if doc_obj else (task.result_summary or "Sem conteúdo.")

                note_text = f"""---
id: "{task.id}"
projeto: "[[00_Overview]]"
etapa: {idx}
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
> **Status**: {task.status.value.upper()}  
> **Voltar para o Projeto**: [[00_Overview]]

---

{body_content}

---
_Gerado e validado automaticamente pelo Oráculo Agent Harness em {now.strftime('%d/%m/%Y às %H:%M')}._
"""
                doc_file.write_text(note_text, encoding="utf-8")
                created_notes.append({
                    "idx": idx,
                    "title": task.title,
                    "file_stem": doc_file.stem,
                    "agent": task.assigned_agent_name,
                    "status": task.status.value
                })

            # 2. Cria a nota 00_Overview.md
            overview_file = proj_dir / "00_Overview.md"
            task_table = "| # | Tarefa | Especialista | Status | Documento |\n|---|---|---|---|---|\n"
            for n in created_notes:
                task_table += f"| {n['idx']} | {n['title']} | {n['agent']} | {n['status'].upper()} | [[{n['file_stem']}]] |\n"

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
  - concluido
  - oraculo
  - {project.area_id}
---

# 🚀 Projeto: {project.title}

> **Área**: {project.area_name}  
> **Gestor Responsável**: {project.manager_agent_name}  
> **Status**: {project.status.value.upper()} ✅  
> **Data de Finalização**: {now.strftime('%d/%m/%Y às %H:%M')}  

---

## 📌 Descrição & Objetivo
{project.description}

---

## 📋 Entregas & Artefatos Produzidos
{task_table}

---

## 🔗 Navegação do Segundo Cérebro
- **MOC Geral de Projetos**: [[MOC_Projetos]]
- **Home**: [[Home]]

_Orquestrado pelo Oráculo Harness & Arquivado no Obsidian._
"""
            overview_file.write_text(overview_content, encoding="utf-8")
            saved_paths.append(overview_file)

            # 3. Atualiza o MOC_Projetos.md do Obsidian
            moc_path = v / "04_Projetos_Ativos" / "MOC_Projetos.md"
            if moc_path.exists():
                try:
                    moc_text = moc_path.read_text(encoding="utf-8")
                    project_link = f"- [[{folder_name}/00_Overview|{project.title}]] — _{project.manager_agent_name} ({now.strftime('%d/%m/%Y')})_\n"
                    if "## ✅ Concluídos" in moc_text and project_link not in moc_text:
                        moc_text = moc_text.replace("## ✅ Concluídos\n", f"## ✅ Concluídos\n{project_link}")
                        moc_path.write_text(moc_text, encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Não foi possível atualizar MOC_Projetos: {e}")

        except Exception as err:
            logger.error(f"Erro ao salvar projeto no vault {v}: {err}")

    return saved_paths

def sync_vault_mirrors():
    """Sincroniza os templates de Pipelines e os projetos entre o Vault primário e o mirror."""
    vaults = get_vault_dirs()
    if len(vaults) < 2:
        return
    
    primary, mirror = vaults[0], vaults[1]
    
    # Copia Pipelines de um pro outro se faltar
    for src, dst in [(primary, mirror), (mirror, primary)]:
        p_src = src / "04_Projetos_Ativos" / "Pipelines"
        p_dst = dst / "04_Projetos_Ativos" / "Pipelines"
        if p_src.exists():
            for f in p_src.glob("*.md"):
                target = p_dst / f.name
                if not target.exists() or f.stat().st_mtime > target.stat().st_mtime:
                    try:
                        shutil.copy2(f, target)
                    except Exception:
                        pass
