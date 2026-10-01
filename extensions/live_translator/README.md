# 🌐 Oráculo Live Translator — Google Meet Real-Time Interpretation

Extensão Chrome Manifest V3 para **Tradução Simultânea em Tempo Real** no Google Meet utilizando o modelo oficial **Gemini 3.5 Live Translate** (`gemini-3.5-live-translate-preview`).

---

## 🎯 Visão Geral

- **Outbound (Você fala Português ➔ Sala ouve Inglês traduzido)**:
  - Intercepta `navigator.mediaDevices.getUserMedia` no Google Meet (`world: MAIN`).
  - Transmite áudio PCM de 16kHz via WebSocket contínuo para o Gemini Live API.
  - Recebe áudio traduzido em 24kHz PCM e injeta diretamente no track do microfone do Meet.
  - Alternância instantânea com atalho <kbd>Alt</kbd> + <kbd>T</kbd> entre voz traduzida em inglês e voz original em português.
- **Inbound (Outro participante fala Inglês ➔ Você lê Legendas em Português)**:
  - Captura áudio da reunião via `chrome.tabCapture` no Offscreen Document.
  - Mantém o áudio local da reunião audível nos fones de ouvido sem mutar a aba.
  - Gera legendas instantâneas em português no HUD flutuante com latência sub-segundo (~700ms–1.2s).

---

## 🏗️ Arquitetura de Módulos

```
extensions/live_translator/
├── manifest.json              # Configuração Manifest V3 (dual-world scripts, offscreen)
├── meet_interceptor.js        # Execução no mundo MAIN (monkey-patch getUserMedia e injeção WebRTC)
├── content_translator.js      # Execução no mundo ISOLATED (ponte entre Meet, HUD e Offscreen)
├── hud_translator.js          # Controlador da interface HUD flutuante (Glassmorphism)
├── hud_translator.css         # Estilização visual cyberpunk/dark glass
├── background.js              # Service Worker Manifest V3 e orquestrador de contextos
├── offscreen.html             # Host do Offscreen Document para Web Audio e WebSockets
├── offscreen.js               # Orquestrador das 2 pipelines do Gemini Live e tabCapture
├── gemini_live_client.js      # Cliente WebSocket contínuo com Gemini 3.5 Live Translate
├── audio_worklet_processor.js # Resampler Linear para 16kHz 16-bit Mono PCM
├── popup.html                 # Interface de configuração da chave de API e idiomas
├── popup.js                   # Lógica de persistência e acionamento
├── popup.css                  # Estilos do popup
└── test_simulator.html        # Simulador local para testar microfone e tradução sem abrir o Meet
```

---

## 🚀 Como Instalar no Google Chrome

1. Abra o navegador Google Chrome e acesse:
   `chrome://extensions/`
2. No canto superior direito, ative o **"Modo do desenvolvedor"** (Developer mode).
3. Clique no botão **"Carregar sem compactação"** (Load unpacked).
4. Selecione a pasta do projeto:
   `C:\Users\Rodrigo\.gemini\antigravity\scratch\oraculo\extensions\live_translator\`
5. Clique no ícone da extensão na barra de ferramentas do Chrome:
   - Cole sua chave de API do Gemini (`AIzaSy...`).
   - Clique em **"Salvar Configurações"**.

---

## 🧪 Como Testar no Simulador Local

Antes de entrar em uma reunião real, você pode testar todo o pipeline de áudio localmente:
1. Abra o arquivo `test_simulator.html` no Chrome (ou clique em **"Abrir Simulador de Testes"** no popup da extensão).
2. Cole sua chave de API e clique em **"Conectar"**.
3. Clique em **"🎙️ Iniciar Microfone"** e fale uma frase em português (ex: *"Olá, nós desenvolvemos sistemas de automação de alto desempenho"*).
4. Você verá sua transcrição e ouvirá a voz sintetizada em inglês nos seus alto-falantes/fones!
5. Clique nos botões de simulação em inglês para ver as legendas em português surgirem no HUD no canto inferior direito.

---

## 🎧 Dica Crítica de Uso no Google Meet

> [!IMPORTANT]
> **Use sempre fones de ouvido** durante chamadas com tradução ativa para evitar que o áudio traduzido que sai dos alto-falantes seja recapturado pelo microfone físico em loop acústico.
