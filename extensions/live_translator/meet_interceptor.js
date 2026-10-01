/**
 * Oráculo Live Translator — Google Meet WebRTC Audio Interceptor
 * Execução: world = "MAIN", run_at = "document_start"
 * 
 * Intercepta navigator.mediaDevices.getUserMedia para injetar um MediaStreamTrack
 * sintético no Google Meet. Permite alternar suavemente entre a voz original (Português)
 * e a voz traduzida sintetizada (Inglês) em tempo real sem desconectar a chamada.
 */

(function () {
  console.log("⚡ [Oráculo Meet Interceptor] Inicializando interceptor de áudio no mundo MAIN...");

  // Salva referência nativa antes de qualquer modificação de página
  const originalGetUserMedia = navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices);
  if (!originalGetUserMedia) {
    console.error("[Oráculo Meet Interceptor] navigator.mediaDevices.getUserMedia não disponível.");
    return;
  }

  let audioContext = null;
  let syntheticDestination = null;
  let realMicStream = null;
  let realMicSource = null;
  let passThroughGain = null;
  let translatedGain = null;
  let downsamplerNode = null;

  // Estado do modo de tradução: 'TRANSLATING' (voz em inglês) vs 'PASSTHROUGH' (voz original)
  let translationMode = "TRANSLATING";
  let audioScheduledTime = 0;

  /**
   * Converte ArrayBuffer Int16 PCM (24kHz little-endian) em AudioBuffer para reprodução.
   */
  function pcm24kToAudioBuffer(arrayBuffer) {
    if (!audioContext) return null;

    const int16Array = new Int16Array(arrayBuffer);
    const length = int16Array.length;
    const audioBuffer = audioContext.createBuffer(1, length, 24000);
    const channelData = audioBuffer.getChannelData(0);

    for (let i = 0; i < length; i++) {
      channelData[i] = int16Array[i] / 32768.0;
    }

    return audioBuffer;
  }

  /**
   * Enfileira chunks de áudio traduzido (24kHz) para tocar no track do microfone do Meet.
   */
  function queueTranslatedAudioChunk(pcmArrayBuffer) {
    if (!audioContext || !translatedGain) return;

    try {
      const audioBuffer = pcm24kToAudioBuffer(pcmArrayBuffer);
      if (!audioBuffer) return;

      const sourceNode = audioContext.createBufferSource();
      sourceNode.buffer = audioBuffer;
      sourceNode.connect(translatedGain);

      const currentTime = audioContext.currentTime;
      const startTime = Math.max(currentTime, audioScheduledTime);
      sourceNode.start(startTime);

      audioScheduledTime = startTime + audioBuffer.duration;
    } catch (e) {
      console.warn("[Oráculo Meet Interceptor] Erro ao agendar reprodução traduzida:", e);
    }
  }

  /**
   * Configura o AudioContext e o grafo de roteamento de áudio sintético.
   */
  async function setupSyntheticAudioPipeline(realStream) {
    realMicStream = realStream;

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContextClass({ latencyHint: "interactive" });

    if (audioContext.state === "suspended") {
      audioContext.resume();
    }

    realMicSource = audioContext.createMediaStreamSource(realStream);
    syntheticDestination = audioContext.createMediaStreamDestination();

    // 1. Canal de Pass-Through (Voz Original Direta)
    passThroughGain = audioContext.createGain();
    // No modo de tradução, o microfone real fica mudo para os participantes do Meet
    passThroughGain.gain.setValueAtTime(translationMode === "PASSTHROUGH" ? 1.0 : 0.0, audioContext.currentTime);
    realMicSource.connect(passThroughGain);
    passThroughGain.connect(syntheticDestination);

    // 2. Canal da Voz Traduzida (Inglês do Gemini)
    translatedGain = audioContext.createGain();
    translatedGain.gain.setValueAtTime(translationMode === "TRANSLATING" ? 1.0 : 0.0, audioContext.currentTime);
    translatedGain.connect(syntheticDestination);

    // 3. Extrator de PCM 16kHz do microfone real para enviar ao Gemini Live
    try {
      const extensionId = window.__ORACULO_TRANSLATOR_EXT_ID__ || "";
      const workletUrl = extensionId
        ? `chrome-extension://${extensionId}/audio_worklet_processor.js`
        : null;

      // Fallback seguro usando ScriptProcessor se o AudioWorklet externo tiver restrição de CORS em MAIN
      const scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);
      const targetSampleRate = 16000;
      const ratio = audioContext.sampleRate / targetSampleRate;

      scriptProcessor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        const outputLength = Math.floor(inputData.length / ratio);
        const pcm16 = new Int16Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
          const sample = inputData[Math.floor(i * ratio)];
          const clamped = Math.max(-1, Math.min(1, sample));
          pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
        }

        // Envia o chunk de 16kHz PCM para o content script isolado
        window.postMessage({
          source: "ORACULO_INTERCEPTOR",
          type: "OUTBOUND_MIC_PCM",
          buffer: Array.from(pcm16)
        }, "*");
      };

      realMicSource.connect(scriptProcessor);
      // Conecta a um nó mudo para manter o processador ativo no grafo Web Audio
      const muteNode = audioContext.createGain();
      muteNode.gain.value = 0;
      scriptProcessor.connect(muteNode);
      muteNode.connect(audioContext.destination);

      console.log("✅ [Oráculo Meet Interceptor] Grafo de áudio sintético ativo com sucesso!");
    } catch (err) {
      console.warn("[Oráculo Meet Interceptor] Erro ao iniciar extrator de PCM:", err);
    }

    return syntheticDestination.stream;
  }

  /**
   * Monkey-Patch de navigator.mediaDevices.getUserMedia
   */
  navigator.mediaDevices.getUserMedia = async function (constraints) {
    console.log("[Oráculo Meet Interceptor] getUserMedia solicitado pelo Meet:", constraints);

    // Se o Meet solicitar áudio, interceptamos e devolvemos o track sintético
    if (constraints && constraints.audio) {
      try {
        const realStream = await originalGetUserMedia(constraints);
        const syntheticStream = await setupSyntheticAudioPipeline(realStream);

        // Clona os tracks de vídeo se existirem (preserva a câmera original do Meet)
        const combinedTracks = [
          syntheticStream.getAudioTracks()[0],
          ...realStream.getVideoTracks()
        ];

        const combinedStream = new MediaStream(combinedTracks);

        // Notifica o content script que a injeção foi concluída com sucesso
        window.postMessage({
          source: "ORACULO_INTERCEPTOR",
          type: "INTERCEPTION_ATTACHED",
          audioTrackId: syntheticStream.getAudioTracks()[0]?.id
        }, "*");

        return combinedStream;
      } catch (err) {
        console.error("[Oráculo Meet Interceptor] Falha na injeção sintética, caindo no nativo:", err);
        return originalGetUserMedia(constraints);
      }
    }

    // Se solicitar apenas vídeo ou outro dispositivo, mantém o fluxo normal
    return originalGetUserMedia(constraints);
  };

  /**
   * Escuta mensagens vindas do content script isolado (hud_translator & content_translator)
   */
  window.addEventListener("message", (event) => {
    if (event.data?.source !== "ORACULO_CONTENT") return;

    const { type, payload } = event.data;

    // 1. Injeção de áudio traduzido vindo do Gemini
    if (type === "INJECT_TRANSLATED_AUDIO" && payload?.buffer) {
      const arrayBuffer = new Uint8Array(payload.buffer).buffer;
      queueTranslatedAudioChunk(arrayBuffer);
    }

    // 2. Mudança de modo (Traduzir vs Bypass Direto)
    if (type === "SET_MODE" && payload?.mode) {
      translationMode = payload.mode;
      const now = audioContext ? audioContext.currentTime : 0;

      if (passThroughGain && translatedGain) {
        if (translationMode === "TRANSLATING") {
          // Mudo o mic real para a sala, ativo o áudio traduzido
          passThroughGain.gain.setTargetAtTime(0.0, now, 0.05);
          translatedGain.gain.setTargetAtTime(1.0, now, 0.05);
          console.log("[Oráculo Meet Interceptor] 🌐 Modo ATIVO: Tradução em Inglês sendo transmitida.");
        } else {
          // Modo Bypass: voz natural em Português transmitida diretamente
          passThroughGain.gain.setTargetAtTime(1.0, now, 0.05);
          translatedGain.gain.setTargetAtTime(0.0, now, 0.05);
          console.log("[Oráculo Meet Interceptor] 🎙️ Modo BYPASS: Voz direta em Português transmitida.");
        }
      }
    }
  });

  console.log("✅ [Oráculo Meet Interceptor] Hook do getUserMedia instalado com sucesso!");
})();
