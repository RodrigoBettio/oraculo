"""
Testes automatizados da API REST do Obsidian Vault e Sincronização Bidirecional.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from web.app import app
from web.vault_routes import _calculate_file_hash
from scripts.sync_vault import sync_local_mirror, build_manifest

client = TestClient(app)


def test_vault_status_endpoint():
    """Testa se o endpoint /api/vault/status retorna as estatísticas do cofre."""
    response = client.get("/api/vault/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_files" in data
    assert "total_markdown_notes" in data
    assert "total_pipelines" in data
    assert data["status"] == "healthy"
    assert data["total_markdown_notes"] >= 3


def test_vault_manifest_endpoint():
    """Testa se o endpoint /api/vault/manifest retorna a árvore de notas com hashes."""
    response = client.get("/api/vault/manifest")
    assert response.status_code == 200
    data = response.json()
    assert "manifest" in data
    manifest = data["manifest"]
    assert any("04_Projetos_Ativos" in path for path in manifest.keys())


def test_vault_file_read_and_write(tmp_path):
    """Testa leitura e escrita de nota via API do cofre."""
    test_rel = "00_Inbox/test_api_note.md"
    test_content = "# Test Note\nCriado via teste unitário."

    # Salva
    save_resp = client.post("/api/vault/file", json={"path": test_rel, "content": test_content})
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "saved"

    # Lê
    read_resp = client.get(f"/api/vault/file?path={test_rel}")
    assert read_resp.status_code == 200
    assert read_resp.json()["content"] == test_content

    # Limpeza
    repo_vault = Path("data/vault") / test_rel
    if repo_vault.exists():
        repo_vault.unlink()


def test_local_mirror_sync(tmp_path):
    """Testa sincronização bidirecional entre dois cofres locais."""
    vault_a = tmp_path / "vault_a"
    vault_b = tmp_path / "vault_b"
    vault_a.mkdir()
    vault_b.mkdir()

    # Cria arquivo no Vault A
    (vault_a / "note_a.md").write_text("Conteudo A", encoding="utf-8")
    (vault_b / "note_b.md").write_text("Conteudo B", encoding="utf-8")

    to_b, to_a = sync_local_mirror(vault_a, vault_b)
    assert to_b == 1
    assert to_a == 1
    assert (vault_b / "note_a.md").exists()
    assert (vault_a / "note_b.md").exists()
