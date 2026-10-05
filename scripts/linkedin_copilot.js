/**
 * Oráculo — LinkedIn AI-Powered Smart Copilot
 * Conecta-se ao cérebro do Oráculo (Gemini 3.8 Flash) para analisar
 * cada perfil individualmente e gerar abordagens hiper-humanas sob medida.
 * 
 * Como usar:
 * 1. Abra o LinkedIn em: https://www.linkedin.com/mynetwork/invitation-manager/
 * 2. Abra o Console (F12)
 * 3. Cole este código e dê Enter.
 */

(async function runOraculoLinkedInCopilot() {
    console.log("🧠 [Oráculo AI Copilot] Conectando ao cérebro do Oráculo...");

    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    const API_URL = "http://34.46.39.111/api/linkedin/smart-message";

    async function generateAIMessage(fullName, headline) {
        try {
            const resp = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ full_name: fullName, headline: headline })
            });
            if (resp.ok) {
                const data = await resp.json();
                return data.message;
            }
        } catch (e) {
            console.warn("⚠️ Fallback local acionado:", e);
        }

        // Fallback humanizado caso a API esteja inacessível
        const firstName = fullName.split(" ")[0];
        return `Oi ${firstName}, obrigado pela conexão! Muito bom conectar com você. Sou desenvolvedor focado em Python, automação e Inteligência Artificial. Como estão os desafios e projetos por aí no momento? Se souber de oportunidades ou reforço na área técnica, adoraria trocar uma ideia rápida!`;
    }

    const cards = document.querySelectorAll(".invitation-card");
    console.log(`📋 ${cards.length} convites localizados na página.`);

    if (cards.length === 0) {
        alert("⚠️ Nenhum cartão de convite encontrado. Certifique-se de estar em https://www.linkedin.com/mynetwork/invitation-manager/");
        return;
    }

    const BATCH_LIMIT = 25; // Lote seguro de 25 por sessão
    let processed = 0;

    for (let i = 0; i < Math.min(cards.length, BATCH_LIMIT); i++) {
        const card = cards[i];
        const titleEl = card.querySelector(".invitation-card__title, .artdeco-entity-lockup__title");
        const subtitleEl = card.querySelector(".invitation-card__subtitle, .artdeco-entity-lockup__subtitle");
        const acceptBtn = card.querySelector('button[aria-label*="Aceitar"], button[aria-label*="Accept"]');

        const fullName = titleEl ? titleEl.innerText.trim() : "";
        const headline = subtitleEl ? subtitleEl.innerText.trim() : "";

        console.log(`\n=========================================`);
        console.log(`[${i + 1}/${BATCH_LIMIT}] 👤 ${fullName}`);
        console.log(`💼 Cargo: "${headline}"`);
        console.log(`🤖 Oráculo analisando perfil e redigindo mensagem com IA...`);

        const messageText = await generateAIMessage(fullName, headline);
        console.log(`💬 Mensagem Gerada pela IA:\n"${messageText}"`);

        if (acceptBtn) {
            console.log("👉 Clicando em Aceitar convite...");
            acceptBtn.click();
            processed++;
            await sleep(2500);

            // Procura botão Mensagem
            const msgBtn = card.querySelector('button[aria-label*="Mensagem"], button[aria-label*="Message"]');
            if (msgBtn) {
                console.log("✉️ Abrindo chat...");
                msgBtn.click();
                await sleep(2000);

                const editor = document.querySelector('.msg-form__contenteditable[contenteditable="true"]');
                if (editor) {
                    editor.focus();
                    document.execCommand('insertText', false, messageText);
                    await sleep(1500);

                    const sendBtn = document.querySelector('.msg-form__send-button, button[type="submit"]');
                    if (sendBtn && !sendBtn.disabled) {
                        console.log("🚀 Enviando mensagem personalizada...");
                        sendBtn.click();
                    } else {
                        console.log("⚠️ Botão de envio não habilitado.");
                    }
                    await sleep(1500);

                    const closeBtn = document.querySelector('.msg-overlay-bubble-header__control--close');
                    if (closeBtn) closeBtn.click();
                }
            } else {
                console.log("ℹ️ Botão de mensagem não exibido no card. Convite aceito com sucesso.");
            }
        }

        // Intervalo anti-spam seguro (8 a 13 segundos)
        const delay = Math.floor(Math.random() * 5000) + 8000;
        console.log(`⏳ Aguardando ${Math.round(delay / 1000)}s antes do próximo perfil para segurança anti-spam...`);
        await sleep(delay);
    }

    console.log(`\n🎉 [Oráculo Copilot] Lote finalizado! ${processed} convites processados com IA.`);
    alert(`🎉 Lote de ${processed} convites processado com IA com sucesso!\nFaça uma pausa antes do próximo lote.`);
})();
