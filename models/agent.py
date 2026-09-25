from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class AgentStatus(str, Enum):
    ACTIVE = "ativo"        # Pronto para responder consultas
    STUDYING = "estudando"  # Em processo de ingestão/estudo de vídeos
    INACTIVE = "inativo"    # Aguardando atribuição de cursos ou sem dados

class StudiedLesson(BaseModel):
    lesson_id: str
    title: str
    duration_hours: float
    duration_seconds: float = 0.0
    theme_name: Optional[str] = None
    companion_files: List[str] = Field(default_factory=list)
    studied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    topics: List[str] = Field(default_factory=list)

class SourceStudy(BaseModel):
    group_name: str
    videos_count: int = 0
    hours_studied: float = 0.0
    last_studied_at: Optional[datetime] = None
    lessons: List[StudiedLesson] = Field(default_factory=list)

class AgentRank(str, Enum):
    ESTAGIARIO = "Estagiário"       # < 2h
    JUNIOR = "Júnior"               # 2h a 10h
    PLENO = "Pleno"                 # 10h a 30h
    SENIOR = "Sênior"               # 30h a 70h
    MESTRE = "Arquiteto Mestre"     # 70h+

class AgentProfile(BaseModel):
    id: str
    name: str
    role: str
    avatar: str = "👨‍💻"
    status: AgentStatus = AgentStatus.INACTIVE
    current_task: Optional[str] = None
    area_id: Optional[str] = None           # Área da Vida à qual o agente pertence
    agent_type: str = "tecnico"             # "gestor" (líder executivo) ou "tecnico" (especialista em tarefas)
    
    # Fontes e horas absorvidas
    sources: List[SourceStudy] = Field(default_factory=list)
    total_hours_studied: float = 0.0
    total_videos_studied: int = 0
    topics_mastered: List[str] = Field(default_factory=list)
    external_skills: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Configurações de Comportamento
    system_prompt: Optional[str] = None
    capabilities: List[str] = Field(default_factory=lambda: ["answer_questions", "generate_specs", "write_code"])
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_seniority_info(self) -> dict:
        """Calcula o nível, patente, percentual de XP e próximo objetivo do agente."""
        hours = self.total_hours_studied
        if hours < 2.0:
            rank = AgentRank.ESTAGIARIO
            badge = "🐣"
            current_level_base = 0.0
            next_level_goal = 2.0
        elif hours < 10.0:
            rank = AgentRank.JUNIOR
            badge = "🥉"
            current_level_base = 2.0
            next_level_goal = 10.0
        elif hours < 30.0:
            rank = AgentRank.PLENO
            badge = "🥈"
            current_level_base = 10.0
            next_level_goal = 30.0
        elif hours < 70.0:
            rank = AgentRank.SENIOR
            badge = "🥇"
            current_level_base = 30.0
            next_level_goal = 70.0
        else:
            rank = AgentRank.MESTRE
            badge = "👑"
            current_level_base = 70.0
            next_level_goal = 100.0

        range_hours = next_level_goal - current_level_base
        progress_pct = min(100.0, max(0.0, round(((hours - current_level_base) / range_hours) * 100, 1)))

        return {
            "rank": rank.value,
            "badge": badge,
            "current_hours": round(hours, 2),
            "next_goal_hours": next_level_goal,
            "progress_percentage": progress_pct,
            "videos_count": self.total_videos_studied,
            "topics_count": len(self.topics_mastered)
        }

    def add_studied_content(
        self, 
        group_name: str, 
        hours: float, 
        topics: List[str] = None, 
        lesson_id: str = None, 
        lesson_title: str = None, 
        duration_seconds: float = 0.0,
        theme_name: Optional[str] = None,
        companion_files: Optional[List[str]] = None
    ):
        """Atualiza a senioridade do agente após estudar um vídeo com registro da aula."""
        # Atualiza a fonte correspondente (busca flexível case-insensitive para evitar duplicar o mesmo canal)
        gn_clean = group_name.lower().strip()
        source = next((s for s in self.sources if s.group_name.lower().strip() == gn_clean or gn_clean in s.group_name.lower() or s.group_name.lower() in gn_clean), None)
        if not source:
            source = SourceStudy(group_name=group_name)
            self.sources.append(source)
        
        source.videos_count += 1
        source.hours_studied = round(source.hours_studied + round(hours, 2), 2)
        source.last_studied_at = datetime.now(timezone.utc)

        if lesson_id:
            # Evita duplicatas se re-estudado
            source.lessons = [l for l in source.lessons if l.lesson_id != lesson_id]
            source.lessons.append(StudiedLesson(
                lesson_id=lesson_id,
                title=lesson_title or lesson_id,
                duration_hours=round(hours, 2),
                duration_seconds=duration_seconds,
                theme_name=theme_name,
                companion_files=companion_files or [],
                topics=topics or []
            ))

        # Recalcula totais precisos a partir de todas as aulas registradas
        all_lessons = [l for s in self.sources for l in s.lessons]
        if all_lessons:
            self.total_videos_studied = len(all_lessons)
            self.total_hours_studied = round(sum(l.duration_hours for l in all_lessons), 2)
        else:
            self.total_hours_studied = round(self.total_hours_studied + round(hours, 2), 2)
            self.total_videos_studied += 1

        if topics:
            for t in topics:
                if t not in self.topics_mastered:
                    self.topics_mastered.append(t)
        
        self.updated_at = datetime.now(timezone.utc)
        if self.status == AgentStatus.STUDYING:
            self.status = AgentStatus.ACTIVE

    def set_topics(self, new_topics: List[str]):
        """Permite ao usuário customizar livremente os tópicos/habilidades dominadas pelo agente."""
        self.topics_mastered = [t.strip() for t in new_topics if t.strip()]
        self.updated_at = datetime.now(timezone.utc)

    def set_total_hours(self, hours: float):
        """Permite calibrar as horas reais do curso para dar o devido mérito ao agente."""
        self.total_hours_studied = round(max(0.0, hours), 2)
        self.updated_at = datetime.now(timezone.utc)

