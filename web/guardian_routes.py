"""
============================================================
ORÁCULO - Guardian & SRE API Routes
============================================================
Endpoints para inspeção de saúde em tempo real, monitoramento
de incidentes e acionamento de auto-cura.
============================================================
"""

from fastapi import APIRouter
from orchestration.guardian import guardian

router = APIRouter(prefix="/api/guardian", tags=["Guardian & SRE"])

@router.get("/status")
def get_guardian_status():
    """Retorna o status de saúde geral, score e incidentes detectados pelo Guardian."""
    return guardian.get_status()

@router.post("/heal")
def trigger_auto_heal():
    """Força um ciclo imediato de diagnóstico e auto-recuperação."""
    db_res = guardian.check_sqlite_health()
    stuck_healed = guardian.check_and_heal_stuck_queue_items()
    worker_res = guardian.check_worker_liveness()
    
    return {
        "success": True,
        "message": f"Diagnóstico concluído: {stuck_healed} itens recuperados.",
        "sqlite": db_res,
        "stuck_items_healed": stuck_healed,
        "worker": worker_res,
        "overall_status": guardian.get_status()
    }
