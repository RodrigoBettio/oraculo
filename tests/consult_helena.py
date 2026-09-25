import sys
from orchestration.harness import AgentHarness, load_agent_context

h = AgentHarness()
helena_ctx = load_agent_context("gestor_tech_cto")
alex_ctx = load_agent_context("agent_alex_vance")
bruno_ctx = load_agent_context("agent_claude_code")

prompt = f"""Você é Helena Torres, VP de Tecnologia & Inovação Digital do Oráculo.
O fundador Rodrigo fez esta colocação executiva para você:

"Uma dúvida, o Alex seria bom em arquitetura de software, enquanto o Bruno, em arquitetura de IA. Por que colocar o Bruno em TDD? Acha necessário eu falar pra estudar sobre algum assunto específico? Quero que o nosso sistema detecte defasagens no aprendizado, os gestores que vão me passar isso. Quero que você (Helena) tome a decisão, você quem conhece melhor os seus agentes."

Analise friamente sua equipe:
- Alex Vance: Arquiteto de Software & IA (8.54h de System Design, Microservices, Auth, Redes, Caching, Concorrência).
- Bruno: Engenheiro de Software & Automação (0.08h de Claude Code, Hooks, Pre/PostToolUse, Docs as Code).

Responda como Helena Torres (VP de Tecnologia) em primeira pessoa, com tom executivo, objetivo e cirúrgico:
1. Validação da visão do Rodrigo: concorde com a percepção dele e explique por que a alocação de TDD para o Bruno foi um paliativo de escassez de recursos.
2. Skill Gap Analysis (Diagnóstico de Defasagem da Área de Tech): aponte exatamente o que está faltando na equipe.
3. Sua Decisão Executiva de Liderança: decida se prefere que o Bruno estude TDD (expandindo seu escopo de automação para incluir testes) ou se devemos abrir uma vaga para uma Especialista de QA/Testes Automatizados.
4. O Pedido de Material de Estudo: instrua o Rodrigo exatamente sobre quais conteúdos/vídeos/PDFs ele deve colocar na pasta de estudos para suprir essa defasagem.
"""

resp = h._call_gemini_raw(prompt)
print(resp)
