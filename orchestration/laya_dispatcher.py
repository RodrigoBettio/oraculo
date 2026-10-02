"""
Oráculo — Motor Laya de Decisão Rápida (System 1 Dispatcher)
Arquitetura: Bruno (AI Builder), Helena Torres (VP Tech) & Alex Vance (Chief Architect)

Raciocínio Heurístico em < 5ms para:
1. Roteamento de Gestores Executivos (Helena, Ricardo, Camila, Marcelo)
2. Guardrail de Competência e Hand-off de Especialistas
3. Detecção de GAPs Técnicos em Tempo Real (Zero Tokens de LLM)
4. Atribuição Automática de Cursos e Pastas do Google Drive
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

from config import settings

logger = logging.getLogger("laya_dispatcher")

PT_STOPWORDS = {
    "a", "ao", "aos", "as", "ate", "com", "como", "da", "das", "de", "dela", "delas",
    "dele", "deles", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre",
    "era", "eram", "essa", "essas", "esse", "esses", "esta", "estao", "estas", "este",
    "estes", "eu", "foi", "fomos", "foram", "isso", "isto", "ja", "lhe", "lhes", "mais",
    "mas", "me", "mesmo", "meu", "meus", "minha", "minhas", "muito", "na", "nas", "nao",
    "no", "nos", "nossa", "nossas", "nosso", "nossos", "num", "numa", "o", "os", "ou",
    "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quando", "que", "quem",
    "se", "sem", "ser", "seu", "seus", "so", "sua", "suas", "tambem", "te", "tem",
    "temos", "tenho", "um", "uma", "voces", "voce", "pra", "pro", "pras", "pros",
    "sobre", "como", "fazer", "ajuda", "duvida", "preciso", "saber", "explicar",
    "quero", "pode", "podemos", "seria", "tenho", "falar", "perguntar",
    "simples", "pessoa", "pessoas", "geral", "forma", "exemplo", "caso", "nivel",
    "tipo", "tipos", "dia", "ano", "mes", "parte", "partes", "coisa", "coisas",
    "tempo", "bom", "boa", "novo", "nova", "novos", "ver", "dar", "ponto", "pontos"
}

# Assinaturas explícitas de domínios técnicos e seus especialistas líderes
DOMAIN_SIGNATURES: Dict[str, Dict[str, Any]] = {
    # === TECNOLOGIA (HELENA TORRES) ===
    "agent_quinn_qa_7781": {
        "keywords": [
            "playwright", "cypress", "selenium", "teste", "testes", "tdd", "bdd",
            "e2e", "end-to-end", "unitario", "unitarios", "integracao", "qa",
            "qualidade", "bug", "bugs", "regressao", "mock", "mocks", "fixture",
            "fixtures", "pytest", "cobertura", "assertion", "assercoes"
        ],
        "weight": 2.5
    },
    "agent_claudio_cloud_4421": {
        "keywords": [
            "docker", "container", "containers", "kubernetes", "k8s", "gcp", "google cloud",
            "aws", "sre", "devops", "cloud run", "compute engine", "vm", "vpc",
            "terraform", "ci/cd", "pipeline de deploy", "deploy", "nginx", "proxy",
            "reverse proxy", "cluster", "escalabilidade de infra", "seguranca de nuvem",
            "resiliencia", "secret manager", "cloud storage", "bucket", "iam"
        ],
        "weight": 2.5
    },
    "agent_alex_vance": {
        "keywords": [
            "fastapi", "python", "backend", "arquitetura", "clean architecture", "ddd",
            "domain-driven", "microsservicos", "microservices", "api", "apis", "rest",
            "restful", "sql", "sqlite", "postgres", "postgresql", "orm", "sqlalchemy",
            "pydantic", "asyncio", "concorrencia", "cache", "redis", "design patterns",
            "solid", "websockets", "fila", "filas", "pubsub", "sistema distribuido"
        ],
        "weight": 2.5
    },
    "agent_claude_code": {
        "keywords": [
            "claude code", "cli", "terminal", "prompt engineering", "refatoracao",
            "scripts", "git", "github", "comandos", "bash", "powershell", "automacao de codigo"
        ],
        "weight": 2.0
    },
    "agent_thales_automations": {
        "keywords": [
            "n8n", "automacao", "webhook", "webhooks", "integracao", "fluxo", "zapier",
            "make", "make.com", "processos", "rpa", "agente de negocio", "conectar apis"
        ],
        "weight": 2.2
    },

    # === VENDAS (RICARDO MONTEIRO) ===
    "agent_jordan_belford_5567": {
        "keywords": [
            "fechamento", "fechar", "objecao", "objecoes", "linha reta", "straight line",
            "preco alto", "ta caro", "negociacao", "vender", "venda", "pitch", "persuasao",
            "ancoragem", "tonalidade", "certeza", "fechador", "desconto", "reuniao de vendas"
        ],
        "weight": 2.5
    },
    "agent_sofia_sdr": {
        "keywords": [
            "sdr", "prospeccao", "prospectar", "leads", "lead", "qualificacao", "cold call",
            "cold mail", "cold message", "bant", "icp", "perfil de cliente ideal",
            "agendamento", "mineracao", "linkedin", "google maps", "abordagem fria"
        ],
        "weight": 2.2
    },
    "agent_caio_copywriter": {
        "keywords": [
            "copy", "copywriting", "texto persuasivo", "headline", "pagina de vendas",
            "landing page", "vsl", "video de vendas", "roteiro", "email de vendas",
            "cta", "call to action", "copywriter", "storytelling"
        ],
        "weight": 2.2
    },
    "agent_felipe_followup": {
        "keywords": [
            "follow-up", "followup", "cadencia", "resgatar proposta", "proposta fria",
            "pipeline de vendas", "crm", "cobrar cliente", "mrr", "receita recorrente",
            "funil de vendas", "estagio do funil"
        ],
        "weight": 2.2
    },

    # === MARKETING (MARCELO MARKETING) ===
    "agent_sobral_marketing": {
        "keywords": [
            "trafego", "trafego pago", "meta ads", "google ads", "facebook ads",
            "anuncio", "anuncios", "campanha", "campanhas", "cpa", "cpc", "roas",
            "cac", "pixel", "publico", "conversao", "pixel do facebook", "subido"
        ],
        "weight": 2.5
    },
    "agent_andre_diamand_1281": {
        "keywords": [
            "sexy canvas", "desejo", "pecados capitais", "emocao", "posicionamento",
            "sensacao", "marca", "branding emocional", "vicios", "criacao de desejo"
        ],
        "weight": 2.3
    },
    "agent_ana_5058": {
        "keywords": [
            "conteudo", "redes sociais", "instagram", "posts", "carrossel", "reels",
            "social media", "engajamento", "comunidade", "calendario de postagem"
        ],
        "weight": 2.0
    },

    # === MENTE & PERFORMANCE (CAMILA REIS) ===
    "agent_jim_kwik": {
        "keywords": [
            "memoria", "leitura dinamica", "supercerebro", "aprendizado acelerado",
            "memorizacao", "cognicao", "foco mental", "concentracao", "reter conteudo"
        ],
        "weight": 2.4
    },
    "agent_o_monge_8324": {
        "keywords": [
            "meditacao", "mindfulness", "ansiedade", "calma", "presenca", "respiracao",
            "clareza mental", "paz interior", "estresse", "burnout", "equilibrio emocional"
        ],
        "weight": 2.4
    },
    "agent_link_4211": {
        "keywords": [
            "gamificacao", "produtividade", "rotina", "habitos", "disciplina",
            "recompensa", "gamify", "sistema de pontos", "consistencia"
        ],
        "weight": 2.0
    }
}


class LayaDispatcher:
    """
    Motor Laya de Decisão Rápida (System 1).
    Indexa em memória RAM as competências de toda a equipe e roteia demandas em < 5ms.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LayaDispatcher, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.agents_cache: Dict[str, Dict[str, Any]] = {}
        self.competency_index: Dict[str, Set[str]] = {}
        self.refresh_cache()

    @staticmethod
    def normalize(text: str) -> str:
        """Limpa acentos, pontuação e converte para minúsculas."""
        if not text:
            return ""
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    def tokenize(self, text: str) -> List[str]:
        """Divide texto em tokens significativos filtrando stopwords."""
        norm = self.normalize(text)
        tokens = [w for w in norm.split() if len(w) > 2 and w not in PT_STOPWORDS]
        return tokens

    def refresh_cache(self):
        """Carrega e indexa todos os agentes de data/agents/ em memória."""
        self.agents_cache.clear()
        self.competency_index.clear()

        agents_dir = settings.AGENTS_DIR
        if not agents_dir.exists():
            return

        for json_path in agents_dir.glob("*.json"):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                agent_id = data.get("id")
                if not agent_id:
                    continue

                self.agents_cache[agent_id] = data

                # Monta conjunto de tokens de competência
                tokens: Set[str] = set()

                # 1. Tópicos dominados
                for topic in data.get("topics_mastered", []):
                    tokens.update(self.tokenize(topic))

                # 2. Skills
                for sk in data.get("skills", []):
                    tokens.update(self.tokenize(sk.get("name", "")))
                    tokens.update(self.tokenize(sk.get("description", "")))

                # 3. Cargo e Nome
                tokens.update(self.tokenize(data.get("role", "")))
                tokens.update(self.tokenize(data.get("name", "")))

                # 4. Assinaturas manuais de domínio (alta prioridade)
                sig = DOMAIN_SIGNATURES.get(agent_id)
                if sig:
                    for kw in sig["keywords"]:
                        tokens.update(self.tokenize(kw))

                self.competency_index[agent_id] = tokens
            except Exception as e:
                logger.warning(f"[LayaDispatcher] Falha ao indexar {json_path.name}: {e}")

        logger.info(f"[LayaDispatcher] Indexados {len(self.agents_cache)} agentes com sucesso.")

    def calculate_agent_score(self, agent_id: str, query: str) -> float:
        """
        Calcula a aderência de um agente a uma query combinando:
        1. Casamento de Keywords Dominantes (Domain Signatures)
        2. Coincidência de Tokens e Cobertura Semântica do Perfil
        """
        query_norm = self.normalize(query)
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return 0.0

        sig_score = 0.0

        # 1. Checagem de Assinaturas de Domínio (Alta Precisão)
        sig = DOMAIN_SIGNATURES.get(agent_id)
        if sig:
            for kw in sig["keywords"]:
                kw_norm = self.normalize(kw)
                # Casamento exato de substring na frase inteira (ex: "playwright", "docker")
                if f" {kw_norm} " in f" {query_norm} " or query_norm.startswith(f"{kw_norm} ") or query_norm.endswith(f" {kw_norm}") or query_norm == kw_norm:
                    sig_score += 2.5 * sig["weight"]
                elif kw_norm in query_norm and len(kw_norm) >= 4:
                    sig_score += 1.5 * sig["weight"]

        # 2. Coincidência de Tokens do Perfil e Skills
        agent_tokens = self.competency_index.get(agent_id, set())
        matches = 0.0
        for q_tok in query_tokens:
            if q_tok in agent_tokens:
                matches += 1.0
            else:
                # Checagem de prefixo morfológico (ex: "automatizar" -> "automacao")
                for a_tok in agent_tokens:
                    if len(q_tok) >= 5 and len(a_tok) >= 5:
                        if q_tok.startswith(a_tok[:5]) or a_tok.startswith(q_tok[:5]):
                            matches += 0.5
                            break

        coverage = matches / len(query_tokens) if query_tokens else 0.0

        if sig_score > 0:
            return sig_score + (coverage * 4.0)
        else:
            # Sem assinatura explícita de domínio, exige densidade de cobertura
            return (coverage ** 1.5) * 4.0


    def classify_intent(
        self,
        query: str,
        candidate_agents: Optional[List[Dict[str, Any]]] = None,
        gap_threshold: float = 1.8
    ) -> Tuple[Optional[Dict[str, Any]], float, bool]:
        """
        Classifica a intenção e escolhe o melhor especialista entre os candidatos.
        Retorna: (best_agent, score, is_gap)
        """
        if candidate_agents is None:
            candidate_agents = [
                ag for ag in self.agents_cache.values()
                if ag.get("agent_type") == "tecnico"
            ]

        if not candidate_agents:
            return (None, 0.0, True)

        best_agent = None
        highest_score = 0.0

        for ag in candidate_agents:
            ag_id = ag.get("id")
            score = self.calculate_agent_score(ag_id, query)
            if score > highest_score:
                highest_score = score
                best_agent = ag

        is_gap = highest_score < gap_threshold
        return (best_agent, highest_score, is_gap)

    def route_manager_demand(self, manager_agent: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Roteia formalmente a demanda recebida por um Gestor Executivo.
        Decide em < 5ms se delega a um especialista da sua área ou se declara GAP.
        """
        manager_id = manager_agent.get("id", "")
        manager_name = manager_agent.get("name", "Gestor")
        area_id = manager_agent.get("area_id", "")

        # Filtra os subordinados técnicos da área do gestor
        subordinates = [
            ag for ag in self.agents_cache.values()
            if ag.get("area_id") == area_id and ag.get("agent_type") == "tecnico" and ag.get("id") != manager_id
        ]

        # Mapeamento defensivo se a lista estiver vazia por arquivo ausente
        if not subordinates:
            if "tech" in area_id.lower() or "helena" in manager_id.lower() or "tiago" in manager_id.lower():
                known_ids = ["agent_alex_vance", "agent_quinn_qa_7781", "agent_claudio_cloud_4421", "agent_claude_code", "agent_thales_automations"]
            elif "marketing" in area_id.lower() or "marcelo" in manager_id.lower():
                known_ids = ["agent_sobral_marketing", "agent_andre_diamand_1281", "agent_ana_5058"]
            elif "sales" in area_id.lower() or "ricardo" in manager_id.lower():
                known_ids = ["agent_jordan_belford_5567", "agent_sofia_sdr", "agent_caio_copywriter", "agent_felipe_followup"]
            elif "mind" in area_id.lower() or "camila" in manager_id.lower():
                known_ids = ["agent_jim_kwik", "agent_o_monge_8324", "agent_link_4211"]
            else:
                known_ids = []

            subordinates = [self.agents_cache[aid] for aid in known_ids if aid in self.agents_cache]

        best_agent, score, is_gap = self.classify_intent(query, subordinates, gap_threshold=1.8)

        # Detecta o domínio em poucas palavras para o relatório de GAP ou encaminhamento
        tokens = self.tokenize(query)
        detected_domain = " ".join(tokens[:4]) if tokens else "o tema consultado"

        if is_gap or not best_agent:
            return {
                "decision": "GAP",
                "specialist": None,
                "score": score,
                "detected_domain": detected_domain,
                "reason": f"Nenhum especialista da área de {area_id} atingiu score mínimo de aderência ({score:.1f} < 1.8)."
            }

        return {
            "decision": "DELEGATE",
            "specialist": best_agent,
            "score": score,
            "detected_domain": detected_domain,
            "reason": f"Especialista {best_agent.get('name')} selecionado por Laya com score {score:.1f}."
        }

    def auto_assign_folder(self, folder_name: str, available_agents: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Atribui automaticamente uma pasta ou curso do Google Drive ao agente técnico correto.
        Ex: "Formação Docker Expert" -> Cláudio Cloud
        Ex: "Playwright do Zero ao Avançado" -> Quinn QA
        """
        best_agent, score, is_gap = self.classify_intent(folder_name, available_agents, gap_threshold=1.5)
        if not is_gap and best_agent:
            logger.info(f"[LayaDispatcher] Pasta '{folder_name}' atribuída automaticamente a {best_agent.get('name')} (score: {score:.1f})")
            return best_agent
        return None
