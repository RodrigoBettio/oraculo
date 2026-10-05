---
id: feature_tdd_sdd
name: Engenharia de Software SDD + TDD com Validação no Sandbox
area: tech
manager: gestor_tech_cto
description: "Ciclo rigoroso de desenvolvimento de software: Especificação Técnica (SDD), Testes Unitários e Casos de Borda (TDD) e Implementação validada no Sandbox."
triggers:
  - sdd
  - tdd
  - feature
  - endpoint
  - api
steps:
  - step: 1
    title: Especificação Técnica, Schemas & Contratos de API (SDD)
    agent_id: agent_alex_vance
    role: Arquiteto de Software & IA
    harness_type: oraculo_cloud
    instruction: |
      Defina a especificação completa da funcionalidade seguindo Spec-Driven Development:
      - Contratos de entrada e saída (Pydantic / JSON Schema).
      - Tratamento de exceções e status codes.
      - Diagrama ou fluxo lógico da regra de negócio.
  - step: 2
    title: Suíte de Testes Unitários e Casos de Borda (TDD)
    agent_id: agent_claude_code
    role: Engenheiro de Software
    harness_type: antigravity_ide
    instruction: |
      Com base na especificação do Alex Vance, escreva a suíte de testes rigorosa com Pytest.
      Cubra:
      - Caminho feliz (Happy path).
      - Erros de validação e payloads inválidos.
      - Casos de borda e concorrência.
  - step: 3
    title: Implementação Completa e Execução no Sandbox
    agent_id: agent_alex_vance
    role: Arquiteto de Software & IA
    harness_type: antigravity_ide
    instruction: |
      Implemente o código de produção que faça todos os testes unitários passarem com 100% de sucesso no sandbox.
---

# 💻 Pipeline: Engenharia de Software SDD + TDD

Garante desenvolvimento de código limpo e confiável, onde os testes garantem conformidade antes do deploy.
