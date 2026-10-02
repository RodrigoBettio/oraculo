/**
 * Oráculo Live Translator — HUD Visual Teleprompter & Legendas em Tempo Real
 * Focado 100% na compreensão imediata da fala estrangeira (Inglês ➔ Português)
 */

class TranslatorHUD {
  constructor(options = {}) {
    this.container = null;
    this.isDragging = false;
    this.dragOffset = { x: 0, y: 0 };
    this.isTabCapturing = false;
    this.fontSize = 17; // Tamanho padrão (px)
    this.isHistoryOpen = false;
    this.historyList = [];

    this.onToggleTabCapture = options.onToggleTabCapture || (() => {});

    this.init();
  }

  init() {
    if (document.getElementById("oraculo-translator-hud")) return;

    this.container = document.createElement("div");
    this.container.id = "oraculo-translator-hud";
    this.container.innerHTML = `
      <div class="hud-header" id="trans-drag-handle">
        <div class="hud-brand">
          <div class="hud-brand-dot" id="trans-status-dot"></div>
          <span>Oráculo Live Subtitles</span>
        </div>
        <div class="hud-header-right">
          <span class="hud-badge-latency" id="trans-latency-badge">⚡ ~250ms</span>
          <div class="hud-controls">
            <button class="hud-btn" id="trans-history-btn" title="Histórico da conversa">📜 Histórico</button>
            <button class="hud-btn" id="trans-toggle-btn" title="Minimizar / Expandir">_</button>
          </div>
        </div>
      </div>

      <div class="hud-body">
        <!-- BARRA DE FERRAMENTAS -->
        <div class="hud-toolbar">
          <button class="hud-tab-capture-btn" id="trans-tab-btn" title="Capturar áudio da reunião para tradução ao vivo">
            📡 Ativar Áudio da Reunião
          </button>
          <div class="hud-font-tools">
            <button class="hud-mini-btn" id="trans-font-dec" title="Diminuir fonte">A-</button>
            <button class="hud-mini-btn" id="trans-font-inc" title="Aumentar fonte">A+</button>
          </div>
        </div>

        <!-- TELEPROMPTER DE LEGENDA PRINCIPAL (AO VIVO) -->
        <div class="hud-subtitle-box">
          <div class="hud-speaker-tag" id="trans-speaker-tag">
            <div class="pulse-dot"></div>
            <span id="trans-speaker-name">Participante (EN ➔ PT)</span>
          </div>
          <div class="hud-subtitle-pt" id="trans-sub-pt">
            Aguardando fala em inglês na chamada...
          </div>
          <div class="hud-subtitle-original" id="trans-sub-orig">
            (Ative o áudio da chamada ou as legendas CC para tradução instantânea)
          </div>
        </div>

        <!-- GAVETA DE HISTÓRICO ROLÁVEL -->
        <div class="hud-history-drawer" id="trans-history-drawer">
          <div style="font-weight: 700; color: #8b949e; margin-bottom: 8px;">HISTÓRICO RECENTE:</div>
          <div id="trans-history-content">
            <div style="color: #6e7681; font-style: italic;">Nenhuma fala registrada ainda nesta reunião.</div>
          </div>
        </div>

        <!-- FOOTER COM INFORMAÇÕES -->
        <div class="hud-footer">
          <span>Gemini Live • Tradução Simultânea</span>
          <span class="hud-shortcut-hint">Pressione <kbd>Alt</kbd> + <kbd>T</kbd> para minimizar</span>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);
    this.setupEventListeners();
  }

  setupEventListeners() {
    const handle = document.getElementById("trans-drag-handle");
    const toggleBtn = document.getElementById("trans-toggle-btn");
    const tabBtn = document.getElementById("trans-tab-btn");
    const historyBtn = document.getElementById("trans-history-btn");
    const fontInc = document.getElementById("trans-font-inc");
    const fontDec = document.getElementById("trans-font-dec");

    // Toggle Minimizar
    toggleBtn?.addEventListener("click", () => {
      this.container.classList.toggle("collapsed");
      toggleBtn.innerText = this.container.classList.contains("collapsed") ? "+" : "_";
    });

    // Toggle Histórico
    historyBtn?.addEventListener("click", () => {
      this.isHistoryOpen = !this.isHistoryOpen;
      const drawer = document.getElementById("trans-history-drawer");
      drawer?.classList.toggle("open", this.isHistoryOpen);
      historyBtn.classList.toggle("active", this.isHistoryOpen);
    });

    // Ajuste de Fonte
    fontInc?.addEventListener("click", () => {
      if (this.fontSize < 24) {
        this.fontSize += 2;
        this.applyFontSize();
      }
    });

    fontDec?.addEventListener("click", () => {
      if (this.fontSize > 13) {
        this.fontSize -= 2;
        this.applyFontSize();
      }
    });

    // Captura da Aba
    tabBtn?.addEventListener("click", () => {
      this.onToggleTabCapture(!this.isTabCapturing);
    });

    // Atalho global Alt + T para minimizar/expandir
    window.addEventListener("keydown", (e) => {
      if (e.altKey && e.code === "KeyT") {
        e.preventDefault();
        this.container.classList.toggle("collapsed");
        toggleBtn.innerText = this.container.classList.contains("collapsed") ? "+" : "_";
      }
    });

    // Drag and Drop
    handle?.addEventListener("mousedown", (e) => {
      if (e.target.closest(".hud-controls") || e.target.closest("button")) return;
      this.isDragging = true;
      this.dragOffset.x = e.clientX - this.container.offsetLeft;
      this.dragOffset.y = e.clientY - this.container.offsetTop;
    });

    document.addEventListener("mousemove", (e) => {
      if (!this.isDragging) return;
      this.container.style.left = `${e.clientX - this.dragOffset.x}px`;
      this.container.style.top = `${e.clientY - this.dragOffset.y}px`;
      this.container.style.right = "auto";
      this.container.style.bottom = "auto";
    });

    document.addEventListener("mouseup", () => {
      this.isDragging = false;
    });
  }

  applyFontSize() {
    const subPt = document.getElementById("trans-sub-pt");
    if (subPt) {
      subPt.style.fontSize = `${this.fontSize}px`;
    }
  }

  setTabCaptureActive(active) {
    this.isTabCapturing = active;
    const tabBtn = document.getElementById("trans-tab-btn");
    if (tabBtn) {
      tabBtn.classList.toggle("active", active);
      tabBtn.innerText = active ? "🟢 Áudio da Reunião Conectado" : "📡 Ativar Áudio da Reunião";
    }
  }

  /**
   * Atualiza a legenda em português da fala do participante em tempo real.
   */
  updateInboundSubtitle(ptText, originalEnText = "", speakerName = "Participante") {
    const subPt = document.getElementById("trans-sub-pt");
    const subOrig = document.getElementById("trans-sub-orig");
    const speakerEl = document.getElementById("trans-speaker-name");

    if (speakerEl && speakerName) {
      speakerEl.innerText = `${speakerName} (EN ➔ PT)`;
    }

    if (subPt && ptText) {
      subPt.innerText = ptText;
    }

    if (subOrig && originalEnText) {
      subOrig.innerText = `Original: "${originalEnText}"`;
    }

    // Adiciona ao histórico recente
    if (ptText && ptText.length > 3) {
      this.addToHistory(speakerName, ptText, originalEnText);
    }
  }

  addToHistory(speaker, ptText, enText) {
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    
    // Evita duplicatas consecutivas
    const lastItem = this.historyList[this.historyList.length - 1];
    if (lastItem && lastItem.pt === ptText) return;

    this.historyList.push({
      time: timeStr,
      speaker,
      pt: ptText,
      en: enText
    });

    // Mantém no máximo 50 itens
    if (this.historyList.length > 50) {
      this.historyList.shift();
    }

    this.renderHistory();
  }

  renderHistory() {
    const content = document.getElementById("trans-history-content");
    if (!content) return;

    content.innerHTML = this.historyList
      .slice(-15)
      .reverse()
      .map(
        (item) => `
        <div class="hud-history-item">
          <div class="hud-history-time">[${item.time}] <b>${item.speaker}</b></div>
          <div class="hud-history-pt">${item.pt}</div>
          ${item.en ? `<div class="hud-history-en">"${item.en}"</div>` : ""}
        </div>
      `
      )
      .join("");
  }

  setStatus(status, latencyMs = null) {
    const dot = document.getElementById("trans-status-dot");
    const latencyBadge = document.getElementById("trans-latency-badge");

    if (dot) {
      dot.className = "hud-brand-dot";
      if (status === "READY" || status === "TRANSLATING") {
        // verde ao vivo
      } else if (status === "CONNECTING") {
        dot.classList.add("connecting");
      } else if (status === "ERROR" || status === "DISCONNECTED") {
        dot.classList.add("error");
      }
    }

    if (latencyBadge && latencyMs) {
      latencyBadge.innerText = `⚡ ~${latencyMs}ms`;
    }
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = TranslatorHUD;
}
