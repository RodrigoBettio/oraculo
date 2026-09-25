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
        from ingestion.telegram_client import TelegramManager
        tm = TelegramManager()
        client = await tm.get_client()
        if not await client.is_user_authorized():
            logger.warning("Telegram não autorizado para envio de notificação.")
            return False

        formatted_msg = (
            f"🔮 **ORÁCULO NOTIFICAÇÃO**\n\n"
            f"📌 **{title}**\n\n"
            f"{message}"
        )

        # 1. Envia para o Grupo Cockpit se houver
        group_id = get_cockpit_group_id()
        if group_id:
            try:
                g_msg = await client.send_message(group_id, formatted_msg)
                _record_sent_id(g_msg)
            except Exception as ge:
                logger.warning(f"Erro ao enviar notificação para grupo {group_id}: {ge}")

        # 2. Envia também para Mensagens Salvas ("me") com teclado tátil
        kwargs = {"buttons": COCKPIT_KEYBOARD} if with_keyboard else {}
        me_msg = await client.send_message("me", formatted_msg, **kwargs)
        _record_sent_id(me_msg)
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

    return (
        "❓ Comando não reconhecido.\n"
        "Toque em um dos botões abaixo ou envie `/ajuda` para ver o menu."
    )

_listener_started = False

async def start_telegram_listener():
    """Inicia o listener de mensagens no Telegram para comandos mobile em Mensagens Salvas e Grupos."""
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

        @client.on(events.NewMessage())
        async def on_incoming_telegram_message(event):
            txt = (event.message.message or "").strip()
            if not txt:
                return

            # Ignora mensagens já processadas ou disparadas pelo próprio robô
            if event.message.id in _sent_message_ids:
                return

            # Ignora cabeçalhos gerados pelos agentes para evitar eco recursivo
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
                sent = await event.reply(welcome_group)
                _record_sent_id(sent)
                return

            # CASO 2: Mensagens Salvas ("me")
            is_me = (not is_group) and (event.is_private or event.chat_id == (await client.get_me()).id)
            if is_me:
                is_button = any(txt.lower() in btn.text.lower() for row in COCKPIT_KEYBOARD for btn in row)
                if txt.startswith("/") or is_button:
                    logger.info(f"📱 Comando recebido em Mensagens Salvas: {txt}")
                    response = await process_telegram_command(txt)
                    sent = await event.reply(response, buttons=COCKPIT_KEYBOARD)
                    _record_sent_id(sent)
                return

            # CASO 3: Mensagens dentro do Grupo Cockpit
            is_cockpit = (cockpit_group_id and chat_id == cockpit_group_id) or ("oraculo" in getattr(chat, "title", "").lower() or "oráculo" in getattr(chat, "title", "").lower())
            if is_group and is_cockpit:
                # Comandos de barra diretos no grupo
                if txt.startswith("/"):
                    logger.info(f"📱 Comando de grupo recebido: {txt}")
                    response = await process_telegram_command(txt)
                    sent = await event.reply(response)
                    _record_sent_id(sent)
                    return

                # Mapeamento de gatilhos de agentes no grupo
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
                        logger.info(f"👥 Roteando mensagem de grupo para @{aid}")
                        ans = await process_telegram_command(cmd_synth)
                        sent = await event.reply(ans)
                        _record_sent_id(sent)
                    return

        _listener_started = True
        logger.info("📱 Telegram Mobile Cockpit Listener iniciado com sucesso (ouvindo em Mensagens Salvas e Grupos)!")
    except Exception as e:
        logger.warning(f"Não foi possível iniciar o Telegram Mobile Listener: {e}")
