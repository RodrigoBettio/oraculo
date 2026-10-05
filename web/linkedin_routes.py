"""
Oráculo — LinkedIn Smart Networking API
Gera mensagens hiper-personalizadas, empáticas e contextuais para cada pessoa
que enviou convite de conexão, usando IA para classificar e abordar com elegância.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestration.agent_delegator import agent_delegator

logger = logging.getLogger("linkedin_routes")
router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn Smart Copilot"])


class SmartMessageRequest(BaseModel):
    full_name: str
    headline: str
    company: Optional[str] = None


@router.post("/smart-message")
def generate_smart_message(req: SmartMessageRequest):
    """
    Analisa o perfil (nome, cargo, empresa) e gera uma mensagem de 3 a 4 linhas,
    calorosa, humana e sem clichês, buscando vagas, indicações ou parcerias.
    """
    if not req.full_name.strip():
        raise HTTPException(status_code=400, detail="Nome não pode estar vazio")

    first_name = req.full_name.strip().split()[0]
    headline = req.headline.strip()

    prompt = f"""Você é o copiloto pessoal de networking e carreira de Rodrigo Bettio Jr. no LinkedIn.
Rodrigo tem 20 anos, estuda Machine Learning na FIAP e é desenvolvedor de software/arquiteto focado em Python, FastAPI, automação com IA e microsserviços.

Sua tarefa é redigir uma mensagem de agradecimento pelo convite de conexão recebido no LinkedIn, adaptada de forma HIPER-HUMANA para o perfil abaixo:

NOME DA PESSOA: {req.full_name} (chame pelo primeiro nome: {first_name})
CARGO / BIO (HEADLINE): {headline}

DIRETRIZES DE OURO (SEM ROBOTIZAÇÃO):
1. Observe com inteligência o que a pessoa faz:
   - Se for Tech Recruiter / RH / Talent: Agradeça o convite, mencione a especialidade (Python, FastAPI, microsserviços e IA) e pergunte como estão as posições em aberto para tecnologia na empresa dela.
   - Se for CTO / Tech Lead / Dev Sênior: Fale de igual para igual, elogie o trabalho do time/empresa e pergunte se estão buscando reforço técnico ou se têm desafios abertos para conversar.
   - Se for Fundador / CEO / Dono de Empresa: Agradeça a conexão entre líderes, cite que atua com arquitetura de software e eliminação de gargalos manuais (Ontologia Tech) e pergunte como estão os desafios de tecnologia e operação da empresa.
   - SE FOR QUALQUER OUTRA ÁREA (Designer, Product Manager, Analista, Consultor, etc.): Agradeça com muita simpatia a conexão, diga que é dev focado em Python e IA, e pergunte gentilmente se ela saberia dizer como está a movimentação no time de tecnologia por lá ou se teria alguém da área técnica/recrutamento para indicar!
2. Tamanho: Máximo de 3 a 4 linhas. Tom natural, caloroso, direto, como uma mensagem real de bate-papo.
3. Não use jargões chatos (como 'espero que este e-mail o encontre bem' ou 'prezado').
4. Retorne EXCLUSIVAMENTE o texto final da mensagem, sem aspas e sem explicações antes ou depois.
"""

    try:
        message = agent_delegator._call_gemini_fast(prompt)
        # Limpa possíveis aspas externas
        cleaned_msg = message.strip().strip('"').strip("'")
        return {
            "full_name": req.full_name,
            "first_name": first_name,
            "headline": headline,
            "message": cleaned_msg
        }
    except Exception as e:
        logger.error(f"Erro ao gerar mensagem de IA: {e}")
        # Fallback humanizado robusto
        fallback = (
            f"Oi {first_name}, obrigado pela conexão! Muito bom conectar com você. "
            f"Sou desenvolvedor focado em Python, automação e Inteligência Artificial. "
            f"Como estão os desafios e projetos por aí no momento? Se souber de oportunidades ou reforço na área técnica, adoraria trocar uma ideia rápida!"
        )
        return {
            "full_name": req.full_name,
            "first_name": first_name,
            "headline": headline,
            "message": fallback
        }
