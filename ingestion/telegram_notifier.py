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
    [Button.text("📊 Relatório Executivo"), Button.text("📂 Navegar Drive")],
    [Button.text("📊 Status & Fila"), Button.text("👥 Equipe & Agentes")],
    [Button.text("🚨 Análise de GAPs"), Button.text("📁 Estudar Curso")],
    [Button.text("💬 Consultar Especialista"), Button.text("🔄 Sincronizar Tudo")]
]

# Teclados Interativos Dinâmicos (Inline Keyboards) para BotFather / Bot API
def get_cockpit_inline_keyboard():
    return [
        [
            Button.inline("📊 Relatório Executivo", data=b"action:daily_report"),
            Button.inline("📂 Navegar Drive", data=b"drv:root")
        ],
        [
            Button.inline("🔄 Atualizar Status", data=b"action:refresh_status"),
            Button.inline("🚨 GAPs dos Gestores", data=b"action:view_gaps")
        ],
        [
            Button.inline("👥 Organograma", data=b"action:view_agents"),
            Button.inline("⚡ Alex Vance", data=b"action:consult_vance")
        ],
        [
            Button.inline("🧪 Contratar QA (Tech)", data=b"action:hire_qa"),
            Button.inline("💼 Contratar SDR (Vendas)", data=b"action:hire_sdr")
        ],
        [
            Button.url("🌐 Abrir Cockpit Web", "http://34.46.39.111")
        ]
    ]

def get_gap_report_inline_keyboard():
    return [
        [
            Button.inline("🧪 Contratar QA (Tech)", data=b"action:hire_qa"),
            Button.inline("💼 Contratar SDR (Vendas)", data=b"action:hire_sdr")
        ],
        [
            Button.inline("☁️ Contratar Cloud (SRE)", data=b"action:hire_cloud"),
            Button.inline("🧠 Contratar Neuro (Mente)", data=b"action:hire_neuro")
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

def get_action_proposal_keyboard(action_id: str):
    return [
        [
            Button.inline("🛑 Cancelar / Vetar", data=f"action:cancel_act:{action_id}".encode("utf-8")),
            Button.inline("⚡ Executar Agora", data=f"action:exec_act:{action_id}".encode("utf-8"))
        ]
    ]


def get_drive_explorer_keyboard(folder_data: dict) -> list:
    """Gera teclado inline para navegação visual do Google Drive."""
    buttons = []
    # Subpastas (máx 6 por tela)
    for sf in folder_data.get('subfolders', [])[:6]:
        label = f"📁 {sf['name'][:22]}"
        buttons.append([Button.inline(label, data=f"drv:f:{sf['id']}".encode())])
    
    # Contagem de vídeos pendentes
    videos = folder_data.get('videos', [])
    pending = [v for v in videos if not v.get('is_studied')]
    studied = [v for v in videos if v.get('is_studied')]
    
    if videos:
        stats_row = []
        if pending:
            stats_row.append(Button.inline(
                f"⚡ Estudar {len(pending)} aulas",
                data=f"drv:enq:{folder_data['current_folder']['id']}".encode()
            ))
        buttons.append(stats_row) if stats_row else None
    
    # Navegação
    nav_row = []
    parent_id = folder_data.get('current_folder', {}).get('parent_id')
    if parent_id:
        nav_row.append(Button.inline("⬆️ Voltar", data=f"drv:up:{parent_id}".encode()))
    nav_row.append(Button.inline("🏠 Raiz", data=b"drv:root"))
    buttons.append(nav_row)
    
    # Atribuição a agente (somente técnicos)
    buttons.append([Button.inline(
        "🎯 Atribuir a Agente",
        data=f"drv:asgn:{folder_data['current_folder']['id']}".encode()
    )])
    buttons.append([Button.inline("🔙 Menu Principal", data=b"action:main_menu")])
    return buttons


def get_agent_selector_keyboard(folder_id: str) -> list:
    """Gera teclado de seleção de agente (SOMENTE técnicos — gestores NÃO executam)."""
    technical_agents = [
        ("Alex Vance", "vance"),
        ("Quinn QA", "quinn"),
        ("Cláudio Cloud", "claudio"),
        ("Bruno", "bruno"),
        ("Jordan Belford", "jordan"),
        ("André Diamand", "diamand"),
        ("Jim Kwik", "jimkwik"),
        ("O Monge", "monge"),
        ("Link", "link"),
        ("Ana", "ana"),
        ("Sobral", "sobral"),
        ("Thales", "thales"),
    ]
    buttons = []
    for name, short in technical_agents:
        cb_data = f"drv:ag:{short}:{folder_id}"
        if len(cb_data.encode()) <= 64:
            buttons.append([Button.inline(f"👤 {name}", data=cb_data.encode())])
    buttons.append([Button.inline("⬅️ Voltar à Pasta", data=f"drv:f:{folder_id}".encode())])
    return buttons


def format_drive_folder_view(folder_data: dict) -> str:
    """Formata a visualização de uma pasta do Drive para o Telegram."""
    current = folder_data.get('current_folder', {})
    breadcrumbs = folder_data.get('breadcrumbs', [])
    subfolders = folder_data.get('subfolders', [])
    videos = folder_data.get('videos', [])
    support_files = folder_data.get('support_files', [])
    
    # Header com breadcrumbs
    bc_text = " › ".join([b['name'][:15] for b in breadcrumbs]) if breadcrumbs else "Raiz"
    
    text = f"📂 **NAVEGADOR DO DRIVE**\n"
    text += f"📍 `{bc_text}`\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Pasta atual
    text += f"📁 **{current.get('name', 'Drive')}**\n\n"
    
    # Stats
    pending = [v for v in videos if not v.get('is_studied')]
    studied = [v for v in videos if v.get('is_studied')]
    
    if subfolders:
        text += f"📂 {len(subfolders)} subpastas\n"
    if videos:
        text += f"🎬 {len(videos)} aulas"
        if studied:
            text += f" ({len(studied)} ✅ estudadas, {len(pending)} ⏳ pendentes)"
        text += "\n"
    if support_files:
        text += f"📎 {len(support_files)} arquivos de apoio\n"
    
    if not subfolders and not videos:
        text += "📭 _Pasta vazia_\n"
    
    text += f"\n💡 _Toque nas pastas para navegar ou atribua a um agente._"
    return text

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
            await event.answer("📋 Consultando GAPs de todos os gestores...", alert=False)
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

        elif data_str == "action:hire_sdr":
            res = await process_telegram_command("/contratar sdr")
            await event.answer("💼 Sofia SDR contratada com sucesso!", alert=True)
            await event.edit(res, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:hire_neuro":
            res = await process_telegram_command("/contratar neuro")
            await event.answer("🧠 Dr. Lucas Neuro contratado com sucesso!", alert=True)
            await event.edit(res, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:hire_copy":
            res = await process_telegram_command("/contratar copywriter")
            await event.answer("✍️ Caio Copywriter contratado com sucesso!", alert=True)
            await event.edit(res, buttons=get_cockpit_inline_keyboard())

        elif data_str.startswith("action:cancel_act:"):
            act_id = data_str.replace("action:cancel_act:", "").strip()
            from orchestration.autonomous_governor import autonomous_governor
            res = autonomous_governor.cancel_action(act_id)
            await event.answer("🛑 Ação cancelada pelo usuário!", alert=True)
            await event.edit(f"🛑 **[AÇÃO AUTÔNOMA CANCELADA / VETADA]**\n\n{res.get('message')}\n\nOperação abortada com sucesso a pedido do Rodrigo Bettio Jr.")

        elif data_str.startswith("action:exec_act:"):
            act_id = data_str.replace("action:exec_act:", "").strip()
            from orchestration.autonomous_governor import autonomous_governor
            res = autonomous_governor.execute_action(act_id, trigger="manual_immediate")
            await event.answer("⚡ Ação executada imediatamente!", alert=False)
            await event.edit(f"⚡ **[AÇÃO AUTÔNOMA DISPARADA]**\n\n{res.get('message')}\n\nExecução realizada com sucesso.")

        elif data_str == "action:main_menu":
            await event.answer()
            main_text = await process_telegram_command("/menu")
            await event.edit(main_text, buttons=get_cockpit_inline_keyboard())

        elif data_str == "action:daily_report":
            await event.answer("📊 Gerando relatório executivo...", alert=False)
            from orchestration.daily_report import get_daily_report_on_demand
            report = await get_daily_report_on_demand()
            await event.edit(report, buttons=get_back_keyboard())

        elif data_str.startswith("drv:"):
            parts = data_str.split(":")
            drv_action = parts[1] if len(parts) > 1 else ""
            
            if drv_action in ("f", "up", "root"):
                await event.answer("📂 Carregando pasta...", alert=False)
                from ingestion.drive_client import GoogleDriveManager
                dm = GoogleDriveManager()
                folder_id = None if drv_action == "root" else parts[2] if len(parts) > 2 else None
                try:
                    folder_data = dm.explore_folder(folder_id)
                    view_text = format_drive_folder_view(folder_data)
                    keyboard = get_drive_explorer_keyboard(folder_data)
                    await event.edit(view_text, buttons=keyboard)
                except Exception as e:
                    await event.edit(f"⚠️ Erro ao acessar Drive: {e}", buttons=get_back_keyboard())
            
            elif drv_action == "enq":
                folder_id = parts[2] if len(parts) > 2 else None
                if folder_id:
                    await event.answer("⚡ Enfileirando curso para estudo...", alert=True)
                    enqueue_text = await process_telegram_command(f"/estudar drive:{folder_id}")
                    await event.edit(enqueue_text, buttons=get_back_keyboard())
            
            elif drv_action == "asgn":
                folder_id = parts[2] if len(parts) > 2 else ""
                await event.answer("🎯 Selecione o agente técnico...", alert=False)
                await event.edit(
                    "🎯 **ATRIBUIR ESTUDO A AGENTE**\n\n"
                    "Selecione o agente técnico que deve estudar este conteúdo.\n\n"
                    "⚠️ _Gestores (Helena, Ricardo, Camila) não executam — apenas delegam._",
                    buttons=get_agent_selector_keyboard(folder_id)
                )
            
            elif drv_action == "ag":
                agent_short = parts[2] if len(parts) > 2 else ""
                folder_id = parts[3] if len(parts) > 3 else ""
                agent_map = {
                    "vance": "agent_alex_vance", "quinn": "agent_quinn_qa_7781",
                    "claudio": "agent_claudio_cloud_4421", "bruno": "agent_claude_code",
                    "jordan": "agent_jordan_belford_5567", "diamand": "agent_andre_diamand_1281",
                    "jimkwik": "agent_jim_kwik", "monge": "agent_o_monge_8324",
                    "link": "agent_link_4211", "ana": "agent_ana_5058",
                    "sobral": "agent_sobral_marketing",
                    "thales": "agent_thales_automations",
                }
                agent_id = agent_map.get(agent_short, "")
                if agent_id and folder_id:
                    await event.answer(f"✅ Atribuído ao {agent_short}!", alert=True)
                    enqueue_text = await process_telegram_command(f"/estudar drive:{folder_id} @{agent_short}")
                    await event.edit(
                        f"✅ **ESTUDO ATRIBUÍDO**\n\n"
                        f"📁 Pasta: `{folder_id[:20]}...`\n"
                        f"👤 Agente: **{agent_short.title()}**\n\n"
                        f"{enqueue_text}",
                        buttons=get_back_keyboard()
                    )
                else:
                    await event.answer("⚠️ Agente não encontrado.", alert=True)

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

LAST_USER_CHAT_ID_FILE = settings.DATA_DIR / "last_user_chat_id.json"

def get_last_user_chat_id() -> Optional[int]:
    """Retorna o chat_id do usuário registrado (do arquivo ou .env)."""
    env_id = getattr(settings, "TELEGRAM_USER_CHAT_ID", None)
    if env_id:
        try:
            return int(env_id)
        except Exception:
            pass
    if LAST_USER_CHAT_ID_FILE.exists():
        try:
            data = json.loads(LAST_USER_CHAT_ID_FILE.read_text(encoding="utf-8"))
            return data.get("chat_id")
        except Exception:
            pass
    return None

def set_last_user_chat_id(chat_id: int):
    """Salva o chat_id do usuário que interagiu com o Bot."""
    try:
        from datetime import datetime
        LAST_USER_CHAT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_USER_CHAT_ID_FILE.write_text(
            json.dumps({"chat_id": chat_id, "updated_at": datetime.now().isoformat()}),
            encoding="utf-8"
        )
        logger.info(f"📱 User chat_id {chat_id} registrado para notificações do Bot!")
    except Exception as e:
        logger.warning(f"Erro ao salvar last_user_chat_id: {e}")

# Rastreamento de mensagens enviadas pelo robô para evitar loops
_sent_message_ids = set()

def _record_sent_id(msg):
    if msg and hasattr(msg, "id"):
        _sent_message_ids.add(msg.id)
        if len(_sent_message_ids) > 2000:
            _sent_message_ids.clear()

async def send_telegram_notification(title: str, message: str, with_keyboard: bool = True) -> bool:
    """Envia notificação push com prioridade máxima para o Bot direto no privado do usuário e/ou grupo."""
    try:
        formatted_msg = (
            f"🔮 **ORÁCULO NOTIFICAÇÃO**\n\n"
            f"📌 **{title}**\n\n"
            f"{message}"
        )

        sent_any = False
        group_id = get_cockpit_group_id()
        user_chat_id = get_last_user_chat_id()
        bot = await get_bot_client()

        # 1. Se o Bot estiver ativo, envia prioritariamente pelo Bot
        if bot and bot.is_connected():
            inline_btns = get_cockpit_inline_keyboard() if with_keyboard else None
            
            # 1.1 Chat Privado direto com o Bot (evita poluir Mensagens Salvas)
            if user_chat_id:
                try:
                    u_msg = await bot.send_message(user_chat_id, formatted_msg, buttons=inline_btns)
                    _record_sent_id(u_msg)
                    sent_any = True
                    logger.info(f"📲 Notificação enviada via Bot para chat privado ({user_chat_id})")
                except Exception as bue:
                    logger.warning(f"Erro ao enviar via Bot para chat privado {user_chat_id}: {bue}")

            # 1.2 Grupo Cockpit
            if group_id:
                try:
                    g_msg = await bot.send_message(group_id, formatted_msg, buttons=inline_btns)
                    _record_sent_id(g_msg)
                    sent_any = True
                    logger.info(f"📲 Notificação enviada via Bot para grupo ({group_id})")
                except Exception as bge:
                    logger.warning(f"Erro ao enviar via Bot para grupo {group_id}: {bge}")

        # 2. Se o Bot NÃO conseguiu enviar (sem token, sem chat_id registrado ou falha), recorre ao User Client
        if not sent_any:
            from ingestion.telegram_client import TelegramManager
            tm = TelegramManager()
            client = await tm.get_client()
            if await client.is_user_authorized():
                if group_id:
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

        logger.info(f"📲 Notificação despachada para o Telegram: {title} (sucesso={sent_any})")
        return sent_any
    except Exception as e:
        logger.warning(f"Erro ao enviar notificação Telegram: {e}")
        return False
async def notify_autonomous_proposal(
    title: str,
    description: str,
    category: str = "operational",
    delay_minutes: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Envia uma notificação de proposta autônoma com contagem regressiva e botões táteis inline.
    Se category='operational' e o usuário não vetar em delay_minutes, o Governor auto-executa.
    Se category='critical', exige aprovação explícita.
    """
    try:
        from orchestration.autonomous_governor import autonomous_governor
        import time

        action_id = f"act_{int(time.time())}"
        delay = delay_minutes if delay_minutes is not None else settings.AUTONOMOUS_EXECUTION_DELAY_MINUTES
        action = autonomous_governor.propose_action(
            action_id=action_id,
            title=title,
            description=description,
            category=category,
            delay_minutes=delay,
            payload=payload
        )

        cat_badge = "⚙️ **[PROPOSTA DE AÇÃO AUTÔNOMA]**" if category == "operational" else "🚨 **[MUDANÇA ESTRUTURAL — REQUER APROVAÇÃO]**"
        countdown_msg = (
            f"⏱️ **Janela de Intervenção**: `{delay} minutos`\n"
            f"_Se você não responder ou vetar dentro do prazo, a ação será executada automaticamente._"
        ) if category == "operational" else (
            f"🛑 **Atenção**: Esta ação é crítica e **NÃO** será executada sem aprovação explícita."
        )

        formatted_msg = (
            f"{cat_badge}\n\n"
            f"📌 **{title}**\n\n"
            f"{description}\n\n"
            f"{countdown_msg}\n\n"
            f"🆔 `ID: {action_id}`"
        )

        group_id = get_cockpit_group_id()
        bot = await get_bot_client()
        buttons = get_action_proposal_keyboard(action_id)

        if bot and bot.is_connected() and group_id:
            try:
                sent = await bot.send_message(group_id, formatted_msg, buttons=buttons)
                _record_sent_id(sent)
            except Exception as be:
                logger.warning(f"Erro ao enviar proposta autônoma via Bot: {be}")

        return action
    except Exception as e:
        logger.warning(f"Erro ao registrar proposta autônoma: {e}")
        return {}

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
            "📊 `/relatorio` — Relatório executivo do dia com métricas e especialistas\n"
            "👥 `/agentes` — Organograma estruturado (horas reais vs gestores)\n"
            "🚨 `/gaps` — Relatório de GAPs consolidado de TODOS os gestores\n"
            "➕ `/contratar <cargo>` — Provisionar novo especialista solicitado pelos gestores\n"
            "📁 `/estudar <link_drive>` — Enfileirar curso do Drive direto pelo celular\n"
            "📂 `/drive` — Navegar visualmente pelas pastas do Google Drive\n"
            "💬 `/perguntar @agente <dúvida>` — Consultar qualquer especialista\n"
            "📋 `/tarefas` — Ver backlog de tarefas recebidas do celular ou chat\n"
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

    # 2.1. Gastos e Consumo de Tokens da API Gemini
    elif cmd_lower.startswith("/gastos") or cmd_lower.startswith("/custos") or cmd_lower.startswith("/tokens") or "gastos da api" in cmd_lower:
        try:
            token_file = settings.DATA_DIR / "token_usage.json"
            if not token_file.exists():
                return "ℹ️ Nenhum registro de consumo de tokens encontrado ainda."

            data = json.loads(token_file.read_text(encoding="utf-8"))
            recs = data.get("records", [])
            total_tokens = sum(r.get("total_tokens", 0) for r in recs)
            total_usd = sum(r.get("cost_usd", 0.0) for r in recs)
            total_brl = sum(r.get("cost_brl", 0.0) for r in recs)

            by_agent = {}
            for r in recs:
                det = r.get("details", "")
                agent = "Outros"
                if "Jordan" in det:
                    agent = "Jordan Belford"
                elif "Bruno" in det or "Codex" in det or "Claude" in det:
                    agent = "Bruno (Codex)"
                elif "Sobral" in det or "Tráfego" in det:
                    agent = "Sobral (Marketing)"
                elif "Alex" in det or "Vance" in det:
                    agent = "Alex Vance"

                if agent not in by_agent:
                    by_agent[agent] = {"calls": 0, "usd": 0.0, "brl": 0.0}
                by_agent[agent]["calls"] += 1
                by_agent[agent]["usd"] += r.get("cost_usd", 0.0)
                by_agent[agent]["brl"] += r.get("cost_brl", 0.0)

            avg_brl = (total_brl / len(recs)) if recs else 0.0

            msg = (
                f"💰 **AUDITORIA DE GASTOS & TOKENS — API GEMINI**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💵 **Gasto Total Acumulado**: `R$ {total_brl:.2f}` (`${total_usd:.4f} USD`)\n"
                f"📊 **Volume de Tokens**: `{total_tokens:,}` tokens consumidos\n"
                f"🎬 **Aulas Processadas**: `{len(recs)}` chamadas multimodais\n"
                f"💡 **Custo Médio por Aula**: `~R$ {avg_brl:.2f}` por vídeo\n\n"
                f"👥 **Distribuição de Custo por Especialista**:\n"
            )
            for a, st in by_agent.items():
                msg += f"• **{a}**: `R$ {st['brl']:.2f}` ({st['calls']} aulas)\n"

            msg += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🛡️ **Gestão de Custos**: O modelo `gemini-3.8-flash` é ultra-eficiente (~$0.075 por 1M tokens de input). "
                f"O curso inteiro do Sobral (239 aulas) custará aproximadamente R$ 42,00 no total."
            )
            return msg
        except Exception as e:
            return f"❌ Erro ao consultar gastos da API: {e}"

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

    # 4. Relatório Executivo de GAPs de Conhecimento (Todos os Gestores)
    elif cmd_lower.startswith("/gaps") or cmd_lower.startswith("/defasagens") or "relatório de gaps" in cmd_lower or "análise de gaps" in cmd_lower:
        try:
            from orchestration.manager_sync import analyze_manager_skill_gaps, get_all_managers_gaps_summary
            parts = cmd.split(maxsplit=1)
            area_arg = parts[1].strip().lower() if len(parts) > 1 else ""

            # Se especificou área (ex: /gaps tech, /gaps vendas, /gaps mente, /gaps marketing)
            if area_arg and area_arg not in ["todos", "geral", "all", "equipe"]:
                target_mgr = None
                if any(x in area_arg for x in ["tech", "ti", "dev", "codigo", "código", "software"]):
                    target_mgr = ("gestor_tech_cto", "tech", "Tecnologia & Desenvolvimento", "💻", "Tiago Tech (VP de TI)")
                elif any(x in area_arg for x in ["mkt", "market", "growth", "trafego", "tráfego"]):
                    target_mgr = ("gestor_marketing", "area_marketing_6867", "Marketing & Growth", "🚀", "Marcelo Marketing (CMO & Growth)")
                elif any(x in area_arg for x in ["venda", "comercial", "negoc", "sales"]):
                    target_mgr = ("gestor_sales_director", "sales", "Vendas & Negociação", "💼", "Victor Vendas (Dir. Comercial)")
                elif any(x in area_arg for x in ["mente", "mind", "foco", "wellness", "saude", "saúde"]):
                    target_mgr = ("gestor_mind_wellness", "mind", "Mente, Foco & Performance", "🧠", "Marina Mente (Head Wellness)")

                if not target_mgr:
                    return f"⚠️ Área '{area_arg}' não encontrada.\n\nOpções disponíveis:\n• `/gaps tech` (Tiago Tech)\n• `/gaps marketing` (Marcelo Marketing)\n• `/gaps vendas` (Victor Vendas)\n• `/gaps mente` (Marina Mente)\n• `/gaps` (Visão Consolidada de Todos)"

                m_id, a_id, a_label, emo, m_name = target_mgr
                gap_data = analyze_manager_skill_gaps(m_id, force_refresh=False)
                if "error" in gap_data:
                    return f"❌ Erro na análise de gaps: {gap_data['error']}"

                team_status = gap_data.get("team_status", "Auditoria de equipe em andamento.")
                gaps = gap_data.get("identified_gaps", [])
                recs = gap_data.get("recommendations", [])
                delegation = gap_data.get("immediate_delegation_strategy", "")

                msg = (
                    f"{emo} **MEMORANDO EXECUTIVO — SKILL GAP REPORT**\n"
                    f"**De**: {m_name}\n"
                    f"**Área**: {a_label}\n"
                    f"**Para**: Rodrigo Bettio Jr.\n\n"
                    f"📋 **Diagnóstico da Equipe Atual**:\n_{team_status}_\n\n"
                    f"🚨 **LACUNAS IDENTIFICADAS**:\n"
                )

                for g in gaps:
                    impact_badge = "🔴" if "crítico" in g.get("impact", "").lower() else "🟡"
                    msg += f"{impact_badge} **{g.get('gap_name')}** (Impacto: {g.get('impact')})\n"
                    msg += f"   • Motivo: {g.get('why_current_team_doesnt_cover')}\n\n"

                msg += "💡 **RECOMENDAÇÕES DE CONTRATAÇÃO & ESTUDO**:\n"
                for r in recs:
                    msg += f"• **{r.get('target_agent')}** ({r.get('action_type')})\n"
                    msg += f"  _Justificativa_: {r.get('rationale')}\n"
                    materials = ", ".join(r.get("requested_study_materials", []))
                    if materials:
                        msg += f"  📚 _Cursos necessários no Drive_: {materials}\n"

                if delegation:
                    msg += f"\n🎯 **Estratégia Imediata de Delegação**:\n_{delegation}_\n"

                msg += (
                    f"\n👉 **Ações Sugeridas**:\n"
                    f"• Para contratar especialistas: envie `/contratar <cargo>`\n"
                    f"• Para ver todos os gestores: `/gaps`"
                )
                return msg

            # Visão Geral Consolidada de Todos os Gestores
            summary = get_all_managers_gaps_summary(force_refresh=False)
            msg = (
                "🚨 **RELATÓRIO CONSOLIDADO DE GAPS DE CONHECIMENTO**\n"
                "**Liderança Executiva**: Levantamento de defasagens apontadas por cada gestor\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )

            for item in summary:
                emo = item.get("emoji", "🏢")
                a_name = item.get("area_name", "")
                m_name = item.get("manager_name", "")
                gaps = item.get("gaps", [])
                recs = item.get("recommendations", [])

                msg += f"{emo} **{a_name}**\n   Gestor(a): **{m_name}**\n"
                if gaps:
                    for g in gaps[:2]:
                        impact_badge = "🔴" if "crítico" in g.get("impact", "").lower() else "🟡"
                        msg += f"   {impact_badge} **{g.get('gap_name')}** ({g.get('impact')})\n"
                        msg += f"      _{g.get('why_current_team_doesnt_cover')[:90]}..._\n"
                else:
                    msg += "   ✅ Equipe capacitada para a demanda atual.\n"

                # Materiais solicitados
                mat_list = []
                for r in recs:
                    for mat in r.get("requested_study_materials", []):
                        mat_list.append(mat)
                if mat_list:
                    msg += f"   📚 **Materiais Solicitados p/ Drive**: {', '.join(mat_list[:2])}\n"
                msg += "\n"

            msg += (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 **Comandos Rápidos**:\n"
                "• Detalhes por Gestor: `/gaps tech` | `/gaps marketing` | `/gaps vendas` | `/gaps mente`\n"
                "• Provisionar Especialista: `/contratar <cargo>`\n"
                "• Enfileirar Cursos: `/estudar <link_drive>`"
            )
            return msg
        except Exception as e:
            return f"❌ Erro ao gerar relatório de gaps: {e}"

    # 5. Provisionamento / Contratação de Novos Especialistas Sugeridos por Qualquer Gestor
    elif cmd_lower.startswith("/contratar"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return (
                "➕ **CONTRATAÇÃO DE ESPECIALISTAS PELOS GESTORES**\n\n"
                "Cada gestor executivo pode solicitar reforços para suprir gaps de conhecimento.\n\n"
                "🎯 **Especialistas mais solicitados prontos para contratação**:\n\n"
                "💻 **Tecnologia & Dev (Helena Torres)**:\n"
                "   • `/contratar qa` — Quinn QA (Testes Automatizados, TDD, Playwright)\n"
                "   • `/contratar cloud` — Cláudio Cloud (GCP, Docker, Kubernetes, SRE)\n"
                "   • `/contratar fullstack` — Pedro Fullstack (Desenvolvimento Web & APIs)\n\n"
                "💼 **Vendas & Negócios (Ricardo Monteiro)**:\n"
                "   • `/contratar sdr` — Sofia SDR (Prospecção Ativa B2B & Qualificação BANT)\n"
                "   • `/contratar copywriter` — Caio Copy (Copywriting de Alta Conversão & VSL)\n"
                "   • `/contratar revops` — Rodrigo RevOps (Métricas de Funil & CRM)\n\n"
                "🧠 **Mente & Performance (Dra. Camila Reis)**:\n"
                "   • `/contratar neuro` — Dr. Lucas Neuro (Neurociência, Foco Profundo & Flow)\n"
                "   • `/contratar habitos` — Helena Hábitos (Rotinas Atômicas & Higiene do Sono)\n\n"
                "💡 _Ou contrate qualquer outro cargo digitando:_ `/contratar <nome_do_cargo>`"
            )

        role_target = parts[1].strip()
        role_lower = role_target.lower()

        # Catálogo pré-definido cobrindo todas as áreas
        catalog = {
            "qa": {
                "id": "agent_quinn_qa_7781",
                "name": "Quinn QA",
                "role": "Especialista em QA & Testes Automatizados (SDET)",
                "avatar": "🧪",
                "area_id": "tech",
                "area_name": "Tecnologia & Desenvolvimento",
                "manager_name": "Helena Torres (VP de TI)",
                "topics": ["Test-Driven Development (TDD)", "Testes Unitários e Integração com PyTest", "Automação End-to-End com Playwright", "Garantia de Qualidade em CI/CD", "Mocks, Spies e Fixtures", "Testes de Carga e Stress"],
                "study_hint": "Playwright, PyTest e TDD por Kent Beck"
            },
            "cloud": {
                "id": "agent_claudio_cloud_4421",
                "name": "Cláudio Cloud",
                "role": "Especialista em Infraestrutura Cloud & DevOps/SRE",
                "avatar": "☁️",
                "area_id": "tech",
                "area_name": "Tecnologia & Desenvolvimento",
                "manager_name": "Helena Torres (VP de TI)",
                "topics": ["Google Cloud Platform (GCP)", "Docker & Containerização de Produção", "Pipelines CI/CD & Deploy Contínuo", "Kubernetes & Orquestração", "Monitoramento & Observabilidade SRE", "Segurança de Redes, Nginx e SSL"],
                "study_hint": "Docker, Kubernetes e Google SRE Handbook"
            },
            "fullstack": {
                "id": "agent_pedro_fullstack",
                "name": "Pedro Fullstack",
                "role": "Engenheiro Full-Stack & Desenvolvimento Web",
                "avatar": "⚡",
                "area_id": "tech",
                "area_name": "Tecnologia & Desenvolvimento",
                "manager_name": "Helena Torres (VP de TI)",
                "topics": ["Next.js & React", "FastAPI & Python", "Tailwind CSS", "Arquitetura REST & WebSockets", "PostgreSQL & SQLite", "TypeScript Moderno"],
                "study_hint": "Next.js 15, FastAPI Mastery e Clean Architecture"
            },
            "sdr": {
                "id": "agent_sofia_sdr",
                "name": "Sofia SDR",
                "role": "Especialista em Prospecção Ativa B2B & Qualificação",
                "avatar": "🎯",
                "area_id": "sales",
                "area_name": "Vendas & Negociação",
                "manager_name": "Ricardo Monteiro (Dir. Comercial)",
                "topics": ["Cold Outreach & Cadências", "Qualificação BANT e MEDDPICC", "Social Selling no LinkedIn", "Cold Call de Alto Impacto", "Pesquisa e Mapeamento de Decisores", "Quebra Prévia de Objeções"],
                "study_hint": "Receita Previsível (Aaron Ross) e Fanatical Prospecting"
            },
            "copywriter": {
                "id": "agent_caio_copywriter",
                "name": "Caio Copywriter",
                "role": "Especialista em Copywriting & Redação Persuasiva",
                "avatar": "✍️",
                "area_id": "sales",
                "area_name": "Vendas & Negociação",
                "manager_name": "Ricardo Monteiro (Dir. Comercial)",
                "topics": ["Copywriting de Conversão", "Roteiros de VSL (Video Sales Letter)", "E-mail Marketing Persuasivo", "Páginas de Captura & Vendas", "Storytelling Aplicado a Vendas", "Gatilhos Emocionais & Sexy Canvas"],
                "study_hint": "The Adweek Copywriting Handbook e Cartas de Dan Kennedy"
            },
            "revops": {
                "id": "agent_rodrigo_revops",
                "name": "Rodrigo RevOps",
                "role": "Especialista em Revenue Operations & CRM",
                "avatar": "📈",
                "area_id": "sales",
                "area_name": "Vendas & Negociação",
                "manager_name": "Ricardo Monteiro (Dir. Comercial)",
                "topics": ["Métricas SaaS (CAC, LTV, Churn, ARR)", "Automação de CRM (HubSpot/Pipedrive)", "Forecast de Vendas", "Gestão de Pipeline Comercial", "Análise de Produtividade Comercial"],
                "study_hint": "Playbooks de RevOps e Gestão Avançada de Pipeline"
            },
            "neuro": {
                "id": "agent_lucas_neuro",
                "name": "Dr. Lucas Neuro",
                "role": "Especialista em Neurociência Aplicada ao Foco & Biohacking",
                "avatar": "🔬",
                "area_id": "mind",
                "area_name": "Mente, Foco & Performance",
                "manager_name": "Dra. Camila Reis (Head Wellness)",
                "topics": ["Regulação de Dopamina", "Foco Profundo (Deep Work)", "Estados de Flow Sustentável", "Gestão de Atenção & TDAH", "Higiene Circadiana & Sono Profundo", "Nutrição Cerebral & Nootrópicos"],
                "study_hint": "Protocolos Huberman Lab e Deep Work de Cal Newport"
            },
            "habitos": {
                "id": "agent_helena_habitos",
                "name": "Helena Hábitos",
                "role": "Especialista em Hábitos de Alta Performance & Rotinas",
                "avatar": "🌱",
                "area_id": "mind",
                "area_name": "Mente, Foco & Performance",
                "manager_name": "Dra. Camila Reis (Head Wellness)",
                "topics": ["Hábitos Atômicos", "Rotinas Matinais e Noturnas", "Recuperação de Energia", "Prevenção de Burnout", "Gestão de Tempo e Blocos de Foco", "Consistência de Longo Prazo"],
                "study_hint": "Hábitos Atômicos (James Clear) e Por Que Nós Dormimos"
            }
        }

        # Localiza match no catálogo
        matched_spec = None
        for key, spec in catalog.items():
            if key in role_lower or (key == "qa" and "teste" in role_lower) or (key == "cloud" and any(x in role_lower for x in ["devops", "sre", "infra"])) or (key == "sdr" and "prospec" in role_lower) or (key == "copywriter" and "copy" in role_lower) or (key == "neuro" and "foco" in role_lower):
                matched_spec = spec
                break

        # Se não estiver no catálogo pré-definido, cria dinamicamente com Gemini
        if not matched_spec:
            try:
                prompt_hire = (
                    f"Um fundador quer contratar um novo especialista para sua equipe de IA com o cargo: '{role_target}'.\n"
                    f"Defina qual gestor deve liderá-lo:\n"
                    f"- gestor_tech_cto (Helena Torres) se for técnico, desenvolvimento, QA, Cloud, dados ou IA.\n"
                    f"- gestor_sales_director (Ricardo Monteiro) se for vendas, marketing, tráfego, SDR ou copywriting.\n"
                    f"- gestor_mind_wellness (Dra. Camila Reis) se for mente, saúde, foco, hábitos ou produtividade humana.\n\n"
                    f"Responda estritamente em JSON com este formato:\n"
                    f"{{\n"
                    f'  "id": "agent_{re.sub(r"[^a-z0-9]", "_", role_lower)[:20]}",\n'
                    f'  "name": "Nome Elegante do Especialista",\n'
                    f'  "role": "{role_target.title()}",\n'
                    f'  "avatar": "um emoji adequado",\n'
                    f'  "area_id": "tech ou sales ou mind",\n'
                    f'  "area_name": "Nome da Área",\n'
                    f'  "manager_name": "Nome do Gestor Escolhido",\n'
                    f'  "topics": ["Topico 1", "Topico 2", "Topico 3", "Topico 4"],\n'
                    f'  "study_hint": "Cursos ou livros recomendados"\n'
                    f"}}"
                )
                raw_json = _call_gemini_resilient(prompt_hire)
                if "```json" in raw_json:
                    raw_json = raw_json.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_json:
                    raw_json = raw_json.split("```")[1].split("```")[0].strip()
                matched_spec = json.loads(raw_json)
            except Exception as dyn_err:
                return f"⚠️ Não foi possível mapear automaticamente o cargo '{role_target}'. Use uma das opções recomendadas: `/contratar qa`, `/contratar cloud`, `/contratar sdr`, `/contratar copywriter`, `/contratar neuro`."

        # Salva o novo agente
        try:
            from web.app import save_agent
            from models.agent import AgentProfile

            agent_id = matched_spec["id"]
            agent_name = matched_spec["name"]
            role_desc = matched_spec["role"]
            avatar = matched_spec.get("avatar", "🤖")
            area_id = matched_spec.get("area_id", "tech")
            area_name = matched_spec.get("area_name", "Tecnologia")
            manager_name = matched_spec.get("manager_name", "Gestor de Área")
            topics = matched_spec.get("topics", [])
            study_hint = matched_spec.get("study_hint", "Cursos específicos no Drive")

            out_file = settings.AGENTS_DIR / f"{agent_id}.json"
            if out_file.exists():
                return f"ℹ️ O especialista **{agent_name}** já foi contratado anteriormente e está ativo no organograma."

            profile = AgentProfile(
                id=agent_id,
                name=agent_name,
                role=role_desc,
                avatar=avatar,
                area_id=area_id,
                agent_type="tecnico",
                topics_mastered=topics,
                capabilities=["answer_questions", "generate_specs", "write_code" if area_id == "tech" else "consulting"]
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
Especialista provisionado sob liderança de {manager_name}.
Aguardando ingestão de materiais de estudo no Google Drive ({study_hint}).
""")

            # Sincroniza mapeamentos do gestor da área
            try:
                from orchestration.manager_sync import sync_all_managers_mappings
                sync_all_managers_mappings()
            except Exception:
                pass

            return (
                f"🎉 **NOVO ESPECIALISTA CONTRATADO COM SUCESSO!**\n\n"
                f"{avatar} **Nome**: {agent_name}\n"
                f"💼 **Cargo**: {role_desc}\n"
                f"🏢 **Área**: {area_name}\n"
                f"👑 **Gestor Responsável**: {manager_name}\n"
                f"🎯 **Tópicos Alvo**: {', '.join(topics[:4])}\n\n"
                f"📁 **Próximo Passo**: Coloque os materiais de estudo ({study_hint}) na pasta do Google Drive (`Mestre dos Cursos`) e use `/estudar` para iniciar o treinamento de {agent_name}!"
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
                "`/estudar <link_ou_id> [@agente] [ocr|audio]`\n\n"
                "Exemplos:\n"
                "• `/estudar https://drive.google.com/drive/folders/1V9oPEonG4znWlZkueIQO5A0EKzpAWXuG @bruno ocr`\n"
                "• `/estudar drive:1nnC-MUpO9SIt9w9iCy0Zj5CQL9Eyd5R6 @sobral ocr`"
            )

        target = parts[1].strip()

        # Extrair Folder ID
        folder_id = None
        m_drv = re.search(r"drive:([a-zA-Z0-9_-]+)", target)
        m_url = re.search(r"folders/([a-zA-Z0-9_-]+)", target)
        if m_drv:
            folder_id = m_drv.group(1)
        elif m_url:
            folder_id = m_url.group(1)
        else:
            first_token = target.split()[0].strip()
            folder_id = first_token if not first_token.startswith("@") else None

        if not folder_id:
            return "❌ Link ou ID da pasta do Google Drive não encontrado na mensagem."

        # Identificar Agente Destino
        target_agent_id = "agent_claude_code" if "bruno" in target.lower() or "claude" in target.lower() else "agent_alex_vance"
        target_agent_name = "Bruno" if "bruno" in target.lower() or "claude" in target.lower() else "Alex Vance"

        agent_match = re.search(r"@([a-zA-Z0-9_]+)", target)
        if agent_match:
            raw_ag = agent_match.group(1).lower()
            agent_map = {
                "vance": ("agent_alex_vance", "Alex Vance"),
                "alex": ("agent_alex_vance", "Alex Vance"),
                "bruno": ("agent_claude_code", "Bruno"),
                "claude": ("agent_claude_code", "Bruno"),
                "agent_claude_code": ("agent_claude_code", "Bruno"),
                "quinn": ("agent_quinn_qa_7781", "Quinn QA"),
                "qa": ("agent_quinn_qa_7781", "Quinn QA"),
                "claudio": ("agent_claudio_cloud_4421", "Cláudio Cloud"),
                "cloud": ("agent_claudio_cloud_4421", "Cláudio Cloud"),
                "jordan": ("agent_jordan_belford_5567", "Jordan Belford"),
                "diamand": ("agent_andre_diamand_1281", "André Diamand"),
                "jimkwik": ("agent_jim_kwik", "Jim Kwik"),
                "jim": ("agent_jim_kwik", "Jim Kwik"),
                "monge": ("agent_o_monge_8324", "O Monge"),
                "link": ("agent_link_4211", "Link"),
                "ana": ("agent_ana_5058", "Ana"),
                "sobral": ("agent_sobral_marketing", "Sobral"),
                "agent_sobral_marketing": ("agent_sobral_marketing", "Sobral"),
                "thales": ("agent_thales_automations", "Thales"),
                "agent_thales_automations": ("agent_thales_automations", "Thales"),
            }
            if raw_ag in agent_map:
                target_agent_id, target_agent_name = agent_map[raw_ag]

        # Tier de Processamento
        tier = "multimodal_ocr" if "ocr" in cmd_lower or target_agent_id in ["agent_claude_code", "agent_sobral_marketing", "agent_thales_automations", "agent_quinn_qa_7781"] else "audio_only"
        tier_label = "Modo Código & OCR (Visão Multimodal)" if tier == "multimodal_ocr" else "Modo Áudio (Transcrição Rápida)"

        try:
            from ingestion.drive_client import GoogleDriveManager
            dm = GoogleDriveManager()
            details = dm.explore_folder(folder_id)
            if not details or not details.get("success"):
                return f"❌ Não foi possível acessar a pasta do Drive (`{folder_id}`). Verifique se o compartilhamento está ativo."

            folder_name = details.get("current_folder", {}).get("name", "Curso Drive")

            from ingestion.study_queue import StudyQueueManager
            sq = StudyQueueManager()
            enqueued = await sq.enqueue_drive_course(
                agent_id=target_agent_id,
                folder_id=folder_id,
                course_name=folder_name,
                tier=tier,
                only_pending=True
            )

            enqueued_count = len(enqueued)
            return (
                f"✅ **ESTUDO DO DRIVE ENFILEIRADO COM SUCESSO!**\n\n"
                f"📁 **Curso**: {folder_name}\n"
                f"👤 **Especialista**: {target_agent_name}\n"
                f"⚡ **Aulas Enfileiradas**: {enqueued_count} itens\n"
                f"👁️ **Formato**: {tier_label}\n\n"
                f"🚀 Os workers de ingestão já iniciaram o download e processamento contínuo!"
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

            from orchestration.agent_delegator import agent_delegator
            return agent_delegator.consult(raw_agent, question)
        except Exception as e:
            return f"❌ Erro ao consultar especialista: {e}"

    # 7.1. Registro de Tarefas Rápidas no Backlog
    elif cmd_lower.startswith("/tarefa") or ('"especialista_alvo"' in cmd):
        try:
            from orchestration.agent_delegator import agent_delegator
            tasks_dir = settings.DATA_DIR / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            json_match = re.search(r"\{.*\}", cmd, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except Exception:
                    pass

            if not data:
                parts = cmd.split(maxsplit=2)
                target = "vance"
                body = ""
                if len(parts) >= 2 and parts[1].startswith("@"):
                    target = parts[1].replace("@", "").strip().lower()
                    body = parts[2] if len(parts) > 2 else ""
                elif len(parts) >= 2:
                    body = " ".join(parts[1:])
                data = {
                    "origem": "telegram_chat",
                    "tipo": "tarefa",
                    "especialista_alvo": target,
                    "prioridade": "alta" if "urgente" in body.lower() else "normal",
                    "titulo": body[:80] if body else "Nova Tarefa",
                    "detalhes": body
                }

            target_agent = data.get("especialista_alvo", "vance").replace("@", "").lower()
            title = data.get("titulo", "Tarefa sem título")
            details = data.get("detalhes", "")
            priority = data.get("prioridade", "normal")

            import time
            task_id = f"task_{int(time.time())}"
            data["id"] = task_id
            data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            with open(tasks_dir / f"{task_id}.json", "w", encoding="utf-8") as tf:
                json.dump(data, tf, indent=2, ensure_ascii=False)

            opinion = agent_delegator.consult(target_agent, f"Tarefa registrada: {title}. Contexto: {details}. Dê seu parecer inicial.")

            return (
                f"💬 [Cockpit Mobile ➔ Oráculo]\n\n"
                f"✅ **NOVA TAREFA REGISTRADA NO BACKLOG!**\n"
                f"📌 **Título**: {title}\n"
                f"🎯 **Responsável**: `@{target_agent}` | Prioridade: `{priority.upper()}`\n"
                f"🆔 **ID**: `{task_id}`\n\n"
                f"📝 **PARECER INICIAL DO ESPECIALISTA**:\n"
                f"{opinion}"
            )
        except Exception as e:
            return f"❌ Erro ao registrar tarefa: {e}"

    elif cmd_lower.startswith("/tarefas") or "backlog de tarefas" in cmd_lower:
        tasks_dir = settings.DATA_DIR / "tasks"
        if not tasks_dir.exists():
            return "ℹ️ Nenhuma tarefa pendente no backlog."
        files = sorted(tasks_dir.glob("task_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return "ℹ️ Nenhuma tarefa pendente no backlog."
        msg = f"📋 **BACKLOG DE TAREFAS** (`{len(files)} registradas`):\n\n"
        for f in files[:6]:
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    d = json.load(jf)
                msg += f"• **{d.get('titulo', 'Tarefa')}** (`@{d.get('especialista_alvo')}`)\n"
                if d.get("detalhes"):
                    msg += f"  _{d.get('detalhes')[:70]}..._\n"
            except Exception:
                continue
        return msg

    # 7.2. Ações Autônomas e Delay de Governança
    elif cmd_lower.startswith("/acoes") or "acoes pendentes" in cmd_lower:
        from orchestration.autonomous_governor import autonomous_governor
        pending = autonomous_governor.get_pending_actions()
        if not pending:
            return "ℹ️ Nenhuma ação autônoma pendente de execução no momento."
        import time
        now = time.time()
        msg = f"⏱️ **AÇÕES AUTÔNOMAS PENDENTES** (`{len(pending)} na fila`):\n\n"
        for act in pending:
            sched = act.get("scheduled_timestamp")
            rem_sec = max(0, int(sched - now)) if sched else 0
            rem_min = rem_sec // 60
            cat = "⚙️ Operacional" if act.get("category") == "operational" else "🚨 Crítica (Aguardando Aprovação)"
            msg += f"• **{act.get('title')}** (`{act.get('id')}`)\n"
            msg += f"  _{act.get('description')[:80]}_\n"
            msg += f"  Categoria: {cat} | Tempo restante: `{rem_min}m {rem_sec % 60}s`\n\n"
        msg += "💡 Para cancelar uma ação: envie `/cancelar <id>` ou use o botão na mensagem original."
        return msg

    elif cmd_lower.startswith("/cancelar"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "⚠️ Uso correto: `/cancelar <id_da_acao>`"
        target_id = parts[1].strip()
        from orchestration.autonomous_governor import autonomous_governor
        res = autonomous_governor.cancel_action(target_id)
        if res.get("status") == "success":
            return f"🛑 **Ação Cancelada**: {res.get('message')}"
        return f"⚠️ {res.get('message')}"

    # === Relatório Diário Executivo ===
    elif cmd_lower.startswith("/relatorio") or cmd_lower.startswith("/relatório") or "relatório executivo" in cmd_lower or "relatório do dia" in cmd_lower:
        from orchestration.daily_report import get_daily_report_on_demand
        parts = command_text.split(maxsplit=1)
        area_filter = None
        if len(parts) > 1:
            raw_arg = parts[1].strip().lower()
            if not any(x in raw_arg for x in ["executivo", "do dia", "diario", "diário"]):
                area_filter = raw_arg
        return await get_daily_report_on_demand(area=area_filter)

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

    # === Navegar Google Drive ===
    elif cmd_lower.startswith("/drive") or "navegar drive" in cmd_lower:
        from ingestion.drive_client import GoogleDriveManager
        dm = GoogleDriveManager()
        parts = cmd.split(" ", 1)
        folder_id = parts[1].strip() if cmd_lower.startswith("/drive") and len(parts) > 1 else None
        try:
            folder_data = dm.explore_folder(folder_id)
            return format_drive_folder_view(folder_data)
        except Exception as e:
            return f"⚠️ Erro ao acessar Google Drive: {e}\n\nVerifique se a autenticação OAuth está configurada."

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
        if has_user_auth:
            try:
                my_user = await user_client.get_me()
                if my_user and not get_last_user_chat_id():
                    set_last_user_chat_id(my_user.id)
                    logger.info(f"📱 last_user_chat_id auto-inicializado com o ID do usuário: {my_user.id}")
            except Exception as uid_err:
                logger.warning(f"Erro ao obter user ID do user_client: {uid_err}")

        if not has_user_auth and not bot_client:
            logger.info("Telegram não autorizado e sem Bot Token configurado. Listener mobile aguardando.")
            return

        # Cache recente de debounce para evitar comandos duplicados em curto intervalo
        import time
        _recent_cmd_cache = {}

        async def handle_message_event(event, is_bot: bool):
            # O Oráculo opera exclusivamente através do Bot Client oficial (@bot_client).
            # Mensagens de contas pessoais (User Client), chats pessoais ou Mensagens Salvas são 100% ignoradas.
            if not is_bot:
                return

            txt = (event.message.message or "").strip()
            if not txt:
                return

            # 1. Ignorar se a mensagem foi enviada pelo próprio sistema
            if event.message.id in _sent_message_ids:
                return

            # 2. Ignorar mensagens enviadas por QUALQUER Bot (inclusive este ou outros)
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                return

            # 3. Filtrar qualquer saída de sistema (com ou sem markdown) para evitar re-interpretação
            SYSTEM_PREFIXES = (
                "🔮", "📊", "🚨", "👥", "📍", "❌", "💬 [", "🧠 [", "🤖 [", "💎 [",
                "👩‍💼 [", "🏗️ [", "🧘 [", "⚙️ [", "🩺 [", "📈 [", "🧪 [", "☁️ [",
                "✨ [", "ℹ️", "⚠️", "🎓", "▰", "▱", "📂 **NAVEGADOR", "⏱️ **AÇÕES",
                "🎉 **NOVO ESPECIALISTA", "✅ Compilação"
            )
            if any(txt.startswith(p) for p in SYSTEM_PREFIXES):
                return

            chat = await event.get_chat()
            is_group = event.is_group or event.is_channel
            chat_id = event.chat_id
            cockpit_group_id = get_cockpit_group_id()

            # O Bot NUNCA processa suas próprias mensagens enviadas
            if event.out:
                return

            # No chat privado com o Bot, registra o ID do usuário para envio direto de relatórios/notificações
            if not is_group and chat_id:
                set_last_user_chat_id(chat_id)

            # Debounce: evitar processar exatamente o mesmo comando no mesmo chat em < 3 segundos
            now_ts = time.time()
            cache_key = f"{chat_id}:{txt}"
            if cache_key in _recent_cmd_cache and (now_ts - _recent_cmd_cache[cache_key] < 3.0):
                return
            _recent_cmd_cache[cache_key] = now_ts
            if len(_recent_cmd_cache) > 200:
                _recent_cmd_cache.clear()

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
                    f"• `@helena <pergunta>` ➔ Helena Torres (VP TI)\n"
                    f"• `@vance <pergunta>` ➔ Alex Vance (Arquitetura & Engenharia)\n"
                    f"• `@sobral <pergunta>` ➔ Sobral (Tráfego Pago & Performance)\n"
                    f"• `@bruno <pergunta>` ➔ Bruno (Codex & Automações)\n"
                    f"• `@monge <pergunta>` ➔ O Monge (Espiritualidade & Códigos)\n"
                    f"• `@oraculo <pergunta>` ➔ Oráculo Central (Visão Geral & Maestro)\n\n"
                    f"📊 **Comandos de Sistema Disponíveis no Grupo**:\n"
                    f"`/status` | `/relatorio` | `/agentes` | `/gaps` | `/contratar` | `/estudar`"
                )
                btns = get_cockpit_inline_keyboard() if is_bot else None
                sent = await event.reply(welcome_group, buttons=btns)
                _record_sent_id(sent)
                return

            # CASO 2: Mensagens Privadas (Direto com o Bot ou em Mensagens Salvas)
            if not is_group:
                def _get_btn_text(b):
                    return getattr(getattr(b, "button", None), "text", "") or ""

                is_button = any(txt.lower() in _get_btn_text(btn).lower() for row in COCKPIT_KEYBOARD for btn in row if _get_btn_text(btn))
                if txt.startswith("/") or is_button:
                    print(f"📱 [Telegram Privado] Comando recebido: {txt}", flush=True)
                    response = await process_telegram_command(txt)
                    btns = get_cockpit_inline_keyboard() if is_bot else COCKPIT_KEYBOARD
                    sent = await event.reply(response, buttons=btns)
                    _record_sent_id(sent)
                else:
                    # Interpretação de Linguagem Natural no Privado
                    print(f"🧠 [Telegram Privado] Interpretando linguagem natural: {txt[:50]}", flush=True)
                    try:
                        from orchestration.intent_interpreter import execute_or_clarify_intent
                        parsed_res = await execute_or_clarify_intent(txt)
                        resp_txt = parsed_res.get("response_text", "")
                        if resp_txt:
                            btns = None
                            if parsed_res.get("status") == "executed_drive":
                                from ingestion.telegram_notifier import get_drive_explorer_keyboard
                                btns = get_drive_explorer_keyboard(parsed_res.get("folder_data", {}))
                            sent = await event.reply(resp_txt, buttons=btns)
                            _record_sent_id(sent)
                    except Exception as nl_err:
                        logger.error(f"Erro ao processar linguagem natural no privado: {nl_err}")
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
                    "@tiago": "tiago",
                    "@tech": "tiago",
                    "@vance": "alex_vance",
                    "@alex": "alex_vance",
                    "@monge": "monge",
                    "@bruno": "bruno",
                    "@camila": "camila",
                    "@marina": "marina",
                    "@mente": "marina",
                    "@ricardo": "ricardo",
                    "@victor": "victor",
                    "@vendas": "victor",
                    "@sofia": "sofia",
                    "@sdr": "sofia",
                    "@caio": "caio",
                    "@copy": "caio",
                    "@felipe": "felipe",
                    "@followup": "felipe",
                    "@qa": "quinn",
                    "@cloud": "claudio",
                    "@jim": "jim",
                    "@kwik": "jim",
                    "@ana": "ana",
                    "@sobral": "sobral",
                    "@thales": "thales",
                    "@marcelo": "marcelo",
                    "@marketing": "marcelo",
                    "@growth": "marcelo",
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

                # Em grupos, o Bot NUNCA responde a conversas normais ou mensagens não direcionadas.
                # Ele responde estritamente a comandos (/...), menções explícitas (@...) ou em tópicos vinculados.
                return

        # Registra no Bot Client (se token configurado)
        if bot_client:
            @bot_client.on(events.NewMessage())
            async def on_bot_message(evt):
                await handle_message_event(evt, is_bot=True)

            @bot_client.on(events.CallbackQuery())
            async def on_bot_callback(evt):
                await handle_callback_query(evt)

            logger.info("🤖 Bot Telethon configurado com listeners exclusivos de mensagem e botões inline!")

        # Sessão de Usuário (User Client):
        # A conta pessoal MTProto do Rodrigo NÃO possui listeners de mensagens ativas.
        # Ela é mantida exclusivamente para download/outbound quando necessário, sem interferir em grupos ou mensagens salvas.
        if has_user_auth:
            logger.info("👤 Sessão de Usuário Telethon mantida exclusivamente para download/outbound (sem listener de mensagens).")

        _listener_started = True
        print("📱 Telegram Mobile Cockpit Listener iniciado com sucesso (ouvindo exclusivamente via Bot Client oficial)!", flush=True)

        # Inicia o Bot do 2º Cérebro (Obsidian Ingestion) se token configurado
        try:
            from ingestion.brain_bot import start_brain_bot
            asyncio.create_task(start_brain_bot())
            logger.info("🧠 Task do Bot do 2º Cérebro despachada com sucesso!")
        except Exception as brain_err:
            logger.warning(f"Não foi possível iniciar o Brain Bot: {brain_err}")
    except Exception as e:
        print(f"⚠️ Não foi possível iniciar o Telegram Mobile Listener: {e}", flush=True)
