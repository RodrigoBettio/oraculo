/**
 * Oráculo Live Translator — Interface do HUD Flutuante no Google Meet
 * Renderiza legendas traduzidas em tempo real e controles de transmissão de áudio.
 */

class TranslatorHUD {
  constructor(options = {}) {
    this.container = null;
    this.isDragging = false;
    this.dragOffset = { x: 0, y: 0 };
    this.currentMode = "TRANSLATING"; // 'TRANSLATING' | 'PASSTHROUGH'
    this.isTabCapturing = false;

    this.onModeChange = options.onModeChange || (() => {});
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
          <span>Oráculo Live Translator</span>
        </div>
        <div class="hud-header-right">
          <span class="hud-badge-latency" id="trans-latency-badge">⚡ ~850ms</span>
          <div class="hud-controls">
            <button class="hud-btn" id="trans-toggle-btn" title="Minimizar / Expandir">_</button>
          </div>
        </div>
      </div>

      <div class="hud-body">
        <!-- SELETOR DE MODO -->
        <div class="hud-mode-selector">
          <button class="hud-mode-btn active translating" id="trans-mode-translate" title="Sua voz em português é traduzida e falada em inglês na chamada">
            🌐 Traduzir (PT ➔ EN)
          </button>
          <button class="hud-mode-btn" id="trans-mode-passthrough" title="Transmite sua voz original em português sem tradução">
            🎙️ Voz Direta (Bypass)
          </button>
        </div>

        <!-- CAIXA DE LEGENDA RECEBIDA (INBOUND: PARTICIPANTE FALA EM INGLÊS ➔ VOCÊ LÊ EM PORTUGUÊS) -->
        <div class="hud-subtitle-box">
          <div class="hud-subtitle-header">
            <span>Legenda em Português (Ao Vivo)</span>
            <button class="hud-tab-capture-btn" id="trans-tab-btn" title="Capturar áudio da reunião para traduzir a fala dos participantes em legendas">
              📡 Capturar Áudio da Chamada
            </button>
          </div>
          <div class="hud-subtitle-pt" id="trans-sub-pt">
            Aguardando fala dos participantes...
          </div>
          <div class="hud-subtitle-original" id="trans-sub-orig">
            (Ative a captura de áudio para legendas em tempo real)
          </div>
        </div>

        <!-- CAIXA DE SUA FALA ENVIADA (OUTBOUND: VOCÊ FALOU EM PT ➔ TRANSMITIDO EM EN) -->
        <div class="hud-outbound-box">
          <div class="hud-outbound-header">
            <span>Sua Transmissão para a Sala</span>
            <span id="trans-outbound-status" style="color: #3fb950;">● Ao Vivo</span>
          </div>
          <div class="hud-outbound-pt" id="trans-out-pt">
            Você: (fale em português no microfone...)
          </div>
          <div class="hud-outbound-en" id="trans-out-en">
            Sala ouve: (áudio em inglês será sintetizado)
          </div>
        </div>

        <!-- FOOTER COM ATALHOS -->
        <div class="hud-footer">
          <span>Gemini 3.5 Live Translate</span>
          <span class="hud-shortcut-hint">Alternar: <kbd>Alt</kbd> + <kbd>T</kbd></span>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);
    this.setupEventListeners();
  }

  setupEventListeners() {
    const handle = document.getElementById("trans-drag-handle");
    const toggleBtn = document.getElementById("trans-toggle-btn");
    const modeTranslate = document.getElementById("trans-mode-translate");
    const modePassthrough = document.getElementById("trans-mode-passthrough");
    const tabBtn = document.getElementById("trans-tab-btn");

    // Toggle Minimizar
    toggleBtn?.addEventListener("click", () => {
      this.container.classList.toggle("collapsed");
      toggleBtn.innerText = this.container.classList.contains("collapsed") ? "+" : "_";
    });

    // Seletor de Modo Traduzir
    modeTranslate?.addEventListener("click", () => {
      this.setMode("TRANSLATING");
    });

    // Seletor de Modo Pass-Through
    modePassthrough?.addEventListener("click", () => {
      this.setMode("PASSTHROUGH");
    });

    // Captura da Aba
    tabBtn?.addEventListener("click", () => {
      this.onToggleTabCapture(!this.isTabCapturing);
    });

    // Atalho global Alt + T
    window.addEventListener("keydown", (e) => {
      if (e.altKey && e.code === "KeyT") {
        e.preventDefault();
        const nextMode = this.currentMode === "TRANSLATING" ? "PASSTHROUGH" : "TRANSLATING";
        this.setMode(nextMode);
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

  setMode(mode) {
    this.currentMode = mode;
    const modeTranslate = document.getElementById("trans-mode-translate");
    const modePassthrough = document.getElementById("trans-mode-passthrough");
    const outStatus = document.getElementById("trans-outbound-status");

    if (mode === "TRANSLATING") {
      modeTranslate?.classList.add("active", "translating");
      modePassthrough?.classList.remove("active", "passthrough");
      if (outStatus) {
        outStatus.innerText = "● Traduzindo EN";
        outStatus.style.color = "#3fb950";
      }
    } else {
      modePassthrough?.classList.add("active", "passthrough");
      modeTranslate?.classList.remove("active", "translating");
      if (outStatus) {
        outStatus.innerText = "● Voz Direta PT";
        outStatus.style.color = "#79c0ff";
      }
    }

    this.onModeChange(mode);
  }

  setTabCaptureActive(active) {
    this.isTabCapturing = active;
    const tabBtn = document.getElementById("trans-tab-btn");
    if (tabBtn) {
      tabBtn.classList.toggle("active", active);
      tabBtn.innerText = active ? "🟢 Legendas Ativas" : "📡 Capturar Áudio da Chamada";
    }
  }

  /**
   * Atualiza a legenda em português da fala de outros participantes.
   */
  updateInboundSubtitle(ptText, originalEnText = "") {
    const subPt = document.getElementById("trans-sub-pt");
    const subOrig = document.getElementById("trans-sub-orig");
    if (subPt && ptText) {
      subPt.innerText = ptText;
    }
    if (subOrig && originalEnText) {
      subOrig.innerText = `Original: "${originalEnText}"`;
    }
  }

  /**
   * Atualiza o log da fala enviada pelo usuário.
   */
  updateOutboundSpeech(ptText, enTranslatedText = "") {
    const outPt = document.getElementById("trans-out-pt");
    const outEn = document.getElementById("trans-out-en");
    if (outPt && ptText) {
      outPt.innerText = `Você: "${ptText}"`;
    }
    if (outEn && enTranslatedText) {
      outEn.innerText = `Sala ouve: "${enTranslatedText}"`;
    }
  }

  setStatus(status, latencyMs = null) {
    const dot = document.getElementById("trans-status-dot");
    const latencyBadge = document.getElementById("trans-latency-badge");

    if (dot) {
      dot.className = "hud-brand-dot";
      if (status === "READY" || status === "TRANSLATING") {
        // normal live green
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
