/**
 * Oráculo Live Translator — Audio Worklet Resampler & PCM Encoder
 * Converte áudio de entrada (44.1kHz / 48kHz Float32) para 16kHz 16-bit Mono PCM
 * Latência de buffer: ~100ms (1600 amostras a 16kHz)
 */

class PcmDownsamplerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetSampleRate = 16000;
    this.sourceSampleRate = options?.processorOptions?.sourceSampleRate || sampleRate;
    this.downsampleRatio = this.sourceSampleRate / this.targetSampleRate;
    
    // Buffer acumulador para pacotes de 100ms (1600 amostras a 16kHz)
    this.chunkSize = 1600;
    this.outputBuffer = new Int16Array(this.chunkSize);
    this.outputBufferIndex = 0;
    
    this.samplePosition = 0;
    this.isActive = true;

    this.port.onmessage = (event) => {
      if (event.data?.type === 'SET_ACTIVE') {
        this.isActive = Boolean(event.data.active);
      }
    };
  }

  process(inputs, outputs, parameters) {
    if (!this.isActive) return true;

    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    // Se houver múltiplos canais (estéreo), converte para mono fazendo média
    const channelCount = input.length;
    const inputLength = input[0].length;
    const monoChannel = new Float32Array(inputLength);

    if (channelCount === 1) {
      monoChannel.set(input[0]);
    } else {
      for (let i = 0; i < inputLength; i++) {
        let sum = 0;
        for (let ch = 0; ch < channelCount; ch++) {
          sum += input[ch][i];
        }
        monoChannel[i] = sum / channelCount;
      }
    }

    // Resampling com interpolação linear para 16kHz
    while (this.samplePosition < inputLength) {
      const idx = Math.floor(this.samplePosition);
      const frac = this.samplePosition - idx;
      const s0 = monoChannel[idx];
      const s1 = (idx + 1 < inputLength) ? monoChannel[idx + 1] : s0;
      const sample = s0 + frac * (s1 - s0);

      // Conversão de Float32 [-1.0, 1.0] para Int16 [-32768, 32767]
      const clamped = Math.max(-1, Math.min(1, sample));
      const int16 = clamped < 0 ? clamped * 32768 : clamped * 32767;

      this.outputBuffer[this.outputBufferIndex++] = Math.round(int16);

      // Quando atinge o tamanho de 100ms (1600 amostras), despacha o buffer
      if (this.outputBufferIndex >= this.chunkSize) {
        const payload = new Int16Array(this.outputBuffer);
        this.port.postMessage({
          type: 'PCM_CHUNK',
          buffer: payload.buffer
        }, [payload.buffer]);

        this.outputBuffer = new Int16Array(this.chunkSize);
        this.outputBufferIndex = 0;
      }

      this.samplePosition += this.downsampleRatio;
    }

    this.samplePosition -= inputLength;
    return true;
  }
}

registerProcessor('pcm-downsampler-processor', PcmDownsamplerProcessor);
