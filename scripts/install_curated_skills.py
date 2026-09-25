#!/usr/bin/env python3
"""
Oráculo Curated Skills Suite
Gera e instala as skills de padrão internacional aprovadas pelo usuário para o Antigravity e Oráculo:
1. QA & Testes (Quinn - QA)
2. Cloud, DevOps & SRE (Claudio - Cloud)
3. Arquitetura & Clean Code (Alex Vance - Arquiteto)
4. Segurança & OWASP (Helena Torres & Alex Vance)
5. Web Vitals & Performance (Alex Vance & Bruno)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("curated_skills")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_SKILLS_DIR = BASE_DIR / "data" / "skills"
GLOBAL_SKILLS_DIR = Path.home() / ".gemini" / "config" / "skills"
AGENTS_DIR = BASE_DIR / "data" / "agents"

CURATED_SKILLS = [
    # ----------------- CLUSTER 1: QA & TESTES -----------------
    {
        "id": "community-qa-playwright-e2e",
        "name": "Playwright E2E Testing Mastery",
        "assigned_agents": ["quinn", "alex_vance"],
        "description": "Automação de testes End-to-End (E2E) com Playwright. Use ao criar testes de interface, validação de fluxos críticos de usuário, emulação mobile, mock de APIs, captura de traces e testes visuais de regressão.",
        "content": """---
name: community-qa-playwright-e2e
description: Automação de testes End-to-End (E2E) com Playwright. Use ao criar testes de interface, validação de fluxos críticos de usuário, emulação mobile, mock de APIs, captura de traces e testes visuais de regressão.
---

# Playwright E2E Testing Mastery

## 1. Filosofia de Testes Resilientes
- **Aguarde Estados, Nunca Tempos Fixos**: Jamais use `time.sleep()` ou `page.wait_for_timeout()`. Confie nos auto-waits do Playwright (`page.wait_for_selector`, `expect(locator).to_be_visible()`).
- **Seletores Voltados ao Usuário**: Priorize `getByRole()`, `getByText()`, `getByLabel()` e `getByPlaceholder()`. Evite seletores frágeis por classes CSS geradas ou XPaths profundos.
- **Isolamento Total**: Cada teste deve rodar em um BrowserContext limpo e independente.

## 2. Padrão Page Object Model (POM)
Estruture os testes separando a lógica de tela dos cenários de teste:
```python
class StudyRoomPage:
    def __init__(self, page):
        self.page = page
        self.btn_study_tab = page.get_by_role("button", name="Sala de Estudos")
        self.card_queue = page.locator("#queue-status-card")
        self.progress_bar = page.locator(".progress-bar-fill")

    async def navigate(self):
        await self.page.goto("/#study")
        await self.btn_study_tab.click()

    async def get_progress_value(self):
        await self.progress_bar.wait_for(state="visible")
        return await self.progress_bar.get_attribute("data-progress")
```

## 3. Interceptação de Rede e Mocking de APIs
```python
async def test_offline_fallback(page):
    await page.route("**/api/study/queue", lambda route: route.fulfill(
        status=503,
        content_type="application/json",
        body='{"error": "Queue service temporarily busy"}'
    ))
    await page.goto("/")
    await expect(page.get_by_text("Queue service temporarily busy")).to_be_visible()
```

## 4. Gravação de Traces e Diagnóstico
Em caso de falha no CI/CD:
- Salve o arquivo de trace `.zip` executando `context.tracing.stop(path="trace.zip")`.
- Inspecione com `npx playwright show-trace trace.zip` com timeline milissegundo a milissegundo.
"""
    },
    {
        "id": "community-qa-test-driven-development",
        "name": "Test-Driven Development (TDD) Protocol",
        "assigned_agents": ["quinn", "alex_vance", "bruno"],
        "description": "Protocolo rigoroso de TDD (Red-Green-Refactor). Use ao iniciar qualquer nova feature ou bugfix para escrever os testes primeiro, isolar dependências com fixtures/mocks e garantir 100% de confiabilidade determinística.",
        "content": """---
name: community-qa-test-driven-development
description: Protocolo rigoroso de TDD (Red-Green-Refactor). Use ao iniciar qualquer nova feature ou bugfix para escrever os testes primeiro, isolar dependências com fixtures/mocks e garantir 100% de confiabilidade determinística.
---

# Test-Driven Development (TDD) Protocol

## 1. O Ciclo Sagrado Red-Green-Refactor
1. **RED**: Escreva um teste que expresse o comportamento desejado antes de escrever qualquer linha de código de produção. Execute o teste e confirme que ele falha pelo motivo correto.
2. **GREEN**: Escreva a menor quantidade possível de código necessária para fazer o teste passar. Sem otimizações prematuras.
3. **REFACTOR**: Limpe o código, elimine duplicações, melhore nomes e respeite os princípios SOLID mantendo a suíte de testes 100% verde.

## 2. Anatomia de um Teste AAA (Arrange-Act-Assert)
```python
import pytest
from orchestration.manager_sync import analyze_manager_skill_gaps

def test_manager_skill_gaps_identifies_missing_qa_and_cloud(tmp_path):
    # Arrange: Preparar o estado e isolar dependências
    mock_area = "gestor_tech_cto"
    
    # Act: Executar a operação
    result = analyze_manager_skill_gaps(mock_area, save_to_disk=False)
    
    # Assert: Verificar contratos estritos
    assert result["area_id"] == "tech"
    gap_ids = [g["id"] for g in result.get("detected_gaps", [])]
    assert "qa_engineer" in gap_ids
    assert "cloud_sre" in gap_ids
    assert result["readiness_score"] < 100.0
```

## 3. Regras de Ouro
- Nunca confie em um teste que você não viu falhar primeiro.
- Teste comportamentos e contratos de saída, nunca detalhes de implementação privada.
- Mocks devem ser usados apenas nos limites do sistema (I/O, APIs externas, banco de dados, relógio do sistema).
"""
    },

    # ----------------- CLUSTER 2: CLOUD & DEVOPS -----------------
    {
        "id": "community-cloud-docker-hardening",
        "name": "Docker Container Hardening (CIS Standards)",
        "assigned_agents": ["claudio", "alex_vance"],
        "description": "Padrões de segurança e otimização para contêineres Docker. Use ao criar ou editar Dockerfiles, compose e deploys para garantir builds leves, execução non-root, healthchecks e proteção de credenciais.",
        "content": """---
name: community-cloud-docker-hardening
description: Padrões de segurança e otimização para contêineres Docker. Use ao criar ou editar Dockerfiles, compose e deploys para garantir builds leves, execução non-root, healthchecks e proteção de credenciais.
---

# Docker Container Hardening (CIS Standards)

## 1. Princípios de Segurança em Contêineres
- **Non-Root por Padrão**: Crie um usuário dedicado com UID fixo (ex: 1001) e utilize a diretiva `USER appuser`. Nunca execute processos web como `root`.
- **Multi-Stage Builds**: Separe o ambiente de compilação (compiladores, headers de C, git) da imagem final de runtime (somente binários e dependências).
- **Sem Segredos em Camadas**: Jamais passe senhas ou tokens via `ENV` ou `ARG`. Utilize segredos montados em tempo de execução via volumes ou Secret Manager.
- **Filesystem Read-Only**: Sempre que possível, execute contêineres com `--read-only` montando volumes efêmeros `tmpfs` apenas em `/tmp` e pastas de dados designadas.

## 2. Exemplo de Dockerfile Python Blindado
```dockerfile
# Estágio 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Estágio 2: Runtime Seguro
FROM python:3.11-slim AS runtime
WORKDIR /app
RUN groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup -s /bin/bash -m appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appgroup . /app
ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD curl -f http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```
"""
    },
    {
        "id": "community-cloud-gcp-sre",
        "name": "Google Cloud Platform (GCP) SRE & Infra",
        "assigned_agents": ["claudio", "helena", "alex_vance"],
        "description": "Engenharia de Confiabilidade de Sites (SRE) na Google Cloud. Use para gerenciar instâncias Compute Engine, redes VPC, Secret Manager, Cloud Storage e resiliência de serviços em nuvem.",
        "content": """---
name: community-cloud-gcp-sre
description: Engenharia de Confiabilidade de Sites (SRE) na Google Cloud. Use para gerenciar instâncias Compute Engine, redes VPC, Secret Manager, Cloud Storage e resiliência de serviços em nuvem.
---

# Google Cloud Platform (GCP) SRE & Infrastructure

## 1. Princípios de SRE para o Oráculo na Nuvem
- **SLO & Error Budget**: Disponibilidade do motor de estudo e APIs em 99.5% de uptime.
- **Failover Gracioso**: Se uma API externa (Telegram MTProto, Google Drive API, Gemini) cair ou retornar 503, o sistema deve entrar em estado degradado com retries exponenciais, sem derrubar o processo principal.
- **Gerenciamento de Segredos**: Nenhuma chave em arquivos `.env` commitados. Use o Google Secret Manager ou arquivos com permissão `chmod 600` em volumes restritos.

## 2. Hardening de Instância Compute Engine
- SSH baseado em chaves criptográficas Ed25519 exclusively (`authorized_keys` com permissão 600).
- Desativação de login por senha (`PasswordAuthentication no`).
- Regras de firewall no Cloud Console liberando estritamente portas 80/443 para o Nginx e 22 para SSH.
- Logs estruturados em formato JSON para agregação automática.
"""
    },

    # ----------------- CLUSTER 3: ARQUITETURA & CLEAN CODE -----------------
    {
        "id": "community-arch-clean-architecture",
        "name": "Clean Architecture & Domain-Driven Design",
        "assigned_agents": ["alex_vance", "helena"],
        "description": "Padrões de Clean Architecture de Uncle Bob e Domain-Driven Design (DDD). Use para organizar o código em camadas concêntricas (Entidades, Casos de Uso, Portas e Adaptadores), eliminando acoplamentos nocivos.",
        "content": """---
name: community-arch-clean-architecture
description: Padrões de Clean Architecture de Uncle Bob e Domain-Driven Design (DDD). Use para organizar o código em camadas concêntricas (Entidades, Casos de Uso, Portas e Adaptadores), eliminando acoplamentos nocivos.
---

# Clean Architecture & Domain-Driven Design (DDD)

## 1. A Regra de Dependência
As dependências do código fonte só podem apontar **para dentro**, em direção às políticas de alto nível (Domínio e Casos de Uso).
- **Entidades de Domínio**: Não conhecem banco de dados, nem FastAPI, nem Telegram.
- **Casos de Uso**: Orquestram o fluxo de dados entre entidades, sem depender de detalhes de entrega HTTP ou SQL.
- **Adaptadores / Gateways**: Implementam as interfaces (Portas) definidas pelos Casos de Uso.
- **Frameworks e Drivers**: A camada mais externa (FastAPI, SQLite, Telethon, Docker) — facilmente substituíveis.

## 2. Separação Prática de Camadas
```
oraculo/
├── domain/            # Entidades puras e regras de negócio invariantes
│   └── agent.py       # Ex: Regras de cálculo de XP, senioridade e patentes
├── use_cases/         # Casos de uso da aplicação
│   ├── study_lesson.py
│   └── route_chat_message.py
├── adapters/          # Implementações concretas de portas
│   ├── drive_repository.py
│   └── telegram_gateway.py
└── entrypoints/       # Pontos de entrada externos
    ├── web_api.py     # FastAPI endpoints
    └── telegram_bot.py
```
"""
    },
    {
        "id": "community-arch-system-design-microservices",
        "name": "System Design & Distributed Scalability",
        "assigned_agents": ["alex_vance"],
        "description": "Padrões de escalabilidade distribuída, filas concorrentes assíncronas, idempotência e resiliência sob alta carga. Use ao projetar filas, workers paralelos e particionamento de estado.",
        "content": """---
name: community-arch-system-design-microservices
description: Padrões de escalabilidade distribuída, filas concorrentes assíncronas, idempotência e resiliência sob alta carga. Use ao projetar filas, workers paralelos e particionamento de estado.
---

# System Design & Distributed Scalability

## 1. Padrões Fundamentais
- **Filas Concorrentes & Semáforos Assimétricos**:
  Separe a vazão de download da vazão de processamento analítico para evitar gargalos de I/O bloqueando a CPU.
- **Garantia de Idempotência**:
  Toda operação de processamento de aula ou mensagem deve ser idempotente: reprocessar a mesma mensagem com o mesmo `hash` não duplica registros nem gera efeitos colaterais.
- **Circuit Breaker Pattern**:
  Ao detectar falhas consecutivas em chamadas externas (ex: Gemini 429 Resource Exhausted), abra o circuito imediatamente e ative fila de espera com backoff exponencial com jitter.

## 2. Concorrência Segura em SQLite (WAL Mode)
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA busy_timeout=5000;
```
O modo WAL permite múltiplos leitores simultâneos enquanto um único escritor atualiza o banco de dados sem bloqueios de leitura.
"""
    },
    {
        "id": "community-arch-fastapi-mastery",
        "name": "FastAPI & Async Python High-Throughput",
        "assigned_agents": ["alex_vance", "bruno"],
        "description": "Engenharia avançada de APIs com FastAPI e Python assíncrono. Use para desenhar rotas ultra-rápidas, injeção de dependências eficiente, Pydantic v2 schemas e streaming de respostas.",
        "content": """---
name: community-arch-fastapi-mastery
description: Engenharia avançada de APIs com FastAPI e Python assíncrono. Use para desenhar rotas ultra-rápidas, injeção de dependências eficiente, Pydantic v2 schemas e streaming de respostas.
---

# FastAPI & Async Python High-Throughput

## 1. Princípios de Performance
- **Nunca Bloqueie o Event Loop**: Operações síncronas de I/O (leitura de disco ou chamadas de rede sem `await`) devem ser despachadas via `asyncio.to_thread()` ou executadas em `BackgroundTasks`.
- **Injeção de Dependências**: Use `Depends()` para resolver conexões de banco, autenticação e serviços de forma limpa e testável.
- **Pydantic v2 com Serialização Nativa**: Use `model_dump(mode='json')` e evite construções manuais de dicionários dentro de loops intensivos.

## 2. Streaming de Respostas & SSE
Para respostas longas de IA ou relatórios em tempo real:
```python
from fastapi.responses import StreamingResponse

async def stream_agent_deliberation(prompt: str):
    async for chunk in generate_gemini_stream(prompt):
        yield f"data: {json.dumps({'chunk': chunk})}\\n\\n"

@app.get("/api/chat/stream")
async def chat_stream(q: str):
    return StreamingResponse(stream_agent_deliberation(q), media_type="text/event-stream")
```
"""
    },

    # ----------------- CLUSTER 4: SEGURANÇA & OWASP -----------------
    {
        "id": "community-sec-owasp-top-10",
        "name": "OWASP Top 10 Security & API Hardening",
        "assigned_agents": ["alex_vance", "helena"],
        "description": "Prevenção contra vulnerabilidades do OWASP Top 10. Use para auditar e blindar endpoints contra injeções, quebra de autorização (BOLA/IDOR), CSRF, SSRF e vazamento de segredos.",
        "content": """---
name: community-sec-owasp-top-10
description: Prevenção contra vulnerabilidades do OWASP Top 10. Use para auditar e blindar endpoints contra injeções, quebra de autorização (BOLA/IDOR), CSRF, SSRF e vazamento de segredos.
---

# OWASP Top 10 Security & API Hardening

## 1. As 5 Vulnerabilidades Críticas em Agentes & APIs
1. **Broken Object Level Authorization (BOLA/IDOR)**:
   Nunca confie cegamente no `agent_id` ou `user_id` enviado no corpo da requisição. Valide se a sessão autenticada possui permissão sobre o recurso alvo.
2. **Server-Side Request Forgery (SSRF)**:
   Ao receber URLs externas para download ou análise (ex: links de Drive ou webhooks), valide estritamente o hostname contra ranges privados de IP (ex: `127.0.0.1`, `10.0.0.0/8`, `169.254.169.254` de metadados da nuvem).
3. **Prompt Injection & Sanitização Multimodal**:
   Separe o prompt de sistema do conteúdo não-confiável do usuário usando delimitadores estritos (XML tags ou JSON estruturado) e bloqueie tentativas de bypass de instruções.
4. **Vazamento de Segredos em Logs**:
   Sanitize headers de autorização e chaves de API antes de gravar em arquivos de log.
5. **CORS Restrito**:
   Em produção, nunca utilize `allow_origins=["*"]` com `allow_credentials=True`. Declare os domínios confiáveis explicitamente.
"""
    },

    # ----------------- CLUSTER 5: FRONTEND & WEB VITALS -----------------
    {
        "id": "community-perf-web-vitals",
        "name": "Core Web Vitals & Frontend Performance",
        "assigned_agents": ["alex_vance", "bruno"],
        "description": "Otimização de Core Web Vitals (LCP, INP, CLS) para carregamento instantâneo e experiência fluida a 60fps. Use ao construir ou refatorar interfaces web e dashboards.",
        "content": """---
name: community-perf-web-vitals
description: Otimização de Core Web Vitals (LCP, INP, CLS) para carregamento instantâneo e experiência fluida a 60fps. Use ao construir ou refatorar interfaces web e dashboards.
---

# Core Web Vitals & Frontend Performance

## 1. As Três Métricas Essenciais do Google
- **LCP (Largest Contentful Paint) < 1.2s**:
  O maior elemento visual (geralmente o card principal ou cabeçalho) deve renderizar quase imediatamente. Precarregue fontes críticas com `<link rel="preload">`.
- **INP (Interaction to Next Paint) < 200ms**:
  Toda interação de clique deve gerar feedback visual no frame seguinte (16ms). Nunca processe arrays pesados na thread principal durante o handler de clique; use `requestAnimationFrame` ou `setTimeout(0)`.
- **CLS (Cumulative Layout Shift) < 0.1**:
  Elementos nunca devem empurrar outros elementos na tela ao carregar. Reserve espaço com `aspect-ratio` ou `min-height` para imagens, cards dinâmicos e skeleton loaders.

## 2. Boas Práticas no Oráculo Web
- Use `fetch` com cancelamento via `AbortController` quando o usuário trocar de aba rapidamente.
- Utilize virtualização de listas em tabelas com mais de 50 itens para poupar nós do DOM.
- Defina dimensões explícitas em ícones Lucide e imagens SVG.
"""
    }
]

def install_all_curated_skills():
    """Instala todas as skills curadas no Antigravity e na pasta data/skills."""
    print("=" * 65)
    print("🔮 ORÁCULO - INSTALAÇÃO DO PACOTE DE SKILLS CURADAS (ANTIGRAVITY)")
    print("=" * 65)

    installed_skills = []

    for sk in CURATED_SKILLS:
        skill_id = sk["id"]
        content = sk["content"].strip() + "\n"

        # 1. Instala no Antigravity Local (~/.gemini/config/skills/<skill_id>/SKILL.md)
        global_target_dir = GLOBAL_SKILLS_DIR / skill_id
        global_target_dir.mkdir(parents=True, exist_ok=True)
        with open(global_target_dir / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(content)

        # 2. Instala no diretório da VM (data/skills/<skill_id>/SKILL.md)
        data_target_dir = DATA_SKILLS_DIR / skill_id
        data_target_dir.mkdir(parents=True, exist_ok=True)
        with open(data_target_dir / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"✅ Skill '{skill_id}' gerada e instalada com sucesso!")
        installed_skills.append(sk)

        # 3. Vincula aos agentes atribuídos
        for agent_target in sk.get("assigned_agents", []):
            for agent_file in AGENTS_DIR.glob("*.json"):
                if agent_target.lower() in agent_file.stem.lower():
                    try:
                        with open(agent_file, "r", encoding="utf-8") as af:
                            profile = json.load(af)
                        
                        ext_skills = profile.setdefault("external_skills", [])
                        if not any(e.get("id") == skill_id for e in ext_skills if isinstance(e, dict)):
                            ext_skills.append({
                                "id": skill_id,
                                "name": sk["name"],
                                "description": sk["description"],
                                "source": "curated_suite"
                            })
                            with open(agent_file, "w", encoding="utf-8") as af:
                                json.dump(profile, af, indent=2, ensure_ascii=False)
                            logger.info(f"   🔗 Vinculada ao agente: {profile.get('name', agent_file.stem)}")
                    except Exception as e:
                        logger.error(f"Erro ao vincular ao agente {agent_file.name}: {e}")

    print("\n" + "=" * 65)
    print(f"🎉 Instalação concluída! {len(installed_skills)} novas skills ativas no Antigravity:")
    for sk in installed_skills:
        print(f"  • {sk['id']}: {sk['name']}")
    print("=" * 65)

if __name__ == "__main__":
    install_all_curated_skills()
