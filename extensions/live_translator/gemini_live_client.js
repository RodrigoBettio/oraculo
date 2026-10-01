/**
 * Oráculo Live Translator — Cliente WebSocket para Gemini Live Translate API
 * Gerencia conexão contínua, streaming de áudio PCM 16kHz e recepção de áudio 24kHz + transcrições.
 */

class GeminiLiveTranslateClient {
  constructor(options = {}) {
    this.apiKey = options.apiKey || "";
    this.model = options.model || "gemini-3.5-live-translate-preview";
    this.targetLanguageCode = options.targetLanguageCode || "en";
    this.echoTargetLanguage = options.echoTargetLanguage ?? false;
    
    this.ws = null;
    this.isConnected = false;
    this.isSetupComplete = false;
    this.connectionStartTime = 0;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;

    // Callbacks de eventos
    this.onAudioChunk = options.onAudioChunk || (() => {});
    this.onInputTranscript = options.onInputTranscript || (() => {});
    this.onOutputTranscript = options.onOutputTranscript || (() => {});
    this.onStatusChange = options.onStatusChange || (() => {});
    this.onError = options.onError || (() => {});
  }

  setApiKey(key) {
    this.apiKey = key;
  }

  setTargetLanguage(langCode) {
    if (this.targetLanguageCode !== langCode) {
      this.targetLanguageCode = langCode;
      if (this.isConnected) {
        console.log(`[GeminiLive] Mudança de idioma para "${langCode}". Reconectando sessão...`);
        this.reconnect();
      }
    }
  }

  connect() {
    if (!this.apiKey) {
      this.notifyStatus("ERROR", "Chave de API do Gemini não configurada.");
      return;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.notifyStatus("CONNECTING", "Conectando ao Gemini Live...");

    const wsUrl = `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=${encodeURIComponent(this.apiKey)}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[GeminiLive] WebSocket Conectado. Enviando configuração inicial...");
        this.isConnected = true;
        this.connectionStartTime = Date.now();
        this.reconnectAttempts = 0;
        this.sendSetupMessage();
      };

      this.ws.onmessage = (event) => {
        this.handleServerMessage(event.data);
      };

      this.ws.onerror = (err) => {
        console.error("[GeminiLive] Erro no WebSocket:", err);
        this.notifyStatus("ERROR", "Erro de conexão com o Gemini Live API.");
        this.onError(err);
      };

      this.ws.onclose = (event) => {
        console.warn(`[GeminiLive] Conexão encerrada (código: ${event.code}, motivo: "${event.reason}")`);
        this.isConnected = false;
        this.isSetupComplete = false;
        this.notifyStatus("DISCONNECTED", "Desconectado do Gemini.");
        
        // Tenta reconexão automática se não foi encerramento voluntário
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
          console.log(`[GeminiLive] Tentativa de reconexão #${this.reconnectAttempts} em ${delay}ms...`);
          this.reconnectTimeout = setTimeout(() => this.connect(), delay);
        }
      };
    } catch (e) {
      console.error("[GeminiLive] Falha ao instanciar WebSocket:", e);
      this.notifyStatus("ERROR", e.message);
    }
  }

  sendSetupMessage() {
    const setup = {
      setup: {
        model: `models/${this.model}`,
        generationConfig: {
          responseModalities: ["AUDIO"],
          inputAudioTranscription: {},
          outputAudioTranscription: {},
          translationConfig: {
            targetLanguageCode: this.targetLanguageCode,
            echoTargetLanguage: this.echoTargetLanguage
          }
        }
      }
    };

    this.ws.send(JSON.stringify(setup));
  }

  handleServerMessage(data) {
    try {
      let response;
      if (typeof data === "string") {
        response = JSON.parse(data);
      } else {
        return;
      }

      // 1. Resposta de Setup Completo
      if (response.setupComplete) {
        console.log("[GeminiLive] ✅ Setup da sessão de tradução concluído!");
        this.isSetupComplete = true;
        this.notifyStatus("READY", `Pronto para traduzir ➔ ${this.targetLanguageCode.toUpperCase()}`);
        return;
      }

      // 2. Conteúdo do Servidor (Áudio e Transcrições)
      if (response.serverContent) {
        const content = response.serverContent;

        // Transcrição de Entrada (o que o locutor falou no idioma de origem)
        if (content.inputTranscription && content.inputTranscription.text) {
          const text = content.inputTranscription.text;
          const lang = content.inputTranscription.languageCode || "";
          this.onInputTranscript(text, lang);
        }

        // Transcrição de Saída (o texto traduzido)
        if (content.outputTranscription && content.outputTranscription.text) {
          const text = content.outputTranscription.text;
          const lang = content.outputTranscription.languageCode || "";
          this.onOutputTranscript(text, lang);
        }

        // Partes de áudio geradas pelo modelo (24kHz 16-bit PCM little-endian)
        if (content.modelTurn?.parts) {
          for (const part of content.modelTurn.parts) {
            if (part.inlineData && part.inlineData.data) {
              const base64Audio = part.inlineData.data;
              const pcmBuffer = this.base64ToArrayBuffer(base64Audio);
              this.onAudioChunk(pcmBuffer);
            }
          }
        }

        // Interrupção de fala
        if (content.interrupted) {
          console.log("[GeminiLive] Interrupção detectada.");
        }
      }
    } catch (e) {
      console.error("[GeminiLive] Erro ao parsear mensagem do servidor:", e);
    }
  }

  /**
   * Envia pacote de áudio PCM de 16kHz (em Base64) para tradução em tempo real.
   */
  sendAudioChunk(pcmArrayBuffer) {
    if (!this.isConnected || !this.isSetupComplete || !this.ws) {
      return false;
    }

    if (this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }

    try {
      const base64Str = this.arrayBufferToBase64(pcmArrayBuffer);
      const message = {
        realtimeInput: {
          audio: {
            data: base64Str,
            mimeType: "audio/pcm;rate=16000"
          }
        }
      };

      this.ws.send(JSON.stringify(message));
      return true;
    } catch (e) {
      console.warn("[GeminiLive] Falha ao enviar chunk de áudio:", e);
      return false;
    }
  }

  /**
   * Sinaliza o fim do fluxo de áudio para flush de buffers do servidor.
   */
  sendAudioStreamEnd() {
    if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        realtimeInput: {
          audioStreamEnd: true
        }
      }));
    }
  }

  notifyStatus(status, details = "") {
    this.onStatusChange({
      status,
      details,
      isConnected: this.isConnected,
      isSetupComplete: this.isSetupComplete,
      targetLanguage: this.targetLanguageCode,
      uptimeSeconds: this.connectionStartTime ? Math.round((Date.now() - this.connectionStartTime) / 1000) : 0
    });
  }

  reconnect() {
    this.disconnect();
    setTimeout(() => this.connect(), 400);
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      try {
        this.ws.close(1000, "Encerramento solicitado pelo cliente");
      } catch (e) {}
      this.ws = null;
    }

    this.isConnected = false;
    this.isSetupComplete = false;
    this.notifyStatus("DISCONNECTED", "Desconectado.");
  }

  // Utilitários de conversão binária
  arrayBufferToBase64(buffer) {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  base64ToArrayBuffer(base64) {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = GeminiLiveTranslateClient;
}
