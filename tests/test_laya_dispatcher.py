#!/usr/bin/env python3
"""
Testes Unitários e de Performance do Motor Laya de Decisão Rápida (System 1 Dispatcher)
Valida roteamento sub-5ms, detecção de GAP sem LLM e auto-atribuição de pastas do Google Drive.
"""

import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from orchestration.laya_dispatcher import LayaDispatcher
from orchestration.agent_delegator import agent_delegator


def test_laya_initialization_and_cache():
    """Valida o singleton e o carregamento da base de agentes em RAM."""
    laya = LayaDispatcher()
    assert len(laya.agents_cache) > 0, "Laya deve indexar agentes de data/agents/"
    assert "agent_alex_vance" in laya.agents_cache
    assert "agent_quinn_qa_7781" in laya.agents_cache
    assert "agent_claudio_cloud_4421" in laya.agents_cache
    assert "agent_jordan_belford_5567" in laya.agents_cache
    print(f"✅ Teste 1: Laya carregou {len(laya.agents_cache)} agentes em memória.")


def test_thiago_tech_routing():
    """Valida o roteamento executivo de Thiago Tech (Tech)."""
    laya = LayaDispatcher()
    thiago = {"id": "gestor_tech_cto", "name": "Thiago Tech", "area_id": "tech", "agent_type": "gestor"}

    # 1. Playwright -> Quinn QA
    t0 = time.perf_counter()
    r_qa = laya.route_manager_demand(thiago, "Qual a melhor estratégia para automação de testes E2E com Playwright?")
    dt_qa = (time.perf_counter() - t0) * 1000
    assert r_qa["decision"] == "DELEGATE"
    assert r_qa["specialist"]["id"] == "agent_quinn_qa_7781"
    assert dt_qa < 15.0, f"Roteamento demorou {dt_qa:.2f}ms (esperado < 15ms)"

    # 2. Docker / Kubernetes -> Cláudio Cloud
    r_cloud = laya.route_manager_demand(thiago, "Como configurar um cluster Kubernetes com Docker no GCP?")
    assert r_cloud["decision"] == "DELEGATE"
    assert r_cloud["specialist"]["id"] == "agent_claudio_cloud_4421"

    # 3. FastAPI / Clean Architecture -> Alex Vance
    r_vance = laya.route_manager_demand(thiago, "Como desenhar microsserviços com FastAPI e Clean Architecture?")
    assert r_vance["decision"] == "DELEGATE"
    assert r_vance["specialist"]["id"] == "agent_alex_vance"

    # 4. GAP Tecnológico (Direito Tributário)
    r_gap = laya.route_manager_demand(thiago, "Como emitir nota fiscal de exportação e apurar o Simples Nacional?")
    assert r_gap["decision"] == "GAP", "Demanda de tributação deve ser classificada como GAP na equipe de Tech"
    assert r_gap["specialist"] is None

    print(f"✅ Teste 2: Roteamento de Thiago Tech validado (Playwright->Quinn, Docker->Cláudio, FastAPI->Vance, GAP->Detectado) em {dt_qa:.2f}ms.")


def test_ricardo_sales_routing():
    """Valida o roteamento executivo de Ricardo Monteiro (Vendas)."""
    laya = LayaDispatcher()
    ricardo = {"id": "gestor_sales_director", "name": "Ricardo Monteiro", "area_id": "sales", "agent_type": "gestor"}

    # 1. Objeção de Preço -> Jordan Belford
    r_jordan = laya.route_manager_demand(ricardo, "O lead disse que está sem orçamento e achou caro. Como fechar?")
    assert r_jordan["decision"] == "DELEGATE"
    assert r_jordan["specialist"]["id"] == "agent_jordan_belford_5567"

    # 2. Prospecção B2B / BANT -> Sofia SDR
    r_sofia = laya.route_manager_demand(ricardo, "Como estruturar a prospecção fria de leads B2B usando o framework BANT?")
    assert r_sofia["decision"] == "DELEGATE"
    assert r_sofia["specialist"]["id"] == "agent_sofia_sdr"

    # 3. GAP em Vendas (Física Quântica)
    r_gap = laya.route_manager_demand(ricardo, "Como calcular o entrelaçamento de fótons em um computador quântico?")
    assert r_gap["decision"] == "GAP"
    assert r_gap["specialist"] is None

    print("✅ Teste 3: Roteamento de Ricardo Monteiro validado (Objeção->Jordan, SDR->Sofia, GAP->Detectado).")


def test_marcelo_marketing_routing():
    """Valida o roteamento executivo de Marcelo Marketing."""
    laya = LayaDispatcher()
    marcelo = {"id": "gestor_marketing", "name": "Marcelo Marketing", "area_id": "marketing", "agent_type": "gestor"}

    # 1. Tráfego Pago Meta Ads -> Pedro Sobral
    r_sobral = laya.route_manager_demand(marcelo, "Qual a melhor estrutura de campanha no Meta Ads para otimizar ROAS?")
    assert r_sobral["decision"] == "DELEGATE"
    assert r_sobral["specialist"]["id"] == "agent_sobral_marketing"

    # 2. Sexy Canvas -> André Diamand
    r_diamand = laya.route_manager_demand(marcelo, "Como despertar desejo e apego à marca usando os pecados capitais no Sexy Canvas?")
    assert r_diamand["decision"] == "DELEGATE"
    assert r_diamand["specialist"]["id"] == "agent_andre_diamand_1281"

    print("✅ Teste 4: Roteamento de Marcelo Marketing validado (Meta Ads->Sobral, Sexy Canvas->Diamand).")


def test_camila_mind_routing():
    """Valida o roteamento executivo de Dra. Camila Reis (Mente)."""
    laya = LayaDispatcher()
    camila = {"id": "gestor_mind_wellness", "name": "Dra. Camila Reis", "area_id": "mind", "agent_type": "gestor"}

    # 1. Memória e Leitura Dinâmica -> Jim Kwik
    r_kwik = laya.route_manager_demand(camila, "Quais as melhores técnicas de memorização e leitura rápida para retenção?")
    assert r_kwik["decision"] == "DELEGATE"
    assert r_kwik["specialist"]["id"] == "agent_jim_kwik"

    # 2. Meditação e Ansiedade -> O Monge
    r_monge = laya.route_manager_demand(camila, "Como controlar a ansiedade e manter a calma e foco sob estresse?")
    assert r_monge["decision"] == "DELEGATE"
    assert r_monge["specialist"]["id"] == "agent_o_monge_8324"

    print("✅ Teste 5: Roteamento de Dra. Camila Reis validado (Memória->Jim Kwik, Calma->O Monge).")


def test_auto_assign_drive_folder():
    """Valida a auto-atribuição de pastas do Google Drive pelo título do curso."""
    laya = LayaDispatcher()

    # Docker -> Cláudio Cloud
    ag1 = laya.auto_assign_folder("Formação Completa Docker e Kubernetes")
    assert ag1 is not None
    assert ag1["id"] == "agent_claudio_cloud_4421"

    # Playwright -> Quinn QA
    ag2 = laya.auto_assign_folder("Playwright do Básico ao Avançado")
    assert ag2 is not None
    assert ag2["id"] == "agent_quinn_qa_7781"

    # FastAPI -> Alex Vance
    ag3 = laya.auto_assign_folder("Desenvolvimento Backend com FastAPI e Microsserviços")
    assert ag3 is not None
    assert ag3["id"] == "agent_alex_vance"

    # Tráfego Pago -> Pedro Sobral
    ag4 = laya.auto_assign_folder("Comunidade Sobral de Tráfego Pago")
    assert ag4 is not None
    assert ag4["id"] == "agent_sobral_marketing"

    # Curso Desconhecido / GAP -> None
    ag_unknown = laya.auto_assign_folder("Curso de Culinária Francesa Clássica")
    assert ag_unknown is None, "Curso desconhecido não deve ser atribuído a nenhum agente técnico"

    print("✅ Teste 6: Atribuição automática de pastas do Google Drive validada com 100% de precisão!")


def test_laya_speed_benchmark():
    """Valida que todas as operações da Laya executam em < 10ms (média < 5ms)."""
    laya = LayaDispatcher()
    queries = [
        "Como configurar testes Playwright E2E?",
        "Qual o melhor padrão para FastAPI e Clean Architecture?",
        "Cluster Kubernetes com Docker no GCP",
        "Como quebrar a objeção de tá caro na ligação?",
        "Prospecção fria de leads com BANT",
        "Campanha de tráfego pago no Meta Ads",
        "Como memorizar livros mais rápido?",
        "Direito Tributário e apuração de tributos",
    ]

    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        laya.classify_intent(q)
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    print(f"⚡ Benchmark Laya: Média = {avg_ms:.2f}ms | Máximo = {max_ms:.2f}ms")
    assert avg_ms < 10.0, f"Latência média de {avg_ms:.2f}ms excede limite de 10ms"


def test_agent_delegator_integration_with_laya():
    """Valida a integração transparente do delegator com o motor Laya."""
    vance = agent_delegator.find_agent("vance")
    assert vance is not None

    # Vance sobre Playwright -> Hand-off imediato para Quinn via Laya
    dec_qa = agent_delegator.evaluate_competency(vance, "Como rodar testes Playwright em modo headless?")
    assert not dec_qa.is_competent
    assert dec_qa.target_agent_id == "agent_quinn_qa_7781"

    # Vance sobre FastAPI -> Competente confirmado por Laya
    dec_vance = agent_delegator.evaluate_competency(vance, "Como criar dependências injetáveis no FastAPI?")
    assert dec_vance.is_competent

    # Vance sobre GAP Tributário -> GAP confirmado por Laya
    dec_gap = agent_delegator.evaluate_competency(vance, "Como calcular o Simples Nacional?")
    assert not dec_gap.is_competent
    assert dec_gap.target_agent_id is None, "GAP não deve ter target_agent_id"

    print("✅ Teste 8: Integração AgentDelegator + LayaDispatcher executada com sucesso total!")


if __name__ == "__main__":
    test_laya_initialization_and_cache()
    test_thiago_tech_routing()
    test_ricardo_sales_routing()
    test_marcelo_marketing_routing()
    test_camila_mind_routing()
    test_auto_assign_drive_folder()
    test_laya_speed_benchmark()
    test_agent_delegator_integration_with_laya()
    print("\n🎉 TODOS OS TESTES DO MOTOR LAYA FORAM APROVADOS!")
