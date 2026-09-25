# 📜 Diretrizes Determinísticas de Engenharia para Agentes (AGENTS.md)
> **Regras Obrigatórias para qualquer Agente de IA atuando neste Workspace (Antigravity & Claude Code)**

---

## 1. O Protocolo Não-Negociável: SDD + TDD

Todo e qualquer desenvolvimento de software ou criação de novo módulo neste repositório DEVE seguir rigorosamente o ciclo de 3 etapas:

```
[Etapa 1: SDD]               [Etapa 2: TDD]                [Etapa 3: Execução & Validação]
Criar/Revisar a Spec   --->   Escrever Testes Unitários --->  Implementar Código até
(docs/spec.md)               (tests/test_*.py)             100% dos testes passarem (Green)
```

### Regra 1: "Spec First" (SDD)
- **NUNCA** escreva código de produção diretamente a partir de um prompt vago.
- Se o projeto ou feature for nova, valide os requisitos, contratos de API e modelos de dados primeiro no padrão de especificação (`docs/sdd_template.md` ou `docs/spec.md`).
- A spec é o contrato de verdade.

### Regra 2: "Test First" (TDD)
- Toda funcionalidade deve ter sua suíte de testes unitários criada antes ou em conjunto com a implementação.
- Os testes devem cobrir no mínimo:
  1. **Caminho Feliz**: O comportamento esperado com dados válidos.
  2. **Validação de Entrada**: Tratamento gracioso de payloads malformados ou inválidos (sem quebrar o processo).
  3. **Casos de Borda**: Valores vazios, nulos, limites numéricos ou exceções esperadas.

### Regra 3: Validação Obrigatória no Sandbox
- Todo código Python deve passar por `py_compile` (zero erros de sintaxe) e rodar os testes unitários via `unittest` ou `pytest`.
- Se um teste falhar, o agente deve analisar o traceback e corrigir o código (Loop ReAct) antes de declarar a tarefa como concluída.

---

## 2. Padrão "Docs as Code"
- Ao concluir uma feature, alteração arquitetural ou decisão relevante, o agente deve atualizar os arquivos na pasta `/docs/` (`docs/architecture.md`, `docs/decisions.md` ou `docs/roadmap.md`).
- Isso preserva a memória do sistema entre conversas e evita a perda de contexto da IA.

---

## 3. Segurança & Proteção de Credenciais
- É terminantemente **PROIBIDO** sobrescrever, ler ou expor arquivos de segredos (`.env`, `credentials/*.json`, tokens de API).
- Chaves devem ser lidas exclusivamente via variáveis de ambiente através do `config.settings`.
