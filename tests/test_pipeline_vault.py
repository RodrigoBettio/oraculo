"""
Testes unitários e de integração para o Pipeline Loader e Obsidian Vault Bridge.
"""

import pytest
from pathlib import Path
from orchestration.pipeline_loader import (
    list_available_pipelines,
    find_pipeline_for_prompt,
    get_pipeline_by_id,
    save_project_to_vault
)
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
