# 📋 Oráculo System Specification (docs/spec.md)
> **Versão Oficial**: 2.0.0 — Setembro/2026  
> **Liderança Técnica**: Helena Torres (👩‍💼 VP de Tecnologia) & Alex Vance (⚡ Arquiteto-Chefe)  
> **Padrão de Engenharia**: SDD (Spec-Driven Development) + TDD (Test-Driven Development)

---

## 1. Visão do Produto & Arquitetura Geral

O **Oráculo** é uma infraestrutura de inteligência artificial de dois hemisférios:
1. **Fábrica de Conhecimento Multimodal 24/7 (Nuvem - Google Cloud VM)**:
   - Ingestão contínua em alta vazão de cursos em vídeo (Google Drive e Telegram).
   - Extração multimodal de áudio, transcrição via Gemini e OCR de frames de código em tela via FFmpeg.
   - Compilação automática de Rich Skills (`SKILL.md`) com citações de aulas, minutos, regras e snippets.
   - Banco de dados de alta performance em SQLite (modo WAL).
2. **Quartel-General de Execução e Interação (Local - Antigravity IDE)**:
   - Hub de interação direta de Rodrigo Bettio Jr. com 11 especialistas e gestores autônomos.
   - Geração de software, estratégias de negócios, marketing, vendas e desenvolvimento pessoal.
   - Sincronização contínua de conhecimento (Zero-Touch).
3. **Controle e Telemetria Mobile (Celular - Telegram Bot)**:
   - Notificações push em tempo real (conclusão de cursos, alertas de tokens, status do sistema).
   - Comandos interativos pelo celular (`/status`, `/estudar <link>`, `/perguntar <agente>`).

---

## 2. Topologia de Infraestrutura

| Componente | Ambiente | Tecnologia | Função |
| :--- | :--- | :--- | :--- |
| **VM Backend** | Google Cloud (`34.46.39.111`) | Docker, FastAPI, Uvicorn, SQLite WAL | Motor de Ingestão e APIs REST |
| **Web Proxy** | Google Cloud (`34.46.39.111`) | Nginx Alpine (Porta 80/443) | Reverse Proxy, SSL e Roteamento |
| **Fila de Estudos** | Google Cloud (Container) | `ingestion/study_queue.py` | 20 Workers paralelos (Dual-Engine Drive/Telegram) |
| **Processador de Vídeo** | Google Cloud (Container) | `ingestion/video_processor.py` | FFmpeg resiliente + Gemini API |
| **CI/CD** | Google Cloud (Cron) | `scripts/auto_deploy.sh` | Deploy contínuo a cada 60s sem conflito |
| **Sincronizador** | Local (PC) | `scripts/sync_skills_from_vm.py` | Importação de skills da VM para Antigravity |
| **Skills do Antigravity** | Local (PC) | `~/.gemini/config/skills/` | Conhecimento vivo dos 11 agentes especialistas |

---

## 3. Matriz do Conselho de Especialistas (Governança Obrigatória)

Nenhuma decisão estrutural deve ser tomada sem a consulta prévia ao especialista correspondente:

```
                  ┌─────────────────────────────────────┐
                  │    Rodrigo Bettio Jr. (Líder)       │
                  └──────────────────┬──────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ 👩‍💼 Helena Torres   │   │ 🤵 Ricardo Monteiro │   │ 🧘‍♀️ Dra. Camila Reis │
│ VP de Tecnologia    │   │ Diretor Comercial   │   │ Diretora Bem-Estar  │
└──────────┬──────────┘   └──────────┬──────────┘   └──────────┬──────────┘
           │                         │                         │
     [Alex Vance & Bruno]     [Jordan Belford]            [O Monge]
   (Engenharia & Código)    (Vendas & Negociação)    (Foco & Espiritualidade)
                                     │
                               [André Diamand]
                            (Sexy Canvas & Marca)
                                     │
                                   [Link]
                           (LinkedIn & Autoridade)
```

---

## 4. Garantia de Preservação de Contexto (Anti-Drift Protocol)

1. **Contrato de Verdade**: Este arquivo (`docs/spec.md`) e `docs/architecture.md` são a âncora de todo o projeto.
2. **Auditoria Pré-Decisão**: Qualquer agente ou subagente atuando neste projeto deve consultar `docs/spec.md` antes de propor alterações funcionais.
3. **Separação Estado vs. Código**: O código vive exclusivamente no GitHub; o conhecimento acumulado e banco de dados vivem em volumes protegidos fora do controle de versão.
