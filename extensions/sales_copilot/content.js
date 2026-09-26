/**
 * Oráculo Sales Copilot — Content Script Injetado no Google Meet
 * Arquitetura: Alex Vance (Senior Architect) & Tiago Tech (VP de TI)
 * Conexão com DOM de Legendas (Closed Captions) e Orquestração
 */

(function () {
  console.log("⚡ [Oráculo Sales Copilot] Inicializando no Google Meet...");

  let engine = null;
  let hud = null;
  let captionObserver = null;
  let processedPhrases = new Set();

  function startCopilot() {
    if (hud) return;

    // Inicializa o Motor Laya com o Playbook do Jordan
    engine = new LayaSalesEngine(JORDAN_PLAYBOOK);
    hud = new SalesHUD(engine);
    hud.update(engine.getState());

    console.log("✅ [Oráculo Sales Copilot] HUD e Motor Laya ativos na chamada!");

    // Observa o surgimento de legendas do Google Meet
    observeGoogleMeetCaptions();
  }

  /**
   * Monitora containers de legendas e blocos individuais de fala no Google Meet.
   */
  function observeGoogleMeetCaptions() {
    const targetNode = document.body;
    const config = { childList: true, subtree: true, characterData: true };

    captionObserver = new MutationObserver((mutations) => {
      // 1. Tenta capturar blocos individuais de fala de cada participante
      const individualBlocks = document.querySelectorAll(
        "div[jsname='YSnbTe'] > div, " +
        ".nMm5Fd, " +
        ".a4bvKc > div, " +
        "div[aria-live='polite'] > div, " +
        "[role='region'][aria-label*='caption' i] > div, " +
        "[role='region'][aria-label*='legenda' i] > div"
      );

      const targets = individualBlocks.length > 0 ? individualBlocks : document.querySelectorAll(
        "[role='region'][aria-label*='caption' i], " +
        "[role='region'][aria-label*='legenda' i], " +
        "div[aria-live='polite'], " +
        "div[jsname='YSnbTe']"
      );

      targets.forEach((block) => {
        // Tenta isolar o texto da fala excluindo o nome do autor
        const textEl = block.querySelector(".iTTPOb, .VbkSUe, span[jsname='tgaKEf']") || block;
        const text = (textEl.innerText || textEl.textContent || "").trim();

        if (text.length >= 3) {
          // Detecta quem falou
          const speakerEl = block.querySelector(".zs7Du, .NWadcf, .TBMuR, span[class*='name' i]");
          const speakerName = speakerEl ? speakerEl.innerText.toLowerCase() : "";

          // Se tiver "você" ou "you", sou eu; senão é cliente (ex: "Rodrigo Bettio", outro participante)
          const speaker = (speakerName.includes("você") || speakerName.includes("you")) ? "me" : "client";

          const phraseKey = `${speaker}:${text}`;
          if (!processedPhrases.has(phraseKey)) {
            processedPhrases.add(phraseKey);
            if (processedPhrases.size > 200) processedPhrases.clear();

            console.log(`[Sales Copilot] Fala capturada [${speaker}]: "${text}"`);
            const newState = engine.processSpeechSnippet(speaker, text);
            hud.update(newState);
          }
        }
      });
    });

    captionObserver.observe(targetNode, config);
  }

  // Tenta iniciar quando o Meet estiver pronto
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(startCopilot, 1200);
  } else {
    window.addEventListener("DOMContentLoaded", () => setTimeout(startCopilot, 1200));
  }
})();
