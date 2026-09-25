#!/usr/bin/env python3
"""
Provisiona oficialmente Quinn QA e Cláudio Cloud no organograma do Oráculo.
Gera os arquivos de perfil em data/agents/ e compila suas skills ricas.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
AGENTS_DIR = BASE_DIR / "data" / "agents"
SKILLS_DIR = BASE_DIR / "data" / "skills"

SPECIALISTS = [
    {
        "id": "agent_quinn_qa_7781",
        "name": "Quinn QA",
        "role": "Especialista em QA & Testes Automatizados (SDET)",
        "avatar": "🧪",
        "status": "ativo",
        "area_id": "tech",
        "agent_type": "tecnico",
        "topics_mastered": [
            "Test-Driven Development (TDD) estrito",
            "Automação End-to-End com Playwright",
            "Page Object Model (POM) para UI",
            "Testes de Unidade e Integração com PyTest",
            "Mocks, Spies, Stubs e Fixtures herméticas",
            "Qualidade e Gates de Teste em Pipelines CI/CD",
            "Testes Visuais de Regressão e Traces",
            "Emulação Mobile e Testes Cross-Browser"
        ],
        "capabilities": ["answer_questions", "generate_specs", "write_code", "write_tests"],
        "external_skills": [
            {
                "id": "community-qa-playwright-e2e",
                "name": "Playwright E2E Testing Mastery",
                "description": "Automação de testes End-to-End com Playwright.",
                "source": "curated_suite"
            },
            {
                "id": "community-qa-test-driven-development",
                "name": "Test-Driven Development (TDD) Protocol",
                "description": "Ciclos TDD (Red-Green-Refactor) e asserções estritas.",
                "source": "curated_suite"
            }
        ]
    },
    {
        "id": "agent_claudio_cloud_4421",
        "name": "Cláudio Cloud",
        "role": "Especialista em Infraestrutura Cloud & DevOps/SRE",
        "avatar": "☁️",
        "status": "ativo",
        "area_id": "tech",
        "agent_type": "tecnico",
        "topics_mastered": [
            "Google Cloud Platform (GCP) Compute, Cloud Run e VPC",
            "Docker Hardening e Builds Multi-Stage seguros",
            "Execução de Containers Non-Root e Least Privilege",
            "Engenharia de Confiabilidade de Sites (SRE) e SLOs",
            "Pipelines CI/CD com GitHub Actions e Deploy Contínuo",
            "Monitoramento, Logs Estruturados e Auto-Healing",
            "Segurança de Redes, Reverse Proxy Nginx e SSL",
            "Kubernetes & Orquestração de Microserviços"
        ],
        "capabilities": ["answer_questions", "generate_specs", "write_code", "manage_infra"],
        "external_skills": [
            {
                "id": "community-cloud-docker-hardening",
                "name": "Production Docker Hardening & Security",
                "description": "Hardening de containers Docker de produção.",
                "source": "curated_suite"
            },
            {
                "id": "community-cloud-gcp-sre",
                "name": "Google Cloud Site Reliability Engineering (SRE)",
                "description": "Confiabilidade, observabilidade e resiliência na GCP.",
                "source": "curated_suite"
            }
        ]
    }
]

def provision_specialists():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    for spec in SPECIALISTS:
        agent_id = spec["id"]
        spec["sources"] = []
        spec["created_at"] = now
        spec["updated_at"] = now

        # Salva o perfil em data/agents/
        agent_file = AGENTS_DIR / f"{agent_id}.json"
        with open(agent_file, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        print(f"✅ Agente '{spec['name']}' ({agent_id}) salvo com sucesso em {agent_file}")

        # Cria a pasta de skill em data/skills/<agent_id>/SKILL.md
        skill_dir = SKILLS_DIR / agent_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        topics_md = "\n".join([f"- {t}" for t in spec["topics_mastered"]])
        ext_skills_md = "\n".join([f"- **{e['name']}** (`{e['id']}`): {e['description']}" for e in spec["external_skills"]])

        content = f"""---
name: oraculo-{spec['name'].lower().replace(' ', '-')}
description: {spec['role']}. Especialista do Oráculo.
---

# Skill: {spec['name']} ({spec['avatar']} — {spec['role']})

## Domínio de Atuação
{spec['role']}.
Atua como referência máxima do Oráculo nesta área.

## Tópicos Dominados
{topics_md}

## Skills Globais Integradas
{ext_skills_md}

## Postura e Diretrizes
1. Seja direto, prático e demonstre autoridade técnica de nível sênior/staff.
2. Forneça sempre exemplos de código funcionais e recomendações claras.
3. Se o usuário perguntar algo fora do seu escopo, indique que seu foco é {spec['role']}.
"""
        with open(skill_file, "w", encoding="utf-8") as sf:
            sf.write(content)
        print(f"✅ Skill de '{spec['name']}' escrita em {skill_file}")

if __name__ == "__main__":
    provision_specialists()
