"""
Serviço de Sincronização e Mapeamento Inteligente: Gestores <-> Especialistas.
Garante que todo gestor de área conheça seus especialistas subordinados, suas competências
atualizadas (cursos estudados, habilidades dominadas) e mantenha seu SKILL.md e system_prompt
100% alinhados para delegação executiva.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import settings

logger = logging.getLogger("oraculo.manager_sync")

def _get_specialist_action_rule(specialist: Dict[str, Any]) -> str:
    """Gera uma recomendação executiva de quando acionar o especialista."""
    role_lower = specialist.get("role", "").lower()
    topics = specialist.get("topics_mastered", [])
    topics_str = ", ".join(topics[:4]).lower() if topics else ""

    if any(k in role_lower for k in ["arquiteto", "cto", "engenheiro", "software", "desenvolvedor", "tech", "código"]):
        return "Decisões de arquitetura, desenvolvimento de features complexas, integrações de APIs e revisão técnica."
    elif any(k in role_lower for k in ["vendas", "closer", "comercial", "negociação", "revenue", "b2b"]):
        return "Elaboração de scripts de vendas, quebra de objeções difíceis, negociação de alto valor e fechamento."
    elif any(k in role_lower for k in ["leitura", "memória", "foco", "mente", "cérebro", "cognitivo", "performance"]):
        return "Técnicas de aprendizado acelerado, absorção de novos conteúdos, rotinas de foco e otimização cognitiva."
    elif any(k in role_lower for k in ["conteúdo", "marketing", "copy", "redação", "mídia"]):
        return "Criação de artigos, roteiros, comunicação estratégica e materiais de marketing."
    else:
        if topics_str:
            return f"Tarefas operacionais e técnicas envolvendo {topics_str}."
        return "Execução operacional e suporte técnico no domínio da área."

def sync_all_managers_mappings() -> Dict[str, Any]:
    """
    Varre todas as áreas e sincroniza os gestores com seus especialistas atuais.
    Atualiza:
    1. O SKILL.md do gestor com a tabela viva de especialistas e competências
    2. O system_prompt do gestor no seu arquivo de perfil .json
    """
    settings.ensure_directories()
    areas_dir = settings.AREAS_DIR
    agents_dir = settings.AGENTS_DIR
    skills_dir = settings.DATA_DIR / "skills"

    if not areas_dir.exists():
        return {"status": "error", "message": "Diretório de áreas não encontrado"}

    synced_managers = []
    
    # Carrega todos os agentes existentes
    all_agents_map = {}
    for agent_file in agents_dir.glob("*.json"):
        try:
            with open(agent_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_agents_map[data.get("id")] = data
        except Exception as e:
            logger.warning(f"Erro ao ler agente {agent_file}: {e}")

    # Processa cada área cadastrada
    for area_file in areas_dir.glob("*.json"):
        try:
            with open(area_file, "r", encoding="utf-8") as f:
                area_data = json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler área {area_file}: {e}")
            continue

        area_id = area_data.get("id")
        area_name = area_data.get("name", area_id)
        manager_id = area_data.get("manager_agent_id")
        subagent_ids = area_data.get("subagent_ids", [])

        if not manager_id or manager_id not in all_agents_map:
            continue

        manager_profile = all_agents_map[manager_id]
        if manager_profile.get("agent_type") != "gestor":
            continue

        # Coleta os especialistas da área
        specialists = []
        for sub_id in subagent_ids:
            if sub_id in all_agents_map and sub_id != manager_id:
                specialists.append(all_agents_map[sub_id])

        # Também verifica se há técnicos com area_id apontando para cá mas fora de subagent_ids
        for ag_id, ag_data in all_agents_map.items():
            if ag_data.get("area_id") == area_id and ag_data.get("agent_type") == "tecnico":
                if ag_id not in subagent_ids:
                    subagent_ids.append(ag_id)
                    specialists.append(ag_data)

        # Salva subagent_ids atualizados na área se houve alteração
        if area_data.get("subagent_ids") != subagent_ids:
            area_data["subagent_ids"] = subagent_ids
            try:
                with open(area_file, "w", encoding="utf-8") as f:
                    json.dump(area_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Erro ao salvar subagent_ids na área {area_file}: {e}")

        # 1. ATUALIZAÇÃO DO SKILL.MD DO GESTOR
        manager_skill_dir = skills_dir / manager_id
        manager_skill_dir.mkdir(parents=True, exist_ok=True)
        manager_skill_file = manager_skill_dir / "SKILL.md"

        # Constrói tabela markdown dos especialistas
        if specialists:
            spec_rows = []
            for sp in specialists:
                sp_name = sp.get("name", sp.get("id"))
                sp_role = sp.get("role", "Especialista")
                topics = sp.get("topics_mastered", [])
                topics_display = ", ".join(topics[:5]) if topics else "Gerais do domínio"
                action_rule = _get_specialist_action_rule(sp)
                spec_rows.append(f"| **{sp_name}** | {sp_role} | `{topics_display}` | {action_rule} |")
            specialists_table = (
                "| Especialista | Cargo / Foco | Competências Principais | Quando Acionar |\n"
                "|--------------|--------------|-------------------------|----------------|\n"
                + "\n".join(spec_rows)
            )
        else:
            specialists_table = "*Nenhum especialista vinculado a esta área no momento. O gestor aguarda alocação de equipe técnica.*"

        # Se o SKILL.md já existe, substitui a seção de especialistas ou reconstrói
        skill_content = ""
        if manager_skill_file.exists():
            try:
                with open(manager_skill_file, "r", encoding="utf-8") as sf:
                    existing_text = sf.read()
                
                # Regex para substituir a seção "## Agentes Especialistas Sob Gestão" até a próxima seção "## "
                pattern = r"(## Agentes Especialistas Sob Gestão\s*\n)(.*?)(?=\n## |\Z)"
                replacement = f"\\1{specialists_table}\n"
                if re.search(pattern, existing_text, flags=re.DOTALL):
                    skill_content = re.sub(pattern, replacement, existing_text, flags=re.DOTALL)
                else:
                    skill_content = existing_text + f"\n\n## Agentes Especialistas Sob Gestão\n{specialists_table}\n"
            except Exception as e:
                logger.warning(f"Erro ao ler SKILL.md de {manager_id}: {e}")

        if not skill_content:
            # Cria do zero se não existia
            skill_content = f"""# Skill: {manager_profile.get('name')} — {manager_profile.get('role')}
**ID**: `{manager_id}`  
**Papel**: {manager_profile.get('role')}  
**Área**: {area_name}  
**Hierarquia**: GESTOR DE NEGÓCIOS  

## Missão Executiva
Liderar estrategicamente a área de {area_name}, convertendo metas de negócio em planos de ação executáveis e delegando tarefas técnicas aos especialistas da equipe.

## Competências de Gestão
- `Liderança e Alocação de Especialistas`
- `Priorização de Backlog e Roadmaps`
- `Análise de ROI, Custo e Prazos`
- `Comunicação Executiva e Report de Status`
- `Alinhamento Cross-Áreas com outros Gestores`

## Agentes Especialistas Sob Gestão
{specialists_table}

## Protocolo de Delegação
1. **Receber demanda** → Avaliar viabilidade e impacto no negócio.
2. **Definir escopo** → Traduzir em briefing estruturado.
3. **Delegar ao especialista certo** → Escolher baseado nas competências mapeadas.
4. **Avaliar entrega** → Validar qualidade antes de aprovar.
5. **Reportar ao solicitante** → Explicar a solução em termos de resultados.

## Regras de Ouro
- NUNCA executar tarefas operacionais diretamente. Sempre delegar para a equipe técnica.
- SEMPRE acompanhar métricas de entrega e aprendizado dos especialistas.
- Em demandas complexas que envolvam outras áreas, alinhar com os respectivos gestores.
"""

        try:
            with open(manager_skill_file, "w", encoding="utf-8") as sf:
                sf.write(skill_content)
        except Exception as e:
            logger.error(f"Erro ao gravar SKILL.md de {manager_id}: {e}")

        # 2. ATUALIZAÇÃO DO SYSTEM_PROMPT DO GESTOR
        specialists_prompt_summary = []
        for sp in specialists:
            sp_name = sp.get("name", sp.get("id"))
            sp_role = sp.get("role", "Especialista")
            topics = sp.get("topics_mastered", [])
            topics_snippet = f" (Domínios: {', '.join(topics[:4])})" if topics else ""
            specialists_prompt_summary.append(f"- {sp_name} [{sp_role}]{topics_snippet}: {_get_specialist_action_rule(sp)}")

        team_desc = "\n".join(specialists_prompt_summary) if specialists_prompt_summary else "Nenhum especialista alocado no momento."

        updated_system_prompt = f"""Você é {manager_profile.get('name')}, {manager_profile.get('role')} da área de {area_name} no Oráculo.
Seu papel é EXCLUSIVAMENTE de liderança executiva, estratégia e distribuição inteligente de tarefas. Você NUNCA faz trabalho braçal ou operacional diretamente.

SUA EQUIPE DE ESPECIALISTAS ATUALMENTE MAPEADA:
{team_desc}

COMO VOCÊ TRABALHA:
1. Quando o usuário ou o Oráculo trouxer uma necessidade, analise o objetivo de negócio.
2. Identifique qual especialista da sua equipe possui as habilidades adequadas.
3. Formule a orientação ou consulte o especialista para obter a resposta técnica precisa.
4. Entregue a solução consolidada com foco em resultado, clareza e impacto no negócio.
5. Se a demanda exigir competências fora da sua área, sugira acionar os gestores responsáveis."""

        manager_profile["system_prompt"] = updated_system_prompt
        manager_profile["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Salva o perfil do gestor atualizado
        manager_file = agents_dir / f"{manager_id}.json"
        try:
            with open(manager_file, "w", encoding="utf-8") as mf:
                json.dump(manager_profile, mf, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar perfil do gestor {manager_id}: {e}")

        synced_managers.append({
            "manager_id": manager_id,
            "manager_name": manager_profile.get("name"),
            "area_id": area_id,
            "area_name": area_name,
            "specialists_count": len(specialists),
            "specialists": [s.get("name") for s in specialists]
        })

    return {
        "status": "success",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "total_managers_synced": len(synced_managers),
        "managers": synced_managers
    }

def analyze_manager_skill_gaps(manager_id: str) -> Dict[str, Any]:
    """O Gestor de Área analisa o portfólio de habilidades de seus especialistas,
    detecta lacunas (Skill Gaps) em relação aos objetivos de projetos e emite um
    parecer executivo com pedidos de materiais de estudo ou recomendação de contratação."""
    from orchestration.harness import AgentHarness, load_agent_context

    manager_ctx = load_agent_context(manager_id)
    if not manager_ctx or manager_ctx.get("agent_type") != "gestor":
        return {"error": f"Agente '{manager_id}' não é um gestor executivo válido."}

    area_id = manager_ctx.get("area_id")
    agents_dir = settings.AGENTS_DIR

    # Localiza especialistas da área
    specialists = []
    if agents_dir.exists():
        for af in agents_dir.glob("*.json"):
            try:
                with open(af, "r", encoding="utf-8") as fp:
                    ag = json.load(fp)
                    if ag.get("area_id") == area_id and ag.get("agent_type") == "tecnico":
                        specialists.append(ag)
            except Exception:
                continue

    team_summary = []
    for s in specialists:
        topics = ", ".join(s.get("topics_mastered", [])[:8]) or "Nenhum tópico formal indexado"
        hours = s.get("total_hours_studied", 0)
        team_summary.append(f"- {s.get('name')} ({s.get('role')}): {hours:.1f}h estudadas. Tópicos dominados: {topics}")

    team_desc = "\n".join(team_summary)

    prompt = f"""Você é {manager_ctx.get('name')}, {manager_ctx.get('role')} da área de {area_id} no Oráculo.
Sua missão é realizar uma análise de lacunas de competência (Skill Gap Analysis) da sua equipe para orientar o fundador.

Sua Equipe Atual de Especialistas:
{team_desc}

Como líder executivo(a), analise friamente e responda estritamente em formato JSON:
{{
  "manager_name": "{manager_ctx.get('name')}",
  "area_id": "{area_id}",
  "team_status": "Um parágrafo resumindo a maturidade técnica atual da equipe",
  "identified_gaps": [
    {{
      "gap_name": "Nome da competência em falta (ex: Engenharia de QA & TDD)",
      "impact": "Alto / Médio / Crítico",
      "why_current_team_doesnt_cover": "Por que os especialistas atuais não devem ser sobrecarregados com isso"
    }}
  ],
  "recommendations": [
    {{
      "action_type": "hire_new_agent ou upskill_existing",
      "target_agent": "Nome do agente ou Novo Agente Sugerido",
      "requested_study_materials": [
        "Livro / Curso / Documentação específica que o fundador deve colocar no Drive/Telegram"
      ],
      "rationale": "Justificativa de negócio"
    }}
  ],
  "immediate_delegation_strategy": "Como você vai distribuir as tarefas enquanto a defasagem não é sanada"
}}
"""

    harness = AgentHarness()
    raw = harness._call_gemini_raw(prompt)

    json_text = raw
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0].strip()

    try:
        diagnosis = json.loads(json_text)
    except Exception as e:
        diagnosis = {
            "manager_name": manager_ctx.get("name"),
            "area_id": area_id,
            "raw_response": raw,
            "error_parsing": str(e)
        }

    # Salva o diagnóstico em data/areas/{area_id}_gap_analysis.json
    gap_file = settings.AREAS_DIR / f"{area_id}_gap_analysis.json"
    try:
        with open(gap_file, "w", encoding="utf-8") as gf:
            json.dump(diagnosis, gf, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar gap analysis: {e}")

    return diagnosis

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    result = sync_all_managers_mappings()
    print(json.dumps(result, indent=2, ensure_ascii=False))
