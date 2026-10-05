"""
Testes unitários e de integração para o Pipeline Loader, Obsidian Vault Bridge e Laya Dispatcher.
"""

import pytest
from pathlib import Path
from orchestration.pipeline_loader import (
    list_available_pipelines,
    find_pipeline_for_prompt,
    get_pipeline_by_id,
    save_project_to_vault,
    sync_project_created,
    sync_task_completed,
    sync_project_completed,
    list_vault_projects,
    get_vault_project_overview,
    get_project_vault_dir_name,
    get_vault_dirs
)
from orchestration.laya_dispatcher import LayaDispatcher
from orchestration.harness import AgentHarness
from models.project import Project, Task, DocumentArtifact, ProjectStatus, TaskStatus, DocumentType

def test_list_available_pipelines():
    pipes = list_available_pipelines()
    pipe_ids = [p["id"] for p in pipes]
    assert "youtube_linkedin" in pipe_ids
    assert "feature_tdd_sdd" in pipe_ids
    assert "funil_vendas_b2b" in pipe_ids

def test_find_pipeline_for_prompt_direct():
    p, theme = find_pipeline_for_prompt("/fluxo youtube_linkedin Hooks no Claude Code")
    assert p is not None
    assert p["id"] == "youtube_linkedin"
    assert theme == "Hooks no Claude Code"

def test_find_pipeline_for_prompt_keywords():
    p, theme = find_pipeline_for_prompt("Quero um vídeo para o youtube e um post no linkedin sobre FastAPI")
    assert p is not None
    assert p["id"] == "youtube_linkedin"

def test_auto_dispatch_uses_pipeline():
    harness = AgentHarness()
    proj = harness.auto_dispatch("/fluxo youtube_linkedin Hooks no Claude Code")
    assert "youtube_linkedin" in proj.title.lower() or "vídeo youtube" in proj.title.lower()
    assert len(proj.tasks) == 3
    assert proj.tasks[0].assigned_agent_id == "agent_claude_code"
    assert proj.tasks[1].assigned_agent_id == "agent_caio_copywriter"
    assert proj.tasks[2].assigned_agent_id == "agent_link_4211"

def test_laya_project_routing():
    laya = LayaDispatcher()
    
    # 1. Tech query
    r_tech = laya.route_project_demand("Criar endpoint /api/metrics no FastAPI com Pytest")
    assert r_tech["area_id"] == "tech"
    assert any(n in r_tech["manager_agent_name"] for n in ["Thiago", "Tiago", "Tech", "Helena"])
    assert not r_tech["is_gap"]

    # 2. Sales query
    r_sales = laya.route_project_demand("Roteiro para quebrar objeção de preço e cold call B2B")
    assert r_sales["area_id"] == "sales"
    assert not r_sales["is_gap"]

    # 3. Marketing query
    r_mkt = laya.route_project_demand("Gestão de tráfego pago e campanhas no Meta Ads")
    assert r_mkt["area_id"] == "marketing"
    assert not r_mkt["is_gap"]

    # 4. GAP query
    r_gap = laya.route_project_demand("Como calcular pensão alimentícia e imposto de renda")
    assert r_gap["is_gap"] is True

def test_real_time_vault_lifecycle():
    proj = Project(
        id="proj_test_vault_rt",
        title="Projeto Teste Vault Tempo Real",
        description="Validando escrita em tempo real das notas no Obsidian",
        area_id="tech",
        area_name="Tecnologia",
        manager_agent_id="gestor_tech_cto",
        manager_agent_name="Thiago Tech",
        status=ProjectStatus.PLANNING
    )
    task1 = Task(
        id="task_rt_1",
        project_id=proj.id,
        title="Especificação Técnica",
        instruction="Criar spec",
        assigned_agent_id="agent_alex_vance",
        assigned_agent_name="Alex Vance",
        status=TaskStatus.TODO
    )
    task2 = Task(
        id="task_rt_2",
        project_id=proj.id,
        title="Testes Unitários",
        instruction="Criar testes",
        assigned_agent_id="agent_claude_code",
        assigned_agent_name="Bruno",
        status=TaskStatus.TODO
    )

    # 1. Criação do projeto (Momento 1)
    paths_created = sync_project_created(proj, [task1, task2])
    assert len(paths_created) > 0
    overview_file = paths_created[0]
    assert overview_file.exists()
    content = overview_file.read_text(encoding="utf-8")
    assert "PENDENTE ⏳" in content

    # 2. Conclusão da Tarefa 1 (Momento 2)
    task1.status = TaskStatus.DONE
    doc1 = DocumentArtifact(
        id="doc_rt_1",
        project_id=proj.id,
        task_id=task1.id,
        created_by_agent_id="agent_alex_vance",
        created_by_agent_name="Alex Vance",
        title="Especificação Técnica Final",
        content="## Contrato de API\nRota /api/v1/test",
        doc_type=DocumentType.REPORT
    )
    paths_t1 = sync_task_completed(proj, task1, doc1, [task1, task2])
    assert len(paths_t1) > 0
    task_file = paths_t1[0]
    assert task_file.exists()
    assert "Rota /api/v1/test" in task_file.read_text(encoding="utf-8")

    # Verifica se 00_Overview.md foi atualizado em tempo real com o link
    overview_updated = overview_file.read_text(encoding="utf-8")
    assert "CONCLUÍDO ✅" in overview_updated

    # 3. Conclusão Total do Projeto (Momento 3)
    task2.status = TaskStatus.DONE
    proj.status = ProjectStatus.COMPLETED
    paths_completed = sync_project_completed(proj, [task1, task2], [doc1])
    assert len(paths_completed) > 0
    overview_final = overview_file.read_text(encoding="utf-8")
    assert "COMPLETED" in overview_final

    # 4. Limpeza do projeto de teste
    folder_name = get_project_vault_dir_name(proj)
    for v in get_vault_dirs():
        test_dir = v / "04_Projetos_Ativos" / "Execucoes" / folder_name
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)
        # Limpa MOC
        moc_file = v / "04_Projetos_Ativos" / "MOC_Projetos.md"
        if moc_file.exists():
            moc_txt = moc_file.read_text(encoding="utf-8")
            moc_lines = [l for l in moc_txt.splitlines(keepends=True) if proj.title not in l]
            moc_file.write_text("".join(moc_lines), encoding="utf-8")
