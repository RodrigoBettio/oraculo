import subprocess
import pytest
from pathlib import Path

def test_imports():
    """Garante que todas as bibliotecas chave estão prontas."""
    import pydantic
    import telethon
    import google.genai
    assert pydantic is not None
    assert telethon is not None
    assert google.genai is not None

def test_settings_and_dirs():
    """Verifica se as configurações e pastas foram inicializadas."""
    from config import settings
    assert settings.DATA_DIR.exists()
    assert settings.VIDEOS_DIR.exists()
    assert settings.PROCESSED_DIR.exists()
    assert settings.AGENTS_DIR.exists()

def test_agent_profile_logic():
    """Testa o ciclo de vida e senioridade do agente humano."""
    from models.agent import AgentProfile, AgentStatus

    agent = AgentProfile(
        id="agent_tailwind",
        name="Alex",
        role="Especialista em Tailwind & UI",
        status=AgentStatus.STUDYING
    )
    assert agent.status == AgentStatus.STUDYING
    assert agent.total_hours_studied == 0.0

    # Simula o estudo de um vídeo de 1.5 horas
    agent.add_studied_content(
        group_name="Codando com Tailwind",
        hours=1.5,
        topics=["Flexbox", "Grid", "Responsividade"]
    )

    assert agent.status == AgentStatus.ACTIVE
    assert agent.total_hours_studied == 1.5
    assert agent.total_videos_studied == 1
    assert "Flexbox" in agent.topics_mastered
    assert len(agent.sources) == 1
    assert agent.sources[0].hours_studied == 1.5

def test_knowledge_document_model():
    """Testa a criação e validação do modelo de documento processado."""
    from models.knowledge import VideoDocument, CodeSnippet, TranscriptSegment, ProcessingTier

    code = CodeSnippet(
        timestamp="03:15",
        language="html",
        code="<div class='flex items-center justify-between'></div>",
        description="Container flexbox responsivo"
    )

    doc = VideoDocument(
        video_id="video_01",
        file_name="aula_01.mp4",
        group_name="Codando com Tailwind",
        tier_used=ProcessingTier.MULTIMODAL_OCR,
        title="Aula 1 - Fundamentos do Tailwind",
        summary="Introdução a utilitários",
        topics=["Flexbox", "Setup"],
        segments=[
            TranscriptSegment(
                start_time="00:00",
                end_time="05:00",
                text="Começando a aula...",
                code_snippets=[code]
            )
        ],
        extracted_codes=[code],
        full_markdown="# Aula 1\n..."
    )

    assert doc.video_id == "video_01"
    assert len(doc.extracted_codes) == 1
    assert doc.extracted_codes[0].timestamp == "03:15"

def test_ffmpeg_available():
    """Verifica se o ffmpeg pode ser invocado."""
    res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "ffmpeg version" in res.stdout

def test_seniority_progression():
    """Valida as patentes e cálculos de XP com o aumento de horas de estudo."""
    from models.agent import AgentProfile, AgentRank

    agent = AgentProfile(id="test_dev", name="Lucas", role="Dev")
    info = agent.get_seniority_info()
    assert info["rank"] == AgentRank.ESTAGIARIO.value
    assert info["progress_percentage"] == 0.0

    # Adiciona 5 horas -> Deve virar Júnior
    agent.add_studied_content(group_name="Cursos", hours=5.0)
    info = agent.get_seniority_info()
    assert info["rank"] == AgentRank.JUNIOR.value
    assert info["progress_percentage"] == 37.5

    # Adiciona 20 horas (total: 25h) -> Deve virar Pleno
    agent.add_studied_content(group_name="Cursos", hours=20.0)
    info = agent.get_seniority_info()
    assert info["rank"] == AgentRank.PLENO.value

    # Adiciona 50 horas (total: 75h) -> Deve virar Mestre
    agent.add_studied_content(group_name="Cursos", hours=50.0)
    info = agent.get_seniority_info()
    assert info["rank"] == AgentRank.MESTRE.value

def test_web_api_routes():
    """Testa os endpoints da API Web FastAPI."""
    from starlette.testclient import TestClient
    from web.app import app

    client = TestClient(app)

    # 1. Rota de Agentes
    res = client.get("/api/agents")
    assert res.status_code == 200
    agents = res.json()
    assert isinstance(agents, list)
    assert any(a["id"] == "agent_claude_code" for a in agents)

    # 2. Status de Estudo
    res = client.get("/api/study/status")
    assert res.status_code == 200
    assert "is_studying" in res.json()

    # 3. Base de Conhecimento
    res = client.get("/api/knowledge")
    assert res.status_code == 200
    docs = res.json()
    assert isinstance(docs, list)
    assert any(d["video_id"] == "aula_04_hooks" for d in docs)

    # 4. Rota raiz (HTML)
    res = client.get("/")
    assert res.status_code == 200
    assert "Oráculo" in res.text

    # 5. Rota de Telemetria de Tokens
    res = client.get("/api/tokens/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "percent_used" in stats
    assert "daily_used" in stats
    assert "weekly_used" in stats

    # 6. Rota da Fila de Estudos
    res = client.get("/api/study/queue")
    assert res.status_code == 200
    qstate = res.json()
    assert "queue_count" in qstate
    assert "is_busy" in qstate

def test_token_tracker_module():
    """Testa funções de registro e agregação de tokens."""
    from utils.token_tracker import record_tokens, get_token_stats, set_daily_budget
    
    set_daily_budget(500000)
    rec = record_tokens(
        source="test_run",
        details="teste de aula",
        prompt_tokens=2000,
        output_tokens=500
    )
    assert rec["total_tokens"] == 2500

    stats = get_token_stats()
    assert stats["daily_budget"] == 500000
    assert stats["daily_used"] >= 2500
    assert stats["percent_used"] >= 0.5

def test_study_queue_lifecycle():
    """Testa o gerenciador de fila de estudos assíncrona."""
    from ingestion.study_queue import StudyQueueManager
    import asyncio

    qm = StudyQueueManager()
    
    async def run_queue_test():
        item = await qm.enqueue(
            agent_id="agent_claude_code",
            group_id=12345,
            group_name="Canal Teste",
            message_id=99999,
            file_name="aula_teste_queue.mp4",
            tier="audio_only"
        )
        assert item.tier == "audio_only"
        assert item.status in ["queued", "downloading", "processing"]
        
        # Teste de remoção
        qm.remove(item.id)

    asyncio.run(run_queue_test())
