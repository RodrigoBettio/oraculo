"""
Oráculo — LinkedIn Invitation Copilot (Playwright CDP Edition)
Conecta-se ao seu Chrome aberto (via porta de depuração 9222),
lê os convites de conexão pendentes, classifica o perfil (Recruiter, Tech ou Founder),
aceita a conexão e dispara a mensagem personalizada correspondente com intervalos humanos.

Como iniciar o Chrome antes de rodar este script:
  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\Users\\Rodrigo\\AppData\\Local\\Google\\Chrome\\User Data"
"""

import sys
import time
import random
import asyncio
from typing import Tuple

from playwright.async_api import async_playwright

# Força UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def classify_headline(headline: str) -> str:
    text = (headline or "").lower()
    if any(k in text for k in ["recruiter", "recrutador", "talent", "rh", "people", "recruiting", "headhunter", "sourcing"]):
        return "recruiter"
    if any(k in text for k in ["founder", "fundador", "ceo", "diretor", "sócio", "socio", "proprietário", "owner", "co-founder"]):
        return "founder"
    if any(k in text for k in ["cto", "tech lead", "engenheiro", "desenvolvedor", "developer", "software", "arquiteto", "tech"]):
        return "tech_lead"
    return "recruiter"


def build_message(profile_type: str, full_name: str, headline: str) -> str:
    first_name = full_name.split()[0] if full_name else "tudo bem"
    
    # Tenta extrair empresa
    company = ""
    for marker in [" na ", " no ", " @ ", " at "]:
        if marker in headline.lower():
            company = headline.split(marker, 1)[1].split("-")[0].split("|")[0].split(",")[0].strip()
            break
    
    comp_str = f" na {company}" if company else ""

    if profile_type == "founder":
        return (
            f"Opa {first_name}, obrigado pelo convite para conectar! "
            f"Vi que você lidera projetos{comp_str}. "
            f"Atuo como Arquiteto de Software e IA, ajudando operações a mapearem processos e eliminarem gargalos operacionais (Ontologia Tech). "
            f"Sempre bom expandir a rede com outros líderes. Como estão os desafios de operação por aí este ano?"
        )
    elif profile_type == "tech_lead":
        return (
            f"Opa {first_name}, obrigado pela conexão! "
            f"Acompanho o que seu time constrói{comp_str}. "
            f"Atuo forte com arquitetura backend em Python, IA e automação de fluxos com APIs. "
            f"Como estão os desafios técnicos da equipe por aí? Se estiverem buscando reforço para o time técnico ou posições remotas, "
            f"adoraria bater um papo rápido de 10 minutos."
        )
    else:
        return (
            f"Opa {first_name}, obrigado pelo convite! É um prazer conectar. "
            f"Vi que você atua com recrutamento{comp_str}. "
            f"Atualmente estou mapeando novos desafios como Desenvolvedor Python / Automação e IA (tenho projetos em produção com FastAPI, microsserviços e integração de agentes). "
            f"Como estão as posições em aberto para tecnologia e engenharia por aí no momento? Se tiver algo no meu perfil, adoraria compartilhar meu portfólio prático."
        )


async def run_copilot(limit: int = 25):
    print("=" * 60)
    print("🚀 ORÁCULO — LINKEDIN INVITATION COPILOT")
    print(f"🎯 Meta: Processar com segurança lote de {limit} convites.")
    print("=" * 60)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"❌ Não foi possível conectar ao Chrome na porta 9222: {e}")
            print("\n💡 Como abrir o Chrome pronto para o robô:")
            print('   Start-Process chrome.exe -ArgumentList "--remote-debugging-port=9222"')
            return

        contexts = browser.contexts
        if not contexts:
            print("❌ Nenhuma aba do Chrome encontrada.")
            return
        
        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
        
        target_url = "https://www.linkedin.com/mynetwork/invitation-manager/"
        if "invitation-manager" not in page.url:
            print(f"🌐 Navegando para {target_url}...")
            await page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)

        cards = await page.query_selector_all(".invitation-card")
        print(f"📋 Encontrados {len(cards)} convites na tela.")

        if not cards:
            print("⚠️ Nenhum cartão de convite localizado.")
            return

        processed = 0
        for idx, card in enumerate(cards[:limit], 1):
            try:
                title_el = await card.query_selector(".invitation-card__title, .artdeco-entity-lockup__title")
                subtitle_el = await card.query_selector(".invitation-card__subtitle, .artdeco-entity-lockup__subtitle")
                accept_btn = await card.query_selector('button[aria-label*="Aceitar"], button[aria-label*="Accept"]')

                full_name = (await title_el.inner_text()).strip() if title_el else ""
                headline = (await subtitle_el.inner_text()).strip() if subtitle_el else ""

                p_type = classify_headline(headline)
                msg = build_message(p_type, full_name, headline)

                print(f"\n[{idx}/{limit}] 👤 {full_name} | {headline[:45]}")
                print(f"   🏷️ Categoria: {p_type.upper()}")
                print(f"   💬 Mensagem pré-pronta: {msg[:80]}...")

                if accept_btn:
                    print("   👉 Clicando em Aceitar...")
                    await accept_btn.click()
                    await asyncio.sleep(2.5)

                    # Tenta abrir mensagem
                    msg_btn = await card.query_selector('button[aria-label*="Mensagem"], button[aria-label*="Message"]')
                    if msg_btn:
                        await msg_btn.click()
                        await asyncio.sleep(2)

                        # Encontra campo de texto
                        editor = await page.query_selector('.msg-form__contenteditable[contenteditable="true"]')
                        if editor:
                            await editor.focus()
                            await page.keyboard.type(msg, delay=random.randint(20, 50))
                            await asyncio.sleep(1.5)

                            # Envia
                            send_btn = await page.query_selector('.msg-form__send-button, button[type="submit"]')
                            if send_btn and await send_btn.is_enabled():
                                await send_btn.click()
                                print("   🚀 Mensagem enviada com sucesso!")
                                await asyncio.sleep(1.5)

                            # Fecha dock
                            close_btn = await page.query_selector('.msg-overlay-bubble-header__control--close')
                            if close_btn:
                                await close_btn.click()

                    processed += 1

                # Intervalo anti-spam seguro (8 a 14 segundos)
                sleep_time = random.uniform(8.0, 14.0)
                print(f"   ⏳ Intervalo humano de {sleep_time:.1f}s antes do próximo...")
                await asyncio.sleep(sleep_time)

            except Exception as item_err:
                print(f"   ⚠️ Erro ao processar item {idx}: {item_err}")
                continue

        print(f"\n🎉 Lote de {processed} convites finalizado com 100% de segurança!")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    asyncio.run(run_copilot(count))
