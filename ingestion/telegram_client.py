import os
import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import DialogFilter, DialogFilterChatlist, InputMessagesFilterVideo, InputMessagesFilterDocument

from config import settings

class TelegramManager:
    _instance = None
    _client = None
    _lock = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        self.session_path = str(settings.DATA_DIR / settings.TELEGRAM_SESSION_NAME)
        self._initialized = True

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    async def get_client(self) -> TelegramClient:
        """Inicializa e retorna o cliente Telethon Singleton conectado de forma resiliente."""
        lock = self._get_lock()
        async with lock:
            if not TelegramManager._client:
                if not self.api_id or not self.api_hash:
                    raise ValueError("TELEGRAM_API_ID e TELEGRAM_API_HASH devem ser configurados no .env!")
                TelegramManager._client = TelegramClient(self.session_path, self.api_id, self.api_hash)
                await asyncio.wait_for(TelegramManager._client.connect(), timeout=15.0)
            elif not TelegramManager._client.is_connected():
                try:
                    await asyncio.wait_for(TelegramManager._client.connect(), timeout=15.0)
                except Exception:
                    await self._force_reconnect()
            return TelegramManager._client

    async def _force_reconnect(self):
        """Reconecta o cliente Telethon de forma thread-safe sem quebrar workers simultâneos."""
        lock = self._get_lock()
        async with lock:
            if TelegramManager._client:
                if TelegramManager._client.is_connected():
                    return TelegramManager._client
                try:
                    await asyncio.wait_for(TelegramManager._client.connect(), timeout=15.0)
                    return TelegramManager._client
                except Exception:
                    try:
                        await asyncio.wait_for(TelegramManager._client.disconnect(), timeout=5.0)
                    except Exception:
                        pass
            TelegramManager._client = TelegramClient(self.session_path, self.api_id, self.api_hash)
            await asyncio.wait_for(TelegramManager._client.connect(), timeout=20.0)
            return TelegramManager._client

    async def is_authorized(self) -> bool:
        """Verifica se o usuário já está autenticado."""
        client = await self.get_client()
        return await client.is_user_authorized()

    async def list_folders(self) -> List[Dict[str, Any]]:
        """Lista todas as pastas de chat (Dialog Filters) da conta do usuário."""
        client = await self.get_client()
        filters_result = await client(GetDialogFiltersRequest())
        
        folders = []
        for f in filters_result.filters:
            if isinstance(f, (DialogFilter, DialogFilterChatlist)):
                title = getattr(getattr(f, "title", None), "text", str(getattr(f, "title", "")))
                folders.append({
                    "id": f.id,
                    "title": title,
                    "pinned_peers": len(getattr(f, "pinned_peers", [])),
                    "include_peers": len(getattr(f, "include_peers", []))
                })
        return folders

    async def list_groups_in_folder(self, folder_name: str) -> List[Dict[str, Any]]:
        """Lista todos os canais e grupos contidos em uma pasta de chat específica de forma resiliente."""
        client = await self.get_client()
        filters_result = await client(GetDialogFiltersRequest())
        
        target_filter = None
        for f in filters_result.filters:
            if isinstance(f, (DialogFilter, DialogFilterChatlist)):
                title = getattr(getattr(f, "title", None), "text", str(getattr(f, "title", "")))
                if title.lower() == folder_name.lower():
                    target_filter = f
                    break
        
        if not target_filter:
            available = [getattr(getattr(f, "title", None), "text", str(getattr(f, "title", ""))) for f in filters_result.filters if hasattr(f, "title")]
            raise ValueError(f"Pasta '{folder_name}' não encontrada! Pastas disponíveis: {available}")

        # Extrai IDs canônicos do Telegram usando utils.get_peer_id
        included_peers = getattr(target_filter, "include_peers", []) + getattr(target_filter, "pinned_peers", [])
        included_ids = set()
        for p in included_peers:
            try:
                included_ids.add(utils.get_peer_id(p))
            except Exception:
                continue

        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.id in included_ids and (dialog.is_group or dialog.is_channel):
                groups.append({
                    "id": dialog.id,
                    "title": dialog.title,
                    "is_group": dialog.is_group,
                    "is_channel": dialog.is_channel,
                    "unread_count": dialog.unread_count
                })
        return groups

    async def list_videos_in_group(self, group_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Lista mensagens com vídeos e cruza com a base de conhecimento para saber o que já foi estudado."""
        client = await self.get_client()
        
        # Obtém o título do grupo para escopo estrito
        group_title = ""
        try:
            entity = await client.get_entity(group_id)
            group_title = getattr(entity, "title", "") or getattr(entity, "first_name", "") or ""
        except Exception:
            pass
        gt_lower = group_title.strip().lower()

        # Mapeia o que já foi processado e estudado pelos agentes
        # 1. Carrega todas as aulas processadas pertinentes a este grupo
        processed_lessons = {}
        for p_file in settings.PROCESSED_DIR.rglob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    pdoc = json.load(f)
                    p_gname = (pdoc.get("group_name") or p_file.parent.name or "").strip().lower()
                    
                    # Pertinência ao canal atual
                    belongs_to_group = False
                    if gt_lower:
                        if p_gname and (p_gname in gt_lower or gt_lower in p_gname):
                            belongs_to_group = True
                    else:
                        belongs_to_group = True

                    vid = pdoc.get("video_id")
                    tg_mid = pdoc.get("telegram_message_id")
                    fname = pdoc.get("file_name")
                    info = {
                        "video_id": vid,
                        "telegram_message_id": tg_mid,
                        "file_name": fname,
                        "title": pdoc.get("title"),
                    }
                    if fname:
                        processed_lessons[str(fname)] = info
                    if belongs_to_group:
                        if vid:
                            processed_lessons[str(vid)] = info
                        if tg_mid:
                            processed_lessons[str(tg_mid)] = info
            except Exception:
                continue

        # 2. Carrega os agentes e cruza quem estudou o que neste grupo
        studied_by_key = {}
        for agent_file in settings.AGENTS_DIR.glob("*.json"):
            try:
                with open(agent_file, "r", encoding="utf-8") as f:
                    adata = json.load(f)
                    agent_name = adata.get("name")
                    for src in adata.get("sources", []):
                        src_gname = (src.get("group_name") or "").strip().lower()
                        if gt_lower:
                            if not (src_gname in gt_lower or gt_lower in src_gname):
                                continue

                        for les in src.get("lessons", []):
                            lid = str(les.get("lesson_id", ""))
                            studied_by_key[lid] = agent_name
                            if lid in processed_lessons:
                                p_info = processed_lessons[lid]
                                if p_info.get("telegram_message_id"):
                                    studied_by_key[str(p_info["telegram_message_id"])] = agent_name
                                if p_info.get("file_name"):
                                    studied_by_key[str(p_info["file_name"])] = agent_name
            except Exception:
                continue

        videos = []
        async for message in client.iter_messages(group_id, limit=limit, filter=InputMessagesFilterVideo):
            if message.video:
                raw_name = None
                for attr in message.video.attributes:
                    if hasattr(attr, "file_name") and attr.file_name:
                        raw_name = attr.file_name
                        break
                
                file_name = raw_name or f"video_{message.id}.mp4"
                clean_name = re.sub(r'[^\w\.-]', '_', file_name)
                lesson_key = f"video_{message.id}"
                msg_id_str = str(message.id)

                # Verifica se é estudado por message_id, lesson_key, raw_name ou clean_name
                is_studied = (
                    msg_id_str in studied_by_key 
                    or lesson_key in studied_by_key 
                    or (raw_name and raw_name in studied_by_key)
                    or clean_name in studied_by_key
                    or msg_id_str in processed_lessons
                    or lesson_key in processed_lessons
                    or (raw_name and raw_name in processed_lessons)
                    or clean_name in processed_lessons
                )

                studied_agent = (
                    studied_by_key.get(msg_id_str)
                    or studied_by_key.get(lesson_key)
                    or (raw_name and studied_by_key.get(raw_name))
                    or studied_by_key.get(clean_name)
                )

                videos.append({
                    "message_id": message.id,
                    "date": message.date.isoformat(),
                    "caption": message.message or "",
                    "duration_seconds": getattr(message.video, "duration", 0),
                    "file_size_bytes": getattr(message.video, "size", 0),
                    "file_name": clean_name,
                    "media_type": "video",
                    "is_studied": is_studied,
                    "studied_by": studied_agent
                })

        # Busca também documentos PDF anexados no canal/grupo
        async for message in client.iter_messages(group_id, limit=limit, filter=InputMessagesFilterDocument):
            if message.document:
                raw_name = None
                for attr in message.document.attributes:
                    if hasattr(attr, "file_name") and attr.file_name:
                        raw_name = attr.file_name
                        break
                mime_type = getattr(message.document, "mime_type", "") or ""
                is_pdf = (raw_name and raw_name.lower().endswith(".pdf")) or ("pdf" in mime_type.lower())
                if not is_pdf:
                    continue

                file_name = raw_name or f"doc_{message.id}.pdf"
                clean_name = re.sub(r'[^\w\.-]', '_', file_name)
                lesson_key = f"doc_{message.id}"
                msg_id_str = str(message.id)

                is_studied = (
                    msg_id_str in studied_by_key 
                    or lesson_key in studied_by_key 
                    or (raw_name and raw_name in studied_by_key)
                    or clean_name in studied_by_key
                    or msg_id_str in processed_lessons
                    or lesson_key in processed_lessons
                    or (raw_name and raw_name in processed_lessons)
                    or clean_name in processed_lessons
                )

                studied_agent = (
                    studied_by_key.get(msg_id_str)
                    or studied_by_key.get(lesson_key)
                    or (raw_name and studied_by_key.get(raw_name))
                    or studied_by_key.get(clean_name)
                )

                videos.append({
                    "message_id": message.id,
                    "date": message.date.isoformat(),
                    "caption": message.message or "",
                    "duration_seconds": 0,
                    "file_size_bytes": getattr(message.document, "size", 0),
                    "file_name": clean_name,
                    "media_type": "pdf",
                    "is_studied": is_studied,
                    "studied_by": studied_agent
                })

        return videos

    async def download_video(
        self, 
        group_id: int, 
        message_id: int, 
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """Baixa o vídeo ou documento com nome sanitizado e callback de progresso."""
        client = await self.get_client()
        try:
            message = await asyncio.wait_for(client.get_messages(group_id, ids=message_id), timeout=25.0)
        except Exception:
            await self._force_reconnect()
            client = await self.get_client()
            message = await asyncio.wait_for(client.get_messages(group_id, ids=message_id), timeout=25.0)
        
        if not message or (not message.video and not message.document):
            raise ValueError(f"Mensagem {message_id} não contém um vídeo ou documento válido.")

        dest_dir = output_dir or settings.VIDEOS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        raw_name = None
        if message.video:
            for attr in message.video.attributes:
                if hasattr(attr, "file_name") and attr.file_name:
                    raw_name = attr.file_name
                    break
            raw_name = raw_name or f"video_{message_id}.mp4"
        elif message.document:
            for attr in message.document.attributes:
                if hasattr(attr, "file_name") and attr.file_name:
                    raw_name = attr.file_name
                    break
            raw_name = raw_name or f"doc_{message_id}.pdf"

        safe_name = re.sub(r'[^\w\.-]', '_', raw_name)
        target_file = dest_dir / safe_name

        # Se já existe baixado e com tamanho consistente, reutiliza
        video_size = 0
        if hasattr(message, "file") and message.file and getattr(message.file, "size", None):
            video_size = message.file.size
        elif message.video and getattr(message.video, "size", None):
            video_size = message.video.size
        elif message.document and getattr(message.document, "size", None):
            video_size = message.document.size

        if target_file.exists() and target_file.stat().st_size > 1024:
            if video_size > 0 and target_file.stat().st_size >= (video_size * 0.95):
                if progress_callback:
                    progress_callback(target_file.stat().st_size, target_file.stat().st_size)
                return target_file

        # Timeout proporcional com folga (mínimo 600s para vídeos grandes)
        timeout_sec = max(600, int(video_size / (100 * 1024))) if video_size > 0 else 600

        for attempt in range(2):
            try:
                file_path = await asyncio.wait_for(
                    client.download_media(
                        message, 
                        file=str(target_file),
                        progress_callback=progress_callback
                    ),
                    timeout=timeout_sec
                )
                return Path(file_path)
            except (asyncio.TimeoutError, ConnectionError, Exception) as err:
                if attempt == 0:
                    await asyncio.sleep(2.0)
                    if not client.is_connected():
                        await self._force_reconnect()
                        client = await self.get_client()
                    continue
                raise RuntimeError(f"Falha ao baixar vídeo após reconexão: {err}")
