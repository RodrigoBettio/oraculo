"""
Oráculo — Relatório Diário Executivo
Gera relatório consolidado de todos os gestores com métricas, execuções e pendências.
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


async def generate_area_report(manager_id: str, area_name: str, emoji: str) -> str:
    """Gera relatório de uma área específica baseado no gestor."""
    # Placeholder for future expansion
    pass


async def generate_daily_executive_report() -> str:
    """Consolida o relatório executivo de todas as áreas."""
    now = datetime.now(BRT)
    
    managers = [
        ("gestor_tech_cto", "tech", "TECNOLOGIA & DESENVOLVIMENTO", "💻", "Helena Torres"),
        ("gestor_sales_director", "sales", "VENDAS & NEGÓCIOS", "💼", "Ricardo Monteiro"),
        ("gestor_mind_wellness", "mind", "MENTE & PERFORMANCE", "🧠", "Dra. Camila Reis"),
    ]
    
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
        f"🤖 _Gerado automaticamente pelo Oráculo às {now.strftime('%H:%M')} BRT_"
    )
    
    return header + "\n".join(sections) + footer


async def generate_area_report_section(manager_id, area_id, area_name, emoji, manager_name) -> str:
    """Gera uma seção do relatório para uma área."""
    # Load agents from data/agents/ matching the area_id
    agents_dir = settings.AGENTS_DIR
    area_agents = []
    for f in agents_dir.glob("*.json"):
        try:
            agent = json.loads(f.read_text(encoding='utf-8'))
            if agent.get('area_id') == area_id and agent.get('agent_type') == 'tecnico':
                area_agents.append(agent)
        except Exception:
            continue
    
    # Count study metrics
    processed_dir = settings.PROCESSED_DIR
    today = datetime.now(BRT).date()
    studied_today = 0
    total_processed = 0
    if processed_dir.exists():
        for pf in processed_dir.iterdir():
            total_processed += 1
            try:
                mtime = datetime.fromtimestamp(pf.stat().st_mtime, tz=BRT).date()
                if mtime == today:
                    studied_today += 1
            except Exception:
                continue
    
    # Count tasks
    tasks_dir = settings.DATA_DIR / "tasks"
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
    
    # Get study queue status
    try:
        from ingestion.study_queue import StudyQueueManager
        sqm = StudyQueueManager()
        queue_status = sqm.get_status()
        queued = queue_status.get('queued', 0)
        processing = queue_status.get('downloading', 0) + queue_status.get('studying', 0)
    except Exception:
        queued = 0
        processing = 0
    
    # Format agent status
    agent_list = ", ".join([f"{a['name']} ✅" for a in area_agents]) if area_agents else "Nenhum agente ativo"
    
    section = f"""
{emoji} **{area_name}**
   Gestor(a): {manager_name}
   
   📊 Métricas: {studied_today} estudados hoje | {queued} na fila | {processing} em andamento
   👥 Equipe: {agent_list}
   📋 Tarefas: {tasks_today} criadas hoje | {tasks_pending} pendentes
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


async def get_daily_report_on_demand() -> str:
    """Gera o relatório sob demanda (para o comando /relatorio)."""
    return await generate_daily_executive_report()
