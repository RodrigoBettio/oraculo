/**
 * Oráculo Live Translator — Content Script (World = ISOLATED)
 * Observa tanto o áudio da chamada (via TabCapture) quanto o DOM de legendas nativas do Meet (CC),
 * garantindo redundância total e latência ultrabaixa para legendas em Português.
 */

(function () {
  console.log("⚡ [Oráculo Live Subtitles] Inicializando no Google Meet...");

  let hud = null;
  let captionObserver = null;
  let processedCaptionHashes = new Set();

  function initTranslator() {
    if (hud) return;

    hud = new TranslatorHUD({
      onToggleTabCapture: (start) => {
        if (start) {
          chrome.runtime.sendMessage({ type: "REQUEST_TAB_CAPTURE" }, (response) => {
            if (response?.success) {
              hud.setTabCaptureActive(true);
            } else {
              console.warn("[ContentTranslator] Falha ao capturar áudio da aba:", response?.error);
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

    // 1. Escuta legendas traduzidas vindas do Offscreen Document (via TabCapture + Gemini Live)
    chrome.runtime.onMessage.addListener((message) => {
      const { type } = message;

      if (type === "INBOUND_OUTPUT_SUBTITLE" && message.text) {
        hud.updateInboundSubtitle(message.text, message.originalEn || "", "Participante");
      }

      if (type === "INBOUND_STATUS_CHANGE" && message.status) {
        hud.setStatus(message.status.status);
      }
    });

    // 2. Observador Instantâneo do DOM do Google Meet (se o botão CC estiver ativo)
    observeGoogleMeetDomCaptions();

    console.log("✅ [Oráculo Live Subtitles] Teleprompter e observador de legendas ativos!");
  }

  /**
   * Monitora o DOM de legendas nativas do Google Meet (Closed Captions).
   * Se o usuário ou alguém ligar o 'CC' do Meet, capturamos o texto em inglês instantaneamente
   * e traduzimos em menos de 200ms!
   */
  function observeGoogleMeetDomCaptions() {
    const targetNode = document.body;
    const config = { childList: true, subtree: true, characterData: true };

    captionObserver = new MutationObserver(() => {
      const captionBlocks = document.querySelectorAll(
        "div[jsname='YSnbTe'] > div, " +
        ".nMm5Fd, " +
        ".a4bvKc > div, " +
        "div[aria-live='polite'] > div, " +
        "[role='region'][aria-label*='caption' i] > div, " +
        "[role='region'][aria-label*='legenda' i] > div"
      );

      captionBlocks.forEach((block) => {
        // Extrai o nome do participante que está falando
        const speakerEl = block.querySelector(".zs7Du, .NWadcf, .TBMuR, span[class*='speaker' i]");
        const speakerName = (speakerEl?.innerText || "Participante").trim();

        // Extrai o texto da fala excluindo o nome do autor
        const textEl = block.querySelector(".iTTPOb, .VbkSUe, span[jsname='tgaKEf']") || block;
        let text = (textEl.innerText || textEl.textContent || "").trim();

        // Remove o nome do autor do início do texto se estiver duplicado
        if (speakerEl && text.startsWith(speakerName)) {
          text = text.replace(speakerName, "").trim();
        }

        // Se você mesmo está falando (marcado como 'Você' ou 'You'), ignora
        const isMe = /^(voc[eê]|you)$/i.test(speakerName);
        if (isMe) return;

        if (text.length >= 4) {
          const hash = `${speakerName}:${text}`;
          if (!processedCaptionHashes.has(hash)) {
            processedCaptionHashes.add(hash);
            if (processedCaptionHashes.size > 200) {
              const first = processedCaptionHashes.values().next().value;
              processedCaptionHashes.delete(first);
            }

            // Envia o texto em inglês para o Offscreen document traduzir imediatamente
            requestDomTranslation(text, speakerName);
          }
        }
      });
    });

    captionObserver.observe(targetNode, config);
  }

  let translationDebounce = null;
  function requestDomTranslation(enText, speakerName) {
    if (translationDebounce) clearTimeout(translationDebounce);

    translationDebounce = setTimeout(() => {
      chrome.runtime.sendMessage({
        target: "OFFSCREEN",
        type: "TRANSLATE_TEXT_SNIPPET",
        payload: { text: enText, speaker: speakerName }
      }, (response) => {
        if (response?.ptText) {
          hud.updateInboundSubtitle(response.ptText, enText, speakerName);
        }
      });
    }, 150);
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(initTranslator, 1000);
  } else {
    window.addEventListener("DOMContentLoaded", () => setTimeout(initTranslator, 1000));
  }
})();
