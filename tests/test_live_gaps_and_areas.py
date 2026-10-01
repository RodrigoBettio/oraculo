"""
Testes Unitários: Real-Time Dynamic Skill GAPs, Área de Marketing e Validação de Áreas
Padrão SDD + TDD (RF04, RF07, RF10, RF16)
"""

import pytest
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from orchestration.manager_sync import analyze_manager_skill_gaps, get_all_managers_gaps_summary, is_competency_covered
from web.app import load_all_areas, get_agent_profile


def test_quad_areas_loaded_without_ghosts():
    """Valida RF10: As 4 áreas da vida devem ser carregadas sem áreas fantasmas ou nulas."""
    areas = load_all_areas()
    assert len(areas) == 4, f"Esperado 4 áreas oficiais, obtido {len(areas)}"

    area_ids = {a.get("id") for a in areas}
    expected_ids = {"tech", "area_marketing_6867", "sales", "mind"}
    assert area_ids == expected_ids, f"IDs de áreas divergentes: {area_ids}"

    for a in areas:
        assert a.get("id") is not None, "Área não pode ter id nulo"
        assert a.get("name") is not None, "Área não pode ter nome nulo"
        assert a.get("manager_agent_id") is not None, f"Área {a.get('id')} deve possuir gestor atribuído"
        assert a.get("agents_count", 0) > 0, f"Área {a.get('id')} deve possuir especialistas vinculados"


def test_marketing_manager_profile_and_skills():
    """Valida RF16: O gestor de marketing deve existir com cargo executivo e equipe vinculada."""
    manager = get_agent_profile("gestor_marketing")
    assert manager is not None, "gestor_marketing deve existir em data/agents/"
    assert manager.agent_type == "gestor", "Marcelo Marketing deve ser do tipo gestor"
    assert manager.area_id == "area_marketing_6867"
    assert "Marketing" in manager.name

    # Verifica se os arquivos de especificação existem
    skill_file = settings.DATA_DIR / "skills" / "gestor_marketing" / "SKILL.md"
    agent_file = settings.DATA_DIR / "skills" / "gestor_marketing" / "AGENT.md"
    assert skill_file.exists(), "SKILL.md de gestor_marketing deve existir"
    assert agent_file.exists(), "AGENT.md de gestor_marketing deve existir"


def test_real_time_gap_detection_cleans_cloud_and_qa():
    """Valida RF07: GAPs de Cloud e QA devem ser reconhecidos como resolvidos pela presença de Cláudio e Quinn."""
    # Simula lista de especialistas contendo Quinn QA e Cláudio Cloud
    specialists = [
        {"id": "agent_quinn_qa_7781", "name": "Quinn QA", "role": "Especialista em QA & Testes Automatizados (SDET)", "topics_mastered": ["TDD", "Playwright"]},
        {"id": "agent_claudio_cloud_4421", "name": "Cláudio Cloud", "role": "Especialista em Infraestrutura Cloud & DevOps/SRE", "topics_mastered": ["GCP", "Docker", "SRE"]}
    ]

    # Verifica detecção de competências cobertas
    assert is_competency_covered("Engenharia de QA & Testes Automatizados", specialists) is not None
    assert is_competency_covered("Infraestrutura Cloud & DevOps SRE", specialists) is not None
    assert is_competency_covered("Engenharia de Prompt Quântica", specialists) is None

    # Avalia diagnóstico do gestor de tech
    tech_diag = analyze_manager_skill_gaps("gestor_tech_cto", force_refresh=False)
    assert "error" not in tech_diag

    gap_names = [g.get("gap_name", "").lower() for g in tech_diag.get("identified_gaps", [])]
    for gn in gap_names:
        assert "qa" not in gn, f"GAP de QA não deveria constar como aberto: {gn}"
        assert "cloud" not in gn, f"GAP de Cloud não deveria constar como aberto: {gn}"
        assert "devops" not in gn, f"GAP de DevOps não deveria constar como aberto: {gn}"


def test_all_managers_gaps_summary_has_four_departments():
    """Valida RF07 e RF08: Resumo de gaps deve incluir todas as 4 áreas executivas."""
    summary = get_all_managers_gaps_summary(force_refresh=False)
    assert len(summary) == 4, f"Esperado 4 áreas no resumo de gaps, obtido {len(summary)}"

    departments = {s["area_id"] for s in summary}
    assert "tech" in departments
    assert "area_marketing_6867" in departments
    assert "sales" in departments
    assert "mind" in departments
