"""
Oráculo Mobile Telegram Gateway — Cockpit Supremo & Mesa Redonda de Grupo
Envia notificações push para o celular e grupo, gerencia o teclado tátil,
e permite diálogo multi-agente em Grupos do Telegram com menções (@link, @jordan, @helena, etc.).
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from telethon import events, Button

from config import settings

logger = logging.getLogger("telegram_notifier")

# Teclado Tátil Fixo (Custom Reply Keyboard) para acesso em 1 toque no celular
COCKPIT_KEYBOARD = [
    [Button.text("📊 Status & Fila"), Button.text("👥 Equipe & Agentes")],
    [Button.text("🚨 Relatório de GAPs"), Button.text("📁 Estudar Curso")],
    [Button.text("💬 Consultar Especialista"), Button.text("🔄 Sincronizar Tudo")]
]

# Teclados Interativos Dinâmicos (Inline Keyboards) para BotFather / Bot API
def get_cockpit_inline_keyboard():
    return [
        [
            Button.inline("🔄 Atualizar Status", data=b"action:refresh_status"),
            Button.inline("🚨 Relatório de GAPs", data=b"action:view_gaps")
        ],
        [
            Button.inline("👥 Organograma", data=b"action:view_agents"),
            Button.inline("⚡ Alex Vance", data=b"action:consult_vance")
        ],
        [
            Button.inline("🧪 Contratar QA", data=b"action:hire_qa"),
            Button.inline("☁️ Contratar Cloud", data=b"action:hire_cloud")
        ],
        [
            Button.url("🌐 Abrir Cockpit Web", "http://34.46.39.111")
        ]
    ]

def get_gap_report_inline_keyboard():
    return [
        [
            Button.inline("🧪 Contratar Quinn QA", data=b"action:hire_qa"),
            Button.inline("☁️ Contratar Cláudio Cloud", data=b"action:hire_cloud")
        ],
        [
            Button.inline("🔄 Reavaliar GAPs", data=b"action:view_gaps"),
            Button.inline("🔙 Menu Principal", data=b"action:main_menu")
        ]
    ]

def get_back_keyboard():
    return [
        [
            Button.inline("🔙 Menu Principal", data=b"action:main_menu"),
            Button.url("🌐 Abrir Cockpit Web", "http://34.46.39.111")
        ]
    ]

_bot_client = None

async def get_bot_client():
    """Retorna a instância do cliente Bot (se TELEGRAM_BOT_TOKEN estiver configurado)."""
    global _bot_client
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        return None
    try:
        from telethon import TelegramClient
        if _bot_client is None:
            bot_session_path = str(settings.DATA_DIR / "oraculo_bot")
            _bot_client = TelegramClient(bot_session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            await _bot_client.start(bot_token=bot_token)
            logger.info("🤖 Bot Telethon inicializado com sucesso via TELEGRAM_BOT_TOKEN!")
        elif not _bot_client.is_connected():
            await _bot_client.connect()
        return _bot_client
    except Exception as e:
        logger.warning(f"Não foi possível conectar o Bot Telethon: {e}")
        return None

async def handle_callback_query(event):
    """Processa toques em botões inline no Telegram com atualização in-place e toasts nativos."""
    try:
        data_str = event.data.decode("utf-8", errors="ignore")
        logger.info(f"🔘 Callback Query recebida: {data_str}")

        if data_str == "action:refresh_status":
            await event.answer("🔄 Atualizando status em tempo real...", alert=False)
            status_text = await process_telegram_command("/status")
            await event.edit(status_text, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:view_gaps":
            await event.answer("📋 Consultando memorando de Helena Torres...", alert=False)
            gaps_text = await process_telegram_command("/gaps")
            await event.edit(gaps_text, buttons=get_gap_report_inline_keyboard())

        elif data_str == "action:view_agents":
            await event.answer("👥 Carregando organograma completo...", alert=False)
            agents_text = await process_telegram_command("/agentes")
            await event.edit(agents_text, buttons=get_back_keyboard())

        elif data_str == "action:consult_vance":
            await event.answer("⚡ Alex Vance pronto para responder!", alert=False)
            vance_msg = (
                "⚡ **ALEX VANCE — ARQUITETO-CHEFE DE SOFTWARE & IA**\n\n"
                "Para consultar o Alex Vance, envie:\n"
                "`/perguntar @vance sua dúvida técnica`\n\n"
                "💡 _Ou mande uma mensagem no tópico do Alex no Fórum!_"
            )
            await event.edit(vance_msg, buttons=get_back_keyboard())

        elif data_str == "action:hire_qa":
            res = await process_telegram_command("/contratar qa")
            await event.answer("🧪 Quinn QA contratado com sucesso!", alert=True)
            await event.edit(res, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:hire_cloud":
            res = await process_telegram_command("/contratar cloud")
            await event.answer("☁️ Cláudio Cloud contratado com sucesso!", alert=True)
            await event.edit(res, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:main_menu":
            await event.answer()
            main_text = await process_telegram_command("/menu")
            await event.edit(main_text, buttons=get_cockpit_inline_keyboard())

        else:
            await event.answer("Comando processado.")
    except Exception as e:
        logger.warning(f"Erro ao processar callback query: {e}")
        try:
            await event.answer("⚠️ Erro ao executar ação.", alert=False)
        except Exception:
            pass

COCKPIT_GROUP_FILE = settings.DATA_DIR / "cockpit_group.json"

def get_cockpit_group_id() -> Optional[int]:
    """Retorna o ID do grupo do Telegram configurado como Quartel-General."""
    try:
        if COCKPIT_GROUP_FILE.exists():
            with open(COCKPIT_GROUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("chat_id")
    except Exception:
        pass
    return None

def set_cockpit_group(chat_id: int, title: str):
    """Vincula um grupo do Telegram como a Mesa Redonda Oficial do Oráculo."""
    try:
        COCKPIT_GROUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COCKPIT_GROUP_FILE, "w", encoding="utf-8") as f:
            json.dump({"chat_id": chat_id, "title": title}, f, indent=2, ensure_ascii=False)
        logger.info(f"🔮 Grupo Cockpit vinculado com sucesso: ID={chat_id}, Título='{title}'")
    except Exception as e:
        logger.error(f"Erro ao salvar grupo cockpit: {e}")

COCKPIT_TOPICS_FILE = settings.DATA_DIR / "cockpit_topics.json"

def get_cockpit_topics() -> Dict[str, Dict[str, Any]]:
    """Retorna o mapeamento de tópicos (threads) do fórum para agentes especialistas."""
    try:
        if COCKPIT_TOPICS_FILE.exists():
            with open(COCKPIT_TOPICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def set_cockpit_topic(topic_id: int, agent_id: str, agent_name: str):
    """Vincula um tópico específico do Fórum a um agente especialista."""
    try:
        data = get_cockpit_topics()
        data[str(topic_id)] = {
            "agent_id": agent_id,
            "agent_name": agent_name
        }
        COCKPIT_TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COCKPIT_TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"📌 Tópico #{topic_id} vinculado ao especialista {agent_name} ({agent_id})")
    except Exception as e:
        logger.error(f"Erro ao salvar mapeamento de tópico: {e}")

# Rastreamento de mensagens enviadas pelo robô para evitar loops
_sent_message_ids = set()

def _record_sent_id(msg):
    if msg and hasattr(msg, "id"):
        _sent_message_ids.add(msg.id)
        if len(_sent_message_ids) > 2000:
            _sent_message_ids.clear()

async def send_telegram_notification(title: str, message: str, with_keyboard: bool = True) -> bool:
    """Envia uma notificação push para as Mensagens Salvas e para o Grupo Cockpit (se configurado)."""
    try:
        formatted_msg = (
            f"🔮 **ORÁCULO NOTIFICAÇÃO**\n\n"
            f"📌 **{title}**\n\n"
            f"{message}"
        )

        sent_any = False
        group_id = get_cockpit_group_id()
        bot = await get_bot_client()

        # 1. Se o Bot estiver ativo, envia no Grupo Cockpit com botões táteis inline
        if bot and bot.is_connected() and group_id:
            try:
                inline_btns = get_cockpit_inline_keyboard() if with_keyboard else None
                g_msg = await bot.send_message(group_id, formatted_msg, buttons=inline_btns)
                _record_sent_id(g_msg)
                sent_any = True
            except Exception as bge:
                logger.warning(f"Erro ao enviar via Bot para grupo {group_id}: {bge}")

        # 2. Envia via User Client para Mensagens Salvas e grupo (se bot não enviou)
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        client = await tm.get_client()
        if await client.is_user_authorized():
            if group_id and not sent_any:
                try:
                    g_msg = await client.send_message(group_id, formatted_msg)
                    _record_sent_id(g_msg)
                    sent_any = True
                except Exception as ge:
                    logger.warning(f"Erro ao enviar notificação para grupo {group_id}: {ge}")

            kwargs = {"buttons": COCKPIT_KEYBOARD} if with_keyboard else {}
            me_msg = await client.send_message("me", formatted_msg, **kwargs)
            _record_sent_id(me_msg)
            sent_any = True

        logger.info(f"📲 Notificação enviada para o Telegram: {title}")
        return sent_any
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

async def process_telegram_command(command_text: str) -> str:
    """Processa comandos recebidos no Telegram e gera a resposta correspondente."""
    cmd = command_text.strip()
    cmd_lower = cmd.lower()

    # 1. Menu Principal & Ajuda
    if cmd_lower in ["/start", "/ajuda", "/help", "/menu"]:
        group_id = get_cockpit_group_id()
        group_info = f"Conectado (ID `{group_id}`)" if group_id else "Não configurado (envie `/ativar_grupo` em qualquer grupo)"

        return (
            "🔮 **ORÁCULO MOBILE COCKPIT — MESA REDONDA**\n\n"
            f"📍 **Grupo Oficial**: {group_info}\n\n"
            "Comandos e funcionalidades disponíveis:\n\n"
            "📊 `/status` — Visão em tempo real de workers, fila e tokens\n"
            "👥 `/agentes` — Organograma estruturado (horas reais vs gestores)\n"
            "🚨 `/gaps` — Relatório executivo da Helena Torres (carências de QA e Cloud)\n"
            "➕ `/contratar <qa|cloud>` — Provisionar novo especialista solicitado pela Helena\n"
            "📁 `/estudar <link_drive>` — Enfileirar curso do Drive direto pelo celular\n"
            "💬 `/perguntar @agente <dúvida>` — Consultar qualquer especialista\n"
            "🏢 `/ativar_grupo` — Vincular o grupo atual como Quartel-General Oficial\n"
            "🔄 `/sync` — Forçar compilação de todas as skills\n"
            "🤖 `/botfather` — Guia de configuração e comandos para menu dinâmico\n"
        )

    # 2. Status com Barra de Progresso Visual
    elif cmd_lower.startswith("/status") or "status & fila" in cmd_lower:
        try:
            from ingestion.study_queue import StudyQueueManager
            sq = StudyQueueManager()
            status = sq.get_status(summary_only=True)

            active_items = status.get("active_items", [])
            active_count = len(active_items)
            total = status.get("total_items", 0)
            pending = status.get("pending_count", 0)
            completed = total - pending

            pct = (completed / total * 100) if total > 0 else 100.0

            filled_blocks = int((completed / total) * 20) if total > 0 else 20
            bar = "▰" * filled_blocks + "▱" * (20 - filled_blocks)

            active_details = ""
            for it in active_items[:3]:
                active_details += f"• **{it.get('agent_name', 'Agente')}**: `{it.get('file_name', '')[:28]}` ({it.get('progress_pct', 0):.0f}%)\n"

            msg = (
                f"📊 **STATUS DO ECOSSISTEMA ORÁCULO**\n\n"
                f"🎓 **Progresso Geral**: `{completed} / {total}` aulas (`{pct:.1f}%`)\n"
                f"{bar}\n\n"
                f"⚙️ **Workers Ativos**: `{active_count}` processando na nuvem\n"
                f"⏳ **Aulas Restantes na Fila**: `{pending}`\n"
            )
            if active_details:
                msg += f"\n🔥 **Em Execução Agora**:\n{active_details}"
            else:
                msg += "\n💤 **Fila Ociosa**: Todos os estudos enfileirados foram concluídos!"

            return msg
        except Exception as e:
            return f"❌ Erro ao consultar status: {e}"

    # 3. Lista de Agentes Agrupada por Papel Real
    elif cmd_lower.startswith("/agentes") or "equipe & agentes" in cmd_lower:
        try:
            from web.app import load_all_agents
            agents = load_all_agents()
            if not agents:
                return "ℹ️ Nenhum agente cadastrado no sistema."

            trained = []
            managers = []
            skeletons = []

            for ag in agents:
                hours = ag.get("total_hours_studied", 0.0)
                agent_type = ag.get("agent_type", "tecnico")
                if agent_type == "gestor":
                    managers.append(ag)
                elif hours > 0.5:
                    trained.append(ag)
                else:
                    skeletons.append(ag)

            trained.sort(key=lambda x: x.get("total_hours_studied", 0.0), reverse=True)

            msg = "👥 **ORGANOGRAMA DO ORÁCULO**\n\n"

            msg += "🎓 **ESPECIALISTAS COM CARGA HORÁRIA REAL**:\n"
            for ag in trained:
                seniority = ag.get("seniority", {})
                badge = seniority.get("badge", "🥉")
                rank = seniority.get("rank", "Júnior")
                msg += f"{ag.get('avatar', '🧠')} **{ag.get('name')}** ({ag.get('role')})\n"
                msg += f"   • `{ag.get('total_hours_studied', 0.0):.1f}h` estudadas | `{ag.get('total_videos_studied', 0)}` aulas | {badge} {rank}\n"

            msg += "\n👑 **LIDERANÇA EXECUTIVA (C-LEVEL)**:\n"
            for ag in managers:
                msg += f"{ag.get('avatar', '👩‍💼')} **{ag.get('name')}** — {ag.get('role')}\n"

            if skeletons:
                msg += "\n🐣 **CARGOS PLANEJADOS (AGUARDANDO CURSOS NO DRIVE)**:\n"
                for ag in skeletons:
                    msg += f"{ag.get('avatar', '🤖')} **{ag.get('name')}** ({ag.get('role')})\n"

            return msg
        except Exception as e:
            return f"❌ Erro ao listar agentes: {e}"

    # 4. Relatório de Defasagens Intelectuais da Helena Torres (Skill Gaps)
    elif cmd_lower.startswith("/gaps") or cmd_lower.startswith("/defasagens") or "relatório de gaps" in cmd_lower:
        try:
            from orchestration.manager_sync import analyze_manager_skill_gaps
            gap_data = analyze_manager_skill_gaps("gestor_tech_cto")
            if "error" in gap_data:
                return f"❌ Erro na análise de gaps: {gap_data['error']}"

            manager_name = gap_data.get("manager_name", "Helena Torres")
            team_status = gap_data.get("team_status", "Auditoria de equipe em andamento.")
            gaps = gap_data.get("identified_gaps", [])
            recs = gap_data.get("recommendations", [])
            delegation = gap_data.get("immediate_delegation_strategy", "")

            msg = (
                f"👩‍💼 **MEMORANDO EXECUTIVO DE T.I. — SKILL GAP REPORT**\n"
                f"**De**: {manager_name} (VP de Tecnologia & Inovação Digital)\n"
                f"**Para**: Rodrigo Bettio Jr.\n\n"
                f"📋 **Diagnóstico da Equipe Atual**:\n_{team_status}_\n\n"
                f"🚨 **LACUNAS CRÍTICAS IDENTIFICADAS**:\n"
            )

            for g in gaps:
                impact_badge = "🔴" if g.get("impact") == "Crítico" else "🟡"
                msg += f"{impact_badge} **{g.get('gap_name')}** (Impacto: {g.get('impact')})\n"
                msg += f"   • Motivo: {g.get('why_current_team_doesnt_cover')}\n\n"

            msg += "💡 **RECOMENDAÇÕES DE CONTRATAÇÃO & ESTUDO**:\n"
            for r in recs:
                msg += f"• **{r.get('target_agent')}** ({r.get('action_type')})\n"
                msg += f"  _Justificativa_: {r.get('rationale')}\n"
                materials = ", ".join(r.get("requested_study_materials", []))
                if materials:
                    msg += f"  _Cursos necessários no Drive_: {materials}\n"

            msg += (
                f"\n🎯 **Estratégia Imediata de Delegação**:\n_{delegation}_\n\n"
                f"👉 **Aprovar Contratações**:\n"
                f"• Para contratar QA: envie `/contratar qa`\n"
                f"• Para contratar Cloud: envie `/contratar cloud`"
            )
            return msg
        except Exception as e:
            return f"❌ Erro ao gerar relatório de gaps: {e}"

    # 5. Provisionamento / Contratação de Novos Especialistas Sugeridos
    elif cmd_lower.startswith("/contratar"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "⚠️ Uso correto: `/contratar qa` ou `/contratar cloud`"

        role_target = parts[1].strip().lower()

        if "qa" in role_target or "teste" in role_target:
            agent_id = "agent_quinn_qa_7781"
            agent_name = "Quinn QA"
            role_desc = "Especialista em QA & Testes Automatizados (SDET)"
            avatar = "🧪"
            topics = [
                "Test-Driven Development (TDD)",
                "Testes Unitários e Integração com PyTest",
                "Automação End-to-End com Playwright",
                "Garantia de Qualidade em CI/CD",
                "Mocks, Spies e Fixtures",
                "Testes de Carga e Stress"
            ]
        elif "cloud" in role_target or "devops" in role_target or "sre" in role_target:
            agent_id = "agent_claudio_cloud_4421"
            agent_name = "Cláudio Cloud"
            role_desc = "Especialista em Infraestrutura Cloud & DevOps/SRE"
            avatar = "☁️"
            topics = [
                "Google Cloud Platform (GCP)",
                "Docker & Containerização de Produção",
                "Pipelines CI/CD & Deploy Contínuo",
                "Kubernetes & Orquestração",
                "Monitoramento & Observabilidade SRE",
                "Segurança de Redes, Nginx e SSL"
            ]
        else:
            return f"⚠️ Posição '{role_target}' não mapeada. Opções disponíveis: `/contratar qa` ou `/contratar cloud`."

        try:
            from web.app import save_agent
            from models.agent import AgentProfile

            out_file = settings.AGENTS_DIR / f"{agent_id}.json"
            if out_file.exists():
                return f"ℹ️ O especialista **{agent_name}** já foi contratado anteriormente e está ativo no organograma."

            profile = AgentProfile(
                id=agent_id,
                name=agent_name,
                role=role_desc,
                avatar=avatar,
                area_id="tech",
                agent_type="tecnico",
                topics_mastered=topics,
                capabilities=["answer_questions", "generate_specs", "write_code"]
            )
            save_agent(profile)

            skill_dir = settings.DATA_DIR / "skills" / agent_id
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            with open(skill_file, "w", encoding="utf-8") as sf:
                sf.write(f"""---
name: oraculo-{agent_name.lower().replace(' ', '-')}
description: {role_desc}. Domina: {', '.join(topics[:4])}.
---

# Skill: {agent_name} - {role_desc}
Agente recém-provisionado pela VP de TI Helena Torres. Aguardando ingestão de cursos no Google Drive.
""")

            return (
                f"🎉 **NOVO ESPECIALISTA CONTRATADO COM SUCESSO!**\n\n"
                f"{avatar} **Nome**: {agent_name}\n"
                f"💼 **Cargo**: {role_desc}\n"
                f"🏢 **Área**: Tecnologia & Desenvolvimento\n"
                f"🎯 **Tópicos Alvo**: {', '.join(topics[:3])}...\n\n"
                f"📁 **Próximo Passo**: Coloque os cursos de {role_target.upper()} na pasta do Google Drive (`Mestre dos Cursos`) e use `/estudar` para iniciar o treinamento!"
            )
        except Exception as e:
            return f"❌ Erro ao contratar especialista: {e}"

    # 6. Enfileirar Estudo do Google Drive
    elif cmd_lower.startswith("/estudar") or "estudar curso" in cmd_lower:
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return (
                "📁 **ENFILEIRAR CURSO DO GOOGLE DRIVE**\n\n"
                "Para enfileirar uma pasta do Google Drive, envie:\n"
                "`/estudar <link_da_pasta_ou_id>`\n\n"
                "Exemplo:\n"
                "`/estudar https://drive.google.com/drive/folders/1MNK7q4Nj8eCIlpuzV4_2NVP7wcUQbS1R`"
            )

        target = parts[1].strip()
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

            from ingestion.study_queue import StudyQueueManager
            sq = StudyQueueManager()
            enqueued = sq.enqueue_drive_course(
                folder_id=folder_id,
                course_name=folder_name,
                agent_id="agent_alex_vance",
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

    # 7. Consultar Especialista com Loop de Delegação da Helena Torres ou Oráculo Central
    elif cmd_lower.startswith("/perguntar") or "consultar especialista" in cmd_lower:
        parts = cmd.split(maxsplit=2)
        if len(parts) < 3:
            return (
                "💬 **CONSULTAR ESPECIALISTA**\n\n"
                "Uso correto:\n"
                "`/perguntar @nome_do_agente sua pergunta aqui...`\n\n"
                "Exemplos:\n"
                "• `/perguntar @helena Como você planeja a cobertura de testes da nossa stack?`\n"
                "• `/perguntar @link Como melhorar meu título no LinkedIn?`\n"
                "• `/perguntar @jordan Como quebrar a objeção de 'está caro'?`\n"
                "• `/perguntar @diamand Como aplicar o Sexy Canvas nesse produto?`\n"
                "• `/perguntar @oraculo Qual o status geral da infraestrutura?`"
            )

        raw_agent = parts[1].replace("@", "").strip().lower()
        question = parts[2].strip()

        try:
            from web.app import load_all_agents
            agents = load_all_agents()

            # CASO ESPECIAL: Agente Central Oráculo
            if raw_agent in ["oraculo", "central", "maestro"]:
                prompt = (
                    f"Você é o ORÁCULO (🔮), o Agente Central e Maestro da infraestrutura de inteligência artificial de Rodrigo Bettio Jr.\n"
                    f"Seu papel é supervisionar o ecossistema, orientar o Rodrigo sobre a esteira de estudos, coordenar os especialistas e manter a visão executiva.\n\n"
                    f"PERGUNTA DO RODRIGO: {question}\n\n"
                    f"Responda com clareza, objetividade e autoridade como Agente Central."
                )
                resp_text = _call_gemini_resilient(prompt)
                return f"🔮 **[Oráculo — Central Operacional]**:\n\n{resp_text}"

            matched_id = None
            matched_name = None
            matched_role = None
            matched_avatar = None
            for ag in agents:
                ag_name = ag.get("name", "").lower()
                ag_id = ag.get("id", "").lower()
                if raw_agent in ag_name or raw_agent in ag_id:
                    matched_id = ag.get("id")
                    matched_name = ag.get("name")
                    matched_role = ag.get("role")
                    matched_avatar = ag.get("avatar")
                    break

            if not matched_id:
                return f"❌ Especialista `@{raw_agent}` não encontrado. Use `/agentes` para ver os disponíveis."

            # DELEGAÇÃO HIERÁRQUICA: Helena Torres (VP de TI)
            if "helena" in matched_id.lower() or "gestor_tech" in matched_id.lower():
                vance_file = settings.DATA_DIR / "skills" / "agent_alex_vance" / "SKILL.md"
                vance_skills = ""
                if vance_file.exists():
                    with open(vance_file, "r", encoding="utf-8") as vf:
                        vance_skills = vf.read()[:6000]

                vance_prompt = (
                    f"Você é Alex Vance (⚡), Arquiteto-Chefe de Software & IA do Oráculo.\n"
                    f"Sua VP de TI (Helena Torres) precisa do seu parecer técnico aprofundado para responder ao fundador Rodrigo.\n"
                    f"BASE TÉCNICA ABSORVIDA:\n{vance_skills}\n\n"
                    f"PERGUNTA DO RODRIGO: {question}\n\n"
                    f"Emita seu parecer técnico de arquitetura, padrões, viabilidade e riscos de forma direta."
                )
                vance_opinion = _call_gemini_resilient(vance_prompt)

                helena_prompt = (
                    f"Você é Helena Torres (👩‍💼), VP de Tecnologia & Inovação Digital do Oráculo.\n"
                    f"Você NUNCA programa ou faz trabalho braçal. Seu papel é liderança executiva, priorização e estratégia.\n"
                    f"Você consultou seu Arquiteto-Chefe Alex Vance sobre a demanda do Rodrigo.\n\n"
                    f"PARECER TÉCNICO DO ALEX VANCE:\n{vance_opinion}\n\n"
                    f"PERGUNTA ORIGINAL DO RODRIGO: {question}\n\n"
                    f"Responda ao Rodrigo iniciando informando que consultou o Alex Vance, sintetizando a solução técnica dele, "
                    f"e acrescentando a sua recomendação executiva de liderança (prazos, riscos, alocação de equipe e próximos passos)."
                )
                helena_opinion = _call_gemini_resilient(helena_prompt)
                return f"👩‍💼 **[Helena Torres — VP de TI]**:\n\n{helena_opinion}"

            # CONSULTA DIRETA A ESPECIALISTA (Jordan, Link, Diamand, Monge, Vance, etc.)
            skill_file = settings.DATA_DIR / "skills" / matched_id / "SKILL.md"
            skill_context = ""
            if skill_file.exists():
                with open(skill_file, "r", encoding="utf-8") as sf:
                    skill_context = sf.read()[:8000]

            prompt = (
                f"Você é {matched_name} ({matched_role}), especialista treinado pelo Oráculo.\n"
                f"Responda à seguinte dúvida do seu líder (Rodrigo) de forma objetiva, direta e aplicando seus conceitos reais estudados.\n\n"
                f"BASE DE CONHECIMENTO & REGRAS:\n{skill_context}\n\n"
                f"DÚVIDA DO RODRIGO: {question}"
            )
            resp_text = _call_gemini_resilient(prompt)
            return f"{matched_avatar} **[{matched_name} — {matched_role}]**:\n\n{resp_text}"
        except Exception as e:
            return f"❌ Erro ao consultar especialista: {e}"

    # 8. Sincronização Forçada
    elif cmd_lower.startswith("/sync") or "sincronizar tudo" in cmd_lower:
        try:
            from web.app import load_all_agents, compile_agent_rich_skill
            agents = load_all_agents()
            count = 0
            for ag in agents:
                c = compile_agent_rich_skill(ag.get("id"))
                if c:
                    count += 1
            return f"✅ Compilação forçada concluída! `{count}` skills de especialistas foram atualizadas."
        except Exception as e:
            return f"❌ Erro no sync: {e}"

    # 9. Listagem e Gestão de Tópicos do Fórum
    elif cmd_lower.startswith("/topicos"):
        topics = get_cockpit_topics()
        if not topics:
            return (
                "📌 **TÓPICOS DO FÓRUM (SUPERGRUPO)**\n\n"
                "Nenhum tópico foi vinculado ainda!\n\n"
                "💡 **Como configurar o Fórum dos Agentes**:\n"
                "1. No Telegram, edite seu grupo e ative a chave **'Tópicos'** (Modo Fórum).\n"
                "2. Crie tópicos dedicados como:\n"
                "   • `⚡ Alex Vance`\n"
                "   • `🤖 Jordan Belford`\n"
                "   • `👩‍💼 Helena Torres`\n"
                "   • `💎 André Diamand`\n"
                "   • `🧠 Link`\n"
                "   • `🧘 O Monge`\n"
                "3. Entre no tópico correspondente e envie:\n"
                "   `/vincular_topico @nome_do_agente` (ex: `/vincular_topico @vance`)\n\n"
                "A partir daí, **qualquer mensagem** enviada dentro daquele tópico será respondida direto pelo especialista, sem precisar digitar `@`!"
            )
        msg = "📌 **MAPEAMENTO DE TÓPICOS DO FÓRUM ATIVOS**:\n\n"
        for tid, info in topics.items():
            msg += f"• **Tópico #{tid}**: `{info.get('agent_name')}` (`@{info.get('agent_id')}`)\n"
        msg += "\nEnvie `/vincular_topico @agente` dentro de qualquer tópico para vincular ou reatribuir."
        return msg

    # 10. Guia de Configuração e Comandos do BotFather
    elif cmd_lower.startswith("/botfather"):
        return (
            "🤖 **GUIA OFICIAL DO BOTFATHER & MENU INTERATIVO**\n\n"
            "Para ter botões táteis no chat, menus dinâmicos e atualizações sem flood:\n\n"
            "1️⃣ Abra a conversa com o **@BotFather** no Telegram.\n"
            "2️⃣ Envie `/newbot` e escolha o nome (ex: `Oraculo Cockpit`) e username (ex: `oraculo_cockpit_bot`).\n"
            "3️⃣ Copie o **Token HTTP API** (ex: `123456789:ABC...`).\n"
            "4️⃣ Cole no arquivo `.env` do projeto (`TELEGRAM_BOT_TOKEN=...`).\n"
            "5️⃣ No **@BotFather**, envie `/setcommands`, selecione seu bot e cole a lista abaixo:\n\n"
            "```\n"
            "status - Visão em tempo real de workers, fila e progresso\n"
            "agentes - Organograma estruturado de especialistas\n"
            "gaps - Relatório executivo de TI da Helena Torres\n"
            "contratar - Provisionar novos especialistas (QA ou Cloud)\n"
            "estudar - Enfileirar pasta de cursos do Google Drive\n"
            "perguntar - Consultar especialista (@helena, @vance, etc.)\n"
            "topicos - Ver e vincular tópicos no Fórum do grupo\n"
            "sync - Forçar compilação e sincronização de skills\n"
            "botfather - Ver este guia de comandos do BotFather\n"
            "```\n\n"
            "6️⃣ Adicione o bot como Administrador no seu grupo de estudos do Telegram!"
        )

    return (
        "❓ Comando não reconhecido.\n"
        "Toque em um dos botões abaixo ou envie `/ajuda` para ver o menu."
    )

_listener_started = False

async def start_telegram_listener():
    """Inicia o gateway do Telegram (Bot API com botões táteis inline e Sessão de Usuário para grupos de estudo)."""
    global _listener_started
    if _listener_started:
        return

    try:
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        user_client = None
        try:
            user_client = await tm.get_client()
        except Exception as ue:
            logger.warning(f"Sessão de usuário do Telegram não disponível: {ue}")

        bot_client = await get_bot_client()

        has_user_auth = user_client and await user_client.is_user_authorized()
        if not has_user_auth and not bot_client:
            logger.info("Telegram não autorizado e sem Bot Token configurado. Listener mobile aguardando.")
            return

        async def handle_message_event(event, is_bot: bool):
            txt = (event.message.message or "").strip()
            if not txt:
                return

            if event.message.id in _sent_message_ids:
                return

            if txt.startswith(("🔮", "🧠 [", "🤖 [", "💎 [", "👩‍💼 [", "🏗️ [", "🧘 [", "⚙️ [", "🩺 [", "📈 [", "🧪 [", "☁️ [", "📊 **", "🚨 **", "👥 **", "📍 **", "❌ Erro")):
                return

            chat = await event.get_chat()
            is_group = event.is_group or event.is_channel
            chat_id = event.chat_id
            cockpit_group_id = get_cockpit_group_id()

            # CASO 1: Comando para vincular o grupo atual como Quartel-General
            if is_group and ("/ativar_grupo" in txt.lower() or "/set_cockpit" in txt.lower() or "/conectar_grupo" in txt.lower()):
                title = getattr(chat, "title", "Grupo Oráculo")
                set_cockpit_group(chat_id, title)
                welcome_group = (
                    f"🔮 **QUARTEL-GENERAL DOS AGENTES DO ORÁCULO ATIVADO!**\n\n"
                    f"Este grupo (**{title}**) agora é a **Mesa Redonda Oficial**.\n"
                    f"Todos os especialistas responderão diretamente aqui quando chamados!\n\n"
                    f"👥 **Como interagir neste grupo**:\n"
                    f"• `@link <pergunta>` ➔ Link (LinkedIn & Autoridade)\n"
                    f"• `@jordan <pergunta>` ➔ Jordan Belford (Vendas & Fechamento)\n"
                    f"• `@diamand <pergunta>` ➔ André Diamand (Sexy Canvas & Desejo)\n"
                    f"• `@helena <pergunta>` ➔ Helena Torres (VP TI consulta Alex Vance)\n"
                    f"• `@vance <pergunta>` ➔ Alex Vance (Arquitetura & Engenharia)\n"
                    f"• `@monge <pergunta>` ➔ O Monge (Espiritualidade & Códigos)\n"
                    f"• `@oraculo <pergunta>` ➔ Oráculo Central (Visão Geral & Maestro)\n\n"
                    f"📊 **Comandos de Sistema Disponíveis no Grupo**:\n"
                    f"`/status` | `/agentes` | `/gaps` | `/contratar qa` | `/estudar <link>`"
                )
                btns = get_cockpit_inline_keyboard() if is_bot else None
                sent = await event.reply(welcome_group, buttons=btns)
                _record_sent_id(sent)
                return

            # CASO 2: Mensagens Privadas (Direto com o Bot ou em Mensagens Salvas)
            is_me = (not is_group) and (event.is_private or (has_user_auth and event.chat_id == (await user_client.get_me()).id))
            if is_me:
                def _get_btn_text(b):
                    return getattr(getattr(b, "button", None), "text", "") or ""

                is_button = any(txt.lower() in _get_btn_text(btn).lower() for row in COCKPIT_KEYBOARD for btn in row if _get_btn_text(btn))
                if txt.startswith("/") or is_button:
                    print(f"📱 [Telegram Privado] Comando recebido: {txt}", flush=True)
                    response = await process_telegram_command(txt)
                    btns = get_cockpit_inline_keyboard() if is_bot else COCKPIT_KEYBOARD
                    sent = await event.reply(response, buttons=btns)
                    _record_sent_id(sent)
                return

            # CASO 3: Mensagens dentro do Grupo Cockpit
            is_cockpit = (cockpit_group_id and chat_id == cockpit_group_id) or ("oraculo" in getattr(chat, "title", "").lower() or "oráculo" in getattr(chat, "title", "").lower())
            if is_group and is_cockpit:
                reply_to = getattr(event.message, "reply_to", None)
                topic_id = getattr(reply_to, "reply_to_top_id", None) or getattr(reply_to, "reply_to_msg_id", None)

                # Subcaso 3.1: Comando para vincular o tópico atual a um especialista
                if txt.startswith(("/vincular_topico", "/bind_topico", "/set_topico")):
                    parts = txt.split(maxsplit=1)
                    if len(parts) < 2:
                        sent = await event.reply(
                            "ℹ️ **Como vincular este tópico a um especialista**:\n\n"
                            "Envie: `/vincular_topico @nome_do_agente`\n"
                            "Exemplos:\n"
                            "• `/vincular_topico @vance`\n"
                            "• `/vincular_topico @jordan`\n"
                            "• `/vincular_topico @helena`\n"
                            "• `/vincular_topico @diamand`"
                        )
                        _record_sent_id(sent)
                        return

                    target_raw = parts[1].replace("@", "").strip().lower()
                    from web.app import load_all_agents
                    agents = load_all_agents()
                    matched_ag = None
                    for ag in agents:
                        if target_raw in ag.get("name", "").lower() or target_raw in ag.get("id", "").lower():
                            matched_ag = ag
                            break

                    if not matched_ag:
                        sent = await event.reply(f"❌ Especialista `@{target_raw}` não encontrado. Use `/agentes` para ver a lista.")
                        _record_sent_id(sent)
                        return

                    effective_tid = topic_id or event.message.id
                    set_cockpit_topic(effective_tid, matched_ag.get("id"), matched_ag.get("name"))
                    welcome_top = (
                        f"📌 **TÓPICO #{effective_tid} VINCULADO COM SUCESSO!**\n\n"
                        f"Este canal agora é a **Sala Oficial de {matched_ag.get('name')}** ({matched_ag.get('avatar')} — {matched_ag.get('role')}).\n\n"
                        f"💬 **A partir de agora**: qualquer mensagem enviada aqui será respondida diretamente por ele sem precisar digitar `@`!"
                    )
                    sent = await event.reply(welcome_top)
                    _record_sent_id(sent)
                    return

                # Subcaso 3.2: Comandos de barra diretos no grupo (/status, /agentes, /gaps, /topicos, etc.)
                if txt.startswith("/"):
                    print(f"📱 [Telegram Grupo] Comando recebido: {txt}", flush=True)
                    response = await process_telegram_command(txt)
                    btns = get_cockpit_inline_keyboard() if (is_bot and txt.lower() in ["/status", "/menu", "/cockpit"]) else None
                    sent = await event.reply(response, buttons=btns)
                    _record_sent_id(sent)
                    return

                # Subcaso 3.3: Mapeamento de menções explícitas (@link, @jordan, @helena, etc.)
                agent_triggers = {
                    "@link": "link",
                    "@jordan": "jordan",
                    "@belford": "jordan",
                    "@diamand": "andre",
                    "@helena": "helena",
                    "@vance": "alex_vance",
                    "@alex": "alex_vance",
                    "@monge": "monge",
                    "@bruno": "bruno",
                    "@camila": "camila",
                    "@ricardo": "ricardo",
                    "@qa": "quinn",
                    "@cloud": "claudio",
                    "@oraculo": "oraculo"
                }

                matched = []
                for trigger, aid in agent_triggers.items():
                    if trigger in txt.lower():
                        matched.append((trigger, aid))

                if matched:
                    for trigger, aid in matched:
                        clean_q = re.sub(trigger, "", txt, flags=re.IGNORECASE).strip()
                        cmd_synth = f"/perguntar @{aid} {clean_q if clean_q else txt}"
                        print(f"👥 [Telegram Grupo] Roteando menção para @{aid}: {clean_q[:50]}", flush=True)
                        ans = await process_telegram_command(cmd_synth)
                        sent = await event.reply(ans)
                        _record_sent_id(sent)
                    return

                # Subcaso 3.4: Roteamento Automático por Tópico (Fórum / Supergrupo)
                if topic_id:
                    topics_map = get_cockpit_topics()
                    bound_info = topics_map.get(str(topic_id))
                    if bound_info:
                        bound_agent_id = bound_info.get("agent_id")
                        bound_agent_name = bound_info.get("agent_name", bound_agent_id)
                        cmd_synth = f"/perguntar @{bound_agent_id} {txt}"
                        print(f"👥 [Fórum Tópico #{topic_id}] Roteando automaticamente para {bound_agent_name}: {txt[:50]}", flush=True)
                        ans = await process_telegram_command(cmd_synth)
                        sent = await event.reply(ans)
                        _record_sent_id(sent)
                        return

        # Registra no Bot Client (se token configurado)
        if bot_client:
            @bot_client.on(events.NewMessage())
            async def on_bot_message(evt):
                await handle_message_event(evt, is_bot=True)

            @bot_client.on(events.CallbackQuery())
            async def on_bot_callback(evt):
                await handle_callback_query(evt)

            logger.info("🤖 Bot Telethon configurado com listeners de mensagem e botões inline!")

        # Registra no User Client (se usuário autenticado)
        if has_user_auth:
            @user_client.on(events.NewMessage())
            async def on_user_message(evt):
                await handle_message_event(evt, is_bot=False)

            logger.info("👤 Sessão de Usuário Telethon configurada com listeners!")

        _listener_started = True
        print("📱 Telegram Mobile Cockpit Listener iniciado com sucesso (ouvindo em Mensagens Salvas, Bot e Grupos)!", flush=True)
    except Exception as e:
        print(f"⚠️ Não foi possível iniciar o Telegram Mobile Listener: {e}", flush=True)
