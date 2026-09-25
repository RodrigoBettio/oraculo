"""
Oráculo Autonomous Competency Guardrail & Inter-Agent Delegator
Módulo de governança técnica que garante que nenhum agente responda fora do seu domínio,
realizando hand-off elegante e delegação automática no mesmo turno para o especialista adequado.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path

from config import settings

logger = logging.getLogger("agent_delegator")

@dataclass
class DelegationDecision:
    is_competent: bool
    detected_topic: str
    target_agent_id: Optional[str]
    target_agent_name: Optional[str]
    target_agent_role: Optional[str]
    target_agent_avatar: Optional[str]
    reason: str

class AgentDelegator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentDelegator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Carrega todos os perfis de agentes ativos do diretório data/agents/."""
        agents = []
        if not settings.AGENTS_DIR.exists():
            return agents
        for f in settings.AGENTS_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as af:
                    data = json.load(af)
                    agents.append(data)
            except Exception as e:
                logger.warning(f"Erro ao ler perfil do agente {f.name}: {e}")
        return agents

    def find_agent(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Busca um agente por ID, nome ou menção (@vance, @jordan, etc.)."""
        clean_id = identifier.replace("@", "").strip().lower()
        agents = self.get_all_agents()

        # Mapeamentos diretos de atalhos comuns
        aliases = {
            "vance": "agent_alex_vance",
            "alex": "agent_alex_vance",
            "alex_vance": "agent_alex_vance",
            "quinn": "agent_quinn_qa_7781",
            "qa": "agent_quinn_qa_7781",
            "claudio": "agent_claudio_cloud_4421",
            "cloud": "agent_claudio_cloud_4421",
            "devops": "agent_claudio_cloud_4421",
            "jordan": "agent_jordan_belford_5567",
            "belford": "agent_jordan_belford_5567",
            "link": "agent_link_4211",
            "diamand": "agent_andre_diamand_1281",
            "andre": "agent_andre_diamand_1281",
            "helena": "gestor_tech_cto",
            "monge": "agent_o_monge_8324",
            "o_monge": "agent_o_monge_8324"
        }
        resolved_id = aliases.get(clean_id, clean_id)

        for ag in agents:
            ag_id = ag.get("id", "").lower()
            ag_name = ag.get("name", "").lower()
            if ag_id == resolved_id or clean_id in ag_id or clean_id in ag_name:
                return ag
        return None

    def _call_gemini_fast(self, prompt: str) -> str:
        """Chama a API do Gemini com rotação de chaves e fallback resiliente."""
        from google import genai
        keys = settings.GEMINI_API_KEYS or ([settings.GEMINI_API_KEY] if settings.GEMINI_API_KEY else [])
        if not keys:
            raise RuntimeError("Nenhuma chave GEMINI_API_KEY disponível.")

        models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
        last_err = None

        for attempt in range(len(keys) * 2):
            key = keys[attempt % len(keys)]
            cl = genai.Client(api_key=key)
            for model_name in models_to_try:
                try:
                    resp = cl.models.generate_content(model=model_name, contents=prompt)
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception as err:
                    last_err = err
                    err_msg = str(err).upper()
                    if any(x in err_msg for x in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "HIGH DEMAND"]):
                        import time
                        time.sleep(0.8)
                        continue
                    else:
                        break
        raise RuntimeError(f"Falha ao chamar Gemini no delegator: {last_err}")

    def evaluate_competency(self, origin_agent: Dict[str, Any], query: str) -> DelegationDecision:
        """Avalia se o origin_agent tem competência para responder à query ou se deve delegar."""
        all_agents = self.get_all_agents()
        origin_id = origin_agent.get("id")
        origin_name = origin_agent.get("name")
        origin_role = origin_agent.get("role")
        origin_topics = origin_agent.get("topics_mastered", [])[:10]

        # Resumo dos outros especialistas disponíveis para a IA de roteamento
        team_catalog = []
        for ag in all_agents:
            if ag.get("id") == origin_id:
                continue
            topics_sample = ", ".join(ag.get("topics_mastered", [])[:5])
            team_catalog.append(
                f"- ID: '{ag.get('id')}' | Nome: '{ag.get('name')}' | Cargo: '{ag.get('role')}' | Domina: {topics_sample}"
            )
        catalog_str = "\n".join(team_catalog)

        prompt = f"""
Você é o Guardião de Competências e Roteador Técnico do Oráculo.
O usuário fez uma pergunta para o especialista: {origin_name} ({origin_role}).
Tópicos dominados por {origin_name}: {', '.join(origin_topics)}.

OUTROS ESPECIALISTAS DISPONÍVEIS NA EQUIPE:
{catalog_str}

PERGUNTA DO USUÁRIO: "{query}"

SUA MISSÃO:
1. Analise se a pergunta está REALMENTE dentro do escopo de atuação de {origin_name}.
   - Exemplo: Se perguntarem de Playwright, automação de testes ou TDD para o Alex Vance (arquiteto de backend), ele NÃO deve responder, pois temos o Quinn QA.
   - Exemplo: Se perguntarem de vendas, prospecção ou fechamento para o Alex Vance ou Quinn, eles NÃO devem responder, pois temos o Jordan Belford.
   - Exemplo: Se perguntarem de Docker, Kubernetes ou infra GCP para o Alex Vance, ele deve delegar para o Cláudio Cloud.
   - Exemplo: Se perguntarem de arquitetura de software para o Quinn ou Jordan, eles devem delegar para o Alex Vance.
   - Se for uma pergunta que o próprio {origin_name} domina diretamente, `is_competent` DEVE ser true.

2. Se `is_competent` for false, encontre o ID do especialista mais qualificado da lista acima.
   - Se nenhum especialista da equipe cobrir o assunto (ex: Direito Tributário, Medicina, Contabilidade), defina `delegate_to_id` como null.

Retorne ESTRITAMENTE um JSON no formato:
{{
  "is_competent": true ou false,
  "detected_topic": "Resumo do tema da pergunta em poucas palavras",
  "reason": "Explicação concisa do motivo",
  "delegate_to_id": "ID_DO_ESPECIALISTA" ou null
}}
"""
        try:
            raw_res = self._call_gemini_fast(prompt)
            match = re.search(r"\{.*\}", raw_res, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                is_comp = bool(data.get("is_competent", True))
                target_id = data.get("delegate_to_id")
                topic = data.get("detected_topic", "o tema consultado")
                reason = data.get("reason", "")

                target_agent = None
                if not is_comp and target_id:
                    target_agent = next((a for a in all_agents if a.get("id") == target_id), None)

                return DelegationDecision(
                    is_competent=is_comp,
                    detected_topic=topic,
                    target_agent_id=target_agent.get("id") if target_agent else None,
                    target_agent_name=target_agent.get("name") if target_agent else None,
                    target_agent_role=target_agent.get("role") if target_agent else None,
                    target_agent_avatar=target_agent.get("avatar") if target_agent else None,
                    reason=reason
                )
        except Exception as e:
            logger.warning(f"Erro na avaliação de competência via IA, mantendo origin_agent: {e}")

        # Fallback padrão seguro: considera competente para não travar o fluxo
        return DelegationDecision(
            is_competent=True,
            detected_topic="consulta geral",
            target_agent_id=None,
            target_agent_name=None,
            target_agent_role=None,
            target_agent_avatar=None,
            reason="Fallback por timeout"
        )

    def generate_agent_response(self, agent: Dict[str, Any], query: str, context_prefix: str = "") -> str:
        """Executa a resposta técnica do agente com base em sua skill e persona."""
        agent_id = agent.get("id")
        agent_name = agent.get("name")
        agent_role = agent.get("role")
        skill_file = settings.DATA_DIR / "skills" / agent_id / "SKILL.md"

        skill_context = ""
        if skill_file.exists():
            try:
                with open(skill_file, "r", encoding="utf-8") as sf:
                    skill_context = sf.read()[:9000]
            except Exception:
                pass

        prompt = f"""
Você é {agent_name} ({agent_role}), especialista oficial do ecossistema Oráculo.
Responda ao Rodrigo Bettio Jr. de forma objetiva, direta e aplicando seus conceitos técnicos reais estudados.

BASE DE CONHECIMENTO & REGRAS:
{skill_context}

{context_prefix}
DÚVIDA DO RODRIGO: {query}
"""
        return self._call_gemini_fast(prompt)

    def consult(self, origin_identifier: str, query: str) -> str:
        """
        Ponto de entrada unificado para consulta com Fallback e Delegação Inter-Agentes.
        """
        origin_agent = self.find_agent(origin_identifier)
        if not origin_agent:
            return f"❌ Especialista `{origin_identifier}` não encontrado no organograma."

        origin_id = origin_agent.get("id")
        origin_name = origin_agent.get("name")
        origin_role = origin_agent.get("role")
        origin_avatar = origin_agent.get("avatar", "🧠")

        # CASO 1: Helena Torres (VP de TI) tem fluxo executivo especial (consulta Alex Vance)
        if "helena" in origin_id.lower() or "gestor_tech" in origin_id.lower():
            vance_agent = self.find_agent("agent_alex_vance")
            vance_skills = ""
            if vance_agent:
                vfile = settings.DATA_DIR / "skills" / "agent_alex_vance" / "SKILL.md"
                if vfile.exists():
                    vance_skills = vfile.read_text(encoding="utf-8")[:6000]

            vance_prompt = (
                f"Você é Alex Vance (⚡), Arquiteto-Chefe de Software & IA do Oráculo.\n"
                f"Sua VP de TI (Helena Torres) precisa do seu parecer técnico para responder ao Rodrigo.\n"
                f"BASE TÉCNICA ABSORVIDA:\n{vance_skills}\n\n"
                f"PERGUNTA DO RODRIGO: {query}\n\n"
                f"Emita seu parecer técnico de arquitetura, padrões e viabilidade."
            )
            vance_opinion = self._call_gemini_fast(vance_prompt)

            helena_prompt = (
                f"Você é Helena Torres (👩‍💼), VP de Tecnologia & Inovação Digital do Oráculo.\n"
                f"Você NUNCA programa ou faz trabalho braçal. Seu papel é liderança executiva, priorização e estratégia.\n"
                f"Você consultou seu Arquiteto-Chefe Alex Vance sobre a demanda do Rodrigo.\n\n"
                f"PARECER TÉCNICO DO ALEX VANCE:\n{vance_opinion}\n\n"
                f"PERGUNTA ORIGINAL DO RODRIGO: {query}\n\n"
                f"Responda ao Rodrigo informando que consultou o Alex Vance, sintetizando a solução técnica dele, "
                f"e acrescentando sua visão executiva de prazos, riscos, alocação de equipe e próximos passos."
            )
            helena_opinion = self._call_gemini_fast(helena_prompt)
            return f"👩‍💼 **[{origin_name} — {origin_role}]**:\n\n{helena_opinion}"

        # CASO 2: Avaliação de Competência e Delegação
        decision = self.evaluate_competency(origin_agent, query)

        # 2.1. Agente é competente: responde normalmente
        if decision.is_competent:
            ans = self.generate_agent_response(origin_agent, query)
            return f"{origin_avatar} **[{origin_name} — {origin_role}]**:\n\n{ans}"

        # 2.2. Agente NÃO é competente e existe especialista qualificado na equipe (Hand-Off)
        if decision.target_agent_id:
            target_agent = self.find_agent(decision.target_agent_id)
            if target_agent:
                target_name = decision.target_agent_name or target_agent.get("name")
                target_role = decision.target_agent_role or target_agent.get("role")
                target_avatar = decision.target_agent_avatar or target_agent.get("avatar", "🧠")

                # Gera a declaração de hand-off elegante do agente de origem
                handoff_prompt = (
                    f"Você é {origin_name} ({origin_role}).\n"
                    f"O Rodrigo perguntou: \"{query}\".\n"
                    f"Esse assunto ({decision.detected_topic}) NÃO é a sua especialidade.\n"
                    f"O especialista certo na equipe é {target_name} ({target_role}).\n"
                    f"Em 1 ou 2 frases curtas, assuma de forma elegante e transparente que essa matéria não faz parte "
                    f"do seu escopo principal e informe que está transferindo a palavra para o {target_name}."
                )
                origin_handoff = self._call_gemini_fast(handoff_prompt)

                # Gera a resposta do especialista de destino
                target_prefix = f"Nota: Você recebeu esta demanda transferida por {origin_name}, pois você é o especialista no assunto.\n"
                target_solution = self.generate_agent_response(target_agent, query, context_prefix=target_prefix)

                return (
                    f"{origin_avatar} **[{origin_name} — {origin_role}]**:\n"
                    f"{origin_handoff}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{target_avatar} **[{target_name} — {target_role}]**:\n\n"
                    f"{target_solution}"
                )

        # 2.3. Agente NÃO é competente e NENHUM especialista cobre o assunto (Team GAP)
        return (
            f"{origin_avatar} **[{origin_name} — {origin_role}]**:\n\n"
            f"Rodrigo, analisei a sua dúvida sobre **{decision.detected_topic}**.\n\n"
            f"Como {origin_role}, meu foco técnico é outro, e identifiquei que **atualmente nenhum especialista da nossa equipe** "
            f"possui formação ou cursos absorvidos sobre essa área no organograma.\n\n"
            f"💡 **Como podemos resolver**:\n"
            f"1. Você pode consultar a nossa VP de TI (**@Helena Torres** via `/perguntar @helena`) para que ela registre essa defasagem (GAP) na equipe.\n"
            f"2. Ou disponibilizar cursos sobre o tema na pasta do Google Drive (`Mestre dos Cursos`), permitindo que a nossa esteira de estudos treine um novo especialista dedicado!"
        )

# Singleton global
agent_delegator = AgentDelegator()
