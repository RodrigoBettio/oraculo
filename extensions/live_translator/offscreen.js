/**
 * Oráculo Live Translator — Offscreen Audio & WebSocket Orchestrator
 * Executa dentro do contexto Offscreen Document (sem limite de 30s de inatividade)
 * Mantém as duas sessões ativas do Gemini Live:
 * 1. Outbound (Microfone PT ➔ Áudio traduzido EN injetado no Meet)
 * 2. Inbound (Áudio da aba EN ➔ Legendas em Português no HUD)
 */

let apiKey = "";
let outboundClient = null;
let inboundClient = null;

let tabAudioContext = null;
let tabAudioStream = null;
let tabAudioSource = null;
let tabProcessorNode = null;

// Configurações padrão
let settings = {
  outboundTargetLang: "en",
  inboundTargetLang: "pt-BR",
  echoOutbound: false,
  isOutboundActive: true,
  isInboundActive: true
};

/**
 * Carrega a chave de API e configurações salvas no chrome.storage
 */
async function loadStoredConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["gemini_api_key", "translator_settings"], (data) => {
      if (data.gemini_api_key) {
        apiKey = data.gemini_api_key;
      }
      if (data.translator_settings) {
        settings = { ...settings, ...data.translator_settings };
      }
      resolve();
    });
  });
}

/**
 * Inicializa os dois clientes Gemini Live
 */
function initializeClients() {
  if (!apiKey) {
    console.warn("[Offscreen] Chave de API não informada. Aguardando configuração.");
    return;
  }

  // === CLIENTE 1: OUTBOUND (Você fala PT ➔ Sala ouve EN) ===
  if (!outboundClient) {
    outboundClient = new GeminiLiveTranslateClient({
      apiKey,
      targetLanguageCode: settings.outboundTargetLang,
      echoTargetLanguage: settings.echoOutbound,
      onAudioChunk: (pcm24kBuffer) => {
        // Envia o áudio traduzido para a aba do Meet via mensagem
        broadcastToTabs({
          type: "INJECT_TRANSLATED_AUDIO",
          buffer: Array.from(new Uint8Array(pcm24kBuffer))
        });
      },
      onInputTranscript: (text, lang) => {
        broadcastToTabs({
          type: "OUTBOUND_INPUT_TRANSCRIPT",
          text,
          lang
        });
      },
      onOutputTranscript: (text, lang) => {
        broadcastToTabs({
          type: "OUTBOUND_OUTPUT_TRANSCRIPT",
          text,
          lang
        });
      },
      onStatusChange: (statusObj) => {
        broadcastToTabs({
          type: "OUTBOUND_STATUS_CHANGE",
          status: statusObj
        });
      }
    });

    outboundClient.connect();
    console.log("✅ [Offscreen] Cliente Outbound (PT ➔ EN) inicializado.");
  }

  // === CLIENTE 2: INBOUND (Outro participante fala EN ➔ Você vê legendas em PT) ===
  if (!inboundClient) {
    inboundClient = new GeminiLiveTranslateClient({
      apiKey,
      targetLanguageCode: settings.inboundTargetLang,
      echoTargetLanguage: false,
      onInputTranscript: (text, lang) => {
        broadcastToTabs({
          type: "INBOUND_INPUT_TRANSCRIPT",
          text,
          lang
        });
      },
      onOutputTranscript: (text, lang) => {
        // Legenda traduzida em Português em tempo real!
        broadcastToTabs({
          type: "INBOUND_OUTPUT_SUBTITLE",
          text,
          lang
        });
      },
      onStatusChange: (statusObj) => {
        broadcastToTabs({
          type: "INBOUND_STATUS_CHANGE",
          status: statusObj
        });
      }
    });

    inboundClient.connect();
    console.log("✅ [Offscreen] Cliente Inbound (EN ➔ PT) inicializado.");
  }
}

/**
 * Despacha mensagem para todas as abas ativas do Google Meet.
 */
function broadcastToTabs(messagePayload) {
  chrome.tabs.query({ url: "https://meet.google.com/*" }, (tabs) => {
    tabs.forEach((tab) => {
      chrome.tabs.sendMessage(tab.id, messagePayload).catch(() => {});
    });
  });
}

/**
 * Inicia a captura de áudio da aba via chrome.tabCapture (Inbound).
 */
async function startTabCapture(streamId) {
  try {
    if (tabAudioStream) {
      stopTabCapture();
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: "tab",
          chromeMediaSourceId: streamId
        }
      },
      video: false
    });

    tabAudioStream = stream;

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    tabAudioContext = new AudioContextClass();

    tabAudioSource = tabAudioContext.createMediaStreamSource(stream);

    // CRÍTICO: Re-conectar à saída de áudio para o usuário não ficar surdo na reunião!
    tabAudioSource.connect(tabAudioContext.destination);

    // Downsampler para 16kHz Mono PCM para alimentar o inboundClient
    const targetSampleRate = 16000;
    const ratio = tabAudioContext.sampleRate / targetSampleRate;
    tabProcessorNode = tabAudioContext.createScriptProcessor(2048, 1, 1);

    tabProcessorNode.onaudioprocess = (e) => {
      if (!settings.isInboundActive || !inboundClient) return;

      const inputData = e.inputBuffer.getChannelData(0);
      const outputLength = Math.floor(inputData.length / ratio);
      const pcm16 = new Int16Array(outputLength);

      for (let i = 0; i < outputLength; i++) {
        const sample = inputData[Math.floor(i * ratio)];
        const clamped = Math.max(-1, Math.min(1, sample));
        pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
      }

      inboundClient.sendAudioChunk(pcm16.buffer);
    };

    tabAudioSource.connect(tabProcessorNode);
    // Mudo para o nó auxiliar
    const muteNode = tabAudioContext.createGain();
    muteNode.gain.value = 0;
    tabProcessorNode.connect(muteNode);
    muteNode.connect(tabAudioContext.destination);

    console.log("✅ [Offscreen] Captura de áudio da aba iniciada com sucesso (com áudio local preservado).");
  } catch (err) {
    console.error("[Offscreen] Falha ao capturar áudio da aba:", err);
  }
}

function stopTabCapture() {
  if (tabAudioStream) {
    tabAudioStream.getTracks().forEach((t) => t.stop());
    tabAudioStream = null;
  }
  if (tabAudioContext) {
    tabAudioContext.close().catch(() => {});
    tabAudioContext = null;
  }
  tabAudioSource = null;
  tabProcessorNode = null;
  console.log("[Offscreen] Captura de áudio da aba finalizada.");
}

// Ouvinte de mensagens no Offscreen Document
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target && message.target !== "OFFSCREEN") return;

  const { type, payload } = message;

  // 1. Recebe chunks PCM de 16kHz do microfone (Outbound) vindos do content script
  if (type === "PROCESS_OUTBOUND_MIC_CHUNK" && payload?.buffer) {
    if (settings.isOutboundActive && outboundClient) {
      const pcmBuffer = new Int16Array(payload.buffer).buffer;
      outboundClient.sendAudioChunk(pcmBuffer);
    }
    return;
  }

  // 2. Inicia captura da aba (Inbound)
  if (type === "START_TAB_CAPTURE" && payload?.streamId) {
    startTabCapture(payload.streamId);
    return;
  }

  // 3. Para captura da aba
  if (type === "STOP_TAB_CAPTURE") {
    stopTabCapture();
    return;
  }

  // 4. Atualização de Configurações ou Chave de API
  if (type === "UPDATE_SETTINGS" && payload) {
    if (payload.apiKey && payload.apiKey !== apiKey) {
      apiKey = payload.apiKey;
      chrome.storage.local.set({ gemini_api_key: apiKey });
      if (outboundClient) outboundClient.setApiKey(apiKey);
      if (inboundClient) inboundClient.setApiKey(apiKey);
      outboundClient?.reconnect();
      inboundClient?.reconnect();
    }

    if (payload.settings) {
      settings = { ...settings, ...payload.settings };
      chrome.storage.local.set({ translator_settings: settings });

      if (payload.settings.outboundTargetLang && outboundClient) {
        outboundClient.setTargetLanguage(payload.settings.outboundTargetLang);
      }
      if (payload.settings.inboundTargetLang && inboundClient) {
        inboundClient.setTargetLanguage(payload.settings.inboundTargetLang);
      }
    }

    sendResponse({ success: true, settings });
    return;
  }

  // 5. Consulta de Status
  if (type === "GET_STATUS") {
    sendResponse({
      hasApiKey: Boolean(apiKey),
      outboundConnected: outboundClient?.isConnected || false,
      inboundConnected: inboundClient?.isConnected || false,
      isTabCaptured: Boolean(tabAudioStream),
      settings
    });
    return;
  }
});

// Inicialização ao carregar o script
loadStoredConfig().then(() => {
  initializeClients();
});
