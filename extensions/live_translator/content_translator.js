/**
 * Oráculo Live Translator — Content Script (World = ISOLATED)
 * Faz a ponte de comunicação entre o interceptor no mundo MAIN (meet_interceptor.js),
 * a interface HUD e o motor de áudio no Offscreen Document.
 */

(function () {
  console.log("⚡ [Oráculo Live Translator] Inicializando Content Script no Google Meet...");

  let hud = null;
  let lastOutboundPt = "";
  let lastInboundEn = "";

  function initTranslator() {
    if (hud) return;

    hud = new TranslatorHUD({
      onModeChange: (mode) => {
        // Envia o novo modo para o interceptor no mundo MAIN
        window.postMessage({
          source: "ORACULO_CONTENT",
          type: "SET_MODE",
          payload: { mode }
        }, "*");
      },
      onToggleTabCapture: (start) => {
        if (start) {
          chrome.runtime.sendMessage({ type: "REQUEST_TAB_CAPTURE" }, (response) => {
            if (response?.success) {
              hud.setTabCaptureActive(true);
            } else {
              console.warn("[ContentTranslator] Falha ao capturar aba:", response?.error);
              hud.setTabCaptureActive(false);
            }
          });
        } else {
          chrome.runtime.sendMessage({ type: "STOP_TAB_CAPTURE" }, () => {
            hud.setTabCaptureActive(false);
          });
        }
      }
    });

    // 1. Escuta eventos vindos do interceptor do Google Meet (mundo MAIN)
    window.addEventListener("message", (event) => {
      if (event.data?.source !== "ORACULO_INTERCEPTOR") return;

      const { type, buffer, audioTrackId } = event.data;

      // Pacote PCM 16kHz do microfone para envio ao Gemini Live
      if (type === "OUTBOUND_MIC_PCM" && buffer) {
        chrome.runtime.sendMessage({
          target: "OFFSCREEN",
          type: "PROCESS_OUTBOUND_MIC_CHUNK",
          payload: { buffer }
        });
      }

      if (type === "INTERCEPTION_ATTACHED") {
        console.log(`[ContentTranslator] ✅ Interceptor de microfone acoplado ao track: ${audioTrackId}`);
        hud.setStatus("READY");
      }
    });

    // 2. Escuta mensagens vindas do Offscreen Document e Background
    chrome.runtime.onMessage.addListener((message) => {
      const { type } = message;

      // A. Áudio traduzido em inglês recebido do Gemini ➔ Repassar para o mundo MAIN injetar no Meet!
      if (type === "INJECT_TRANSLATED_AUDIO" && message.buffer) {
        window.postMessage({
          source: "ORACULO_CONTENT",
          type: "INJECT_TRANSLATED_AUDIO",
          payload: { buffer: message.buffer }
        }, "*");
      }

      // B. Transcrição do que você falou (Outbound PT)
      if (type === "OUTBOUND_INPUT_TRANSCRIPT" && message.text) {
        lastOutboundPt = message.text;
        hud.updateOutboundSpeech(lastOutboundPt);
      }

      // C. Transcrição traduzida que a sala ouviu (Outbound EN)
      if (type === "OUTBOUND_OUTPUT_TRANSCRIPT" && message.text) {
        hud.updateOutboundSpeech(lastOutboundPt, message.text);
      }

      // D. Transcrição do participante em inglês (Inbound EN original)
      if (type === "INBOUND_INPUT_TRANSCRIPT" && message.text) {
        lastInboundEn = message.text;
      }

      // E. Legenda traduzida em Português recebida (Inbound PT)
      if (type === "INBOUND_OUTPUT_SUBTITLE" && message.text) {
        hud.updateInboundSubtitle(message.text, lastInboundEn);
      }

      // F. Status do motor Gemini Live
      if (type === "OUTBOUND_STATUS_CHANGE" && message.status) {
        hud.setStatus(message.status.status);
      }
    });

    console.log("✅ [Oráculo Live Translator] HUD e ponte de comunicação ativos!");
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(initTranslator, 1000);
  } else {
    window.addEventListener("DOMContentLoaded", () => setTimeout(initTranslator, 1000));
  }
})();
