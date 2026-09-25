"""
Oráculo Mobile Telegram Gateway
Envia notificações push para o celular (via 'Mensagens Salvas' ou Bot)
e processa comandos interativos (/status, /estudar, /agentes, /perguntar).
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from telethon import events

from config import settings

logger = logging.getLogger("telegram_notifier")

async def send_telegram_notification(title: str, message: str) -> bool:
    """Envia uma notificação push para as Mensagens Salvas do Telegram do usuário."""
    try:
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        client = await tm.get_client()
        if not await client.is_user_authorized():
            logger.warning("Telegram não autorizado para envio de notificação.")
            return False

        formatted_msg = (
            f"🔮 **ORÁCULO NOTIFICAÇÃO**\n\n"
            f"📌 **{title}**\n\n"
            f"{message}\n\n"
            f"⏱️ _{asyncio.get_event_loop().time():.0f}_"
        )
        await client.send_message("me", formatted_msg)
        logger.info(f"📲 Notificação enviada para o Telegram: {title}")
        return True
    except Exception as e:
        logger.warning(f"Erro ao enviar notificação Telegram: {e}")
        return False

def sync_send_notification(title: str, message: str):
    """Dispara a notificação de forma assíncrona segura a partir de contexto síncrono."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(send_telegram_notification(title, message))
        else:
            loop.run_until_complete(send_telegram_notification(title, message))
    except Exception as e:
        logger.warning(f"Falha ao despachar notificação síncrona: {e}")

async def process_telegram_command(command_text: str) -> str:
    """Processa comandos recebidos no Telegram e gera a resposta correspondente."""
    cmd = command_text.strip()
    cmd_lower = cmd.lower()

    if cmd_lower in ["/start", "/ajuda", "/help"]:
        return (
            "🔮 **ORÁCULO MOBILE COCKPIT**\n\n"
            "Comandos disponíveis direto do celular:\n\n"
            "📊 `/status` — Status dos workers, fila de estudos e tokens\n"
            "👥 `/agentes` — Lista de especialistas e horas acumuladas\n"
            "📁 `/estudar <link_drive>` — Iniciar estudo de uma pasta do Google Drive\n"
            "💬 `/perguntar @agente <pergunta>` — Consultar um especialista\n"
            "🔄 `/sync` — Forçar compilação de todas as skills\n"
        )

    elif cmd_lower.startswith("/status"):
        try:
            from ingestion.study_queue import StudyQueueManager
            sq = StudyQueueManager()
            status = sq.get_status(summary_only=True)

            active = len(status.get("active_items", []))
            total = status.get("total_items", 0)
            pending = status.get("pending_count", 0)
            completed = total - pending

            pct = (completed / total * 100) if total > 0 else 100.0

            active_details = ""
            for item in status.get("active_items", [])[:3]:
                active_details += f"• **{item.get('agent_name', 'Agente')}**: {item.get('file_name', '')[:30]} ({item.get('progress_pct', 0):.0f}%)\n"

            msg = (
                f"📊 **STATUS DO SISTEMA ORÁCULO**\n\n"
                f"⚙️ **Workers Ativos**: `{active}` processando agora\n"
                f"🎓 **Aulas Concluídas**: `{completed} / {total}` (`{pct:.1f}%`)\n"
                f"⏳ **Restantes**: `{pending}` aulas na fila\n"
            )
            if active_details:
                msg += f"\n🔥 **Em Execução Agora**:\n{active_details}"
            else:
                msg += "\n💤 **Fila Ociosa**: Nenhum worker processando no momento."

            return msg
        except Exception as e:
            return f"❌ Erro ao consultar status: {e}"

    elif cmd_lower.startswith("/agentes"):
        try:
            from web.app import get_all_agents
            agents = get_all_agents()
            if not agents:
                return "ℹ️ Nenhum agente cadastrado no sistema."

            msg = "👥 **ESPECIALISTAS DO ORÁCULO**\n\n"
            for ag in agents:
                seniority = ag.get_seniority_info()
                badge = seniority.get("badge", "🥉")
                rank = seniority.get("rank", "Júnior")
                msg += f"{ag.avatar} **{ag.name}** ({ag.role})\n"
                msg += f"   • Horas: `{ag.total_hours_studied:.1f}h` | Aulas: `{ag.total_videos_studied}` | Nível: {badge} {rank}\n\n"
            return msg
        except Exception as e:
            return f"❌ Erro ao listar agentes: {e}"

    elif cmd_lower.startswith("/estudar"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "⚠️ Uso correto: `/estudar <link_do_drive_ou_folder_id>`"

        target = parts[1].strip()
        # Extrai folder ID se for URL
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", target)
        folder_id = match.group(1) if match else target

        try:
            from ingestion.drive_client import GoogleDriveManager
            dm = GoogleDriveManager()
            details = dm.explore_folder(folder_id)
            if not details or not details.get("success"):
                return f"❌ Não foi possível acessar a pasta do Drive (`{folder_id}`). Verifique se o compartilhamento está ativo."

            folder_name = details.get("current_folder", {}).get("name", "Pasta Drive")
            lessons_count = details.get("lessons_count", 0)

            # Enfileira para estudo
            from ingestion.study_queue import StudyQueueManager
            sq = StudyQueueManager()
            enqueued = sq.enqueue_drive_course(
                folder_id=folder_id,
                course_name=folder_name,
                agent_id="agent_alex_vance", # default ou mapeado
                agent_name="Alex Vance"
            )

            return (
                f"✅ **CURSO ENFILEIRADO COM SUCESSO!**\n\n"
                f"📁 **Curso**: {folder_name}\n"
                f"📚 **Aulas Encontradas**: {lessons_count}\n"
                f"⚡ **Agente Responsável**: Alex Vance\n"
                f"🚀 Os workers na VM já começaram o download e processamento!"
            )
        except Exception as e:
            return f"❌ Erro ao enfileirar curso do Drive: {e}"

    elif cmd_lower.startswith("/perguntar"):
        # Formato: /perguntar @link <pergunta> ou /perguntar link <pergunta>
        parts = cmd.split(maxsplit=2)
        if len(parts) < 3:
            return "⚠️ Uso correto: `/perguntar @nome_do_agente sua pergunta aqui...`\nExemplo: `/perguntar @link Como melhorar meu título?`"

        raw_agent = parts[1].replace("@", "").strip().lower()
        question = parts[2].strip()

        try:
            from web.app import get_all_agents
            from google import genai
            agents = get_all_agents()

            matched_agent = None
            for ag in agents:
                if raw_agent in ag.name.lower() or raw_agent in ag.id.lower():
                    matched_agent = ag
                    break

            if not matched_agent:
                return f"❌ Especialista `@{raw_agent}` não encontrado. Use `/agentes` para ver os disponíveis."

            # Lê a skill compilada do especialista se houver
            skill_file = settings.DATA_DIR / "skills" / matched_agent.id / "SKILL.md"
            skill_context = ""
            if skill_file.exists():
                with open(skill_file, "r", encoding="utf-8") as sf:
                    skill_context = sf.read()[:8000]

            prompt = (
                f"Você é {matched_agent.name} ({matched_agent.role}), especialista treinado pelo Oráculo.\n"
                f"Responda à seguinte dúvida do seu líder (Rodrigo) de forma objetiva, direta e aplicando seus conceitos reais estudados.\n\n"
                f"BASE DE CONHECIMENTO & REGRAS:\n{skill_context}\n\n"
                f"DÚVIDA DO RODRIGO: {question}"
            )

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
            ans = resp.text.strip()
            return f"{matched_agent.avatar} **{matched_agent.name} Responde**:\n\n{ans}"
        except Exception as e:
            return f"❌ Erro ao consultar especialista: {e}"

    elif cmd_lower.startswith("/sync"):
        try:
            from web.app import get_all_agents, compile_agent_rich_skill
            agents = get_all_agents()
            count = 0
            for ag in agents:
                c = compile_agent_rich_skill(ag.id)
                if c:
                    count += 1
            return f"✅ Compilação forçada concluída! `{count}` skills de especialistas foram atualizadas."
        except Exception as e:
            return f"❌ Erro no sync: {e}"

    return (
        "❓ Comando não reconhecido.\n"
        "Envie `/ajuda` para ver os comandos disponíveis."
    )

_listener_started = False

async def start_telegram_listener():
    """Inicia o listener de mensagens no Telegram para comandos mobile."""
    global _listener_started
    if _listener_started:
        return

    try:
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        client = await tm.get_client()

        if not await client.is_user_authorized():
            logger.info("Telegram não autorizado. Listener mobile não iniciado.")
            return

        @client.on(events.NewMessage(chats="me"))
        async def on_saved_message(event):
            txt = (event.message.message or "").strip()
            if txt.startswith("/"):
                # É um comando para o Oráculo
                logger.info(f"📱 Comando recebido do celular: {txt}")
                response = await process_telegram_command(txt)
                await event.reply(response)

        _listener_started = True
        logger.info("📱 Telegram Mobile Cockpit Listener iniciado com sucesso (ouvindo em Mensagens Salvas)!")
    except Exception as e:
        logger.warning(f"Não foi possível iniciar o Telegram Mobile Listener: {e}")
