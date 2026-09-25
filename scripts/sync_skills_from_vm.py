#!/usr/bin/env python3
"""
Oráculo Knowledge Synchronizer
Sincroniza o conhecimento acumulado na VM (data/skills e data/agents)
diretamente para a pasta global de skills do Antigravity (~/.gemini/config/skills).
"""

import os
import sys
import json
import shutil
import subprocess
import re
from pathlib import Path

# Garante suporte a UTF-8 no console do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VM_USER = "rodriguinhobettiojr"
VM_HOST = "34.46.39.111"
SSH_KEY = Path.home() / ".ssh" / "id_ed25519"

LOCAL_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DATA_DIR = LOCAL_ROOT / "data"
LOCAL_SKILLS_DIR = LOCAL_DATA_DIR / "skills"
LOCAL_AGENTS_DIR = LOCAL_DATA_DIR / "agents"

ANTIGRAVITY_SKILLS_DIR = Path.home() / ".gemini" / "config" / "skills"

def run_ssh_cmd(cmd: str) -> str:
    """Executa um comando remoto na VM via SSH."""
    ssh_cmd = [
        "ssh",
        "-i", str(SSH_KEY),
        "-o", "StrictHostKeyChecking=no",
        f"{VM_USER}@{VM_HOST}",
        cmd
    ]
    res = subprocess.run(ssh_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"Erro no SSH: {res.stderr.strip()}")
    return res.stdout.strip()

def run_scp_download(remote_path: str, local_path: Path):
    """Baixa arquivos ou pastas da VM via SCP."""
    local_path.mkdir(parents=True, exist_ok=True)
    scp_cmd = [
        "scp",
        "-i", str(SSH_KEY),
        "-o", "StrictHostKeyChecking=no",
        "-r",
        f"{VM_USER}@{VM_HOST}:{remote_path}",
        str(local_path)
    ]
    res = subprocess.run(scp_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"Erro no SCP: {res.stderr.strip()}")

def trigger_remote_compilation():
    """Garante que a VM compile os SKILL.md de todos os agentes a partir das aulas processadas."""
    print("🔄 Solicitando à VM para compilar os SKILL.md dos agentes atualizados...")
    remote_script = (
        "curl -s http://localhost:8000/api/agents | "
        "grep -o '\"id\":\"[^\"]*\"' | cut -d'\"' -f4 | "
        "while read -r aid; do "
        "  curl -s \"http://localhost:8000/api/agents/$aid/spec\" > /dev/null; "
        "done"
    )
    try:
        run_ssh_cmd(remote_script)
        print("✅ Compilação na VM concluída!")
    except Exception as e:
        print(f"⚠️ Aviso na compilação remota: {e} (prosseguindo com arquivos existentes)")

def sync_knowledge():
    print(f"\n========================================================")
    print(f"   🔮 ORÁCULO ➔ ANTIGRAVITY KNOWLEDGE SYNCHRONIZER     ")
    print(f"========================================================\n")
    print(f"📡 Conectando na VM ({VM_HOST})...")

    # 1. Compila na VM
    trigger_remote_compilation()

    # 2. Baixa data/agents da VM para local
    print("📥 Baixando agentes atualizados da VM...")
    LOCAL_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        run_scp_download("~/oraculo/data/agents/*", LOCAL_AGENTS_DIR)
        print(f"✅ Agentes salvos em: {LOCAL_AGENTS_DIR}")
    except Exception as e:
        print(f"⚠️ Erro ao baixar agentes: {e}")

    # 3. Baixa data/skills da VM para local
    print("📥 Baixando skills compiladas da VM...")
    LOCAL_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        run_scp_download("~/oraculo/data/skills/*", LOCAL_SKILLS_DIR)
        print(f"✅ Skills salvas em: {LOCAL_SKILLS_DIR}")
    except Exception as e:
        print(f"⚠️ Erro ao baixar skills: {e}")

    # 4. Instala as skills no Antigravity (~/.gemini/config/skills/)
    print("\n🧠 Instalando e atualizando Skills no Antigravity...")
    ANTIGRAVITY_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    synced_agents = []

    for agent_json in LOCAL_AGENTS_DIR.glob("*.json"):
        try:
            with open(agent_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            agent_id = data.get("id")
            name = data.get("name", "Especialista")
            role = data.get("role", "Consultor")
            avatar = data.get("avatar", "🧠")
            hours = data.get("total_hours_studied", 0.0)
            videos = data.get("total_videos_studied", 0)
            topics = data.get("topics_mastered", [])
            seniority = data.get("seniority", {})
            rank = seniority.get("rank", "Júnior")
            badge = seniority.get("badge", "🥉")

            # Determina slug da pasta da skill
            clean_name = re.sub(r'[^\w\s-]', '', name).strip().lower().replace(" ", "-")
            skill_dir_name = f"oraculo-{clean_name}"
            target_skill_dir = ANTIGRAVITY_SKILLS_DIR / skill_dir_name
            target_skill_dir.mkdir(parents=True, exist_ok=True)
            target_skill_file = target_skill_dir / "SKILL.md"

            # Busca o arquivo de skill compilado correspondente
            src_skill_file = LOCAL_SKILLS_DIR / agent_id / "SKILL.md"
            if not src_skill_file.exists():
                # Tenta buscar pelo slug direto se houver
                src_skill_file = LOCAL_SKILLS_DIR / skill_dir_name / "SKILL.md"

            if src_skill_file.exists():
                shutil.copy2(src_skill_file, target_skill_file)
            else:
                # Gera um SKILL.md de alta fidelidade a partir do JSON do agente se ainda não compilado
                courses_str = ", ".join([s.get("group_name", "") for s in data.get("sources", [])]) or "Base de Conhecimento Oráculo"
                topics_sample = ", ".join(topics[:6]) if topics else "Especialista Multimodal"
                
                content = f"""---
name: {skill_dir_name}
description: Especialista {name} ({role}). Domina: {topics_sample}. Use quando o usuário pedir análises, estratégias e padrões aprendidos em {courses_str}.
---

# Skill: {name} - {role}

> [!NOTE]
> Esta skill foi sintetizada automaticamente pelo **Oráculo Engine** a partir de **{hours:.2f} horas** e **{videos} aulas reais** estudadas.

## 1. Identidade & Ficha Operacional
- **Especialista**: {name} ({avatar})
- **Papel**: {role}
- **Senioridade**: {rank} ({badge})
- **Horas Estudadas**: `{hours:.2f}h` ({videos} aulas concluídas)
- **Cursos Estudados**: {courses_str}

## 2. Habilidades & Tópicos Dominados
"""
                for t in topics:
                    content += f"- `{t}`\n"

                content += f"""
## 3. Diretrizes de Comunicação
- Responda como o especialista **{name}**, utilizando o tom, vocabulário e mentalidade de {role}.
- Aplique diretamente os conceitos e frameworks aprendidos nos cursos estudados.
- Sempre que pertinente, cite lições e regras práticas aprendidas nas aulas.
"""
                with open(target_skill_file, "w", encoding="utf-8") as f:
                    f.write(content)

            synced_agents.append({
                "name": f"{avatar} {name}",
                "role": role,
                "hours": f"{hours:.1f}h",
                "videos": videos,
                "rank": f"{badge} {rank}",
                "skill_path": str(target_skill_file)
            })

        except Exception as e:
            print(f"⚠️ Erro ao processar agente {agent_json.name}: {e}")

    # 5. Relatório final formatado
    print("\n" + "="*80)
    print(f"{'AGENTE':<25} | {'CARGO':<20} | {'HORAS':<7} | {'AULAS':<6} | {'SENIORIDADE'}")
    print("="*80)
    for ag in synced_agents:
        print(f"{ag['name']:<25} | {ag['role']:<20} | {ag['hours']:<7} | {ag['videos']:<6} | {ag['rank']}")
    print("="*80)
    print(f"\n🎉 Sincronização concluída com sucesso!")
    print(f"Total de {len(synced_agents)} especialistas prontos para interação direta no Antigravity!\n")

if __name__ == "__main__":
    sync_knowledge()
