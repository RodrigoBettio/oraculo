"""
Oráculo — Obsidian Vault REST API & Bidirectional Sync Engine
Permite que o Obsidian (Desktop, Mobile e Scripts) sincronize em tempo real
com o cofre hospedado na nuvem (Única Fonte da Verdade / Segundo Cérebro).
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from config import settings
from orchestration.pipeline_loader import get_primary_vault, get_vault_dirs

logger = logging.getLogger("vault_routes")
router = APIRouter(prefix="/api/vault", tags=["Obsidian Vault"])


def _calculate_file_hash(path: Path) -> str:
    """Calcula SHA-256 do conteúdo do arquivo."""
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def _get_vault_root() -> Path:
    """Retorna o diretório do cofre que serve como fonte no servidor."""
    # Prioriza o cofre do repositório local/docker
    repo_vault = settings.DATA_DIR / "vault"
    if repo_vault.exists():
        return repo_vault
    return get_primary_vault()


def _is_safe_relative_path(rel_path: str) -> bool:
    """Valida contra path traversal."""
    normalized = os.path.normpath(rel_path)
    return not (normalized.startswith("..") or os.path.isabs(normalized))


class VaultFilePayload(BaseModel):
    path: str
    content: str
    mtime: Optional[float] = None


class VaultSyncRequest(BaseModel):
    client_manifest: Dict[str, Dict[str, Any]] = {}
    client_files: Dict[str, str] = {}  # rel_path -> content (arquivos que o cliente quer enviar)


@router.get("/status")
def get_vault_status():
    """Retorna o resumo do Vault: total de notas, pipelines e projetos."""
    root = _get_vault_root()
    all_files = [f for f in root.rglob("*") if f.is_file() and not f.name.startswith(".")]
    md_files = [f for f in all_files if f.suffix.lower() == ".md"]
    
    pipelines = list((root / "04_Projetos_Ativos" / "Pipelines").glob("*.md")) if (root / "04_Projetos_Ativos" / "Pipelines").exists() else []
    execucoes = [d for d in (root / "04_Projetos_Ativos" / "Execucoes").iterdir() if d.is_dir()] if (root / "04_Projetos_Ativos" / "Execucoes").exists() else []

    last_modified = None
    if all_files:
        newest = max(all_files, key=lambda f: f.stat().st_mtime)
        last_modified = datetime.fromtimestamp(newest.stat().st_mtime).isoformat()

    return {
        "vault_path": str(root),
        "total_files": len(all_files),
        "total_markdown_notes": len(md_files),
        "total_pipelines": len(pipelines),
        "total_projects": len(execucoes),
        "last_modified": last_modified,
        "status": "healthy"
    }


@router.get("/manifest")
def get_vault_manifest():
    """Retorna o manifesto completo do cofre (caminhos, mtime, tamanho e sha256)."""
    root = _get_vault_root()
    manifest = {}

    for f in root.rglob("*"):
        if f.is_file():
            # Ignora arquivos de sistema e cache de workspace
            rel = str(f.relative_to(root)).replace("\\", "/")
            if "workspace" in rel.lower() or f.name.startswith(".git"):
                continue
            
            st = f.stat()
            manifest[rel] = {
                "size": st.st_size,
                "mtime": st.st_mtime,
                "hash": _calculate_file_hash(f)
            }

    return {
        "root": str(root),
        "manifest": manifest
    }


@router.get("/file")
def get_vault_file(path: str = Query(..., description="Caminho relativo da nota no cofre")):
    """Lê e retorna o conteúdo de uma nota específica do cofre."""
    if not _is_safe_relative_path(path):
        raise HTTPException(status_code=400, detail="Caminho inválido")
    
    root = _get_vault_root()
    target = root / path
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    
    try:
        content = target.read_text(encoding="utf-8")
        st = target.stat()
        return {
            "path": path.replace("\\", "/"),
            "content": content,
            "mtime": st.st_mtime,
            "size": st.st_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler nota: {e}")


@router.post("/file")
def save_vault_file(payload: VaultFilePayload):
    """Cria ou atualiza uma nota no cofre na nuvem."""
    if not _is_safe_relative_path(payload.path):
        raise HTTPException(status_code=400, detail="Caminho inválido")
    
    root = _get_vault_root()
    target = root / payload.path
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        target.write_text(payload.content, encoding="utf-8")
        if payload.mtime:
            os.utime(target, (payload.mtime, payload.mtime))
        
        # Também replica para outros cofres registrados caso existam
        for v in get_vault_dirs():
            if v != root:
                sec = v / payload.path
                sec.parent.mkdir(parents=True, exist_ok=True)
                sec.write_text(payload.content, encoding="utf-8")
                if payload.mtime:
                    os.utime(sec, (payload.mtime, payload.mtime))

        logger.info(f"💾 [Vault API] Arquivo atualizado: {payload.path}")
        return {"status": "saved", "path": payload.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {e}")


@router.post("/sync")
def sync_vault(req: VaultSyncRequest):
    """
    Sincronização bidirecional atômica:
    1. Salva os arquivos mais recentes enviados pelo cliente.
    2. Compara o manifesto do servidor e retorna os arquivos mais recentes do servidor para o cliente.
    """
    root = _get_vault_root()
    updated_on_server = []

    # 1. Aplicar arquivos enviados pelo cliente
    for rel_path, content in req.client_files.items():
        if not _is_safe_relative_path(rel_path):
            continue
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        
        # Atualiza mtime se fornecido
        client_meta = req.client_manifest.get(rel_path)
        if client_meta and "mtime" in client_meta:
            mtime = client_meta["mtime"]
            os.utime(target, (mtime, mtime))
            
        updated_on_server.append(rel_path)

    # 2. Levantar manifesto atual do servidor
    server_manifest = {}
    for f in root.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(root)).replace("\\", "/")
            if "workspace" in rel.lower() or f.name.startswith(".git"):
                continue
            st = f.stat()
            server_manifest[rel] = {
                "size": st.st_size,
                "mtime": st.st_mtime,
                "hash": _calculate_file_hash(f)
            }

    # 3. Descobrir quais arquivos o servidor tem que são novos ou mais recentes que o cliente
    files_to_send_to_client = {}
    for rel_path, s_info in server_manifest.items():
        c_info = req.client_manifest.get(rel_path)
        
        # Se cliente não tem o arquivo OU servidor tem hash diferente e mtime maior
        needs_download = False
        if not c_info:
            needs_download = True
        elif s_info["hash"] != c_info.get("hash"):
            if s_info["mtime"] > c_info.get("mtime", 0):
                needs_download = True

        if needs_download:
            try:
                target = root / rel_path
                files_to_send_to_client[rel_path] = {
                    "content": target.read_text(encoding="utf-8"),
                    "mtime": s_info["mtime"],
                    "hash": s_info["hash"]
                }
            except Exception as e:
                logger.warning(f"Erro ao ler arquivo para sync {rel_path}: {e}")

    return {
        "status": "synchronized",
        "saved_on_server": updated_on_server,
        "files_for_client": files_to_send_to_client,
        "server_manifest": server_manifest
    }
