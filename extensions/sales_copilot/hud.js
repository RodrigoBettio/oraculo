/**
 * Oráculo Sales Copilot — Gerenciador da Interface do HUD
 * Arquitetura: Alex Vance & Caio Copywriter
 * Execução: Local, Sem Bloqueio, Alta Legibilidade
 */

const DEAL_PRESETS = {
  mecanica: {
    client: "Oficina Mecânica",
    product: "Landing Page + Agendamento WhatsApp",
    setupPrice: 2000,
    monthlyPrice: 150,
    clientTicket: 250
  },
  artista: {
    client: "Artista / Músico",
    product: "Site Institucional + Plataforma",
    setupPrice: 3000,
    monthlyPrice: 100,
    clientTicket: 1500
  },
  scraping: {
    client: "Empresa de Scraping",
    product: "Robô de Extração de Dados",
    setupPrice: 12000,
    monthlyPrice: 0,
    clientTicket: 5000
  },
  teste: {
    client: "Cliente Teste",
    product: "Oferta Simbólica",
    setupPrice: 1,
    monthlyPrice: 0,
    clientTicket: 1
  }
};

class SalesHUD {
  constructor(engine) {
    this.engine = engine;
    this.container = null;
    this.isDragging = false;
    this.dragOffset = { x: 0, y: 0 };
    this.recognition = null;
    this.isMicActive = false;
    this.isDrawerOpen = false;

    // Carrega contexto salvo no localStorage
    this.loadSavedDealContext();

    this.init();
  }

  loadSavedDealContext() {
    try {
      const saved = localStorage.getItem("oraculo_sales_deal_context");
      if (saved) {
        const parsed = JSON.parse(saved);
        this.engine.setDealContext(parsed);
      }
    } catch (e) {
      console.warn("[SalesHUD] Falha ao carregar contexto salvo:", e);
    }
  }

  saveDealContext(ctx) {
    try {
      localStorage.setItem("oraculo_sales_deal_context", JSON.stringify(ctx));
    } catch (e) {
      console.warn("[SalesHUD] Falha ao salvar contexto:", e);
    }
  }

  init() {
    if (document.getElementById("oraculo-sales-hud")) return;

    const ctx = this.engine.getDealContext();

    this.container = document.createElement("div");
    this.container.id = "oraculo-sales-hud";
    this.container.innerHTML = `
      <div class="hud-header" id="hud-drag-handle">
        <div class="hud-brand">
          <div class="hud-brand-dot"></div>
          <span>Jordan HUD (Laya)</span>
        </div>
        <div class="hud-controls">
          <button class="hud-btn" id="hud-mic-btn" title="Ativar Microfone Direto">🎙️</button>
          <button class="hud-btn" id="hud-deal-btn" title="Configurar Contexto do Negócio">⚙️</button>
          <button class="hud-btn" id="hud-toggle-btn" title="Minimizar / Expandir">_</button>
        </div>
      </div>

      <div class="hud-body">
        <!-- CONTEXTO DO NEGÓCIO (BADGE CLICÁVEL) -->
        <div class="hud-deal-badge" id="hud-deal-badge" title="Clique para editar parâmetros do negócio">
          <span class="hud-deal-badge-icon">💼</span>
          <span class="hud-deal-badge-text" id="hud-deal-badge-text">${ctx.client} • Setup R$ ${ctx.setupPrice} ${ctx.monthlyPrice > 0 ? "• R$ " + ctx.monthlyPrice + "/m" : ""}</span>
          <span class="hud-deal-badge-tag">⚙️</span>
        </div>

        <!-- GAVETA DE CONTEXTO DO NEGÓCIO (EXPANSÍVEL) -->
        <div class="hud-deal-drawer" id="hud-deal-drawer" style="display: none;">
          <div class="hud-drawer-header">
            <span>Parâmetros da Negociação</span>
            <button class="hud-drawer-close" id="hud-drawer-close">✕</button>
          </div>

          <div class="hud-presets-label">Presets Rápidos:</div>
          <div class="hud-presets-grid">
            <button class="hud-preset-btn" data-preset="mecanica">🛠️ Oficina Tio</button>
            <button class="hud-preset-btn" data-preset="artista">🎨 Artista</button>
            <button class="hud-preset-btn" data-preset="scraping">🤖 Scraping</button>
            <button class="hud-preset-btn" data-preset="teste">🧪 Teste R$ 1</button>
          </div>

          <div class="hud-drawer-form">
            <div class="hud-form-group">
              <label>Cliente / Nicho</label>
              <input type="text" id="deal-client" value="${ctx.client || ""}" placeholder="Ex: Oficina Mecânica">
            </div>
            <div class="hud-form-group">
              <label>Produto Ofertado</label>
              <input type="text" id="deal-product" value="${ctx.product || ""}" placeholder="Ex: Landing Page + WhatsApp">
            </div>
            <div class="hud-form-row">
              <div class="hud-form-group">
                <label>Setup (R$)</label>
                <input type="number" id="deal-setup" value="${ctx.setupPrice || 0}">
              </div>
              <div class="hud-form-group">
                <label>Mensal (R$)</label>
                <input type="number" id="deal-monthly" value="${ctx.monthlyPrice || 0}">
              </div>
              <div class="hud-form-group">
                <label>Ticket (R$)</label>
                <input type="number" id="deal-ticket" value="${ctx.clientTicket || 100}">
              </div>
            </div>
            <button class="hud-save-btn" id="hud-save-deal-btn">Aplicar Parâmetros ao Jordan</button>
          </div>
        </div>

        <!-- LIVE TICKER DE CAPTURA -->
        <div class="hud-ticker">
          <span class="hud-ticker-dot" id="hud-ticker-dot"></span>
          <span class="hud-ticker-text" id="hud-ticker-text">Aguardando fala (Ative legendas [CC])</span>
        </div>

        <!-- SCORE DE FECHAMENTO -->
        <div class="hud-score-card">
          <div class="hud-score-header">
            <span class="hud-score-label">Probabilidade de Fechar</span>
            <span class="hud-score-val" id="hud-score-text">50%</span>
          </div>
          <div class="hud-score-bar-bg">
            <div class="hud-score-bar-fill" id="hud-score-fill"></div>
          </div>
        </div>

        <!-- TALK-TO-LISTEN RATIO -->
        <div class="hud-ratio-card">
          <div class="hud-ratio-labels">
            <span>Você: <b id="hud-ratio-me">50%</b></span>
            <span>Cliente: <b id="hud-ratio-client">50%</b></span>
          </div>
          <div class="hud-ratio-bar">
            <div class="hud-ratio-me" id="hud-bar-me"></div>
            <div class="hud-ratio-client" id="hud-bar-client"></div>
          </div>
        </div>

        <!-- MENSAGEM / ALERTA TÁTICO -->
        <div class="hud-advice-box" id="hud-advice-text">
          Ouvindo chamada no Meet... Faça perguntas abertas sobre os gargalos do cliente.
        </div>

        <!-- CARTÃO DINÂMICO DE OBJEÇÃO -->
        <div class="hud-objection-card" id="hud-obj-card">
          <div class="hud-obj-header">
            <span class="hud-obj-badge">Objeção Detectada</span>
            <span class="hud-obj-title" id="hud-obj-name">Objeção</span>
          </div>
          <div class="hud-obj-steps">
            <div class="hud-step">
              <span class="hud-step-num">1.</span>
              <span class="hud-step-text" id="hud-step-1">Concorde com a dor...</span>
            </div>
            <div class="hud-step">
              <span class="hud-step-num">2.</span>
              <span class="hud-step-text" id="hud-step-2">Redirecione para o valor...</span>
            </div>
            <div class="hud-step">
              <span class="hud-step-num">3.</span>
              <span class="hud-step-text" id="hud-step-3">Feche com baixo atrito...</span>
            </div>
          </div>
          <button class="hud-dismiss-btn" id="hud-obj-dismiss">Marcar como contornada ✓</button>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);
    this.setupEventListeners();
  }

  setupEventListeners() {
    const handle = document.getElementById("hud-drag-handle");
    const toggleBtn = document.getElementById("hud-toggle-btn");
    const dealBtn = document.getElementById("hud-deal-btn");
    const dealBadge = document.getElementById("hud-deal-badge");
    const drawerClose = document.getElementById("hud-drawer-close");
    const saveDealBtn = document.getElementById("hud-save-deal-btn");
    const dismissBtn = document.getElementById("hud-obj-dismiss");
    const micBtn = document.getElementById("hud-mic-btn");

    // Toggle Minimizar
    toggleBtn.addEventListener("click", () => {
      this.container.classList.toggle("collapsed");
      toggleBtn.innerText = this.container.classList.contains("collapsed") ? "+" : "_";
    });

    // Toggle Drawer de Contexto
    const toggleDrawer = () => {
      const drawer = document.getElementById("hud-deal-drawer");
      this.isDrawerOpen = !this.isDrawerOpen;
      drawer.style.display = this.isDrawerOpen ? "block" : "none";
      dealBtn.classList.toggle("active", this.isDrawerOpen);
    };

    dealBtn?.addEventListener("click", toggleDrawer);
    dealBadge?.addEventListener("click", toggleDrawer);
    drawerClose?.addEventListener("click", toggleDrawer);

    // Presets
    document.querySelectorAll(".hud-preset-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const presetKey = e.currentTarget.getAttribute("data-preset");
        const preset = DEAL_PRESETS[presetKey];
        if (preset) {
          document.getElementById("deal-client").value = preset.client;
          document.getElementById("deal-product").value = preset.product;
          document.getElementById("deal-setup").value = preset.setupPrice;
          document.getElementById("deal-monthly").value = preset.monthlyPrice;
          document.getElementById("deal-ticket").value = preset.clientTicket;

          this.applyDealContextForm();
        }
      });
    });

    // Salvar formulário de contexto
    saveDealBtn?.addEventListener("click", () => {
      this.applyDealContextForm();
      toggleDrawer();
    });

    // Dismiss Objeção
    dismissBtn?.addEventListener("click", () => {
      this.engine.dismissObjection();
      this.update(this.engine.getState());
    });

    // Mic Direto (Web Speech API)
    micBtn?.addEventListener("click", () => {
      this.toggleDirectMic();
    });

    // Drag and Drop
    handle.addEventListener("mousedown", (e) => {
      if (e.target.closest(".hud-controls")) return;
      this.isDragging = true;
      this.dragOffset.x = e.clientX - this.container.offsetLeft;
      this.dragOffset.y = e.clientY - this.container.offsetTop;
    });

    document.addEventListener("mousemove", (e) => {
      if (!this.isDragging) return;
      this.container.style.left = `${e.clientX - this.dragOffset.x}px`;
      this.container.style.top = `${e.clientY - this.dragOffset.y}px`;
      this.container.style.right = "auto";
    });

    document.addEventListener("mouseup", () => {
      this.isDragging = false;
    });
  }

  applyDealContextForm() {
    const client = document.getElementById("deal-client").value.trim() || "Cliente";
    const product = document.getElementById("deal-product").value.trim() || "Solução";
    const setupPrice = parseFloat(document.getElementById("deal-setup").value) || 0;
    const monthlyPrice = parseFloat(document.getElementById("deal-monthly").value) || 0;
    const clientTicket = parseFloat(document.getElementById("deal-ticket").value) || 100;

    const newContext = { client, product, setupPrice, monthlyPrice, clientTicket };
    this.engine.setDealContext(newContext);
    this.saveDealContext(newContext);

    // Atualiza texto da badge
    this.updateDealBadge(newContext);
    this.update(this.engine.getState());
  }

  updateDealBadge(ctx) {
    const badgeText = document.getElementById("hud-deal-badge-text");
    if (badgeText) {
      const monthlyStr = ctx.monthlyPrice > 0 ? ` • R$ ${ctx.monthlyPrice}/m` : "";
      badgeText.innerText = `${ctx.client} • Setup R$ ${ctx.setupPrice}${monthlyStr}`;
    }
  }

  /**
   * Ativa/Desativa o microfone direto do navegador via Web Speech API
   * (independente de legendas do Google Meet!).
   */
  toggleDirectMic() {
    const micBtn = document.getElementById("hud-mic-btn");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Seu navegador não suporta Web Speech API nativa.");
      return;
    }

    if (this.isMicActive && this.recognition) {
      this.recognition.stop();
      this.isMicActive = false;
      micBtn.classList.remove("active");
      this.setTicker("Microfone direto desativado", false);
      return;
    }

    try {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = "pt-BR";

      this.recognition.onstart = () => {
        this.isMicActive = true;
        micBtn.classList.add("active");
        this.setTicker("🎙️ Microfone ativo e escutando...", true);
      };

      this.recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }

        if (transcript.trim().length > 3) {
          const state = this.engine.processSpeechSnippet("client", transcript);
          this.update(state);
        }
      };

      this.recognition.onerror = (e) => {
        console.warn("[Oráculo Sales Copilot] Erro no microfone:", e.error);
        if (e.error === "not-allowed") {
          alert("Permissão de microfone negada no navegador.");
        }
      };

      this.recognition.onend = () => {
        if (this.isMicActive) {
          try { this.recognition.start(); } catch (err) {}
        }
      };

      this.recognition.start();
    } catch (e) {
      console.error("[Oráculo Sales Copilot] Falha ao iniciar reconhecimento:", e);
    }
  }

  setTicker(text, isActive = true) {
    const tickerText = document.getElementById("hud-ticker-text");
    const tickerDot = document.getElementById("hud-ticker-dot");
    if (tickerText) tickerText.innerText = text;
    if (tickerDot) {
      if (isActive) tickerDot.classList.add("active");
      else tickerDot.classList.remove("active");
    }
  }

  /**
   * Atualiza o HUD com base no novo estado emitido pelo LayaSalesEngine.
   */
  update(state) {
    if (!this.container) return;

    // Atualiza Deal Badge
    if (state.dealContext) {
      this.updateDealBadge(state.dealContext);
    }

    // Atualiza Ticker
    if (state.lastCapturedSnippet) {
      this.setTicker(state.lastCapturedSnippet, true);
    }

    // Atualiza Probabilidade
    const scoreText = document.getElementById("hud-score-text");
    const scoreFill = document.getElementById("hud-score-fill");
    scoreText.innerText = `${state.probability}%`;
    scoreFill.style.width = `${state.probability}%`;

    if (state.probability >= 75) {
      scoreText.style.color = "#3fb950";
    } else if (state.probability >= 45) {
      scoreText.style.color = "#e3b341";
    } else {
      scoreText.style.color = "#f85149";
    }

    // Atualiza Talk Ratio
    document.getElementById("hud-ratio-me").innerText = `${state.talkRatio.me}%`;
    document.getElementById("hud-ratio-client").innerText = `${state.talkRatio.client}%`;
    document.getElementById("hud-bar-me").style.width = `${state.talkRatio.me}%`;
    document.getElementById("hud-bar-client").style.width = `${state.talkRatio.client}%`;

    // Atualiza Conselho Tático
    const adviceBox = document.getElementById("hud-advice-text");
    adviceBox.innerText = state.tacticalAdvice;
    if (state.status === "STRIKE_ZONE") {
      adviceBox.classList.add("strike");
    } else {
      adviceBox.classList.remove("strike");
    }

    // Atualiza Cartão de Objeção
    const objCard = document.getElementById("hud-obj-card");
    if (state.activeObjection) {
      objCard.classList.add("active");
      document.getElementById("hud-obj-name").innerText = state.activeObjection.title;
      document.getElementById("hud-step-1").innerText = state.activeObjection.jordan_script.step1_agree;
      document.getElementById("hud-step-2").innerText = state.activeObjection.jordan_script.step2_pivot;
      document.getElementById("hud-step-3").innerText = state.activeObjection.jordan_script.step3_close;
    } else {
      objCard.classList.remove("active");
    }
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = SalesHUD;
}
