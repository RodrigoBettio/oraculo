"""
Oráculo Autonomous Decision Governor
Gerenciador de governança autônoma com janela de silêncio (Grace Period de X minutos).
Permite ao assistente executar ações rotineiras e operacionais de forma autônoma
caso não haja objeção do Rodrigo Bettio Jr. no prazo estipulado, mantendo veto
absoluto de auto-execução em mudanças estruturais ou críticas.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import settings

logger = logging.getLogger("autonomous_governor")

class AutonomousGovernor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AutonomousGovernor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.actions_dir = settings.DATA_DIR / "autonomous_actions"
        self.actions_dir.mkdir(parents=True, exist_ok=True)

    def propose_action(
        self,
        action_id: str,
        title: str,
        description: str,
        category: str = "operational",
        delay_minutes: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Registra uma nova proposta de ação autônoma.
        category: 'operational' (auto-executa após delay) ou 'critical' (exige aprovação explícita).
        """
        now = time.time()
        delay = delay_minutes if delay_minutes is not None else settings.AUTONOMOUS_EXECUTION_DELAY_MINUTES
        scheduled_for = now + (delay * 60) if category == "operational" else None

        action_data = {
            "id": action_id,
            "title": title,
            "description": description,
            "category": category,
            "status": "pending",
            "delay_minutes": delay,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "created_timestamp": now,
            "scheduled_timestamp": scheduled_for,
            "executed_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "payload": payload or {}
        }

        self._save_action(action_data)
        logger.info(f"⏱️ Ação autônoma proposta: {action_id} ('{title}') | Categoria: {category} | Delay: {delay} min")
        return action_data

    def cancel_action(self, action_id: str, reason: str = "Cancelado pelo Rodrigo Bettio Jr.") -> Dict[str, Any]:
        """Cancela uma ação pendente imediatamente."""
        action = self.get_action(action_id)
        if not action:
            return {"status": "error", "message": f"Ação {action_id} não encontrada."}

        if action.get("status") != "pending":
            return {"status": "error", "message": f"Ação já está no estado: {action.get('status')}."}

        action["status"] = "cancelled"
        action["cancelled_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        action["cancel_reason"] = reason
        self._save_action(action)
        logger.info(f"🛑 Ação autônoma {action_id} cancelada. Motivo: {reason}")
        return {"status": "success", "message": f"Ação '{action.get('title')}' cancelada com sucesso.", "action": action}

    def execute_action(self, action_id: str, trigger: str = "manual") -> Dict[str, Any]:
        """Marca a ação como executada."""
        action = self.get_action(action_id)
        if not action:
            return {"status": "error", "message": f"Ação {action_id} não encontrada."}

        if action.get("status") != "pending":
            return {"status": "error", "message": f"Ação já está no estado: {action.get('status')}."}

        action["status"] = "executed"
        action["executed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        action["executed_trigger"] = trigger
        self._save_action(action)
        logger.info(f"⚡ Ação autônoma {action_id} executada com sucesso via trigger: {trigger}")
        return {"status": "success", "message": f"Ação '{action.get('title')}' executada com sucesso.", "action": action}

    def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.actions_dir / f"{action_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler ação {action_id}: {e}")
            return None

    def get_pending_actions(self) -> List[Dict[str, Any]]:
        actions = []
        for f in self.actions_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as af:
                    d = json.load(af)
                    if d.get("status") == "pending":
                        actions.append(d)
            except Exception:
                pass
        return sorted(actions, key=lambda x: x.get("created_timestamp", 0))

    def check_due_actions(self) -> List[Dict[str, Any]]:
        """Verifica quais ações operacionais atingiram o timeout sem objeção e devem ser executadas."""
        now = time.time()
        due = []
        for action in self.get_pending_actions():
            if action.get("category") == "operational":
                sched = action.get("scheduled_timestamp")
                if sched and now >= sched:
                    due.append(action)
        return due

    def _save_action(self, action_data: Dict[str, Any]):
        file_path = self.actions_dir / f"{action_data['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(action_data, f, indent=2, ensure_ascii=False)

# Singleton global
autonomous_governor = AutonomousGovernor()
