"""
Oráculo — Bot de Ingestão do Segundo Cérebro (Obsidian)
Recebe áudios, textos e links no Telegram e grava automaticamente
no cofre Obsidian em 00_Inbox/ com frontmatter YAML, tags e botões
interativos de triagem GTD em 1 toque (Tech, Vendas, Mente, Projetos).
"""

import asyncio
import io
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

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

# Teclado fixo do Segundo Cérebro
BRAIN_KEYBOARD = [
    [Button.text("📥 Ver Inbox"), Button.text("🏛️ Status do Cofre")],
    [Button.text("💡 Como Usar o 2º Cérebro"), Button.text("🔄 Atualizar MOCs")]
]


def get_vault_path() -> Path:
    """Retorna a raiz do cofre Obsidian."""
    vault = settings.OBSIDIAN_VAULT_PATH
    if not vault or not str(vault).strip():
        vault = Path(r"C:\Users\Rodrigo\Documents\ObsidianVault")
    vault.mkdir(parents=True, exist_ok=True)
    return vault


def get_vault_inbox() -> Path:
    """Retorna o caminho da pasta 00_Inbox do cofre Obsidian."""
    inbox = get_vault_path() / "00_Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows/Linux."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip().replace(" ", "_")
    return clean[:50] if clean else "nota_sem_titulo"


def _call_gemini_brain(prompt: str, parts: Optional[list] = None) -> str:
    """Chama a API do Gemini com fallback resiliente para o Brain Bot."""
    from google import genai
    keys = settings.GEMINI_API_KEYS or ([settings.GEMINI_API_KEY] if settings.GEMINI_API_KEY else [])
    models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
    
    if not keys:
        raise RuntimeError("Nenhuma GEMINI_API_KEY configurada.")

    for attempt in range(len(keys) * 2):
        key = keys[attempt % len(keys)]
        cl = genai.Client(api_key=key)
        for model in models_to_try:
            try:
                contents = parts if parts else prompt
                resp = cl.models.generate_content(model=model, contents=contents)
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                err_msg = str(e).upper()
                if any(x in err_msg for x in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "HIGH DEMAND"]):
                    import time
                    time.sleep(1.0)
                    continue
                else:
                    break
    raise RuntimeError("Falha ao comunicar com Gemini no Brain Bot.")


async def transcribe_audio_with_gemini(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """Usa o Gemini para transcrever áudio em texto limpo e bem formatado."""
    try:
        from google.genai import types

        prompt = (
            "Você é um transcritor e organizador de notas de alta precisão do Segundo Cérebro. "
            "Transcreva o áudio a seguir com máxima fidelidade. "
            "Se o usuário estiver pensando alto ou ditando ideias, estruture em tópicos limpos. "
            "Mantenha a voz e termos originais, corrigindo apenas pontuação e concordâncias gritantes. "
            "Retorne APENAS a transcrição/nota organizada, sem comentários introdutórios."
        )

        parts = [
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            prompt
        ]
        return _call_gemini_brain(prompt, parts=parts)
    except Exception as e:
        logger.error(f"Erro na transcrição via Gemini: {e}")
        return f"[Falha na transcrição: {e}]"


async def extract_title_and_tags_with_gemini(content: str) -> Tuple[str, List[str]]:
    """Gera um título conciso e tags relevantes para a nota."""
    try:
        prompt = (
            "Analise a nota abaixo e responda RIGOROSAMENTE em JSON com duas chaves:\n"
            '1. "title": Título conciso de 3 a 7 palavras (sem pontuação final)\n'
            '2. "tags": Lista de 2 a 4 tags temáticas em minúsculas (sem #)\n\n'
            f"Nota:\n{content[:1000]}\n\n"
            "Responda APENAS o JSON:"
        )

        text = _call_gemini_brain(prompt)
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


def save_note_to_vault(title: str, content: str, note_type: str, tags: list) -> Path:
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
status: inbox
---

# {title}

{content}

---
_Capturado via Telegram Brain Bot em {now.strftime('%d/%m/%Y às %H:%M:%S')}_
"""

    filepath.write_text(note_text, encoding="utf-8")
    logger.info(f"📝 Nota salva no cofre: {filepath.name}")
    return filepath


def get_note_triage_keyboard(filename: str) -> list:
    """Teclado interativo inline para triagem da nota para as pastas MOC com 1 toque."""
    fn_short = filename[-35:] if len(filename) > 35 else filename
    return [
        [
            Button.inline("💻 Mover p/ Tech", data=f"brn:mov:tech:{fn_short}".encode()),
            Button.inline("💼 Mover p/ Vendas", data=f"brn:mov:sales:{fn_short}".encode())
        ],
        [
            Button.inline("🧠 Mover p/ Mente", data=f"brn:mov:mind:{fn_short}".encode()),
            Button.inline("🎯 Mover p/ Projetos", data=f"brn:mov:proj:{fn_short}".encode())
        ],
        [
            Button.inline("🗑️ Descartar Nota", data=f"brn:del:{fn_short}".encode())
        ]
    ]


async def handle_brain_callback(event):
    """Processa toques em botões de triagem de notas no cofre."""
    try:
        data_str = event.data.decode("utf-8", errors="ignore")
        vault = get_vault_path()
        inbox = get_vault_inbox()

        if data_str.startswith("brn:mov:"):
            parts = data_str.split(":", 3)
            target_key = parts[2] if len(parts) > 2 else ""
            fn_sub = parts[3] if len(parts) > 3 else ""

            target_dirs = {
                "tech": ("01_Tech_Dev", "💻 Tecnologia & Desenvolvimento"),
                "sales": ("02_Vendas_Negocios", "💼 Vendas & Negócios"),
                "mind": ("03_Mente_Foco", "🧠 Mente & Performance"),
                "proj": ("04_Projetos_Ativos", "🎯 Projetos Ativos")
            }

            folder_rel, folder_label = target_dirs.get(target_key, ("00_Inbox", "Inbox"))
            dest_dir = vault / folder_rel
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Localiza o arquivo na Inbox que corresponda ao sufixo
            target_file = None
            for f in inbox.glob("*.md"):
                if f.name.endswith(fn_sub) or fn_sub in f.name:
                    target_file = f
                    break

            if target_file and target_file.exists():
                dest_file = dest_dir / target_file.name
                shutil.move(str(target_file), str(dest_file))
                await event.answer(f"✅ Arquivado em {folder_label}!", alert=True)
                await event.edit(
                    f"✅ **NOTA ARQUIVADA COM SUCESSO!**\n\n"
                    f"📁 **Pasta**: `{folder_rel}/`\n"
                    f"📝 **Arquivo**: `{dest_file.name}`\n\n"
                    f"🏛️ _A nota foi movida da Inbox para seu cofre estruturado._"
                )
            else:
                await event.answer("⚠️ Arquivo já movido ou não encontrado na Inbox.", alert=True)

        elif data_str.startswith("brn:del:"):
            fn_sub = data_str.replace("brn:del:", "").strip()
            target_file = None
            for f in inbox.glob("*.md"):
                if f.name.endswith(fn_sub) or fn_sub in f.name:
                    target_file = f
                    break
            if target_file and target_file.exists():
                target_file.unlink()
                await event.answer("🗑️ Nota descartada da Inbox!", alert=True)
                await event.edit("🗑️ **Nota descartada da Inbox do Segundo Cérebro.**")
            else:
                await event.answer("⚠️ Arquivo já removido.", alert=False)
    except Exception as e:
        logger.error(f"Erro no callback do brain bot: {e}")


async def handle_brain_message(event):
    """Processa mensagens recebidas no grupo/chat do 2º Cérebro."""
    sender = await event.get_sender()
    if sender and getattr(sender, "bot", False):
        return

    message = event.message
    now = datetime.now(BRT)

    # 1. Processamento de Áudio / Mensagem de Voz
    if message.voice or message.audio:
        try:
            status_msg = await event.reply("🎙️ _Transcrevendo áudio com Gemini 3.8 Flash..._")
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
                f"🧠 **Nota de Áudio Capturada!** 🎙️\n\n"
                f"📌 **Título**: `{title}`\n"
                f"🏷️ **Tags**: `#{' #'.join(tags)}`\n"
                f"📂 **Salvo em**: `00_Inbox/{saved_path.name}`\n\n"
                f"📝 **Resumo**:\n_{transcription[:220]}..._\n\n"
                f"👇 _Deseja arquivar esta nota em uma pasta definitiva agora?_",
                buttons=get_note_triage_keyboard(saved_path.name)
            )
        except Exception as e:
            logger.error(f"Erro ao processar áudio no brain bot: {e}")
            await event.reply(f"⚠️ Erro ao capturar áudio: {e}", buttons=BRAIN_KEYBOARD)
        return

    # 2. Processamento de Texto e Links
    text = message.text or ""
    if not text.strip():
        return

    # Comandos e botões táteis
    txt_clean = text.strip().lower()
    if txt_clean in ("/start", "/help", "/ajuda", "💡 como usar o 2º cérebro"):
        welcome = (
            "🧠 **SEGUNDO CÉREBRO — INGESTÃO & GTD**\n\n"
            "Envie qualquer coisa neste chat para gravar no seu Obsidian:\n\n"
            "🎙️ **Áudios & Ditados** → Transcrição instantânea com IA\n"
            "📝 **Pensamentos & Notas** → Tagueamento automático\n"
            "🔗 **Links & Referências** → Captura estruturada\n\n"
            "⚡ **Triagem Rápida**: Assim que salvar, botões inline permitem mover a nota direto para:\n"
            "• `01_Tech_Dev/`\n"
            "• `02_Vendas_Negocios/`\n"
            "• `03_Mente_Foco/`\n"
            "• `04_Projetos_Ativos/`\n\n"
            f"📁 Local no computador: `{get_vault_path()}`"
        )
        await event.reply(welcome, buttons=BRAIN_KEYBOARD)
        return

    if txt_clean in ("/status", "/cofre", "📥 ver inbox", "🏛️ status do cofre"):
        vault = get_vault_path()
        inbox = get_vault_inbox()
        notes = list(inbox.glob("*.md"))
        
        # Estatísticas por pasta
        tech_count = len(list((vault / "01_Tech_Dev").glob("*.md")))
        sales_count = len(list((vault / "02_Vendas_Negocios").glob("*.md")))
        mind_count = len(list((vault / "03_Mente_Foco").glob("*.md")))
        proj_count = len(list((vault / "04_Projetos_Ativos").glob("*.md")))

        recent_inbox = "\n".join([f"• `{n.name[:35]}...`" for n in notes[:5]]) if notes else "📭 _Inbox vazia e organizada!_"

        status_msg = (
            f"🏛️ **PANORAMA DO SEGUNDO CÉREBRO**\n\n"
            f"📥 **00_Inbox**: `{len(notes)}` notas pendentes de triagem\n"
            f"💻 **01_Tech**: `{tech_count}` notas arquivadas\n"
            f"💼 **02_Vendas**: `{sales_count}` notas arquivadas\n"
            f"🧠 **03_Mente**: `{mind_count}` notas arquivadas\n"
            f"🎯 **04_Projetos**: `{proj_count}` notas arquivadas\n\n"
            f"📋 **Últimas notas na Inbox**:\n{recent_inbox}\n\n"
            f"🕒 _Atualizado em {now.strftime('%d/%m/%Y às %H:%M:%S')}_"
        )
        await event.reply(status_msg, buttons=BRAIN_KEYBOARD)
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
            f"📂 **Salvo em**: `00_Inbox/{saved_path.name}`\n\n"
            f"👇 _Deseja arquivar esta nota em uma pasta definitiva?_",
            buttons=get_note_triage_keyboard(saved_path.name)
        )
    except Exception as e:
        logger.error(f"Erro ao salvar nota de texto no brain bot: {e}")
        await event.reply(f"⚠️ Erro ao salvar nota: {e}", buttons=BRAIN_KEYBOARD)


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
        _brain_bot_client.add_event_handler(handle_brain_callback, events.CallbackQuery())
        return _brain_bot_client
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Bot do 2º Cérebro: {e}")
        return None
