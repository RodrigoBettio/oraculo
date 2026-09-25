from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AreaProfile(BaseModel):
    id: str                                  # Identificador unico (ex: 'tech', 'sales', 'mind', 'finance', 'marketing', 'health')
    name: str                                # Nome da area (ex: 'Tecnologia & Dev', 'Vendas & Negociacao')
    icon: str = '📁'                         # Emoji ou icone representativo
    color: str = '#10b981'                   # Cor tematica em HEX
    description: str = ''                    # Descricao dos objetivos dessa area
    manager_agent_id: Optional[str] = None   # ID do Agente Gestor (Lider executivo)
    subagent_ids: List[str] = Field(default_factory=list) # IDs dos agentes tecnicos subordinados
    
    # Metricas de vida / Cockpit Orbital (estilo imagem de referencia)
    health_score: int = 100                  # Score de vitalidade/saude da area (0 a 100)
    routines_count: int = 0                  # Rotinas ativas vinculadas
    projects_count: int = 0                  # Projetos em andamento
    meetings_count: int = 0                  # Reunioes / alinhamentos
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
