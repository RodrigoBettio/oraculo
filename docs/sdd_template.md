# 📋 Template Universal de SDD (Spec-Driven Development)
> **Padrão Oficial de Engenharia para Projetos com Agentes Autônomos (Antigravity & Oráculo)**

---

## 1. Visão Geral & Objetivo do Negócio
- **Nome do Projeto / Módulo**: `[Nome claro e direto]`
- **Propósito**: `[O que este software resolve em 2 a 3 frases]`
- **Usuário Final**: `[Quem usa? Desenvolvedor, cliente final, outro agente?]`
- **Métrica de Sucesso (DoD - Definition of Done)**: `[Como sabemos que está 100% pronto?]`

---

## 2. Casos de Uso & Requisitos Funcionais (User Stories)
Descreva as ações que o sistema deve suportar no formato:

- **US01**: Como `[usuário/cliente]`, quero `[fazer ação]` para que `[benefício esperado]`.
  - *Critério de Aceite 1*: `[Condição obrigatória]`
  - *Critério de Aceite 2*: `[Condição obrigatória]`
- **US02**: Como `[sistema/agente]`, quero `[fazer ação]` para que `[benefício esperado]`.
  - *Critério de Aceite 1*: `[Condição obrigatória]`

---

## 3. Contratos de Interface & Modelos de Dados (Schemas)
*Defina os tipos de dados e contratos antes de qualquer código ser escrito.*

### 3.1. Entidades de Dados (Entradas e Saídas)
```json
// Exemplo de payload esperado:
{
  "id": "str (uuid)",
  "name": "str (min 3 chars)",
  "status": "enum [pending, active, completed]",
  "created_at": "datetime (ISO 8601)"
}
```

### 3.2. Endpoints / Funções Principais
| Método / Função | Rota ou Assinatura | Entrada | Saída Esperada | Código de Retorno |
|---|---|---|---|---|
| `POST` | `/api/v1/recurso` | `CreateResourceRequest` | `ResourceResponse` | `201 Created` |
| `GET` | `/api/v1/recurso/{id}` | `id: str` | `ResourceResponse` | `200 OK` / `404` |

---

## 4. Requisitos Não-Funcionais & Restrições Técnicas
- **Linguagem & Framework**: `[Ex: Python 3.12+ / FastAPI / TypeScript / Node.js]`
- **Persistência**: `[Ex: SQLite WAL / PostgreSQL / Redis]`
- **Performance / Limites**: `[Ex: Tempo de resposta < 200ms, timeout máximo de 10s]`
- **Segurança**: `[Ex: Validação estrita de tipos com Pydantic, sanitização de inputs contra XSS/SQLi]`
- **Regras Proibidas**: `[Ex: Proibido usar bibliotecas pesadas X ou Y; proibido expor segredos em código]`

---

## 5. Estratégia de TDD (Test-Driven Development)
*Os testes que devem ser escritos ANTES da implementação:*

- **Teste 1 (Caminho Feliz)**: `test_create_resource_success()` -> Deve retornar 201 e dados persistidos.
- **Teste 2 (Validação de Entrada)**: `test_create_resource_invalid_payload()` -> Deve retornar 422 com mensagem amigável.
- **Teste 3 (Caso de Borda / Falha)**: `test_get_resource_not_found()` -> Deve retornar 404 sem derrubar o processo.

---

## 6. Checklist de Aprovação da Spec
Antes de iniciar a escrita de código:
- [ ] O usuário revisou e aprovou a Spec?
- [ ] Os tipos de dados e contratos de API estão 100% claros?
- [ ] A lista de testes unitários necessários foi definida?
