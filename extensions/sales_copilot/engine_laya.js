/**
 * Oráculo Sales Copilot — Motor Laya de Decisão Rápida (System 1)
 * Arquitetura: Bruno (AI Builder) & Tiago Tech (VP de TI)
 * Latência de Inferência: < 50ms (Zero-blocking, Pure JS Local)
 */

const PT_STOPWORDS = new Set([
  "voce", "voces", "ele", "ela", "eles", "elas", "nos",
  "tem", "temos", "tinha", "tinham", "ter",
  "que", "para", "pra", "pras", "pro", "pros", "com", "sem", "por",
  "seu", "sua", "seus", "suas", "dele", "dela", "deles", "delas",
  "outro", "outra", "outros", "outras",
  "mais", "menos", "muito", "muita", "muitos", "muitas", "pouco",
  "aqui", "ali", "la", "esse", "essa", "esses", "essas", "isso", "este", "esta", "isto",
  "onde", "como", "quando", "qual", "quais", "quem",
  "uma", "uns", "umas", "pelo", "pela", "pelos", "pelas", "num", "numa",
  "mas", "porem", "so", "sozinho", "todo", "toda", "tudo"
]);

class LayaSalesEngine {
  constructor(playbook, dealContext) {
    this.playbook = playbook || JORDAN_PLAYBOOK;
    this.dealContext = dealContext || {
      client: "Oficina Mecânica",
      product: "Landing Page + WhatsApp",
      setupPrice: 2000,
      monthlyPrice: 150,
      clientTicket: 250
    };
    this.probability = this.playbook.config.baseline_probability;
    this.talkTime = {
      meSeconds: 0,
      clientSeconds: 0
    };
    this.history = [];
    this.activeObjection = null;
    this.activeBuyingSignal = null;
    this.lastSpeaker = null;
    this.lastTimestamp = Date.now();
    this.lastCapturedSnippet = "";
  }

  /**
   * Atualiza o contexto da negociação (cliente, produto, ticket, preços).
   */
  setDealContext(ctx) {
    if (ctx && typeof ctx === "object") {
      this.dealContext = { ...this.dealContext, ...ctx };
      // Se houver uma objeção ativa, recalcula imediatamente com o novo contexto
      if (this.activeObjection) {
        this.activeObjection.jordan_script = this.playbook.getContextualScript(
          this.activeObjection.id,
          this.dealContext
        );
      }
    }
  }

  getDealContext() {
    return this.dealContext;
  }

  /**
   * Limpa e normaliza texto removendo acentos e pontuação.
   */
  normalizeText(str) {
    if (!str) return "";
    return str
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /**
   * Verifica se dois tokens têm correspondência semântica ou morfológica.
   * Evita falsos positivos onde palavras curtas ("pro") casam por acaso com palavras longas ("processo").
   */
  isTokenMatch(p, t) {
    if (p === t) return true;
    const minLen = Math.min(p.length, t.length);
    if (minLen >= 4 && (p.startsWith(t) || t.startsWith(p))) return true;
    return false;
  }

  /**
   * Algoritmo de Similaridade Semântica por N-Grams e Co-ocorrência.
   * Filtra stopwords do português para garantir foco nas palavras conceituais.
   */
  calculateSemanticSimilarity(phrase, trigger) {
    // 1. Verificação de Substring direta
    if (phrase.includes(trigger) || trigger.includes(phrase)) return 1.0;

    const filterTokens = (tokens) => tokens.filter(w => w.length > 2 && !PT_STOPWORDS.has(w));

    const pAllTokens = phrase.split(" ").filter(w => w.length > 2);
    const tAllTokens = trigger.split(" ").filter(w => w.length > 2);

    const pTokens = filterTokens(pAllTokens);
    const tTokens = filterTokens(tAllTokens);

    const finalPTokens = pTokens.length > 0 ? pTokens : pAllTokens;
    const finalTTokens = tTokens.length > 0 ? tTokens : tAllTokens;

    if (finalPTokens.length === 0 || finalTTokens.length === 0) return 0.0;

    // 2. Coincidência de tokens significativos
    let matches = 0;
    for (const t of finalTTokens) {
      if (finalPTokens.some(p => this.isTokenMatch(p, t))) {
        matches++;
      }
    }

    // Se o gatilho tem mais de 1 token, precisa casar pelo menos 2 tokens ou >= 60%
    if (finalTTokens.length > 1 && matches < 2 && (matches / finalTTokens.length) < 0.60) {
      return 0.0;
    }

    const similarity = matches / finalTTokens.length;
    return similarity;
  }

  /**
   * Detecta se uma keyword está em contexto de negação na frase.
   * Ex: "não achei caro" → retorna true (negação presente antes de "caro")
   * Ex: "o preço não é problema" → retorna true (negação presente logo após "preço")
   * Previne falsos positivos em afirmações de segurança ou aceitação do cliente.
   */
  hasNegationContext(normalizedText, keyword) {
    const kwIndex = normalizedText.indexOf(keyword);
    if (kwIndex === -1) {
      // Se não achou a palavra exata, checa se tokens longos estão presentes com negação
      const tokens = keyword.split(" ").filter(w => w.length > 3);
      for (const tok of tokens) {
        if (this.hasNegationContext(normalizedText, tok)) return true;
      }
      return false;
    }

    // 1. Verifica os 30 caracteres ANTES da keyword por palavras de negação (ex: "não achei caro")
    const windowStart = Math.max(0, kwIndex - 30);
    const windowBefore = normalizedText.substring(windowStart, kwIndex);
    const negationBefore = /\b(nao|nem|nenhum|nenhuma|nunca|jamais|zero|sem)\b/;
    if (negationBefore.test(windowBefore)) {
      const doubleNegation = /\b(nao|nem)\b.*\b(nao|nem)\b/;
      if (!doubleNegation.test(windowBefore)) {
        return true;
      }
    }

    // 2. Verifica os 35 caracteres DEPOIS da keyword (ex: "o preço não é problema", "o valor é tranquilo")
    const windowEnd = Math.min(normalizedText.length, kwIndex + keyword.length + 35);
    const windowAfter = normalizedText.substring(kwIndex + keyword.length, windowEnd);
    const negationAfter = /\b(nao|nem)\s+(e|eh|tem|sera|seria)?\s*(um\s*)?(problema|impedimento|empecilho|questao|dilema|dificuldade)\b|\b(ta|esta|e|eh)\s+(tranquilo|tranquila|ok|de boa|suave)\b/;
    if (negationAfter.test(windowAfter)) {
      return true;
    }

    return false;
  }

  /**
   * Processa um bloco de transcrição em tempo real vindo do Google Meet.
   * @param {string} speaker - "me" (Rodrigo) ou "client" (Cliente)
   * @param {string} text - Texto capturado na legenda
   */
  processSpeechSnippet(speaker, text) {
    const now = Date.now();
    const elapsedSeconds = Math.min((now - this.lastTimestamp) / 1000, 10);
    this.lastTimestamp = now;
    this.lastCapturedSnippet = `[${speaker === "me" ? "Você" : "Cliente"}]: ${text}`;

    // Atualiza o Talk-to-Listen Ratio
    if (speaker === "me") {
      this.talkTime.meSeconds += Math.max(elapsedSeconds, 1);
    } else {
      this.talkTime.clientSeconds += Math.max(elapsedSeconds, 1);
    }

    const normText = this.normalizeText(text);
    if (normText.length < 3) return this.getState();

    // Escaneia SEMPRE por Objeções e Sinais de Compra (resiliente contra erros de speaker)
    this.scanForObjections(normText);
    this.scanForBuyingSignals(normText);

    // Calcula penalidade/bônus de Talk-to-Listen Ratio
    this.evaluateTalkRatioImpact();

    // Registra no histórico da sessão
    this.history.push({
      timestamp: new Date().toISOString(),
      speaker,
      text,
      probability: this.probability
    });

    return this.getState();
  }

  /**
   * Varre o texto em busca de clusters semânticos de Objeção.
   */
  scanForObjections(text) {
    let bestMatch = null;
    let highestScore = 0;

    for (const [key, obj] of Object.entries(this.playbook.objections)) {
      // Verifica se o cluster suporta filtro de negação (ex: Preço Alto, Complexidade)
      // Objeções como 'NAO_E_MOMENTO' ou 'TEMPO_IMPLANTACAO' têm a negação como parte do próprio gatilho!
      const negationSensitive = obj.negation_cancels ?? (key === "PRECO_ALTO" || key === "COMPLEXIDADE_ADOTABILIDADE" || key === "DESCONFIANCA_TECNICA");

      let isClusterNegated = false;
      if (negationSensitive && obj.keywords) {
        for (const kw of obj.keywords) {
          const normKw = this.normalizeText(kw);
          if (normKw.length >= 3 && text.includes(normKw) && this.hasNegationContext(text, normKw)) {
            console.log(`[Laya] Negação detectada para "${normKw}" — ignorando cluster ${key}`);
            isClusterNegated = true;
            break;
          }
        }
      }
      if (isClusterNegated) continue;

      // 1. Verificação de Keywords Dominantes
      if (obj.keywords) {
        for (const kw of obj.keywords) {
          const normKw = this.normalizeText(kw);
          if (text.includes(normKw)) {
            const score = 0.95;
            if (score > highestScore) {
              highestScore = score;
              bestMatch = obj;
            }
            break;
          }
        }
      }

      // 2. Verificação Semântica por N-Grams e Substring
      if (obj.semantic_triggers) {
        for (const trigger of obj.semantic_triggers) {
          const normTrigger = this.normalizeText(trigger);
          const score = this.calculateSemanticSimilarity(text, normTrigger);

          if (score >= 0.40 && score > highestScore) {
            highestScore = score;
            bestMatch = obj;
          }
        }
      }
    }

    if (bestMatch) {
      const contextualScript = this.playbook.getContextualScript
        ? this.playbook.getContextualScript(bestMatch.id, this.dealContext)
        : bestMatch.jordan_script;

      this.activeObjection = {
        ...bestMatch,
        jordan_script: contextualScript,
        confidence: Math.round(highestScore * 100),
        detected_at: new Date().toLocaleTimeString()
      };

      // Aplica penalidade ponderada na probabilidade de fechamento
      this.adjustProbability(bestMatch.weight);
    }
  }

  /**
   * Varre o texto em busca de Sinais de Compra (Green Flags).
   */
  scanForBuyingSignals(text) {
    let bestSignal = null;
    let highestScore = 0;

    for (const [key, signal] of Object.entries(this.playbook.buying_signals)) {
      // 1. Keywords Dominantes
      if (signal.keywords) {
        for (const kw of signal.keywords) {
          const normKw = this.normalizeText(kw);
          if (text.includes(normKw)) {
            const score = 0.95;
            if (score > highestScore) {
              highestScore = score;
              bestSignal = signal;
            }
            break;
          }
        }
      }

      // 2. Semântica por N-Grams
      if (signal.semantic_triggers) {
        for (const trigger of signal.semantic_triggers) {
          const normTrigger = this.normalizeText(trigger);
          const score = this.calculateSemanticSimilarity(text, normTrigger);

          if (score >= 0.40 && score > highestScore) {
            highestScore = score;
            bestSignal = signal;
          }
        }
      }
    }

    if (bestSignal) {
      // Se há objeção ativa e a frase tem conjunção adversativa (ex: "gostei mas tá caro", "legal porém não é o momento"),
      // a objeção real sempre prevalece sobre o elogio de polidez!
      const hasAdversative = /\b(mas|porem|so que|contudo|entretanto|no entanto)\b/.test(text);
      if (this.activeObjection && hasAdversative) {
        console.log(`[Laya] Sinal "${bestSignal.id}" ignorado pois há objeção com ressalva adversativa ("${this.activeObjection.id}")`);
        return;
      }

      this.activeBuyingSignal = {
        ...bestSignal,
        confidence: Math.round(highestScore * 100),
        detected_at: new Date().toLocaleTimeString()
      };

      // Remove objeção ativa anterior apenas se não houver ressalva adversativa
      this.activeObjection = null;

      // Aplica bônus de conversão na probabilidade de fechamento
      this.adjustProbability(bestSignal.weight);
    }
  }

  /**
   * Ajusta a probabilidade respeitando os limites mínimo e máximo.
   */
  adjustProbability(delta) {
    this.probability = Math.max(
      this.playbook.config.min_probability,
      Math.min(this.playbook.config.max_probability, this.probability + delta)
    );
  }

  /**
   * Avalia a saúde do Talk-to-Listen Ratio.
   */
  evaluateTalkRatioImpact() {
    const totalTime = this.talkTime.meSeconds + this.talkTime.clientSeconds;
    if (totalTime < 20) return;

    const myPercentage = (this.talkTime.meSeconds / totalTime) * 100;

    // Se o vendedor fala demais (> 75%), reduz probabilidade gradualmente
    if (myPercentage > 75) {
      this.adjustProbability(-1);
    }
    // Se há equilíbrio saudável (35% a 55%), recompensa
    else if (myPercentage >= 35 && myPercentage <= 55) {
      this.adjustProbability(+0.5);
    }
  }

  /**
   * Retorna o snapshot completo do estado para o HUD da UI.
   */
  getState() {
    const totalTime = this.talkTime.meSeconds + this.talkTime.clientSeconds || 1;
    const myRatio = Math.round((this.talkTime.meSeconds / totalTime) * 100);
    const clientRatio = 100 - myRatio;

    let status = "NORMAL";
    let tacticalAdvice = "Ouvindo chamada no Meet... Faça perguntas abertas sobre os gargalos do cliente.";

    if (this.probability >= this.playbook.config.strike_zone_threshold) {
      status = "STRIKE_ZONE";
      tacticalAdvice = "🔥 MOMENTO DE FECHAMENTO: Pare de explicar código! Peça os dados e confirme o início!";
    } else if (this.activeObjection) {
      status = "OBJECTION_ACTIVE";
      tacticalAdvice = `⚠️ Objeção detectada: ${this.activeObjection.title}. Siga os 3 passos do Jordan abaixo!`;
    } else if (this.activeBuyingSignal) {
      status = "BUYING_SIGNAL";
      tacticalAdvice = this.activeBuyingSignal.jordan_alert;
    } else if (myRatio > 70) {
      status = "MONOLOGUE_WARNING";
      tacticalAdvice = "🚨 Você está falando demais! Devolva a palavra com: 'Como vocês resolvem isso hoje?'";
    }

    return {
      probability: Math.round(this.probability),
      status,
      tacticalAdvice,
      lastCapturedSnippet: this.lastCapturedSnippet,
      talkRatio: {
        me: myRatio,
        client: clientRatio
      },
      dealContext: this.dealContext,
      activeObjection: this.activeObjection,
      activeBuyingSignal: this.activeBuyingSignal
    };
  }

  /**
   * Limpa ou dispensa a objeção atual manualmente pelo HUD.
   */
  dismissObjection() {
    this.activeObjection = null;
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = LayaSalesEngine;
}
