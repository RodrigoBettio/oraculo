/**
 * Oráculo Sales Copilot — Playbook de Quebra de Objeções & Sinais de Compra
 * Curadoria: Jordan Belford (Closer) & Caio Copywriter (Direto ao Ponto)
 */

const JORDAN_PLAYBOOK = {
  // === CLUSTERS DE OBJEÇÕES (Sinais de Fricção) ===
  objections: {
    PRECO_ALTO: {
      id: "PRECO_ALTO",
      title: "Preço / Custo / Orçamento",
      severity: "critica",
      weight: -20,
      keywords: [
        "caro", "cara", "carissim", "carinho", "salgado", "salgada",
        "pesado", "pesada", "desconto", "barato", "barata",
        "orcamento", "grana", "dinheiro", "muito alto", "preco alto",
        "valor alto", "achou caro", "achei caro", "achou muito caro",
        "achei muito caro", "ta caro", "ta muito caro", "e caro", "muito salgado"
      ],
      semantic_triggers: [
        "achei muito caro",
        "achou muito caro",
        "achou caro",
        "achei caro",
        "ta muito caro",
        "ta caro",
        "muito caro",
        "achei um pouco caro",
        "esta fora do meu orcamento",
        "muito salgado para o momento",
        "nao tenho essa grana agora",
        "o valor esta pesado",
        "consegue fazer mais barato",
        "consegue dar um desconto",
        "muito dinheiro para o que faz",
        "pesou um pouco no bolso",
        "esperava um valor menor",
        "o preco ta alto",
        "muito puxado o preco"
      ],
      jordan_script: {
        step1_agree: "Eu entendo que parece um investimento à primeira vista.",
        step2_pivot: "Mas quanto custa você perder 5 clientes por semana porque ninguém respondeu rápido no WhatsApp? A perda invisível é 5x maior que a mensalidade.",
        step3_close: "Se recuperarmos apenas 2 clientes que você perderia no mês, a ferramenta já se pagou e deu lucro. Vamos estruturar isso já?"
      }
    },

    COMPLEXIDADE_ADOTABILIDADE: {
      id: "COMPLEXIDADE_ADOTABILIDADE",
      title: "Medo da Equipe / Complexidade",
      severity: "alta",
      weight: -15,
      keywords: [
        "equipe", "funcionario", "funcionarios", "dificil", "complexo",
        "complexa", "mexer", "usar", "adaptar", "aprender", "treinar",
        "resistencia", "resistente", "resistentes", "conseguir usar",
        "nao vao saber", "vai conseguir", "saber usar"
      ],
      semantic_triggers: [
        "minha equipe vai conseguir usar",
        "sera que a minha equipe vai conseguir",
        "minha equipe vai conseguir",
        "equipe nao vai saber",
        "nao sao chegados em tecnologia",
        "pessoal aqui e mais velho",
        "vai dar muito trabalho pra treinar",
        "muito complexo para eles",
        "eles tem dificuldade com computador",
        "nao sei se vao se adaptar",
        "sera que vao conseguir mexer",
        "sistema parece dificil",
        "meus funcionarios sao resistentes"
      ],
      jordan_script: {
        step1_agree: "Compreendo perfeitamente, e essa é a principal preocupação dos donos de empresa.",
        step2_pivot: "Nós desenhamos isso para rodar direto no WhatsApp que sua equipe já usa todo santo dia. Não tem tela nova nem app complicado.",
        step3_close: "Eu mesmo dou o treinamento de 20 minutos com eles. Se em 7 dias eles não estiverem dominando, cancelamos sem custo. Fechado?"
      }
    },

    TEMPO_IMPLANTACAO: {
      id: "TEMPO_IMPLANTACAO",
      title: "Falta de Tempo / Momento Ruim",
      severity: "media",
      weight: -12,
      keywords: [
        "tempo", "correria", "enrolado", "enrolada", "mes que vem",
        "semana que vem", "depois", "final do ano", "agora nao",
        "sem tempo", "muita coisa", "cabeca cheia"
      ],
      semantic_triggers: [
        "estou sem tempo agora",
        "correria danada no momento",
        "vamos ver mes que vem",
        "mais pro final do ano",
        "agora nao e uma boa hora",
        "estou muito enrolado",
        "minha cabeca esta cheia",
        "nao consigo focar nisso agora"
      ],
      jordan_script: {
        step1_agree: "Justamente por você estar nessa correria é que você precisa disso ontem.",
        step2_pivot: "O objetivo desse software é tirar tarefas repetitivas das suas costas e liberar 2 horas do seu dia.",
        step3_close: "Você só precisa me passar os dados básicos e eu cuido de todo o setup e deploy. Começamos a rodar nesta semana?"
      }
    },

    JA_TENHO_SOLUCAO: {
      id: "JA_TENHO_SOLUCAO",
      title: "Status Quo / Já uso Planilha ou Amador",
      severity: "media",
      weight: -10,
      keywords: [
        "planilha", "excel", "caderno", "caderninho", "sobrinho",
        "ja tenho", "ja usamos", "ja temos", "se vira", "ja faco"
      ],
      semantic_triggers: [
        "ja tenho alguem que faz",
        "meu sobrinho cuida disso",
        "ja uso planilha de excel",
        "ja usamos um sistema aqui",
        "a gente se vira no caderninho",
        "do jeito que ta ta funcionando",
        "ja temos um processo",
        "nao vejo motivo pra trocar"
      ],
      jordan_script: {
        step1_agree: "Planilhas e soluções manuais funcionaram muito bem até você chegar nesse tamanho.",
        step2_pivot: "O problema é que elas dependem 100% de alguém lembrar de preencher. O nosso sistema faz isso de forma autônoma 24h por dia.",
        step3_close: "Não precisa abandonar o que você usa hoje. Vamos rodar em paralelo por 14 dias para você comparar os números?"
      }
    },

    DECISOR_TERCEIRO: {
      id: "DECISOR_TERCEIRO",
      title: "Decisor Ausente (Sócio / Esposa / Diretoria)",
      severity: "alta",
      weight: -15,
      keywords: [
        "socio", "esposa", "marido", "diretoria", "financeiro",
        "patrao", "gerente", "consultar", "conversar com", "falar com"
      ],
      semantic_triggers: [
        "preciso falar com meu socio",
        "vou conversar com a minha esposa",
        "preciso levar pra diretoria",
        "nao decido isso sozinho",
        "tenho que consultar o financeiro",
        "vou passar pro meu socio ver"
      ],
      jordan_script: {
        step1_agree: "Faz total sentido alinhar com ele(a), vocês são parceiros nisso.",
        step2_pivot: "Para não perder o contexto técnico, o que você acha de marcarmos uma chamada de 10 minutos nós 3 juntos amanhã?",
        step3_close: "Assim eu tiro as dúvidas financeiras e de segurança direto com ele, economizando seu tempo. Qual melhor horário amanhã?"
      }
    },

    DESCONFIANCA_TECNICA: {
      id: "DESCONFIANCA_TECNICA",
      title: "Ceticismo com Inteligência Artificial",
      severity: "media",
      weight: -10,
      keywords: [
        "robo", "ia", "inteligencia artificial", "mecanico", "alucinar",
        "alucinacao", "besteira", "automatizado", "falar errado"
      ],
      semantic_triggers: [
        "sera que ia funciona",
        "robo nao fica muito mecanico",
        "nao gosto de atendimento automatizado",
        "clientes nao gostam de falar com robo",
        "vai falar besteira pro meu cliente",
        "tenho receio de alucinar"
      ],
      jordan_script: {
        step1_agree: "Eu também odeio aqueles menus antigos de 'digite 1 para financeiro'.",
        step2_pivot: "Nossa tecnologia usa linguagem natural calibrada com o tom da sua empresa. Se o cliente fizer uma pergunta fora do escopo, ele transfere para você na hora.",
        step3_close: "Posso te mandar um áudio teste agora no seu próprio WhatsApp para você ver como é humanizado?"
      }
    },

    VOU_PENSAR: {
      id: "VOU_PENSAR",
      title: "Empurrando com a Barriga / Vou Pensar",
      severity: "critica",
      weight: -18,
      keywords: [
        "vou pensar", "pensar", "analisar", "avaliar", "refletir",
        "manda por email", "manda proposta", "manda pdf", "envia proposta",
        "manda material", "vou dar uma olhada", "deixa eu ver"
      ],
      semantic_triggers: [
        "vou pensar com calma",
        "preciso pensar sobre isso",
        "deixa eu analisar em casa",
        "manda a proposta por email",
        "pode enviar por whatsapp pra eu ver depois",
        "vou refletir e te retorno",
        "vou dar uma estudada",
        "deixa eu pensar e te falo",
        "preciso processar essas informacoes",
        "me manda um resumo",
        "manda pdf com os detalhes",
        "vou avaliar com calma e retorno",
        "vou pensar e qualquer coisa te chamo"
      ],
      jordan_script: {
        step1_agree: "Faz todo sentido querer processar as informações. Eu faço questão que você tome a melhor decisão.",
        step2_pivot: "Normalmente, quando alguém diz 'vou pensar', tem uma dúvida específica que eu não respondi. Pode ser preço, pode ser funcionalidade, pode ser timing — qual é a sua?",
        step3_close: "Se eu resolver essa dúvida agora, conseguimos fechar hoje e já começar o setup na segunda. O que te trava?"
      }
    },

    FALTA_PROVA_SOCIAL: {
      id: "FALTA_PROVA_SOCIAL",
      title: "Credibilidade / Falta de Prova Social",
      severity: "alta",
      weight: -14,
      keywords: [
        "cases", "case", "depoimento", "depoimentos", "portfolio",
        "quem usa", "clientes seus", "referencias", "referencia",
        "cnpj", "tempo de mercado", "quanto tempo voces tem"
      ],
      semantic_triggers: [
        "voce tem case de sucesso",
        "quem mais usa isso",
        "tem algum cliente que eu possa conversar",
        "cade os depoimentos",
        "qual o cnpj da empresa",
        "quanto tempo voces tem de mercado",
        "nunca ouvi falar de voces",
        "como sei que funciona de verdade",
        "tem portfolio pra me mostrar",
        "tem referencia no seu segmento"
      ],
      jordan_script: {
        step1_agree: "Essa é uma preocupação inteligente. Profissional que pesquisa antes de investir toma decisão melhor.",
        step2_pivot: "Nós temos clientes ativos em nichos parecidos com o seu que tiveram resultados em menos de 30 dias. Posso te mostrar prints reais e até passar o contato de um para conversar direto.",
        step3_close: "Quer que eu te envie agora 2 depoimentos de clientes do seu segmento e marcamos um piloto para você validar pessoalmente?"
      }
    },

    MEDO_LGPD_SEGURANCA: {
      id: "MEDO_LGPD_SEGURANCA",
      title: "Medo de LGPD / Segurança de Dados",
      severity: "media",
      weight: -12,
      keywords: [
        "lgpd", "dados", "seguranca", "seguro", "privacidade",
        "banir", "banido", "bloquear", "bloqueio", "vazamento",
        "hackear", "hacker", "compliance"
      ],
      semantic_triggers: [
        "meus dados ficam seguros",
        "e a lgpd como fica",
        "whatsapp pode banir meu numero",
        "nao quero ter problema com dados",
        "como protegem as informacoes",
        "tem risco de vazar dados do cliente",
        "e se der problema de privacidade",
        "meu whatsapp pode ser bloqueado"
      ],
      jordan_script: {
        step1_agree: "Essa preocupação mostra maturidade. Segurança de dados é inegociável para nós também.",
        step2_pivot: "Todos os dados são criptografados em trânsito e em repouso, rodamos em infraestrutura Google Cloud com certificação SOC 2, e nosso bot usa a API oficial do WhatsApp Business — zero risco de banimento.",
        step3_close: "Quer que eu te envie nosso documento de compliance e política de privacidade para seu jurídico validar enquanto avançamos?"
      }
    },

    INTEGRACAO_SISTEMA: {
      id: "INTEGRACAO_SISTEMA",
      title: "Integração com Sistemas Existentes",
      severity: "media",
      weight: -10,
      keywords: [
        "integra", "integracao", "integrar", "erp", "bling", "tiny",
        "omie", "nfe", "nota fiscal", "sistema atual", "meu sistema",
        "conecta", "conectar", "api", "webhook"
      ],
      semantic_triggers: [
        "integra com meu erp",
        "funciona junto com o bling",
        "conecta com o tiny",
        "integra com o omie",
        "consigo usar com meu sistema atual",
        "como faz a integracao",
        "tem api pra conectar",
        "e o meu sistema de notas"
      ],
      jordan_script: {
        step1_agree: "Ótima pergunta. Ninguém quer jogar fora um sistema que já funciona.",
        step2_pivot: "Nosso sistema conecta via webhook ou API com qualquer plataforma: Bling, Tiny, Omie, RD Station, ou qualquer ERP que tenha integração. Não substituímos — complementamos.",
        step3_close: "Posso agendar uma call técnica de 15 minutos com seu responsável de TI para validar a integração antes de avançar?"
      }
    },

    NAO_E_MOMENTO: {
      id: "NAO_E_MOMENTO",
      title: "Adiamento / Não é o Momento",
      severity: "alta",
      weight: -14,
      keywords: [
        "momento", "agora nao", "janeiro", "fevereiro", "depois do carnaval",
        "ano que vem", "proximo mes", "comeco do ano", "apos", "daqui a pouco"
      ],
      semantic_triggers: [
        "nao e o momento certo",
        "depois do carnaval a gente ve",
        "vamos deixar para janeiro",
        "ano que vem pode ser",
        "final do ano ta complicado",
        "estou reorganizando a empresa",
        "preciso organizar a casa primeiro",
        "agora nao da mas no futuro sim",
        "vamos conversar daqui uns meses"
      ],
      jordan_script: {
        step1_agree: "Entendo que timing é tudo em negócios. Você conhece sua empresa melhor que ninguém.",
        step2_pivot: "Mas me responde uma coisa: o que muda entre agora e janeiro? Porque o custo de cada mês sem a solução são clientes que entram em contato e ninguém responde. Em 3 meses isso pode ser 50-100 leads perdidos.",
        step3_close: "E se a gente começar o setup agora — você só paga a mensalidade quando estiver 100% rodando? Assim você não perde o timing e controla o investimento."
      }
    }
  },

  // === CLUSTERS DE SINAIS DE COMPRA (Green Flags) ===
  buying_signals: {
    PERGUNTA_PRAZO: {
      id: "PERGUNTA_PRAZO",
      title: "Interesse em Prazo de Entrega",
      weight: +18,
      keywords: [
        "prazo", "quanto tempo", "quando entrega", "quando fica pronto",
        "quando sobe", "dias demora", "quantos dias", "entrega quando"
      ],
      semantic_triggers: [
        "quanto tempo demora",
        "fica pronto em quanto tempo",
        "quando consegue entregar",
        "se a gente fechar hoje quando sobe",
        "qual o prazo de implantacao",
        "demora muito pra rodar",
        "consegue entregar essa semana"
      ],
      jordan_alert: "🔥 CLIENTE COM COMPORTAMENTO DE COMPRA! Pare de explicar código e confirme o prazo agora para fechar."
    },

    PERGUNTA_PAGAMENTO: {
      id: "PERGUNTA_PAGAMENTO",
      title: "Interesse em Forma de Pagamento",
      weight: +22,
      keywords: [
        "pix", "pagamento", "pagar", "parcelar", "parcela",
        "parcelas", "cartao", "boleto", "fatura", "mensalidade", "entrada"
      ],
      semantic_triggers: [
        "como funciona o pagamento",
        "voce aceita pix",
        "da pra parcelar",
        "tem entrada",
        "como e a cobranca da mensalidade",
        "fatura no boleto",
        "divide no cartao"
      ],
      jordan_alert: "🚨 ALERTA VERMELHO DE FECHAMENTO: O cliente já decidiu comprar e está negociando pagamento. Puxe o contrato agora!"
    },

    PERGUNTA_CONTRATO_GARANTIA: {
      id: "PERGUNTA_CONTRATO_GARANTIA",
      title: "Validação de Segurança / Contrato",
      weight: +15,
      keywords: [
        "nota fiscal", "nf", "contrato", "garantia", "cancelar",
        "cancelamento", "seguranca", "termo"
      ],
      semantic_triggers: [
        "emite nota fiscal",
        "tem contrato",
        "como e o termo de confidencialidade",
        "tem garantia",
        "posso cancelar se nao gostar"
      ],
      jordan_alert: "🔒 CLIENTE QUERENDO SEGURANÇA. Confirme a nota e a garantia incondicional e peça os dados cadastrais."
    },

    ENTUSIASMO_IMPACTO: {
      id: "ENTUSIASMO_IMPACTO",
      title: "Validação Espontânea de Valor",
      weight: +14,
      keywords: [
        "foda", "sensacional", "incrivel", "muito bom", "gostei",
        "dor de cabeca", "rapido", "animal", "top", "show"
      ],
      semantic_triggers: [
        "caramba que rapido",
        "nossa isso e muito foda",
        "isso resolveria uma dor de cabeca aqui",
        "muito interessante isso",
        "gostei bastante dessa parte",
        "sensacional essa ideia"
      ],
      jordan_alert: "⚡ MOMENTO DE PICO EMOCIONAL: Ancore o valor e emende a proposta de implantação imediatamente."
    },

    PEDIDO_DEMO: {
      id: "PEDIDO_DEMO",
      title: "Pedido de Demo / Teste / Trial",
      weight: +16,
      keywords: [
        "testar", "teste", "trial", "demonstracao", "demo",
        "ver funcionando", "experimentar", "provar"
      ],
      semantic_triggers: [
        "posso testar antes de fechar",
        "tem versao de teste",
        "quero ver funcionando na pratica",
        "da pra experimentar antes",
        "tem um trial gratuito",
        "posso fazer um teste rapido",
        "quero ver rodando no meu negocio"
      ],
      jordan_alert: "🧪 PEDIDO DE DEMO = Interesse concreto! Ofereça piloto de 7 dias SEM risco e peça os dados de acesso."
    },

    PERGUNTA_SUPORTE_ONBOARDING: {
      id: "PERGUNTA_SUPORTE_ONBOARDING",
      title: "Interesse em Suporte e Onboarding",
      weight: +15,
      keywords: [
        "suporte", "pos-venda", "acompanhamento", "onboarding",
        "treinamento", "quem me atende", "ajuda depois"
      ],
      semantic_triggers: [
        "como funciona o suporte de voces",
        "tem alguem pra me ajudar no dia a dia",
        "se der problema quem eu chamo",
        "voces dao treinamento pro meu pessoal",
        "como e o acompanhamento depois que comeca",
        "tem suporte no whatsapp"
      ],
      jordan_alert: "🤝 CLIENTE PENSANDO NO DIA A DIA! Garanta suporte direto e feche a contratação agora."
    },

    INCLUSAO_TERCEIROS_POSITIVA: {
      id: "INCLUSAO_TERCEIROS_POSITIVA",
      title: "Inclusão Positiva de Stakeholders",
      weight: +12,
      keywords: [
        "trazer meu socio", "mostrar pro time", "meu gerente ver",
        "apresentar pro diretor", "chamar meu parceiro"
      ],
      semantic_triggers: [
        "posso trazer meu socio pra proxima call",
        "vou mostrar pro meu time",
        "quero que meu gerente veja isso",
        "posso apresentar isso internamente",
        "meu parceiro precisa conhecer"
      ],
      jordan_alert: "👥 MOBILIZANDO STAKEHOLDERS! Ofereça uma call conjunta imediata — não deixe esfriar."
    },

    COMPARACAO_FAVORAVEL: {
      id: "COMPARACAO_FAVORAVEL",
      title: "Comparação Competitiva Favorável",
      weight: +18,
      keywords: [
        "melhor que", "mais completo", "prefiro voces", "superior",
        "ganharam", "melhor opcao", "mais bonito"
      ],
      semantic_triggers: [
        "gostei mais do que o concorrente",
        "voces sao melhores que o outro",
        "a outra empresa nao tinha isso",
        "ja vi outras opcoes e a de voces e melhor",
        "prefiro o de voces",
        "voces tem mais recursos que os outros"
      ],
      jordan_alert: "🏆 COMPARAÇÃO FAVORÁVEL! Reforce o diferencial exclusivo e FECHE AGORA antes que pesquise mais."
    }
  },

  // === CONFIGURAÇÕES GERAIS DE SCORING ===
  config: {
    baseline_probability: 50,
    max_probability: 98,
    min_probability: 12,
    strike_zone_threshold: 75,
    danger_zone_threshold: 40
  },

  /**
   * Gera o roteiro de contra-ataque do Jordan hipercontextualizado
   * com o nome do cliente, o produto ofertado, o preço e o ticket médio!
   */
  getContextualScript: function (objectionId, dealContext) {
    const ctx = dealContext || {
      client: "Oficina Mecânica",
      product: "Landing Page + WhatsApp",
      setupPrice: 2000,
      monthlyPrice: 200,
      clientTicket: 250
    };

    const ticket = Math.max(Number(ctx.clientTicket) || 1, 1);
    const monthly = Number(ctx.monthlyPrice) || 0;
    const setup = Number(ctx.setupPrice) || 0;
    const clientsToPayMonthly = Math.max(1, Math.ceil(monthly / ticket));
    const clientsToPaySetup = Math.max(1, Math.ceil(setup / ticket));

    if (objectionId === "PRECO_ALTO") {
      if (monthly <= 10 && setup <= 10) {
        return {
          step1_agree: `Compreendo que qualquer valor chama atenção, mas R$ ${monthly || setup} é um valor puramente simbólico de ativação para teste.`,
          step2_pivot: `Isso custa literalmente menos que uma bala ou uma água no balcão da sua empresa.`,
          step3_close: `O valor é só para formalizar o compromisso técnico. Vamos colocar para rodar agora?`
        };
      }
      if (monthly > 0) {
        return {
          step1_agree: `Eu entendo que parece um investimento à primeira vista para o seu momento.`,
          step2_pivot: `Mas com o ticket médio de R$ ${ticket} na sua empresa, com apenas ${clientsToPayMonthly} cliente(s) novo(s) que fechar(em) pelo ${ctx.product}, a mensalidade de R$ ${monthly}/mês já está 100% paga e o resto é lucro limpo no caixa.`,
          step3_close: `Se o sistema trouxer apenas ${clientsToPayMonthly} venda(s) a mais por mês ele se paga sozinho. Faz sentido começarmos?`
        };
      } else {
        return {
          step1_agree: `Eu entendo que parece um investimento à primeira vista para o seu momento.`,
          step2_pivot: `Mas com o ticket médio de R$ ${ticket} no seu negócio, com apenas ${clientsToPaySetup} cliente(s) atendidos pelo ${ctx.product}, o investimento único de R$ ${setup} se paga por completo e todo o resto é lucro líquido vitalício.`,
          step3_close: `Se recuperarmos só ${clientsToPaySetup} venda(s) ele já se pagou 100%. Vamos estruturar isso já?`
        };
      }
    }

    if (objectionId === "COMPLEXIDADE_ADOTABILIDADE") {
      return {
        step1_agree: `Compreendo perfeitamente, e essa é a principal preocupação dos donos de ${ctx.client || "empresas"}.`,
        step2_pivot: `O ${ctx.product} foi feito para rodar direto onde sua equipe já mexe todo dia (como o WhatsApp). Zero telas novas ou treinamento difícil.`,
        step3_close: `Eu mesmo acompanho os primeiros 7 dias da sua equipe. Se acharem complicado, devolvo o valor. Fechado?`
      };
    }

    if (objectionId === "TEMPO_IMPLANTACAO") {
      return {
        step1_agree: `Justamente por você estar nessa correria é que o ${ctx.product} se faz necessário agora.`,
        step2_pivot: `Você não precisa gastar tempo: eu cuido de 100% da instalação e entrego funcionando pronto na sua mão.`,
        step3_close: `Você só precisa aprovar os acessos e nós colocamos para rodar em poucos dias. Podemos avançar?`
      };
    }

    if (objectionId === "JA_TENHO_SOLUCAO") {
      return {
        step1_agree: `O que você usa hoje funcionou muito bem para você chegar até onde está.`,
        step2_pivot: `Mas o ${ctx.product} automatiza a parte manual que hoje toma tempo e corre risco de esquecimento humano.`,
        step3_close: `Não precisa trocar nada agora. Vamos rodar em paralelo por 14 dias para você ver a diferença no caixa?`
      };
    }

    if (objectionId === "DECISOR_TERCEIRO") {
      return {
        step1_agree: `Faz total sentido alinhar com seu sócio/parceiro, é uma decisão conjunta.`,
        step2_pivot: `Para economizar o seu tempo de ter que explicar toda a parte técnica do ${ctx.product}, o que acha de eu entrar 10 minutos numa call com vocês dois?`,
        step3_close: `Assim eu tiro as dúvidas financeiras direto com ele e você não perde tempo. Qual melhor horário amanhã?`
      };
    }

    if (objectionId === "VOU_PENSAR") {
      return {
        step1_agree: `Faz todo sentido querer processar. Eu faço questão que você tome a melhor decisão sobre o ${ctx.product}.`,
        step2_pivot: `Normalmente, quando alguém diz "vou pensar", tem uma dúvida específica que eu não respondi. Pode ser preço, pode ser se funciona para ${ctx.client}, pode ser timing — qual é a sua?`,
        step3_close: `Se eu resolver essa dúvida agora, conseguimos fechar hoje e já começar o setup. O que te trava?`
      };
    }

    if (objectionId === "FALTA_PROVA_SOCIAL") {
      return {
        step1_agree: `Essa é uma preocupação inteligente. Dono de ${ctx.client} que pesquisa antes de investir toma decisão melhor.`,
        step2_pivot: `Temos clientes ativos em nichos parecidos com ${ctx.client} que viram resultado com o ${ctx.product} em menos de 30 dias. Posso te mostrar prints reais e até passar o contato de um para conversar direto.`,
        step3_close: `Quer que eu te envie agora 2 depoimentos de clientes do seu segmento e marcamos um piloto para você validar pessoalmente?`
      };
    }

    if (objectionId === "MEDO_LGPD_SEGURANCA") {
      return {
        step1_agree: `Essa preocupação mostra maturidade. Segurança de dados do ${ctx.client} é inegociável para nós também.`,
        step2_pivot: `O ${ctx.product} roda em infraestrutura Google Cloud com criptografia de ponta a ponta. Se usa WhatsApp, é via API Business oficial — zero risco de banimento.`,
        step3_close: `Quer que eu te envie nosso documento de compliance para seu jurídico validar enquanto avançamos com o setup?`
      };
    }

    if (objectionId === "INTEGRACAO_SISTEMA") {
      return {
        step1_agree: `Ótima pergunta. Ninguém quer jogar fora um sistema que já funciona no ${ctx.client}.`,
        step2_pivot: `O ${ctx.product} conecta via webhook ou API com qualquer plataforma: Bling, Tiny, Omie, RD Station. Não substituímos seu sistema — complementamos.`,
        step3_close: `Posso agendar uma call técnica de 15 minutos com seu responsável de TI para validar a integração antes de fechar?`
      };
    }

    if (objectionId === "NAO_E_MOMENTO") {
      const lostLeadsPerMonth = Math.round(monthly > 0 ? (monthly / ticket) * 15 : 30);
      return {
        step1_agree: `Entendo que timing é tudo em negócios. Você conhece o ${ctx.client} melhor que ninguém.`,
        step2_pivot: `Mas o que muda entre agora e o "momento ideal"? Cada mês sem o ${ctx.product} podem ser ${lostLeadsPerMonth}+ leads que entram e ninguém responde a tempo.`,
        step3_close: `E se a gente começar o setup agora — você só paga a mensalidade quando estiver 100% rodando? Assim não perde o timing.`
      };
    }

    return this.objections[objectionId]?.jordan_script || {
      step1_agree: "Compreendo o seu ponto perfeitamente.",
      step2_pivot: "Mas avaliando o retorno sobre o investimento, a conta fecha com folga.",
      step3_close: "Vamos estruturar um piloto rápido para validar?"
    };
  }
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = JORDAN_PLAYBOOK;
}
