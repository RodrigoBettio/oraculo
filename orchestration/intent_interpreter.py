"""
Oráculo — Interpretador de Intenções em Linguagem Natural & Despachante Operacional
Interpreta mensagens livres no Telegram (ex: 'Coloque o Jim Kwik para estudar as aulas do Super Cérebro no telegram em modo audio'),
extrai entidades, detecta lacunas de informação e executa ou solicita esclarecimento proativo.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

from config import settings

logger = logging.getLogger("intent_interpreter")


def _call_gemini_resilient(prompt: str) -> str:
    """Chama a API do Gemini com rotação de chaves e fallback resiliente."""
    from google import genai
    keys = settings.GEMINI_API_KEYS or ([settings.GEMINI_API_KEY] if settings.GEMINI_API_KEY else [])
    models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
    last_err = None

    if not keys:
        raise RuntimeError("Nenhuma chave GEMINI_API_KEY configurada no sistema.")

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
                    time.sleep(1.0)
                    continue
                else:
                    break
    raise RuntimeError(f"Falha ao chamar Gemini após tentativas: {last_err}")


async def interpret_user_intent(text: str) -> Dict[str, Any]:
    """Usa Gemini para analisar o texto em linguagem natural e extrair intenções e entidades estruturadas."""
    try:
        prompt = f"""Você é o Interpretador de Linguagem Natural e Despachante Operacional do Oráculo (Cockpit de IA Multi-Agente).
O usuário enviou a seguinte mensagem no Telegram:
"{text}"

O sistema possui as seguintes áreas e agentes:
- Área Tech (Gestora: Helena Torres / Especialistas: Alex Vance [@vance], Quinn QA [@qa], Cláudio Cloud [@cloud], Bruno [@bruno])
- Área Vendas (Gestor: Ricardo Monteiro / Especialista: Jordan Belford [@jordan])
- Área Marketing & Branding (Gestor: Ricardo Monteiro / Especialistas: André Diamand [@diamand], Ana [@ana])
- Área Mente & Super Cérebro (Gestora: Dra. Camila Reis / Especialistas: Jim Kwik [@jim], O Monge [@monge], Link [@link])

Analise a mensagem e retorne RIGOROSAMENTE um JSON com as seguintes chaves:
{{
  "intent": "STUDY" | "CONSULT" | "REPORT" | "GAPS" | "STATUS" | "NAVIGATE_DRIVE" | "TASK" | "CHAT",
  "target_agent_id": id do agente especialista ou gestor (ex: "agent_jim_kwik", "agent_alex_vance", "agent_andre_diamand_1281", "gestor_tech_cto", etc.) ou null se não aplicável,
  "target_agent_name": nome do agente reconhecido (ex: "Jim Kwik", "Alex Vance", "Helena Torres") ou null,
  "course_name": nome do curso, livro ou assunto a ser estudado/analisado (ex: "Super Cérebro", "Sexy Canvas", "Clean Architecture") ou null,
  "source_type": "telegram" | "google_drive" | null,
  "tier": "audio_only" | "standard_video" | "ocr_code" | null,
  "explicit_link": link URL encontrado na mensagem (ex: https://t.me/... ou https://drive.google.com/...) ou null,
  "missing_info": lista de strings de informações essenciais que faltam para executar a ação imediatamente (ex: ["link_ou_canal_de_aulas"] ou []),
  "friendly_clarification": se missing_info não for vazia, elabore uma mensagem acolhedora, executiva e prestativa em português explicando o que entendeu e como o usuário pode fornecer o dado que falta,
  "summary": resumo de 1 linha da ação pretendida
}}

Atenção às regras de 'tier':
- Se o usuário mencionar 'áudio', 'audio', 'ouvir', 'podcast', defina "tier": "audio_only".
- Se mencionar 'código', 'ocr', 'programar', defina "tier": "ocr_code".
- Caso contrário, "standard_video" ou null.

Responda APENAS o JSON válido, sem comentários antes ou depois."""

        raw_text = _call_gemini_resilient(prompt)
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(raw_text)
        return data
    except Exception as e:
        logger.error(f"Erro ao interpretar intenção via Gemini: {e}")
        return {
            "intent": "CHAT",
            "target_agent_id": None,
            "target_agent_name": None,
            "course_name": None,
            "source_type": None,
            "tier": None,
            "explicit_link": None,
            "missing_info": [],
            "friendly_clarification": None,
            "summary": "Falha na interpretação",
            "error": str(e)
        }


async def execute_or_clarify_intent(text: str) -> Dict[str, Any]:
    """Interpreta a mensagem do usuário e executa a ação correspondente ou devolve resposta com esclarecimento."""
    parsed = await interpret_user_intent(text)
    intent = parsed.get("intent", "CHAT")
    
    # 1. INTENÇÃO: ESTUDAR CURSO / AULA (ex: 'Coloque o Jim Kwik para estudar...')
    if intent == "STUDY":
        agent_id = parsed.get("target_agent_id") or "agent_jim_kwik"
        agent_name = parsed.get("target_agent_name") or "Especialista"
        course_name = parsed.get("course_name") or "Curso"
        source_type = parsed.get("source_type") or "telegram"
        tier = parsed.get("tier") or "standard_video"
        explicit_link = parsed.get("explicit_link")
        tier_label = "Modo Áudio (Transcrição Rápida)" if tier == "audio_only" else ("Modo Código & OCR" if tier == "ocr_code" else "Modo Vídeo Completo")

        # Caso A: Link direto fornecido no próprio texto
        if explicit_link:
            if "drive.google.com" in explicit_link or "folders/" in explicit_link:
                from ingestion.telegram_notifier import process_telegram_command
                res = await process_telegram_command(f"/estudar {explicit_link} @{agent_id}")
                return {
                    "status": "executed",
                    "response_text": f"⚡ **ESTUDO INICIADO COM SUCESSO!**\n\n👤 **Especialista**: {agent_name}\n📂 **Origem**: Google Drive\n🎧 **Formato**: {tier_label}\n\n{res}"
                }
            elif "t.me/" in explicit_link:
                from ingestion.telegram_notifier import process_telegram_command
                res = await process_telegram_command(f"/estudar {explicit_link} @{agent_id}")
                return {
                    "status": "executed",
                    "response_text": f"⚡ **ESTUDO DO TELEGRAM ENFILEIRADO!**\n\n👤 **Especialista**: {agent_name}\n📱 **Origem**: Telegram ({explicit_link})\n🎧 **Formato**: {tier_label}\n\n{res}"
                }

        # Caso B: Sem link direto - busca inteligente na pasta de Estudos do Telegram do usuário
        found_chat = None
        try:
            from ingestion.telegram_client import TelegramManager
            tm = TelegramManager()
            if await tm.is_authorized():
                target_folder = getattr(settings, "TELEGRAM_TARGET_FOLDER", "Estudos")
                groups = await tm.list_groups_in_folder(target_folder)
                
                # Procura por correspondência no nome do curso
                clean_target = course_name.lower().replace("curso", "").replace("aulas", "").strip()
                for g in groups:
                    g_title = g.get("title", "").lower()
                    if clean_target in g_title or g_title in clean_target:
                        found_chat = g
                        break
        except Exception as e:
            logger.warning(f"Não foi possível buscar na pasta de Estudos do Telegram: {e}")

        # Se encontrou o canal automaticamente na conta Telegram
        if found_chat:
            chat_id = found_chat.get("id")
            chat_title = found_chat.get("title")
            return {
                "status": "needs_confirmation",
                "chat_id": chat_id,
                "agent_id": agent_id,
                "tier": tier,
                "response_text": (
                    f"🔍 **CANAL ENCONTRADO NO SEU TELEGRAM!**\n\n"
                    f"Localizei o canal **{chat_title}** na sua pasta de `{settings.TELEGRAM_TARGET_FOLDER}`.\n\n"
                    f"👤 **Especialista**: **{agent_name}**\n"
                    f"📚 **Curso**: `{course_name}`\n"
                    f"🎧 **Modo Selecionado**: **{tier_label}**\n\n"
                    f"Deseja enfileirar todas as aulas para estudo imediato?"
                ),
                "suggested_action": f"/estudar tg_chat:{chat_id} @{agent_id}"
            }

        # Caso C: Não encontrou ou precisa de canal/link (Esclarecimento Proativo)
        msg_clarification = (
            f"🧠 **Entendido perfeitamente!**\n\n"
            f"Você quer colocar o especialista **{agent_name}** para estudar o conteúdo **'{course_name}'** em **{tier_label}** pelo Telegram.\n\n"
            f"⚠️ **Para eu operar isso agora, preciso apenas de um desses detalhes:**\n\n"
            f"1️⃣ **Encaminhe aqui** uma mensagem de áudio ou vídeo da aula desse curso;\n"
            f"2️⃣ **Envie o link** do canal ou mensagem no Telegram (ex: `https://t.me/c/12345/678`);\n"
            f"3️⃣ Ou se as aulas estiverem no Google Drive, envie o link da pasta ou toque em **📂 Navegar Drive**."
        )
        return {
            "status": "clarification_needed",
            "response_text": msg_clarification
        }

    # 2. INTENÇÃO: RELATÓRIO EXECUTIVO (ex: 'Me dá um relatório de marketing', 'Relatório geral')
    elif intent == "REPORT":
        from orchestration.daily_report import get_daily_report_on_demand
        target_area = None
        t_low = text.lower()
        if "marketing" in t_low or "branding" in t_low:
            target_area = "area_marketing_6867"
        elif "tech" in t_low or "tecnologia" in t_low or "ti" in t_low:
            target_area = "tech"
        elif "venda" in t_low or "comercial" in t_low:
            target_area = "sales"
        elif "mente" in t_low or "cérebro" in t_low or "cerebro" in t_low or "wellness" in t_low:
            target_area = "mind"
            
        report_text = await get_daily_report_on_demand(area=target_area)
        return {
            "status": "executed",
            "response_text": report_text
        }

    # 3. INTENÇÃO: CONSULTAR ESPECIALISTA OU DIRETOR
    elif intent == "CONSULT":
        agent_id = parsed.get("target_agent_id") or "gestor_tech_cto"
        from orchestration.agent_delegator import agent_delegator
        response = agent_delegator.consult(agent_id=agent_id, user_query=text)
        return {
            "status": "executed",
            "response_text": response
        }

    # 4. INTENÇÃO: ABRIR OU NAVEGAR DRIVE
    elif intent == "NAVIGATE_DRIVE":
        from ingestion.drive_client import GoogleDriveManager
        from ingestion.telegram_notifier import format_drive_folder_view
        dm = GoogleDriveManager()
        try:
            folder_data = dm.explore_folder(None)
            view_text = format_drive_folder_view(folder_data)
            return {
                "status": "executed_drive",
                "response_text": view_text,
                "folder_data": folder_data
            }
        except Exception as e:
            return {
                "status": "error",
                "response_text": f"⚠️ Erro ao acessar o Google Drive: {e}"
            }

    # 5. INTENÇÃO: VER STATUS / FILA
    elif intent == "STATUS":
        from ingestion.telegram_notifier import process_telegram_command
        status_text = await process_telegram_command("/status")
        return {
            "status": "executed",
            "response_text": status_text
        }

    # 6. INTENÇÃO: ANÁLISE DE GAPS
    elif intent == "GAPS":
        from ingestion.telegram_notifier import process_telegram_command
        gaps_text = await process_telegram_command("/gaps")
        return {
            "status": "executed",
            "response_text": gaps_text
        }

    # 7. INTENÇÃO: CRIAR TAREFA
    elif intent == "TASK":
        from ingestion.telegram_notifier import process_telegram_command
        task_text = await process_telegram_command(f"/tarefa {text}")
        return {
            "status": "executed",
            "response_text": task_text
        }

    # 8. CASO PADRÃO: CHAT GERAL OU CONSULTA AO ORÁCULO
    else:
        target_id = parsed.get("target_agent_id")
        if target_id:
            from orchestration.agent_delegator import agent_delegator
            ans = agent_delegator.consult(agent_id=target_id, user_query=text)
            return {"status": "executed", "response_text": ans}
        
        # Resposta Maestro Oráculo Central
        prompt_central = (
            f"Você é o ORÁCULO (🔮), o Agente Central e Maestro da infraestrutura de inteligência artificial de Rodrigo Bettio Jr.\n"
            f"Seu papel é supervisionar o ecossistema, orientar o Rodrigo sobre a esteira de estudos, coordenar os especialistas e manter a visão executiva.\n\n"
            f"MENSAGEM DO RODRIGO: {text}\n\n"
            f"Responda com clareza, objetividade e autoridade como Agente Central."
        )
        resp_text = _call_gemini_resilient(prompt_central)
        return {"status": "executed", "response_text": f"🔮 **[Oráculo — Central Operacional]**:\n\n{resp_text}"}
