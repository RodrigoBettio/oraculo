import io
import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from config import settings

logger = logging.getLogger(__name__)

# Extensões e MimeTypes suportados para aulas
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".mp3", ".m4a", ".wav"}
VIDEO_MIME_TYPES = {
    "video/mp4", "video/x-matroska", "video/quicktime", "video/x-msvideo", 
    "video/webm", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/wav"
}

# Extensões suportadas para arquivos de apoio e complementares por tema/módulo
SUPPORT_FILE_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".json", ".py", ".js", ".ts", ".html", ".css",
    ".docx", ".doc", ".zip", ".csv", ".pptx", ".ppt", ".xml", ".yaml", ".yml", ".sql", ".ipynb"
}


class GoogleDriveManager:
    """Gerenciador de integração com Google Drive (Pastas Compartilhadas e Shared Drives).
    Suporta autenticação transparente via Service Account (headless/servidor) ou OAuth 2.0."""

    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly"
    ]

    _course_cache: Dict[str, Any] = {}

    def __init__(self):
        self.service = None
        self.auth_type = "none" # "service_account", "oauth", "oauth_needs_login", "none"
        self.service_account_email = None
        self.user_email = None
        self.user_display_name = None
        self._authenticate()

    def _authenticate(self):
        """Inicializa o cliente autenticado da API v3 do Google Drive."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            # 1. Modo Conta de Serviço (se o arquivo existir)
            sa_path = settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE
            if sa_path and sa_path.exists():
                try:
                    with open(sa_path, "r", encoding="utf-8") as f:
                        sa_data = json.load(f)
                        self.service_account_email = sa_data.get("client_email")
                    
                    creds = service_account.Credentials.from_service_account_file(
                        str(sa_path), scopes=self.SCOPES
                    )
                    self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
                    self.auth_type = "service_account"
                    logger.info(f"✅ Google Drive autenticado via Service Account: {self.service_account_email}")
                    return
                except Exception as e:
                    logger.error(f"Erro ao autenticar com Service Account ({sa_path}): {e}")

            # 2. Modo Conta Pessoal Google (OAuth 2.0) - Acesso total a pastas privadas compartilhadas
            oauth_path = settings.GOOGLE_DRIVE_OAUTH_FILE
            token_path = settings.GOOGLE_DRIVE_TOKEN_FILE

            if token_path and token_path.exists():
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request

                creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(token_path, "w", encoding="utf-8") as tf:
                            tf.write(creds.to_json())
                    except Exception as ref_err:
                        logger.warning(f"Não foi possível renovar token OAuth: {ref_err}")
                        creds = None

                if creds and creds.valid:
                    self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
                    self.auth_type = "oauth"
                    try:
                        about = self.service.about().get(fields="user(displayName, emailAddress)").execute()
                        self.user_email = about.get("user", {}).get("emailAddress")
                        self.user_display_name = about.get("user", {}).get("displayName")
                    except Exception:
                        pass
                    logger.info(f"✅ Google Drive autenticado via Conta Pessoal OAuth: {self.user_email}")
                    return

            if oauth_path and oauth_path.exists():
                self.auth_type = "oauth_needs_login"
                logger.info("ℹ️ Arquivo credentials.json encontrado, aguardando login do usuário via OAuth.")
                return

        except Exception as e:
            logger.warning(f"Google Drive não inicializado: {e}")
            self.service = None
            self.auth_type = "none"

    def get_status(self) -> Dict[str, Any]:
        """Retorna o estado detalhado da conexão com o Google Drive."""
        has_oauth_file = settings.GOOGLE_DRIVE_OAUTH_FILE.exists()
        has_token_file = settings.GOOGLE_DRIVE_TOKEN_FILE.exists()
        has_sa_file = settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE.exists()

        status = {
            "is_configured": self.service is not None,
            "auth_type": self.auth_type,
            "user_email": self.user_email,
            "user_display_name": self.user_display_name,
            "service_account_email": self.service_account_email,
            "has_oauth_credentials": has_oauth_file,
            "has_oauth_token": has_token_file,
            "has_service_account": has_sa_file,
            "root_folder_id": settings.GOOGLE_DRIVE_FOLDER_ID or None,
            "root_folder_name": None,
            "accessible": False,
            "error": None
        }

        if not self.service:
            if self.auth_type == "oauth_needs_login":
                status["error"] = "Credenciais OAuth (credentials.json) encontradas! Clique em 'Conectar com Google' ou execute: python -m ingestion.drive_auth"
            elif not has_sa_file and not has_oauth_file:
                status["error"] = "Nenhuma credencial encontrada. Coloque credentials/credentials.json (conta pessoal) ou credentials/google_drive_service_account.json."
            else:
                status["error"] = "Credenciais encontradas, mas a conexão ainda não foi autorizada."
            return status

        if not settings.GOOGLE_DRIVE_FOLDER_ID:
            status["error"] = "Conectado ao seu Google Drive! Selecione abaixo uma pasta dos 'Compartilhados comigo' para definir como raiz dos estudos."
            return status

        try:
            folder = self.service.files().get(
                fileId=settings.GOOGLE_DRIVE_FOLDER_ID,
                fields="id, name, mimeType",
                supportsAllDrives=True
            ).execute()
            status["root_folder_name"] = folder.get("name")
            status["accessible"] = True
        except Exception as e:
            status["accessible"] = False
            status["error"] = f"Não foi possível acessar a pasta {settings.GOOGLE_DRIVE_FOLDER_ID}: {str(e)}"

        return status

    def list_shared_with_me_folders(self) -> List[Dict[str, Any]]:
        """Lista todas as pastas privadas compartilhadas diretamente com a sua conta pessoal."""
        if not self.service:
            return []

        query = "sharedWithMe = true and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = []
        try:
            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, owners, modifiedTime)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=50
            ).execute()
            for f in response.get('files', []):
                results.append({
                    "id": f["id"],
                    "name": f["name"],
                    "owner": (f.get("owners") or [{}])[0].get("displayName", "Proprietário"),
                    "modified_time": f.get("modifiedTime")
                })
            results.sort(key=lambda x: x["name"].lower())
            return results
        except Exception as e:
            logger.error(f"Erro ao listar pastas compartilhadas comigo: {e}")
            return []

    def list_subfolders(self, parent_id: str) -> List[Dict[str, Any]]:
        """Lista todas as subpastas dentro de uma pasta mãe."""
        if not self.service:
            return []

        query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = []
        page_token = None

        try:
            while True:
                response = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, createdTime, modifiedTime)',
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageSize=100
                ).execute()

                results.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            # Ordena alfabeticamente
            results.sort(key=lambda x: x.get('name', '').lower())
            return results
        except Exception as e:
            logger.error(f"Erro ao listar subpastas de {parent_id}: {e}")
            return []

    def list_folder_contents(
        self, 
        folder_id: str, 
        course_name: Optional[str] = None, 
        theme_name: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Lista e classifica todos os arquivos dentro de uma pasta (vídeos/áudios e arquivos complementares)."""
        if not self.service:
            return {"videos": [], "support_files": []}

        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        files = []
        page_token = None

        try:
            while True:
                response = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, size, mimeType, webViewLink, videoMediaMetadata)',
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageSize=100
                ).execute()

                files.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            # Ordenação natural por nome
            files.sort(key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x.get('name', ''))])

            # Cruzamento com aulas já estudadas
            studied_stems = set()
            for p_file in settings.PROCESSED_DIR.rglob("*.json"):
                try:
                    with open(p_file, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                        studied_stems.add(Path(pdata.get("file_name", "")).stem.lower())
                        studied_stems.add(pdata.get("video_id", "").lower())
                except Exception:
                    pass

            videos = []
            support_files = []

            for f in files:
                fid = f["id"]
                fname = f.get("name", "")
                fstem = Path(fname).stem.lower()
                ext = Path(fname).suffix.lower()
                mime = f.get("mimeType", "")
                size_bytes = int(f.get("size", 0))
                size_mb = round(size_bytes / (1024 * 1024), 2)

                if ext in VIDEO_EXTENSIONS or mime in VIDEO_MIME_TYPES:
                    meta = f.get("videoMediaMetadata", {})
                    duration_ms = int(meta.get("durationMillis", 0)) if meta else 0
                    duration_sec = round(duration_ms / 1000.0, 1) if duration_ms else 0.0
                    is_studied = (fstem in studied_stems) or (f"drive_{fid}" in studied_stems)

                    videos.append({
                        "id": fid,
                        "drive_file_id": fid,
                        "name": fname,
                        "file_name": fname,
                        "size_bytes": size_bytes,
                        "size_mb": size_mb,
                        "duration_seconds": duration_sec,
                        "web_view_link": f.get("webViewLink"),
                        "is_studied": is_studied,
                        "course_name": course_name,
                        "theme_name": theme_name
                    })
                elif ext in SUPPORT_FILE_EXTENSIONS or "pdf" in mime or "text" in mime or "document" in mime or "code" in mime or "zip" in mime:
                    is_studied = (fstem in studied_stems) or (f"drive_{fid}" in studied_stems)
                    support_files.append({
                        "id": fid,
                        "drive_file_id": fid,
                        "name": fname,
                        "file_name": fname,
                        "size_bytes": size_bytes,
                        "size_mb": size_mb,
                        "mime_type": mime,
                        "extension": ext,
                        "web_view_link": f.get("webViewLink"),
                        "is_studied": is_studied,
                        "course_name": course_name,
                        "theme_name": theme_name
                    })

            return {"videos": videos, "support_files": support_files}

        except Exception as e:
            logger.error(f"Erro ao listar conteúdo da pasta {folder_id}: {e}")
            return {"videos": [], "support_files": []}

    def list_videos_in_folder(self, folder_id: str, course_name: Optional[str] = None, theme_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Compatibilidade retroativa: lista apenas vídeos/áudios da pasta."""
        return self.list_folder_contents(folder_id, course_name=course_name, theme_name=theme_name)["videos"]

    def _inspect_course_folder(self, folder_id: str, folder_name: str, area_name: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Inspeciona detalhadamente uma pasta de Curso, detectando seus temas/módulos (inclusive aninhados),
        aulas em vídeo e materiais de apoio complementares."""
        import time
        if not force_refresh and folder_id in self._course_cache:
            ts, cached = self._course_cache[folder_id]
            if time.time() - ts < 1800:
                return cached

        direct_contents = self.list_folder_contents(folder_id, course_name=folder_name, theme_name=None)
        direct_videos = direct_contents["videos"]
        direct_support = direct_contents["support_files"]
        subfolders = self.list_subfolders(folder_id)

        themes = []

        def _explore_folder(fid: str, current_theme_name: str, depth: int = 0):
            cont = self.list_folder_contents(fid, course_name=folder_name, theme_name=current_theme_name)
            vids = cont["videos"]
            supp = cont["support_files"]
            subf = self.list_subfolders(fid)

            # Subpastas dedicadas a materiais complementares (ex: MATERIAIS, SLIDES, ARQUIVOS)
            material_subs = [s for s in subf if any(k in s["name"].lower() for k in ["material", "materiais", "slide", "anexo", "apoio", "recurso", "pdf", "codigo", "code"])]
            other_subs = [s for s in subf if s not in material_subs]

            for ms in material_subs:
                m_cont = self.list_folder_contents(ms["id"], course_name=folder_name, theme_name=current_theme_name)
                supp.extend(m_cont["support_files"])
                supp.extend(m_cont["videos"])

            if vids or supp or not other_subs:
                t_studied = sum(1 for v in vids if v["is_studied"])
                t_bytes = sum(v["size_bytes"] for v in vids) + sum(s["size_bytes"] for s in supp)
                themes.append({
                    "id": fid,
                    "name": current_theme_name,
                    "type": "theme",
                    "course_name": folder_name,
                    "videos_count": len(vids),
                    "studied_count": t_studied,
                    "pending_count": len(vids) - t_studied,
                    "support_files_count": len(supp),
                    "total_size_mb": round(t_bytes / (1024 * 1024), 1),
                    "videos": vids,
                    "support_files": supp
                })

            if depth < 3:
                for os in other_subs:
                    sub_theme_name = f"{current_theme_name} / {os['name']}" if current_theme_name else os["name"]
                    _explore_folder(os["id"], sub_theme_name, depth + 1)

        if subfolders:
            for sf in subfolders:
                if any(k in sf["name"].lower() for k in ["material", "materiais", "slide", "anexo", "apoio", "recurso", "pdf", "codigo", "code"]):
                    m_cont = self.list_folder_contents(sf["id"], course_name=folder_name, theme_name=None)
                    direct_support.extend(m_cont["support_files"])
                    direct_support.extend(m_cont["videos"])
                else:
                    _explore_folder(sf["id"], sf["name"], depth=0)

        all_videos_count = len(direct_videos) + sum(t["videos_count"] for t in themes)
        all_studied_count = sum(1 for v in direct_videos if v["is_studied"]) + sum(t["studied_count"] for t in themes)
        all_support_count = len(direct_support) + sum(t["support_files_count"] for t in themes)
        
        all_bytes = (
            sum(v["size_bytes"] for v in direct_videos) + 
            sum(s["size_bytes"] for s in direct_support) + 
            sum(sum(v["size_bytes"] for v in t["videos"]) + sum(s["size_bytes"] for s in t["support_files"]) for t in themes)
        )

        res = {
            "id": folder_id,
            "name": folder_name,
            "type": "course",
            "area_name": area_name or "Geral",
            "videos_count": all_videos_count,
            "studied_count": all_studied_count,
            "pending_count": all_videos_count - all_studied_count,
            "support_files_count": all_support_count,
            "themes_count": len(themes),
            "total_size_mb": round(all_bytes / (1024 * 1024), 1),
            "themes": themes,
            "direct_videos": direct_videos,
            "direct_support_files": direct_support,
            "videos": direct_videos + [v for t in themes for v in t["videos"]],
            "support_files": direct_support + [s for t in themes for s in t["support_files"]]
        }
        self._course_cache[folder_id] = (time.time(), res)
        return res

    def get_full_hierarchy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Escaneia a estrutura do Drive suportando a taxonomia de 3 níveis:
        Nível 1 (Pastas Raiz) ➔ Áreas da Vida OU Cursos
        Nível 2 (Subpastas) ➔ Cursos OU Temas/Módulos
        Nível 3 (Conteúdo) ➔ Aulas (Vídeo/Áudio) + Arquivos de Apoio (PDFs, Códigos, Notas)"""
        if force_refresh:
            self._course_cache.clear()

        status = self.get_status()
        if not status.get("accessible"):
            return {
                "status": status,
                "tree": []
            }

        root_id = settings.GOOGLE_DRIVE_FOLDER_ID
        root_name = status.get("root_folder_name", "Oráculo")

        top_folders = self.list_subfolders(root_id)
        tree = []

        # 1. Verifica se a pasta raiz possui arquivos diretos (vídeos ou PDFs soltos na raiz)
        root_contents = self.list_folder_contents(root_id, course_name=root_name, theme_name=None)
        if root_contents.get("videos") or root_contents.get("support_files"):
            root_course = self._inspect_course_folder(root_id, root_name, area_name=root_name, force_refresh=force_refresh)
            if root_course["videos_count"] > 0 or root_course["support_files_count"] > 0:
                tree.append(root_course)

        if not top_folders and not tree:
            # Caso especial: a pasta compartilhada raiz não tem subpastas e é o único curso
            course_node = self._inspect_course_folder(root_id, root_name, area_name=root_name, force_refresh=force_refresh)
            if course_node["videos_count"] > 0 or course_node["support_files_count"] > 0 or course_node["themes"]:
                tree.append(course_node)
            return {
                "status": status,
                "root_folder_id": root_id,
                "root_folder_name": root_name,
                "tree": tree
            }

        material_keywords = ["material", "materiais", "slide", "slides", "anexo", "anexos", "apoio", "recurso", "recursos", "pdf", "codigo", "code", "html"]

        for f1 in top_folders:
            f1_id = f1["id"]
            f1_name = f1["name"]
            f1_subfolders = self.list_subfolders(f1_id)

            content_subs = [s for s in f1_subfolders if not any(k in s["name"].lower() for k in material_keywords)]
            is_module_pattern = bool(re.match(r'^\s*(\d+|m[oó]dulo|cap[ií]tulo|aula|ebook|parte)', f1_name, re.IGNORECASE))

            course_node = self._inspect_course_folder(f1_id, f1_name, area_name=root_name, force_refresh=force_refresh)
            has_direct_content = bool(course_node.get("direct_videos") or course_node.get("direct_support_files"))

            if has_direct_content or not content_subs or is_module_pattern:
                # F1 é um curso ou módulo direto (possui vídeos/materiais diretos, subpastas são apenas materiais, ou tem padrão de módulo)
                if course_node["videos_count"] > 0 or course_node["support_files_count"] > 0 or course_node["themes"]:
                    tree.append(course_node)
            else:
                # F1 é uma Área de Conhecimento / Categoria (ex: Programação, Marketing, etc.)
                area_node = {
                    "id": f1_id,
                    "name": f1_name,
                    "type": "area",
                    "courses": []
                }
                for f2 in content_subs:
                    area_node["courses"].append({
                        "id": f2["id"],
                        "name": f2["name"],
                        "type": "course",
                        "area_name": f1_name,
                        "videos_count": 0,
                        "studied_count": 0,
                        "pending_count": 0,
                        "support_files_count": 0,
                        "themes_count": 0,
                        "total_size_mb": 0.0,
                        "themes": [],
                        "direct_videos": [],
                        "direct_support_files": [],
                        "lazy": True
                    })
                if area_node["courses"]:
                    tree.append(area_node)

        return {
            "status": status,
            "root_folder_id": root_id,
            "root_folder_name": root_name,
            "tree": tree
        }

    def download_file(
        self, 
        file_id: str, 
        destination_path: Path, 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """Faz o download de um arquivo do Google Drive em chunks com callback de progresso em tempo real."""
        if not self.service:
            raise RuntimeError("Cliente Google Drive não está inicializado ou autenticado.")

        from googleapiclient.http import MediaIoBaseDownload

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)

        # Obtém o tamanho total para acompanhamento
        try:
            file_meta = self.service.files().get(
                fileId=file_id, 
                fields="size, name", 
                supportsAllDrives=True
            ).execute()
            total_size = int(file_meta.get("size", 0))
        except Exception:
            total_size = 0

        # Se o arquivo já existe no destino completo, reaproveita sem gastar download
        if destination_path.exists() and destination_path.stat().st_size > 0:
            dest_size = destination_path.stat().st_size
            if (total_size > 0 and dest_size == total_size) or (total_size == 0 and dest_size > 1024 * 1024):
                logger.info(f"⚡ Arquivo já existe completo em disco ({round(dest_size / (1024*1024), 1)} MB): {destination_path.name}")
                if progress_callback:
                    progress_callback(dest_size, dest_size)
                return destination_path

        logger.info(f"⬇️ Iniciando download do Google Drive: {file_id} -> {destination_path.name} ({round(total_size / (1024*1024), 1)} MB)")

        with io.FileIO(destination_path, 'wb') as fh:
            # Chunks de 5MB para alta velocidade e baixo overhead
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 5)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    current_bytes = int(status.resumable_progress)
                    if progress_callback:
                        progress_callback(current_bytes, total_size)
                    if total_size > 0:
                        pct = round(status.progress() * 100, 1)
                        logger.debug(f"Progresso Drive {destination_path.name}: {pct}%")

        logger.info(f"✅ Download do Google Drive concluído com sucesso: {destination_path.name}")
        return destination_path
