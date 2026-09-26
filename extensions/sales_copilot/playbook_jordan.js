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
