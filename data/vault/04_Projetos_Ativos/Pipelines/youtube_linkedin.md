---
id: youtube_linkedin
name: Vídeo YouTube (8min) + Post LinkedIn
area: marketing
manager: gestor_marketing
description: Pipeline de produção multiplataforma para transformar temas técnicos em vídeo de alta retenção no YouTube e post de autoridade no LinkedIn.
triggers:
  - youtube
  - linkedin
  - video e post
steps:
  - step: 1
    title: Mapeamento Técnico & Exemplos Práticos de Código
    agent_id: agent_claude_code
    role: Engenheiro de Software
    harness_type: antigravity_ide
    instruction: |
      Pesquise a fundo o tema fornecido e elabore o dossiê técnico:
      1. Arquitetura e conceitos fundamentais sem superficialidade.
      2. Código de demonstração prático, funcional e elegante.
      3. Pontos de dor reais que desenvolvedores enfrentam.
      4. Resumo de insights práticos que o roteirista deve enfatizar no vídeo.
  - step: 2
    title: Roteiro Audiovisual Completo (8 Minutos)
    agent_id: agent_caio_copywriter
    role: Copywriter Audiovisual
    harness_type: oraculo_cloud
    instruction: |
      Utilizando todo o mapeamento técnico e código de exemplo produzido pelo Bruno (agent_claude_code), elabore o roteiro audiovisual completo de 8 minutos para o YouTube.
      Estruture rigorosamente com:
      - Gancho Magnético (0 a 15s): Quebra de padrão imediata e promessa clara.
      - Retenção & Contexto (15 a 45s): Por que a maioria faz errado e qual o custo disso.
      - Bloco 1 - Desmontando o Problema: Análise técnica do gargalo.
      - Bloco 2 - A Implementação Prática: Demonstração na tela com o código do Bruno.
      - Bloco 3 - Padrões Avançados & Cuidados: Boas práticas de produção.
      - Fechamento & CTA: Chamada forte para ação e inscrição no canal.
      Inclua indicações visuais de tela: [TELA: Código], [CÂMERA PRINCIPAL], [B-ROLL], [GC].
  - step: 3
    title: Post Estratégico de Autoridade para LinkedIn
    agent_id: agent_link_4211
    role: Especialista em LinkedIn & Growth B2B
    harness_type: oraculo_cloud
    instruction: |
      Utilizando os insights do Bruno e o roteiro do Caio Copywriter, crie uma publicação de autoridade máxima para o LinkedIn.
      Estruture:
      - Headline Magnética: 1 linha com gancho forte e sem clichês corporativos.
      - Quebra de crença comum do mercado nos primeiros 3 parágrafos.
      - Resumo executivo em 4 a 6 bullets pontuais.
      - Framework ou regra de ouro acionável.
      - CTA para comentários gerando debate técnico genuíno.
---

# 🎬 Pipeline: Vídeo YouTube + Post LinkedIn

Este playbook automatiza o ciclo completo de produção de conteúdo técnico de alta autoridade:
1. **Bruno (`agent_claude_code`)**: Garante precisão técnica e código real.
2. **Caio Copywriter (`agent_caio_copywriter`)**: Converte o insumo em roteiro audiovisual de 8 minutos com retenção máxima.
3. **Link (`agent_link_4211`)**: Extrai a tese executiva para o LinkedIn gerando leads e autoridade B2B.
