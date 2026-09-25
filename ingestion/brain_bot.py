"""
Oráculo — Bot de Ingestão do Segundo Cérebro (Obsidian)
Recebe áudios, textos e links no Telegram e grava automaticamente
no cofre Obsidian em 00_Inbox/ com frontmatter YAML e tags.
"""

import asyncio
import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeFilename

from config import settings

logger = logging.getLogger("brain_bot")

try:
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo("America/Sao_Paulo")
except Exception:
    from datetime import timezone, timedelta
    BRT = timezone(timedelta(hours=-3))

_brain_bot_client: Optional[TelegramClient] = None


def get_vault_inbox() -> Path:
    """Retorna o caminho da pasta 00_Inbox do cofre Obsidian."""
    vault = settings.OBSIDIAN_VAULT_PATH
    if not vault or not str(vault).strip():
        # Fallback para caminho padrão do usuário
        vault = Path(r"C:\Users\Rodrigo\Documents\ObsidianVault")
    inbox = vault / "00_Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip().replace(" ", "_")
    return clean[:50] if clean else "nota_sem_titulo"


async def transcribe_audio_with_gemini(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """Usa o Gemini para transcrever áudio em texto limpo e bem formatado."""
    try:
        from google import genai
        from google.genai import types

        api_key = settings.GEMINI_API_KEY
        if not api_key and settings.GEMINI_API_KEYS:
            api_key = settings.GEMINI_API_KEYS[0]

        if not api_key:
            return "[Erro: Nenhuma API Key do Gemini configurada para transcrição]"

        client = genai.Client(api_key=api_key)

        prompt = (
            "Você é um transcritor e organizador de notas de alta precisão. "
            "Transcreva o áudio a seguir com máxima fidelidade. "
            "Se o usuário estiver pensando alto ou ditando ideias, estruture em tópicos limpos. "
            "Mantenha a voz e termos originais, corrigindo apenas pontuação e concordâncias gritantes. "
            "Retorne APENAS a transcrição/nota organizada, sem comentários introdutórios."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                prompt
            ]
        )
        return response.text.strip() if response.text else "[Áudio inaudível ou vazio]"
    except Exception as e:
        logger.error(f"Erro na transcrição via Gemini: {e}")
        return f"[Falha na transcrição: {e}]"


async def extract_title_and_tags_with_gemini(content: str) -> tuple[str, list[str]]:
    """Gera um título conciso e tags relevantes para a nota."""
    try:
        from google import genai

        api_key = settings.GEMINI_API_KEY or (settings.GEMINI_API_KEYS[0] if settings.GEMINI_API_KEYS else "")
        if not api_key:
            return "Nota Rápida", ["inbox"]

        client = genai.Client(api_key=api_key)

        prompt = (
            "Analise a nota abaixo e responda em JSON com duas chaves:\n"
            '1. "title": Título conciso de 3 a 7 palavras (sem pontuação final)\n'
            '2. "tags": Lista de 2 a 4 tags temáticas em minúsculas (sem #)\n\n'
            f"Nota:\n{content[:1000]}\n\n"
            "Responda APENAS o JSON:"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        title = data.get("title", "Nota Rápida")
        tags = data.get("tags", ["inbox"])
        if "inbox" not in tags:
            tags.insert(0, "inbox")
        return title, tags
    except Exception as e:
        logger.warning(f"Erro ao extrair título/tags: {e}")
        first_line = content.strip().split("\n")[0][:40]
        return first_line or "Nota Rápida", ["inbox"]


def save_note_to_vault(title: str, content: str, note_type: str, tags: list[str]) -> Path:
    """Grava a nota com YAML frontmatter no 00_Inbox do Obsidian."""
    inbox = get_vault_inbox()
    now = datetime.now(BRT)
    timestamp_prefix = now.strftime("%Y-%m-%d_%H%M%S")
    clean_title = sanitize_filename(title)
    filename = f"{timestamp_prefix}_{clean_title}.md"
    filepath = inbox / filename

    tags_str = ", ".join(tags)

    note_text = f"""---
date: {now.isoformat()}
source: telegram
type: {note_type}
tags: [{tags_str}]
status: pendente
---

# {title}

{content}

---
_Capturado via Telegram Brain Bot em {now.strftime('%d/%m/%Y às %H:%M:%S')}_
"""

    filepath.write_text(note_text, encoding="utf-8")
    logger.info(f"📝 Nota salva no cofre: {filepath.name}")
    return filepath


async def handle_brain_message(event):
    """Processa mensagens recebidas no grupo/chat do 2º Cérebro."""
    # Ignora mensagens de bots para evitar loops
    sender = await event.get_sender()
    if sender and getattr(sender, "bot", False):
        return

    message = event.message
    now = datetime.now(BRT)

    # 1. Processamento de Áudio / Mensagem de Voz
    if message.voice or message.audio:
        try:
            status_msg = await event.reply("🎙️ _Transcrevendo áudio com Gemini..._")
            audio_bytes = await message.download_media(file=bytes)

            mime = "audio/ogg"
            if message.voice:
                mime = "audio/ogg"
            elif hasattr(message, "file") and message.file and message.file.mime_type:
                mime = message.file.mime_type

            transcription = await transcribe_audio_with_gemini(audio_bytes, mime)
            title, tags = await extract_title_and_tags_with_gemini(transcription)
            saved_path = save_note_to_vault(title, transcription, "audio", tags)

            await status_msg.edit(
                f"🧠 **Nota de Áudio Capturada!**\n\n"
                f"📌 **Título**: `{title}`\n"
                f"🏷️ **Tags**: `#{' #'.join(tags)}`\n"
                f"📂 **Arquivo**: `00_Inbox/{saved_path.name}`\n\n"
                f"📝 **Resumo**:\n_{transcription[:200]}..._\n\n"
                f"✅ _Salva no seu cofre Obsidian!_"
            )
        except Exception as e:
            logger.error(f"Erro ao processar áudio no brain bot: {e}")
            await event.reply(f"⚠️ Erro ao capturar áudio: {e}")
        return

    # 2. Processamento de Texto e Links
    text = message.text or ""
    if not text.strip():
        return

    # Comandos básicos
    if text.strip() in ("/start", "/help", "/ajuda"):
        welcome = (
            "🧠 **SEGUNDO CÉREBRO — INGESTÃO RÁPIDA**\n\n"
            "Envie qualquer coisa aqui para salvar no seu Obsidian:\n\n"
            "🎙️ **Áudios & Mensagens de Voz** → Transcrição com IA\n"
            "📝 **Textos & Pensamentos** → Tagueamento automático\n"
            "🔗 **Links & URLs** → Captura com referência\n\n"
            f"📂 As notas caem direto em `00_Inbox/` no seu computador."
        )
        await event.reply(welcome)
        return

    if text.strip() in ("/status", "/cofre"):
        inbox = get_vault_inbox()
        total_inbox = len(list(inbox.glob("*.md")))
        await event.reply(
            f"🏛️ **STATUS DO SEGUNDO CÉREBRO**\n\n"
            f"📁 **Pasta**: `{inbox}`\n"
            f"📥 **Notas na Inbox**: `{total_inbox}` notas pendentes\n"
            f"🕒 **Última checagem**: `{now.strftime('%d/%m/%Y %H:%M:%S')}`"
        )
        return

    # Processamento de nota de texto
    try:
        is_link = bool(re.search(r"https?://", text))
        note_type = "link" if is_link else "texto"

        title, tags = await extract_title_and_tags_with_gemini(text)
        if is_link and "referencia" not in tags:
            tags.append("referencia")

        saved_path = save_note_to_vault(title, text, note_type, tags)

        tipo_emoji = "🔗" if is_link else "📝"
        await event.reply(
            f"🧠 **Nota Salva no 2º Cérebro!** {tipo_emoji}\n\n"
            f"📌 **Título**: `{title}`\n"
            f"🏷️ **Tags**: `#{' #'.join(tags)}`\n"
            f"📂 **Local**: `00_Inbox/{saved_path.name}`\n\n"
            f"✅ _Disponível no seu Obsidian._"
        )
    except Exception as e:
        logger.error(f"Erro ao salvar nota de texto no brain bot: {e}")
        await event.reply(f"⚠️ Erro ao salvar nota: {e}")


async def start_brain_bot():
    """Inicia o cliente Telethon para o bot do 2º Cérebro."""
    global _brain_bot_client
    bot_token = settings.TELEGRAM_BOT_TOKEN_BRAIN
    if not bot_token:
        logger.info("ℹ️ TELEGRAM_BOT_TOKEN_BRAIN não configurado. Brain bot desativado.")
        return None

    try:
        session_path = str(settings.DATA_DIR / "oraculo_brain_bot")
        _brain_bot_client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
        await _brain_bot_client.start(bot_token=bot_token)
        logger.info("🧠 Bot do Segundo Cérebro (Brain Bot) inicializado com sucesso!")

        _brain_bot_client.add_event_handler(handle_brain_message, events.NewMessage())
        return _brain_bot_client
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Bot do 2º Cérebro: {e}")
        return None
