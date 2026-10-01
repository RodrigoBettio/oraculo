/**
 * Oráculo Live Translator — Background Service Worker (Manifest V3)
 * Orquestra o ciclo de vida do Offscreen Document e o roteamento de áudio/mensagens.
 */

let offscreenCreating = null;

/**
 * Garante que o Offscreen Document está criado e ativo.
 */
async function ensureOffscreenDocument() {
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"]
  });

  if (existingContexts.length > 0) {
    return;
  }

  if (offscreenCreating) {
    await offscreenCreating;
  } else {
    offscreenCreating = chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA", "AUDIO_PLAYBACK"],
      justification: "Processamento de streaming de áudio e conexões WebSocket da Gemini Live API"
    });
    await offscreenCreating;
    offscreenCreating = null;
    console.log("✅ [Background] Offscreen Document criado com sucesso.");
  }
}

// Inicialização na instalação
chrome.runtime.onInstalled.addListener(async () => {
  console.log("🚀 [Oráculo Live Translator] Extensão instalada com sucesso.");
  await ensureOffscreenDocument();
});

// Listener de mensagens entre Content Scripts, Popup e Offscreen
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type, payload } = message;

  (async () => {
    await ensureOffscreenDocument();

    // 1. Solicitação de Captura de Áudio da Aba (Inbound - Outro participante no Meet)
    if (type === "REQUEST_TAB_CAPTURE") {
      try {
        const tabId = sender.tab ? sender.tab.id : payload?.tabId;
        if (!tabId) {
          sendResponse({ success: false, error: "Nenhuma aba ativa identificada." });
          return;
        }

        const streamId = await chrome.tabCapture.getMediaStreamId({
          targetTabId: tabId
        });

        // Repassa o streamId para o Offscreen document iniciar a captura
        chrome.runtime.sendMessage({
          target: "OFFSCREEN",
          type: "START_TAB_CAPTURE",
          payload: { streamId, tabId }
        });

        sendResponse({ success: true, streamId });
      } catch (err) {
        console.error("[Background] Erro ao obter tabCapture streamId:", err);
        sendResponse({ success: false, error: err.message });
      }
      return;
    }

    // 2. Parar captura da aba
    if (type === "STOP_TAB_CAPTURE") {
      chrome.runtime.sendMessage({
        target: "OFFSCREEN",
        type: "STOP_TAB_CAPTURE"
      });
      sendResponse({ success: true });
      return;
    }

    // 3. Status Ping
    if (type === "PING") {
      sendResponse({ status: "alive" });
      return;
    }
  })();

  return true; // Resposta assíncrona
});
