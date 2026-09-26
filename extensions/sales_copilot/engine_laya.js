/**
 * Oráculo Sales Copilot — Motor Laya de Decisão Rápida (System 1)
 * Arquitetura: Bruno (AI Builder) & Tiago Tech (VP de TI)
 * Latência de Inferência: < 50ms (Zero-blocking, Pure JS Local)
 */

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
   * Algoritmo de Similaridade Semântica por N-Grams e Co-ocorrência.
   */
  calculateSemanticSimilarity(phrase, trigger) {
    const pTokens = phrase.split(" ").filter(w => w.length > 2);
    const tTokens = trigger.split(" ").filter(w => w.length > 2);

    if (pTokens.length === 0 || tTokens.length === 0) return 0.0;

    // 1. Verificação de Substring direta
    if (phrase.includes(trigger) || trigger.includes(phrase)) return 1.0;

    // 2. Coincidência de tokens significativos (Jaccard ponderado)
    let matches = 0;
    for (const t of tTokens) {
      if (pTokens.some(p => p.includes(t) || t.includes(p))) {
        matches++;
      }
    }

    const similarity = matches / tTokens.length;
    return similarity;
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
      // 1. Verificação de Keywords Dominantes (Garante match para palavras-chave como 'caro', 'salgado', etc.)
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
      this.activeBuyingSignal = {
        ...bestSignal,
        confidence: Math.round(highestScore * 100),
        detected_at: new Date().toLocaleTimeString()
      };

      // Remove objeção ativa anterior (o cliente avançou na Linha Reta)
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
