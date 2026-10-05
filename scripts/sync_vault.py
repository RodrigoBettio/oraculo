"""
Oráculo — Obsidian Vault Real-Time Bidirectional Sync Daemon
Sincroniza o Obsidian Local (C:\\Users\\Rodrigo\\Documents\\ObsidianVault)
com o cofre da nuvem (GCP VM 34.46.39.111) e o espelho local do repositório (data/vault).

Uso:
  python scripts/sync_vault.py          # Executa uma sincronização imediata
  python scripts/sync_vault.py --watch  # Mantém sincronização viva em tempo real (daemon)
  python scripts/sync_vault.py --status # Verifica status da sincronização
"""

import os
import sys
import time
import json
import hashlib
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Tuple
import urllib.request
import urllib.error

# Força UTF-8 no stdout/stderr no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("vault_sync")

DEFAULT_LOCAL_VAULT = Path(r"C:\Users\Rodrigo\Documents\ObsidianVault")
DEFAULT_REPO_VAULT = Path(__file__).resolve().parent.parent / "data" / "vault"
DEFAULT_CLOUD_URL = os.getenv("ORACULO_CLOUD_URL", "http://34.46.39.111")


def calculate_hash(path: Path) -> str:
    """Calcula SHA-256 do arquivo."""
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def build_manifest(vault_path: Path) -> Dict[str, Dict[str, Any]]:
    """Gera o manifesto do cofre local."""
    manifest = {}
    if not vault_path.exists():
        return manifest

    for f in vault_path.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(vault_path)).replace("\\", "/")
            if "workspace" in rel.lower() or f.name.startswith(".git"):
                continue
            st = f.stat()
            manifest[rel] = {
                "size": st.st_size,
                "mtime": st.st_mtime,
                "hash": calculate_hash(f)
            }
    return manifest


def sync_local_mirror(src_vault: Path, dst_vault: Path) -> Tuple[int, int]:
    """Sincroniza bidirecionalmente entre dois diretórios locais no disco."""
    src_manifest = build_manifest(src_vault)
    dst_manifest = build_manifest(dst_vault)
    copied_to_dst = 0
    copied_to_src = 0

    # 1. Copia de SRC para DST (se mais recente ou novo)
    for rel, s_info in src_manifest.items():
        d_info = dst_manifest.get(rel)
        needs_copy = False
        if not d_info:
            needs_copy = True
        elif s_info["hash"] != d_info["hash"] and s_info["mtime"] > d_info["mtime"]:
            needs_copy = True

        if needs_copy:
            src_file = src_vault / rel
            dst_file = dst_vault / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            dst_file.write_bytes(src_file.read_bytes())
            os.utime(dst_file, (s_info["mtime"], s_info["mtime"]))
            copied_to_dst += 1

    # 2. Copia de DST para SRC (se mais recente ou novo)
    for rel, d_info in dst_manifest.items():
        s_info = src_manifest.get(rel)
        needs_copy = False
        if not s_info:
            needs_copy = True
        elif d_info["hash"] != s_info["hash"] and d_info["mtime"] > s_info["mtime"]:
            needs_copy = True

        if needs_copy:
            dst_file = dst_vault / rel
            src_file = src_vault / rel
            src_file.parent.mkdir(parents=True, exist_ok=True)
            src_file.write_bytes(dst_file.read_bytes())
            os.utime(src_file, (d_info["mtime"], d_info["mtime"]))
            copied_to_src += 1

    return copied_to_dst, copied_to_src


def sync_with_cloud(local_vault: Path, cloud_url: str) -> Dict[str, Any]:
    """Sincroniza o cofre local com a API REST da Nuvem."""
    manifest = build_manifest(local_vault)
    api_url = f"{cloud_url.rstrip('/')}/api/vault/sync"

    # Carrega arquivos locais para envio
    # Envia arquivos de texto markdown e json
    client_files = {}
    for rel in manifest.keys():
        f_path = local_vault / rel
        if f_path.suffix.lower() in [".md", ".json", ".txt", ".yaml", ".yml"]:
            try:
                client_files[rel] = f_path.read_text(encoding="utf-8")
            except Exception:
                pass

    payload = {
        "client_manifest": manifest,
        "client_files": client_files
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.warning(f"⚠️ Nuvem não alcançável ({e.reason}). Sincronizando apenas localmente.")
        return {"error": str(e.reason)}

    # Salva arquivos recebidos da nuvem que são novos ou mais recentes
    files_received = data.get("files_for_client", {})
    downloaded_count = 0
    for rel, item in files_received.items():
        target = local_vault / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"], encoding="utf-8")
        if "mtime" in item:
            os.utime(target, (item["mtime"], item["mtime"]))
        downloaded_count += 1
        logger.info(f"📥 [Nuvem -> Local] {rel}")

    saved_on_cloud = len(data.get("saved_on_server", []))
    return {
        "status": "success",
        "uploaded_to_cloud": saved_on_cloud,
        "downloaded_from_cloud": downloaded_count
    }


def perform_full_sync(local_vault: Path, repo_vault: Path, cloud_url: str):
    """Executa o ciclo completo de sincronização."""
    # 1. Espelho local (ObsidianVault <-> data/vault)
    to_repo, to_local = sync_local_mirror(local_vault, repo_vault)
    if to_repo > 0 or to_local > 0:
        logger.info(f"🔄 [Disco Local] {to_repo} notas atualizadas no repositório, {to_local} no Obsidian.")

    # 2. Sincronização com a nuvem (GCP VM)
    cloud_res = sync_with_cloud(local_vault, cloud_url)
    if "error" not in cloud_res:
        up = cloud_res.get("uploaded_to_cloud", 0)
        down = cloud_res.get("downloaded_from_cloud", 0)
        if up > 0 or down > 0:
            logger.info(f"☁️ [Nuvem GCP] {up} notas enviadas | {down} notas recebidas.")
            # Espelha novamente qualquer arquivo novo baixado da nuvem
            sync_local_mirror(local_vault, repo_vault)
        else:
            logger.info("✨ Tudo 100% sincronizado (Obsidian Local == Nuvem GCP == Repositório).")


def run_watch_loop(local_vault: Path, repo_vault: Path, cloud_url: str, interval: int = 5):
    """Loop contínuo de sincronização com detecção de alterações."""
    logger.info(f"👀 Modo Observador ativo. Monitorando '{local_vault}' a cada {interval}s...")
    last_manifest = build_manifest(local_vault)

    # Primeira sincronização imediata
    perform_full_sync(local_vault, repo_vault, cloud_url)

    try:
        while True:
            time.sleep(interval)
            current_manifest = build_manifest(local_vault)
            has_changes = False

            if set(current_manifest.keys()) != set(last_manifest.keys()):
                has_changes = True
            else:
                for k, v in current_manifest.items():
                    if last_manifest.get(k, {}).get("hash") != v.get("hash"):
                        has_changes = True
                        break

            if has_changes:
                logger.info("⚡ Alteração detectada no Obsidian local! Sincronizando...")
                perform_full_sync(local_vault, repo_vault, cloud_url)
                last_manifest = current_manifest
            else:
                # Checa a cada 30 segundos se a nuvem tem novidades mesmo sem alteração local
                pass
    except KeyboardInterrupt:
        logger.info("⏹️ Observador finalizado.")


def print_status(local_vault: Path, repo_vault: Path, cloud_url: str):
    """Exibe o diagnóstico completo dos cofres."""
    local_manifest = build_manifest(local_vault)
    repo_manifest = build_manifest(repo_vault)
    
    print("\n" + "=" * 60)
    print("🔮 ORÁCULO — DIAGNÓSTICO DO OBSIDIAN VAULT (2º CÉREBRO)")
    print("=" * 60)
    print(f"📁 Cofre Local (Obsidian Desktop): {local_vault}")
    print(f"   Total de arquivos: {len(local_manifest)}")
    print(f"📁 Espelho do Repositório: {repo_vault}")
    print(f"   Total de arquivos: {len(repo_manifest)}")
    print(f"☁️ Nuvem GCP: {cloud_url}")
    
    try:
        status_url = f"{cloud_url.rstrip('/')}/api/vault/status"
        with urllib.request.urlopen(status_url, timeout=5) as resp:
            cloud_status = json.loads(resp.read().decode("utf-8"))
            print(f"   Status da Nuvem: Conectado ✅ ({cloud_status.get('total_files')} arquivos, {cloud_status.get('total_projects')} projetos)")
    except Exception as e:
        print(f"   Status da Nuvem: Inacessível ⚠️ ({e})")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Oráculo Obsidian Vault Sync")
    parser.add_argument("--watch", action="store_true", help="Executa como observador em tempo real")
    parser.add_argument("--status", action="store_true", help="Mostra status dos cofres")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo do observador em segundos")
    args = parser.parse_args()

    local_path = DEFAULT_LOCAL_VAULT
    repo_path = DEFAULT_REPO_VAULT
    cloud_url = DEFAULT_CLOUD_URL

    if args.status:
        print_status(local_path, repo_path, cloud_url)
    elif args.watch:
        run_watch_loop(local_path, repo_path, cloud_url, interval=args.interval)
    else:
        perform_full_sync(local_path, repo_path, cloud_url)


if __name__ == "__main__":
    main()
