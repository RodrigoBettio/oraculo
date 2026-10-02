# 📋 Oráculo System Specification (docs/spec.md)
> **Versão Oficial**: 2.1.0 — Outubro/2026  
> **Liderança Executiva**: Thiago Tech (💻 VP de TI & Inovação), Marcelo Marketing (🚀 CMO & Growth), Victor Vendas (💼 Dir. Comercial), Marina Mente (🧠 Head Wellness)  
> **Padrão de Engenharia**: SDD (Spec-Driven Development) + TDD (Test-Driven Development) + Clean Architecture

---

## 1. Visão do Produto & Arquitetura Geral

O **Oráculo** é uma plataforma distribuída de inteligência artificial autônoma estruturada em dois hemisférios complementares:

1. **Fábrica de Conhecimento Multimodal 24/7 (Nuvem - GCP / Oracle Cloud VM)**:
   - Ingestão contínua em alta vazão de cursos em vídeo (Google Drive e canais do Telegram).
   - Extração multimodal de áudio, transcrição profunda via Gemini API e OCR de frames de código em tela via FFmpeg.
   - Compilação contínua de Rich Skills (`SKILL.md`) e perfis de agente (`agent.md`) com citações de aulas, minutos, regras e snippets.
   - Banco de dados de altíssima performance em SQLite (modo WAL).
2. **Quartel-General de Execução e Interação (Local - Antigravity IDE / Desktop)**:
   - Hub de interação direta do fundador (Rodrigo Bettio Jr.) com os gestores executivos e especialistas técnicos.
   - Geração de software, estratégias de negócios, marketing de performance, vendas e performance cognitiva.
   - Sincronização contínua de conhecimento (Zero-Touch Sync).
3. **Controle e Telemetria Mobile (Celular - Telegram Bot Oficial)**:
   - Notificações push em tempo real (conclusão de cursos, relatórios matinais, telemetria).
   - Cockpit de comando interativo via Bot dedicado (`/status`, `/relatorio`, `/gaps`, `/drive`, `/estudar`).

---

## 2. Topologia de Infraestrutura

| Componente | Ambiente | Tecnologia | Função |
| :--- | :--- | :--- | :--- |
| **VM Backend** | Google Cloud / Oracle Cloud | Docker, FastAPI, Uvicorn, SQLite WAL | Motor de Ingestão e APIs REST |
| **Web Proxy** | Cloud Host | Nginx Alpine (Porta 80/443) | Reverse Proxy, SSL e Roteamento |
| **Fila de Estudos** | Cloud Container | `ingestion/study_queue.py` | 20 Workers paralelos (Dual-Engine Drive/Telegram) |
| **Processador de Vídeo**| Cloud Container | `ingestion/video_processor.py` | FFmpeg OCR resiliente + Gemini API |
| **Telegram Bot** | Cloud Daemon | `ingestion/telegram_notifier.py` | Mobile Cockpit via Bot Client (@bot_client) |
| **Brain Bot (Obsidian)**| Cloud Daemon | `ingestion/brain_bot.py` | Ingestão e sincronização do Segundo Cérebro |
| **MCP Server** | Cloud / Local | `/mcp/sse` (Starlette SSE Transport) | Protocolo MCP para IDEs (Antigravity, Cursor) |
| **Skills Antigravity** | Local (PC) | `~/.gemini/config/skills/` | Conhecimento operacional dos agentes especialistas |

---

## 3. Matriz do Conselho Executivo (Governança Obrigatória)

Nenhuma decisão estrutural deve ser tomada sem a consulta prévia ao gestor executivo e seus respectivos especialistas:

```
                          ┌─────────────────────────────────────┐
                          │    Rodrigo Bettio Jr. (Fundador)    │
                          └──────────────────┬──────────────────┘
                                             │
      ┌──────────────────────┬───────────────┴───────────────┬──────────────────────┐
      ▼                      ▼                               ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ 💻 Thiago Tech   │   │ 🚀 Marcelo Mkt   │   │ 💼 Victor Vendas │   │ 🧠 Marina Mente  │
│ VP de TI & Eng.  │   │ CMO & Growth     │   │ Diretor Comercial│   │ Head Wellness    │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │                      │
   • Alex Vance           • Pedro Sobral         • Jordan Belford       • Jim Kwik
     (Arquitetura/IA)       (Tráfego/Ads)          (Closer/Linha Reta)    (Supermemória)
   • Bruno                • André Diamand        • Sofia SDR            • O Monge
     (Codex/Automação)      (Sexy Canvas)          (Prospecção B2B)       (Espiritualidade)
   • Thales               • Ana                  • Caio Copywriter      • Link
     (N8N/Workflows)        (Conteúdo/Social)      (Copywriting/Vídeo)    (LinkedIn)
   • Quinn QA                                    • Felipe Follow-up
     (SDET/TDD)                                    (RevOps/Cadência)
   • Cláudio Cloud
     (DevOps/SRE)
```

---

## 4. Requisitos Funcionais (RFs)

### RF01: Ingestão Dual-Engine de Cursos (Google Drive & Telegram)
- **Descrição**: O sistema deve ingerir arquivos de vídeo a partir de pastas compartilhadas do Google Drive e canais/grupos do Telegram.
- **Critérios de Aceite**:
  - Suporte a múltiplos tiers (`full_ocr`, `audio_fast`, `transcription_only`).
  - Fila persistida em SQLite WAL através de `ingestion/study_queue.py`.
  - Retomada transparente de downloads interrompidos sem perda de progresso.

### RF02: Processamento Multimodal e Extração de Aulas
- **Descrição**: O processador de vídeo deve transcrever áudios via Gemini API e realizar OCR automatizado em frames de código com FFmpeg.
- **Critérios de Aceite**:
  - Geração de artefatos estruturados em JSON contendo resumo da aula, tópicos dominados, minutos exatos e snippets de código capturados em tela.
  - Taxa de sucesso em arquivos longos (> 1 hora) com divisão de chunks sem estouro de memória.

### RF03: Compilação Automatizada de Rich Skills
- **Descrição**: O sistema deve sintetizar o conhecimento absorvido em arquivos `SKILL.md` modulares por especialista e `AGENT.md` formais.
- **Critérios de Aceite**:
  - Registro de horas de estudo reais absorvidas e contagem de vídeos indexados.
  - Atualização dos metadados de senioridade (Estagiário -> Júnior -> Pleno -> Sênior -> Especialista).

### RF04: Interação Mobile Exclusiva via Bot Telegram
- **Descrição**: O canal de interação mobile do Oráculo deve operar estritamente através da sessão oficial do Bot (`bot_client`).
- **Critérios de Aceite**:
  - A sessão pessoal MTProto (`user_client`) não deve ter listeners de novas mensagens ativos, garantindo que o Oráculo **nunca** responda em conversas privadas pessoais, grupos não autorizados ou Mensagens Salvas.
  - No privado do Bot, suporte a comandos rápidos, botões tácteis e diálogos diretos com o ecossistema.
  - Em grupos autorizados (Mesa Redonda), o Bot deve responder **apenas** quando expressamente acionado via comando (`/...`), menção explícita (`@...`) ou em tópicos vinculados (`/vincular_topico`). Conversas normais de terceiros devem ser sumariamente ignoradas.

### RF05: Roteamento Inteligente de Perguntas (@agente)
- **Descrição**: No grupo QG ou no privado do bot, menções a agentes (ex: `@vance`, `@jordan`, `@sobral`, `@quinn`) devem ser roteadas diretamente para o especialista correspondente.
- **Critérios de Aceite**:
  - Preservação da persona, diretrizes operacionais e base de cursos estudados de cada especialista.
  - Respostas em markdown limpo com identificação visual clara do especialista (avatar + nome + cargo).

### RF06: Protocolo de Não-Execução de Gestores
- **Descrição**: Gestores executivos (Tiago Tech, Marcelo Marketing, Victor Vendas, Marina Mente) nunca devem executar código, programar ou redigir criativos diretamente.
- **Critérios de Aceite**:
  - Quando acionado com uma demanda técnica, o gestor avalia a solicitação, consulta seu especialista subordinado e devolve um parecer executivo consolidado com foco em negócio, prazos e riscos.
  - Se nenhum especialista possuir a competência demandada, o gestor emite um diagnóstico de Skill GAP.

### RF07: Diagnóstico de Skill GAPs em Tempo Real
- **Descrição**: A identificação de lacunas de conhecimento (Skill GAPs) pelos gestores deve ser computada dinamicamente em tempo real, avaliando o quadro ativo de especialistas.
- **Critérios de Aceite**:
  - GAPs supridos por especialistas já ativos no sistema (ex: Cláudio em Cloud/DevOps, Quinn em QA/TDD, Thales em N8N, Sobral em Tráfego) **não** devem ser exibidos como carências abertas.
  - Caches estáticos em disco não devem sobrepor o quadro real de especialistas contratados.
  - Acesso via `/gaps` (visão consolidada de todas as 4 áreas) e `/gaps <area>` (memorando detalhado).

### RF08: Relatório Executivo Diário Matinal
- **Descrição**: O sistema deve compilar diariamente às 08:00 BRT (e sob demanda via `/relatorio`) um relatório executivo consolidando todas as 4 áreas.
- **Critérios de Aceite**:
  - Métricas de aulas absorvidas e horas de estudo por área.
  - Lista de especialistas em linhas separadas com badges de horas reais.
  - Seção dedicada de GAPs de conhecimento atualizada em tempo real.
  - Status do backlog de tarefas do dia.

### RF09: Navegação Visual e Atribuição de Cursos do Google Drive
- **Descrição**: O bot do Telegram deve permitir navegar pelas pastas do Google Drive através de inline keyboards (`/drive`).
- **Critérios de Aceite**:
  - Visualização de subpastas, contagem de aulas pendentes e breadcrumbs de navegação.
  - Botão "Estudar aulas" para enfileirar em lote com 1 clique.
  - Botão "Atribuir a Agente" restringindo a seleção exclusivamente a especialistas técnicos.

### RF10: CRUD Completo de Áreas da Vida no Cockpit Web e API REST
- **Descrição**: O painel web e os endpoints `/api/areas` devem oferecer gerenciamento completo (Create, Read, Update, Delete) das Áreas da Vida.
- **Critérios de Aceite**:
  - Botão visível "+ Nova Área" no cabeçalho do Radar Orbital.
  - Botões rápidos de edição e exclusão nos cards de cada área.
  - Validação estrita impedindo arquivos não-área (como relatórios de gaps) de serem interpretados como domínios órfãos.

### RF11: Radar Orbital e Constelação de Conhecimento
- **Descrição**: O cockpit web deve apresentar visualização em Radar Orbital (Canvas 2D) e Grafo Interativo (Constelação de Estudos estilo Obsidian).
- **Critérios de Aceite**:
  - Exibição balanceada dos 4 domínios (Tech, Marketing, Vendas, Mente) com suas cores e pontuações de vitalidade.
  - Carregamento instantâneo sem travamentos, limitando a nós essenciais e habilidades principais.

### RF12: Exposição como MCP Server (Model Context Protocol)
- **Descrição**: O Oráculo deve expor seu acervo e ferramentas através de endpoint SSE `/mcp/sse`.
- **Critérios de Aceite**:
  - Compatibilidade com Antigravity IDE, Cursor e Claude Code.
  - Disponibilização de ferramentas de consulta a agentes, base de cursos e busca semântica.

### RF13: Segundo Cérebro & Ingestão com Obsidian
- **Descrição**: O bot secundário (`ingestion/brain_bot.py`) deve capturar notas de áudio, textos e links enviados pelo operador e organizá-los no cofre do Obsidian.
- **Critérios de Aceite**:
  - Transcrição automática de áudios via Gemini.
  - Criação de notas diárias (`Daily Notes`) estruturadas com tags automáticas.

### RF14: Provisionamento Dinâmico de Novos Especialistas
- **Descrição**: O operador pode contratar novos especialistas sob demanda via `/contratar <cargo>` ou via interface web.
- **Critérios de Aceite**:
  - Geração automática do perfil `.json` em `data/agents/`.
  - Vinculação à área da vida correspondente e notificação ao gestor da pasta.
  - Inicialização de diretório de skill em `data/skills/<agent_id>/`.

### RF15: Sandboxing & Validação TDD
- **Descrição**: Tarefas que envolvam geração de código devem ser executadas em ambiente isolado (`orchestration/sandbox.py`) com suíte de testes unitários.
- **Critérios de Aceite**:
  - 100% dos testes devem passar antes da promoção de código para produção.
  - Timeout rígido de execução e isolamento de processos.

### RF16: Governança Dedicada de Marketing & Growth
- **Descrição**: O departamento de Marketing & Growth deve operar como área autônoma sob a gestão de Marcelo Marketing.
- **Critérios de Aceite**:
  - Gestão de Pedro Sobral (tráfego e mídia de performance), André Diamand (Sexy Canvas e desejo) e Ana (conteúdo e redes sociais).
  - Alinhamento estratégico contínuo com a área comercial de Victor Vendas.

---

## 5. Requisitos Não-Funcionais (RNFs)

- **RNF01 (Performance de Dados)**: Banco de dados SQLite local operando estritamente em modo WAL com tempos de resposta de leitura e escrita < 1ms.
- **RNF02 (Custo Fixo Mínimo/Zero)**: Toda a arquitetura do monolito modular é dimensionada para operar em instâncias econômicas ou tiers gratuitos permanentes (GCP / Oracle Cloud).
- **RNF03 (Segurança & Blindagem de Segredos)**: Nenhuma chave privada, token de bot ou credencial de banco deve ser versionada no Git; todas as configurações devem ser lidas exclusivamente via variáveis de ambiente (`.env`) e `credentials.json`.
- **RNF04 (Resiliência & Tolerância a Falhas)**: Workers assíncronos devem possuir reconexão automática, controle estrito de concorrência com semáforos e política de retry com backoff exponencial para chamadas à Gemini API.
- **RNF05 (Manutenibilidade & Anti-Drift)**: Todos os projetos derivados e futuros desenvolvimentos devem manter os contratos especificados neste documento (`docs/spec.md`) e nas decisões arquiteturais (`docs/architecture.md`).
- **RNF06 (Isolamento de Privacidade)**: O sistema de escuta e mensageria é proibido de ler, registrar ou responder a mensagens privadas do operador em canais não autorizados.

---

## 6. Critérios de Aceite Globais (Definition of Done - DoD)

1. [x] Todos os 4 gestores executivos configurados com seus especialistas mapeados.
2. [x] Bot do Telegram ouvindo exclusivamente em canais autorizados (sem interferência em chats pessoais).
3. [x] GAPs de conhecimento auditados em tempo real (Cloud e QA não exibidos após contratação de Cláudio e Quinn).
4. [x] Área de Marketing & Growth com gestor executivo (`gestor_marketing`), `SKILL.md` e `agent.md` cadastrados.
5. [x] Radar Orbital e Áreas com CRUD completo e sem domínios órfãos.
6. [x] 100% dos testes unitários e compilações de arquivos Python passando sem erros.
