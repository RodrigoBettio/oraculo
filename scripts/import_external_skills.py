#!/usr/bin/env python3
"""
Oráculo External Skill Importer
Importa pacotes de skills curadas de repositórios do GitHub (ex: emilkowalski/skills)
e os integra ao Antigravity (~/.gemini/config/skills/) e aos Agentes Especialistas do Oráculo.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skill_importer")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_SKILLS_DIR = BASE_DIR / "data" / "skills"
GLOBAL_SKILLS_DIR = Path.home() / ".gemini" / "config" / "skills"
AGENTS_DIR = BASE_DIR / "data" / "agents"

def sanitize_name(name: str) -> str:
    """Normaliza o nome do diretório da skill."""
    return re.sub(r'[^a-zA-Z0-9_-]', '-', name.strip().lower())

def clone_repo(repo_url: str, dest_dir: Path) -> bool:
    """Clona superficialmente o repositório git."""
    if not repo_url.startswith("http://") and not repo_url.startswith("https://"):
        repo_url = f"https://github.com/{repo_url}.git"
    elif not repo_url.endswith(".git"):
        repo_url = f"{repo_url}.git"

    logger.info(f"📥 Clonando repositório: {repo_url}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao clonar repositório: {e.stderr}")
        return False

def find_skills_in_repo(repo_dir: Path) -> List[Path]:
    """Localiza todos os arquivos SKILL.md no repositório."""
    skills_found = []
    for skill_file in repo_dir.rglob("SKILL.md"):
        # Ignora arquivos de teste ou templates internos se houver
        if ".git" in str(skill_file):
            continue
        skills_found.append(skill_file.parent)
    return skills_found

def process_and_install_skill(
    skill_source_dir: Path,
    namespace_prefix: str,
    dry_run: bool = False
) -> Optional[Dict[str, Any]]:
    """Processa e instala uma skill no Antigravity e na pasta data/skills."""
    raw_name = skill_source_dir.name
    skill_id = f"{namespace_prefix}-{sanitize_name(raw_name)}"
    
    skill_file = skill_source_dir / "SKILL.md"
    if not skill_file.exists():
        return None

    with open(skill_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Atualiza o frontmatter YAML para o novo namespace
    new_content = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2]
            # Substitui ou adiciona o name:
            if re.search(r'^name:\s*.*$', frontmatter, re.MULTILINE):
                frontmatter = re.sub(r'^name:\s*.*$', f'name: {skill_id}', frontmatter, flags=re.MULTILINE)
            else:
                frontmatter = f"name: {skill_id}\n" + frontmatter.strip() + "\n"
            new_content = f"---{frontmatter}---{body}"

    # Extrai descrição para registro
    desc_match = re.search(r'description:\s*(.*?)(?=\n[a-zA-Z0-9_-]+:|\n---)', new_content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else f"Skill importada de {skill_source_dir.name}"

    if dry_run:
        logger.info(f"🔎 [Dry-Run] Detectada skill '{skill_id}' em {skill_source_dir.name}")
        return {"id": skill_id, "name": raw_name, "description": description}

    # 1. Instala no Antigravity Local (~/.gemini/config/skills/<skill_id>)
    target_global = GLOBAL_SKILLS_DIR / skill_id
    target_global.mkdir(parents=True, exist_ok=True)
    
    # Copia todo o diretório da skill (subpastas, scripts, resources se houver)
    for item in skill_source_dir.iterdir():
        if item.name == ".git":
            continue
        dest_item = target_global / item.name
        if item.is_dir():
            shutil.copytree(item, dest_item, dirs_exist_ok=True)
        else:
            if item.name == "SKILL.md":
                with open(dest_item, "w", encoding="utf-8") as f:
                    f.write(new_content)
            else:
                shutil.copy2(item, dest_item)

    # 2. Instala também no data/skills/<skill_id> para replicação com a VM
    target_data = DATA_SKILLS_DIR / skill_id
    target_data.mkdir(parents=True, exist_ok=True)
    with open(target_data / "SKILL.md", "w", encoding="utf-8") as f:
        f.write(new_content)

    logger.info(f"✅ Skill '{skill_id}' instalada com sucesso no Antigravity e no Oráculo!")
    return {
        "id": skill_id,
        "name": raw_name,
        "description": description,
        "global_path": str(target_global),
        "data_path": str(target_data)
    }

def link_skills_to_agent(agent_target: str, installed_skills: List[Dict[str, Any]]):
    """Vincula as skills importadas ao perfil JSON do agente alvo."""
    if not installed_skills:
        return

    agent_file = None
    # Procura agente pelo nome ou ID
    for f in AGENTS_DIR.glob("*.json"):
        if agent_target.lower() in f.stem.lower():
            agent_file = f
            break

    if not agent_file:
        logger.warning(f"Agente '{agent_target}' não encontrado em {AGENTS_DIR}. Skills não vinculadas a um perfil específico.")
        return

    try:
        with open(agent_file, "r", encoding="utf-8") as af:
            profile = json.load(af)

        external_skills = profile.setdefault("external_skills", [])
        existing_ids = {s.get("id") for s in external_skills if isinstance(s, dict)}

        added_count = 0
        for sk in installed_skills:
            if sk["id"] not in existing_ids:
                external_skills.append({
                    "id": sk["id"],
                    "name": sk["name"],
                    "description": sk.get("description", ""),
                    "source": "github_community"
                })
                added_count += 1

        with open(agent_file, "w", encoding="utf-8") as af:
            json.dump(profile, af, indent=2, ensure_ascii=False)

        agent_name = profile.get("name", agent_target)
        logger.info(f"🔗 {added_count} skills vinculadas com sucesso ao agente {agent_name} ({agent_file.name})!")
    except Exception as e:
        logger.error(f"Erro ao vincular skills ao perfil do agente: {e}")

def main():
    parser = argparse.ArgumentParser(description="Importador de Skills Comunitárias do GitHub para o Oráculo & Antigravity")
    parser.add_argument("--repo", default="emilkowalski/skills", help="Repositório GitHub (ex: emilkowalski/skills)")
    parser.add_argument("--prefix", default="community-emil", help="Prefixo de namespace para as skills (ex: community-emil)")
    parser.add_argument("--agent", default="alex_vance", help="Agente do Oráculo que herdará as skills (ex: alex_vance, bruno, quinn)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas inspeciona as skills sem instalar")
    args = parser.parse_args()

    print("=" * 60)
    print("🔮 ORÁCULO - HUB DE SKILLS COMUNITÁRIAS (GITHUB)")
    print(f"📦 Repositório Alvo : {args.repo}")
    print(f"🏷️ Namespace Prefixo: {args.prefix}")
    print(f"🎯 Agente Herdeiro  : {args.agent}")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "repo"
        if not clone_repo(args.repo, temp_path):
            sys.exit(1)

        skill_dirs = find_skills_in_repo(temp_path)
        if not skill_dirs:
            logger.warning("Nenhuma pasta contendo SKILL.md foi encontrada no repositório.")
            sys.exit(0)

        logger.info(f"✨ Encontradas {len(skill_dirs)} skills candidatas no repositório.")

        installed = []
        for sdir in skill_dirs:
            res = process_and_install_skill(sdir, namespace_prefix=args.prefix, dry_run=args.dry_run)
            if res:
                installed.append(res)

        if not args.dry_run and args.agent:
            link_skills_to_agent(args.agent, installed)

        print("\n" + "=" * 60)
        print(f"🎉 Processo concluído! Total de skills processadas: {len(installed)}")
        for it in installed:
            print(f"  • {it['id']} ({it['name']})")
        print("=" * 60)

if __name__ == "__main__":
    main()
