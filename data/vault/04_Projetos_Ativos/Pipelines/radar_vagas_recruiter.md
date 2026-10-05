---
id: radar_vagas_recruiter
name: Radar de Vagas & Abordagem Direta de Tech Recruiters
area: tech
manager: gestor_tech_cto
description: Pipeline cirúrgico para caçar vagas remotas de Desenvolvedor (Python/IA/Automação de R$ 3k a R$ 6k), minerar os Tech Recruiters e Hiring Managers no LinkedIn e executar abordagem que pula a fila dos portais (Gupy/ATS).
triggers:
  - vagas
  - emprego
  - recruiter
  - tech recruiter
  - vaga remota
steps:
  - step: 1
    title: Mapeamento de Vagas Remotas Compatíveis
    agent_id: agent_alex_vance
    role: Engenheiro de Software & IA
    harness_type: antigravity_ide
    instruction: |
      Mapeie de 5 a 10 vagas remotas ativas para Desenvolvedor Python / Automação / IA (PJ ou CLT de R$ 3k a R$ 6k).
      Requisitos fundamentais para filtrar:
      1. Stack compatível: Python, FastAPI, Automação de Processos, APIs, Scraping, IA Generativa.
      2. Modelo 100% Home Office (Brasil ou Internacional).
      3. Extraia o link da vaga, empresa contratante e requisitos essenciais.
  - step: 2
    title: Mineração de Tech Recruiters & Líderes de Engenharia no LinkedIn
    agent_id: agent_link_4211
    role: Pesquisador Web & Inteligência de Negócios
    harness_type: oraculo_cloud
    instruction: |
      Para cada empresa mapeada na etapa anterior:
      1. Pesquise e identifique o perfil do LinkedIn do Tech Recruiter, Talent Acquisition ou Head/CTO da empresa.
      2. Extraia o nome completo, cargo exato e URL do perfil no LinkedIn.
      3. Organize um dossiê limpo para contato direto.
  - step: 3
    title: Copy de Abordagem Direta "Skip the Queue"
    agent_id: agent_jordan_belford_5567
    role: Closer & Negociador de Alto Impacto
    harness_type: oraculo_cloud
    instruction: |
      Redija mensagens personalizadas de alta conversão para cada decisor minerado:
      1. Nota de Conexão no LinkedIn (limite estrito de 300 caracteres): personalizada, citando a vaga e destacando experiência prática com sistemas em produção.
      2. Mensagem de Follow-up (pós-conexão): pitch de 3 parágrafos destacando cases reais (automação de scraping, arquitetura Oráculo com FastAPI/Docker) e convidando para bate-papo de 10 minutos.
---

# 🎯 Pipeline: Radar de Vagas & Abordagem Direta de Tech Recruiters

> **Gestor Responsável**: Thiago Tech (VP de TI)  
> **Objetivo Estratégico**: Garantir o **Trilho de Segurança** nos próximos 17 dias (fechar vaga remota de R$ 3k a R$ 6k) sem perder semanas esperando retorno passivo de portais como Gupy.

---

## 📋 Entradas Necessárias
- Stack alvo: Python, FastAPI, Integração de APIs, Automação com Scripts, IA Generativa (Gemini/OpenAI), Web Scraping.
- Nível de senioridade alvo: Júnior a Pleno / Desenvolvedor de Automação / Software Engineer.
- Modelo de contratação: PJ ou CLT Remoto (Brasil ou internacional).

---

## ⚙️ Etapas de Execução

### Etapa 1: Mapeamento de Vagas Remotas Compatíveis
- **Responsável**: Alex Vance (Backend & IA)
- **Ação**: Varrer plataformas com menor atrito (Programathor, Remotar, LinkedIn Jobs, trampos.co) buscando vagas postadas nas últimas 48 horas.
- **Critério**: Vagas onde o stack bata com projetos reais que o Rodrigo já construiu (automações, scraping, FastAPI, Telegram bots).

### Etapa 2: Mineração do Decisor (Tech Recruiter ou CTO)
- **Responsável**: Link (Pesquisa Web & OSINT)
- **Ação**: Identificar quem publicou a vaga ou quem é o Tech Recruiter / Head de Engenharia daquela empresa no LinkedIn.
- **Regra**: Nunca se candidatar apenas pela plataforma genérica. O contato direto pelo LinkedIn tem taxa de resposta 8x superior.

### Etapa 3: Roteiro de Abordagem "Skip the Queue"
- **Responsável**: Jordan Belford (Closer) & Caio Copy
- **Ação**: Redigir nota de conexão magnética e humana que demonstra valor imediato.
- **Estrutura da Mensagem de Conexão (Máx 300 caracteres)**:
  > *"Olá [Nome], vi a vaga de [Cargo] na [Empresa]. Já desenvolvi sistemas completos em Python com IA e APIs rodando em produção. Sei como o processo seletivo costuma ser concorrido, adoraria me conectar e compartilhar um case prático com você."*
- **Mensagem pós-aceite (com portfólio/cases reais)**:
  > Apresenta brevemente o case da automação de dados e do Oráculo, disponibilizando 10 minutos para bate-papo rápido.

---

## 📁 Saída no Obsidian
Os resultados são salvos em `04_Projetos_Ativos/Execucoes/vagas_[data]/00_Overview.md` com a lista de empresas abordadas e status das respostas.
