"""
Oráculo — Relatório Diário Executivo
Gera relatório consolidado de todos os gestores com métricas, execuções e pendências.
Formatação estruturada com quebras de linha para cada especialista e seção dedicada de GAPs.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from config import settings

logger = logging.getLogger("daily_report")

try:
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo("America/Sao_Paulo")
except Exception:
    from datetime import timezone
    BRT = timezone(timedelta(hours=-3))


async def generate_daily_executive_report(filter_area: Optional[str] = None) -> str:
    """Consolida o relatório executivo de todas as áreas ou filtra por área específica."""
    now = datetime.now(BRT)
    
    managers = [
        ("gestor_tech_cto", "tech", "TECNOLOGIA & DESENVOLVIMENTO", "💻", "Helena Torres (VP de TI)"),
        ("gestor_marketing", "area_marketing_6867", "MARKETING & GROWTH", "🚀", "Marcelo Marketing (CMO & Growth)"),
        ("gestor_sales_director", "sales", "VENDAS & NEGOCIAÇÃO", "💼", "Victor Vendas (Dir. Comercial)"),
        ("gestor_mind_wellness", "mind", "MENTE, FOCO & SUPER CÉREBRO", "🧠", "Marina Mente (Head Wellness)"),
    ]
    
    # Filtro opcional por área
    if filter_area:
        fa = filter_area.lower().strip()
        filtered = []
        for m in managers:
            mid, aid, aname, em, mname = m
            if fa in aid.lower() or fa in aname.lower():
                filtered.append(m)
        if filtered:
            managers = filtered

    header = (
        f"🔮 **RELATÓRIO EXECUTIVO DIÁRIO**\n"
        f"📅 {now.strftime('%d/%m/%Y')} — {get_weekday_pt(now)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    sections = []
    for manager_id, area_id, area_name, emoji, manager_name in managers:
        section = await generate_area_report_section(manager_id, area_id, area_name, emoji, manager_name)
        sections.append(section)
    
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 _Para ver GAPs detalhados de qualquer gestor: `/gaps <tech|vendas|marketing|mente>`_\n"
        f"🤖 _Gerado automaticamente pelo Oráculo às {now.strftime('%H:%M')} BRT_"
    )
    
    return header + "\n".join(sections) + footer


async def generate_area_report_section(manager_id: str, area_id: str, area_name: str, emoji: str, manager_name: str) -> str:
    """Gera uma seção do relatório para uma área com especialistas em linhas separadas e GAPs do gestor."""
    agents_dir = settings.AGENTS_DIR
    area_agents = []
    total_area_hours = 0.0
    total_area_videos = 0

    if agents_dir.exists():
        for f in agents_dir.glob("*.json"):
            try:
                agent = json.loads(f.read_text(encoding='utf-8'))
                agent_aid = agent.get('area_id', '')
                is_match = (agent_aid == area_id) or (area_id == "area_marketing_6867" and "marketing" in agent_aid.lower())
                
                if is_match and agent.get('agent_type') == 'tecnico':
                    area_agents.append(agent)
                    total_area_hours += float(agent.get("total_hours_studied", 0.0) or 0.0)
                    total_area_videos += int(agent.get("total_videos_studied", 0) or 0)
            except Exception:
                continue
    
    # Ordenar especialistas por horas de estudo (maior primeiro)
    area_agents.sort(key=lambda x: float(x.get("total_hours_studied", 0.0) or 0.0), reverse=True)

    # Formatar especialistas em linhas separadas com quebra de linha
    agent_lines = []
    for a in area_agents:
        videos = int(a.get("total_videos_studied", 0) or 0)
        hours = float(a.get("total_hours_studied", 0.0) or 0.0)
        role = a.get("role", "Especialista")
        avatar = a.get("avatar", "👤")
        name = a.get("name", a.get("id"))
        if videos > 0:
            status_tag = f"`{videos} aulas` • `{hours:.1f}h` ✅"
        else:
            status_tag = f"`{hours:.1f}h` 🐣 _(Aguardando cursos)_"
        agent_lines.append(f"   • {avatar} **{name}** ({role}): {status_tag}")
    
    specialists_text = "\n".join(agent_lines) if agent_lines else "   • _Nenhum especialista vinculado ainda._"

    # GAPs de conhecimento identificados pelo gestor da área
    from orchestration.manager_sync import analyze_manager_skill_gaps
    gap_data = analyze_manager_skill_gaps(manager_id, force_refresh=False)
    identified_gaps = gap_data.get("identified_gaps", [])
    recs = gap_data.get("recommendations", [])

    gap_lines = []
    if identified_gaps:
        for g in identified_gaps[:2]:
            impact = g.get("impact", "Alto")
            badge = "🔴" if "crítico" in impact.lower() else "🟡"
            gap_lines.append(f"   {badge} **{g.get('gap_name')}** ({impact})")
        
        mats = []
        for r in recs:
            for m in r.get("requested_study_materials", []):
                mats.append(m)
        if mats:
            gap_lines.append(f"      📚 *Material Solicitado*: {', '.join(mats[:2])}")
    
    if gap_lines:
        gaps_section = "🔍 **GAPs de Conhecimento Apontados pelo Gestor**:\n" + "\n".join(gap_lines)
    else:
        gaps_section = "🔍 **GAPs de Conhecimento**: ✅ Equipe alinhada com as metas atuais."

    # Contagem de tarefas
    tasks_dir = settings.DATA_DIR / "tasks"
    today = datetime.now(BRT).date()
    tasks_today = 0
    tasks_pending = 0
    if tasks_dir.exists():
        for tf in tasks_dir.glob("*.json"):
            try:
                task = json.loads(tf.read_text(encoding='utf-8'))
                task_date = task.get('created_at', '')[:10]
                if task_date == str(today):
                    tasks_today += 1
                if task.get('status', 'pending') == 'pending':
                    tasks_pending += 1
            except Exception:
                continue

    section = f"""
{emoji} **{area_name}**
   Gestor(a): **{manager_name}**

   📊 **Métricas da Área**: **{total_area_videos} aulas absorvidas** ({total_area_hours:.1f}h de estudo)
👥 **Especialistas da Equipe**:
{specialists_text}

{gaps_section}
   📋 **Backlog**: {tasks_today} criadas hoje | {tasks_pending} pendentes
"""
    return section


def get_weekday_pt(dt: datetime) -> str:
    """Retorna o dia da semana em português."""
    days = {
        0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
        3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
    }
    return days.get(dt.weekday(), "")


async def check_and_send_daily_report():
    """Verifica se é hora de enviar o relatório diário e envia se necessário."""
    now = datetime.now(BRT)
    
    # Verificar se é o horário programado
    if now.hour != settings.DAILY_REPORT_HOUR or now.minute != settings.DAILY_REPORT_MINUTE:
        return False
    
    # Verificar se já foi enviado hoje
    report_tracker = settings.DATA_DIR / "last_daily_report.json"
    if report_tracker.exists():
        try:
            data = json.loads(report_tracker.read_text(encoding='utf-8'))
            last_date = data.get('last_sent_date', '')
            if last_date == str(now.date()):
                return False  # Já enviado hoje
        except Exception:
            pass
    
    # Gerar e enviar
    try:
        report = await generate_daily_executive_report()
        from ingestion.telegram_notifier import send_telegram_notification
        await send_telegram_notification("Relatório Executivo Matinal", report)
        
        # Marcar como enviado
        report_tracker.write_text(
            json.dumps({'last_sent_date': str(now.date()), 'sent_at': now.isoformat()}),
            encoding='utf-8'
        )
        logger.info(f"📊 Relatório diário enviado com sucesso às {now.strftime('%H:%M')}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar relatório diário: {e}")
        return False


async def get_daily_report_on_demand(area: Optional[str] = None) -> str:
    """Gera o relatório sob demanda (para o comando /relatorio [area])."""
    return await generate_daily_executive_report(filter_area=area)
