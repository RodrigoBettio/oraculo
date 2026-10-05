---
id: prospeccao_leads_jordan
name: Prospecção B2B Multicanal com Fechamento Jordan
area: sales
manager: gestor_sales_director
description: Pipeline completo de mineração de leads (Apollo.io, Google Maps, Instagram), elaboração de diagnósticos cirúrgicos e abordagem humana multitoque direcionando os decisores para o WhatsApp com o Jordan Belford.
triggers:
  - prospeccao
  - outbound
  - apollo
  - leads
  - clientes
  - jordan
steps:
  - step: 1
    title: Mineração de Decisores (Apollo.io, Google Maps e Instagram)
    agent_id: agent_sofia_sdr
    role: Especialista em Prospecção B2B & SDR
    harness_type: oraculo_cloud
    instruction: |
      Mine e qualifique uma lista de 15 a 30 empresas dentro do ICP definido (Clínicas, Imobiliárias, Distribuidoras ou E-commerce de médio porte):
      1. Extraia o nome do sócio, fundador ou diretor operacional.
      2. Obtenha o WhatsApp comercial, link do Instagram e site oficial.
      3. Identifique o gargalo provável (ex: atendimento manual lento, falta de integração de catálogo, agendamento confuso).
  - step: 2
    title: Diagnóstico Prévio de 1 Minuto & Gancho de Abordagem
    agent_id: agent_ricardo_monteiro
    role: Diretor Comercial & Estrategista de Vendas
    harness_type: oraculo_cloud
    instruction: |
      Para cada empresa da lista, elabore uma abordagem cirúrgica de 3 linhas:
      1. Sem empurrar produto ou parecer vendedor chato.
      2. Apontando uma falha ou oportunidade concreta e oferecendo um vídeo/áudio de demonstração de 40 segundos sem compromisso.
      3. Roteiro pronto para envio via WhatsApp ou Direct do Instagram.
  - step: 3
    title: Cadência de Conversação & Fechamento no WhatsApp com Jordan Belford
    agent_id: agent_jordan_belford_5567
    role: Closer & Qualificador de Vendas
    harness_type: oraculo_cloud
    instruction: |
      Elabore a árvore conversacional que o Jordan utilizará no WhatsApp quando o lead responder:
      1. Envio da demonstração personalizada.
      2. Duas perguntas de qualificação BANT (Orçamento, Autoridade, Necessidade e Tempo).
      3. Tratamento das 3 objeções mais comuns ('não tenho tempo', 'quanto custa', 'já tenho equipe').
      4. Fechamento do agendamento da call de Diagnóstico de Ontologia Tech de 15 minutos com o Rodrigo.
---

# 💼 Pipeline: Prospecção B2B Multicanal com Fechamento Jordan

> **Gestor Responsável**: Ricardo Monteiro (Diretor Comercial)  
> **Especialistas**: Sofia SDR, Caio Copy e Jordan Belford  
> **Objetivo**: Colocar **1 a 2 reuniões qualificadas por semana** na agenda do Rodrigo para fechar projetos de R$ 2.000 a R$ 5.000.

---

## 🎯 Nichos de Alto Potencial (PMEs com Dinheiro e Processos Manuais)
1. **Clínicas Médicas & Odontológicas**: Atendimento via WhatsApp lento, confirmação manual de consultas, perda de pacientes.
2. **Imobiliárias & Corretores de Médio Padrão**: Cadastro manual de imóveis, demora no retorno a novos contatos de portais (Zap/VivaReal).
3. **Distribuidoras & Pequenas Logísticas**: Pedidos tirados em PDF ou WhatsApp que precisam ser redigitados em sistemas internos (exatamente onde entra automação Python).
4. **Escritórios de Advocacia / Contabilidade**: Coleta repetitiva de certidões e relatórios mensais.

---

## ⚙️ Etapas de Execução

### Etapa 1: Mineração Cirúrgica de Leads
- **Fontes**:
  - **Apollo.io**: Filtro por localização, cargo e tamanho da empresa (5 a 50 funcionários).
  - **Google Maps**: Busca por estabelecimentos bem avaliados no Google na região alvo.
  - **Instagram**: Perfis de empresas ativas com anúncios rodando.
- **Saída**: Nome do decisor, WhatsApp comercial, link do Instagram e dados da empresa.

### Etapa 2: A Abordagem de 3 Linhas (Anti-Spam)
- **Princípio**: Nunca mande um textão de vendas genérico. Ninguém lê.
- **Roteiro no WhatsApp/Instagram**:
  > *"Olá [Nome do Dono], tudo bem?*  
  > *Estava analisando o fluxo de atendimento da [Nome da Empresa] e notei que vocês perdem quase 20 minutos para responder contatos novos que chegam no site/anúncios.*  
  > *Desenvolvi um modelo de triagem com IA que responde em menos de 10 segundos e já agenda no calendário. Gravei um vídeo rápido de 40 segundos mostrando como funciona. Posso te enviar por aqui?"*
- **Taxa de Conversão esperada**: 25% a 35% de resposta positiva solicitando o vídeo.

### Etapa 3: Atendimento & Condução pelo Jordan Belford
- Quando o empresário responder:
  1. O **Jordan Belford** envia a demonstração em vídeo ou áudio curto humanizado.
  2. Faz 2 perguntas de qualificação BANT.
  3. Convite para o **Diagnóstico de Ontologia Tech de 15 minutos** com o Rodrigo pelo Google Meet.
