"""
Testes de Validação das Novas Funcionalidades:
1. Google Drive Explorer & Inline Keyboards
2. Seletor de Agentes (Trava para não incluir gestores)
3. Relatório Diário Executivo
4. Ingestão no 2º Cérebro (Obsidian)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ajusta path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import settings


def test_drive_keyboards_and_manager_lock():
    """Testa os teclados inline do Drive e valida que gestores NUNCA aparecem."""
    from ingestion.telegram_notifier import (
        get_drive_explorer_keyboard,
        get_agent_selector_keyboard,
        format_drive_folder_view
    )

    mock_folder = {
        "current_folder": {"id": "1cBDvRvFL4B5TmD7oXYfcTYvlHl40GXGG", "name": "Cursos Python", "parent_id": "root_id"},
        "breadcrumbs": [{"id": "root_id", "name": "Raiz"}, {"id": "1cBDvRvFL4B5TmD7oXYfcTYvlHl40GXGG", "name": "Cursos Python"}],
        "subfolders": [
            {"id": "sub1", "name": "Modulo 01 - Basico"},
            {"id": "sub2", "name": "Modulo 02 - Avancado"}
        ],
        "videos": [
            {"id": "v1", "name": "Aula 01.mp4", "is_studied": True},
            {"id": "v2", "name": "Aula 02.mp4", "is_studied": False}
        ],
        "support_files": []
    }

    # 1. Explorer Keyboard
    kb = get_drive_explorer_keyboard(mock_folder)
    assert len(kb) >= 4, "Teclado do explorer deve ter pelo menos 4 linhas"
    print("✅ Teste 1: get_drive_explorer_keyboard gerado com sucesso!")

    # 2. View Text
    view = format_drive_folder_view(mock_folder)
    assert "Cursos Python" in view
    assert "1 ✅ estudadas" in view
    assert "1 ⏳ pendentes" in view
    print("✅ Teste 2: format_drive_folder_view formatou corretamente!")

    # 3. Agent Selector & Manager Lock
    agent_kb = get_agent_selector_keyboard("sub1")
    agent_texts = []
    for row in agent_kb:
        for btn in row:
            if hasattr(btn, 'text'):
                agent_texts.append(btn.text)

    # Nomes proibidos de gestores
    assert not any("Helena" in t for t in agent_texts), "Helena Torres (gestora) NÃO pode aparecer no seletor!"
    assert not any("Ricardo" in t for t in agent_texts), "Ricardo Monteiro (gestor) NÃO pode aparecer no seletor!"
    assert not any("Camila" in t for t in agent_texts), "Dra. Camila Reis (gestora) NÃO pode aparecer no seletor!"

    # Técnicos devem aparecer
    assert any("Alex Vance" in t for t in agent_texts), "Alex Vance deve estar no seletor"
    assert any("Quinn QA" in t for t in agent_texts), "Quinn QA deve estar no seletor"
    assert any("Cláudio Cloud" in t for t in agent_texts), "Cláudio Cloud deve estar no seletor"
    print("✅ Teste 3: Trava de Gestores validada! Apenas especialistas técnicos podem ser atribuídos.")


async def test_daily_report_generation():
    """Testa a geração do relatório diário executivo."""
    from orchestration.daily_report import generate_daily_executive_report, get_weekday_pt
    from datetime import datetime

    report = await generate_daily_executive_report()
    assert "RELATÓRIO EXECUTIVO DIÁRIO" in report
    assert "TECNOLOGIA & DESENVOLVIMENTO" in report
    assert "VENDAS & NEGÓCIOS" in report
    assert "MENTE & PERFORMANCE" in report
    assert "Helena Torres" in report
    assert "Ricardo Monteiro" in report
    assert "Dra. Camila Reis" in report
    print("✅ Teste 4: Relatório Diário Executivo gerado perfeitamente com todas as 3 áreas!")


def test_brain_bot_note_saving():
    """Testa a gravação de notas no cofre Obsidian com YAML frontmatter."""
    from ingestion.brain_bot import save_note_to_vault, get_vault_inbox

    title = "Teste Automatizado do Brain Bot"
    content = "Esta é uma nota de teste para verificar a persistência no cofre."
    tags = ["inbox", "teste", "antigravity"]
    
    saved_file = save_note_to_vault(title, content, "texto", tags)
    assert saved_file.exists(), f"Arquivo {saved_file} deveria existir no cofre"

    text = saved_file.read_text(encoding="utf-8")
    assert "---" in text
    assert "source: telegram" in text
    assert "status: pendente" in text
    assert "tags: [inbox, teste, antigravity]" in text
    assert title in text
    assert content in text

    # Limpeza do teste
    saved_file.unlink()
    print(f"✅ Teste 5: Nota criada e validada com frontmatter YAML em {saved_file.parent.name}!")


if __name__ == "__main__":
    test_drive_keyboards_and_manager_lock()
    asyncio.run(test_daily_report_generation())
    test_brain_bot_note_saving()
    print("\n🎉 TODOS OS TESTES PASSARAM COM SUCESSO!")
