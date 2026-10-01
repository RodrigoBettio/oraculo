/**
 * Oráculo Live Translator — Popup Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  const apiKeyInput = document.getElementById("api-key-input");
  const toggleKeyBtn = document.getElementById("toggle-key-btn");
  const outboundLangSelect = document.getElementById("outbound-lang");
  const inboundLangSelect = document.getElementById("inbound-lang");
  const saveBtn = document.getElementById("save-btn");
  const openSimulatorBtn = document.getElementById("open-simulator-btn");
  const statusText = document.getElementById("status-text");
  const statusDot = document.getElementById("status-dot");

  // 1. Carrega dados salvos
  chrome.storage.local.get(["gemini_api_key", "translator_settings"], (data) => {
    if (data.gemini_api_key) {
      apiKeyInput.value = data.gemini_api_key;
      statusText.innerText = "Configurado";
      statusText.style.color = "#3fb950";
      statusDot.classList.remove("error");
    } else {
      statusText.innerText = "Sem Chave";
      statusText.style.color = "#f85149";
      statusDot.classList.add("error");
    }

    if (data.translator_settings) {
      if (data.translator_settings.outboundTargetLang) {
        outboundLangSelect.value = data.translator_settings.outboundTargetLang;
      }
      if (data.translator_settings.inboundTargetLang) {
        inboundLangSelect.value = data.translator_settings.inboundTargetLang;
      }
    }
  });

  // 2. Mostrar/Ocultar chave
  toggleKeyBtn.addEventListener("click", () => {
    apiKeyInput.type = apiKeyInput.type === "password" ? "text" : "password";
    toggleKeyBtn.innerText = apiKeyInput.type === "password" ? "👁️" : "🙈";
  });

  // 3. Salvar configurações
  saveBtn.addEventListener("click", () => {
    const key = apiKeyInput.value.trim();
    const settings = {
      outboundTargetLang: outboundLangSelect.value,
      inboundTargetLang: inboundLangSelect.value
    };

    chrome.storage.local.set({
      gemini_api_key: key,
      translator_settings: settings
    }, () => {
      // Notifica o Offscreen document
      chrome.runtime.sendMessage({
        target: "OFFSCREEN",
        type: "UPDATE_SETTINGS",
        payload: {
          apiKey: key,
          settings
        }
      });

      saveBtn.innerText = "Salvo com Sucesso! ✓";
      saveBtn.style.background = "#2ea043";

      statusText.innerText = key ? "Conectando..." : "Sem Chave";
      statusText.style.color = key ? "#3fb950" : "#f85149";
      statusDot.classList.toggle("error", !key);

      setTimeout(() => {
        saveBtn.innerText = "Salvar Configurações";
        saveBtn.style.background = "#238636";
      }, 1800);
    });
  });

  // 4. Abrir Simulador de Testes
  openSimulatorBtn.addEventListener("click", () => {
    chrome.tabs.create({
      url: chrome.runtime.getURL("test_simulator.html")
    });
  });
});
