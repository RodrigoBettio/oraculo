#!/usr/bin/env python3
"""
Testes de Avaliação de Competência e Delegação Inter-Agentes do Oráculo
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from orchestration.agent_delegator import agent_delegator

def test_delegator_finds_agents():
    vance = agent_delegator.find_agent("vance")
    assert vance is not None, "Alex Vance deve ser encontrado pelo alias 'vance'"
    assert vance.get("name") == "Alex Vance"

    quinn = agent_delegator.find_agent("quinn")
    assert quinn is not None, "Quinn QA deve ser encontrado pelo alias 'quinn'"
    assert "QA" in quinn.get("name")

    claudio = agent_delegator.find_agent("claudio")
    assert claudio is not None, "Cláudio Cloud deve ser encontrado pelo alias 'claudio'"

    jordan = agent_delegator.find_agent("jordan")
    assert jordan is not None, "Jordan Belford deve ser encontrado pelo alias 'jordan'"

    print("✅ Teste 1: Resolução de todos os agentes e aliases aprovada!")

def test_competency_alex_vance_qa_delegation():
    vance = agent_delegator.find_agent("vance")
    assert vance is not None

    query = "Como estruturar uma suíte de testes E2E com Playwright usando Page Object Model?"
    decision = agent_delegator.evaluate_competency(vance, query)

    print(f"\n🔍 Decisão para Vance sobre Playwright: {decision}")
    assert not decision.is_competent, "Alex Vance não deve ser considerado competente para Playwright E2E"
    assert decision.target_agent_id == "agent_quinn_qa_7781", f"Deveria delegar para Quinn QA, mas delegou para {decision.target_agent_id}"
    print("✅ Teste 2: Alex Vance identificou que Playwright é QA e delegou para Quinn QA!")

def test_competency_alex_vance_own_domain():
    vance = agent_delegator.find_agent("vance")
    assert vance is not None

    query = "Como implementar o padrão Ports and Adapters (Hexagonal Architecture) com FastAPI assíncrono?"
    decision = agent_delegator.evaluate_competency(vance, query)

    print(f"\n🔍 Decisão para Vance sobre Arquitetura Hexagonal: {decision}")
    assert decision.is_competent, "Alex Vance DEVE ser considerado competente para Ports and Adapters / FastAPI"
    print("✅ Teste 3: Alex Vance identificou que Arquitetura Hexagonal é seu próprio domínio!")

def test_competency_jordan_sales_own_domain():
    jordan = agent_delegator.find_agent("jordan")
    assert jordan is not None

    query = "O cliente disse que o preço tá caro no final da call. Como quebrar essa objeção na Linha Reta?"
    decision = agent_delegator.evaluate_competency(jordan, query)

    print(f"\n🔍 Decisão para Jordan sobre Quebra de Objeção: {decision}")
    assert decision.is_competent, "Jordan Belford DEVE ser competente para quebra de objeção em vendas"
    print("✅ Teste 4: Jordan Belford identificou que quebra de objeção é seu próprio domínio!")

def test_full_consultation_hand_off():
    query = "Como criar um teste no Playwright para validar o clique no botão do painel?"
    full_response = agent_delegator.consult("vance", query)

    print("\n" + "=" * 60)
    print("💬 Resposta Completa da Consulta (Vance ➔ Quinn):")
    print(full_response)
    print("=" * 60)

    assert "Alex Vance" in full_response, "Deveria conter a mensagem de passagem do Alex Vance"
    assert "Quinn" in full_response, "Deveria conter a resposta do especialista Quinn QA"
    print("✅ Teste 5: Diálogo completo com Hand-Off e resposta de Quinn QA executado com perfeição!")

def test_helena_executive_delegation_to_qa():
    query = "Helena, qual a estratégia recomendada para testes E2E do nosso login com Playwright?"
    full_response = agent_delegator.consult("helena", query)

    print("\n" + "=" * 60)
    print("👩‍💼 Resposta Executiva de Helena Torres:")
    print(full_response)
    print("=" * 60)

    assert "Helena Torres" in full_response, "Deveria conter a síntese executiva de Helena Torres"
    assert "Quinn" in full_response, "Helena deveria ter acionado a especialista Quinn QA para Playwright"
    print("✅ Teste 6: Helena Torres atuou como executiva não-técnica e acionou Quinn QA!")

def test_autonomous_governor_flow():
    from orchestration.autonomous_governor import autonomous_governor
    import time

    test_act_id = f"test_act_{int(time.time())}"
    action = autonomous_governor.propose_action(
        action_id=test_act_id,
        title="Teste de Otimização de Imagens",
        description="Reduzir tamanho dos assets para acelerar o LCP",
        category="operational",
        delay_minutes=5
    )
    assert action["status"] == "pending"
    assert action["delay_minutes"] == 5

    # Cancelamento
    res_cancel = autonomous_governor.cancel_action(test_act_id, reason="Teste de veto do usuário")
    assert res_cancel["status"] == "success"

    saved = autonomous_governor.get_action(test_act_id)
    assert saved["status"] == "cancelled"
    print("✅ Teste 7: Fluxo do AutonomousGovernor (Proposta e Veto) aprovado com sucesso!")

if __name__ == "__main__":
    test_delegator_finds_agents()
    test_competency_alex_vance_qa_delegation()
    test_competency_alex_vance_own_domain()
    test_competency_jordan_sales_own_domain()
    test_full_consultation_hand_off()
    test_helena_executive_delegation_to_qa()
    test_autonomous_governor_flow()
    print("\n🎉 TODOS OS TESTES DE DELEGAÇÃO, HELENA EXECUTIVA E GOVERNADOR PASSARAM COM SUCESSO!")
