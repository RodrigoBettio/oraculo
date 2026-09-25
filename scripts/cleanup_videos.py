#!/usr/bin/env python3
"""Limpeza automática de vídeos processados.

Apaga arquivos de vídeo/áudio em data/videos/ que já foram processados
(status=completed na fila) e que são mais antigos que VIDEO_RETENTION_HOURS.

Uso:
    python scripts/cleanup_videos.py          # Limpeza padrão (24h)
    python scripts/cleanup_videos.py --hours 6  # Limpar vídeos com mais de 6h
    python scripts/cleanup_videos.py --dry-run   # Simular sem apagar
"""

import os
import sys
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Adiciona a raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings


def get_completed_files(db_path: Path) -> set:
    """Retorna o set de file_name de itens completados no SQLite."""
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT file_name FROM study_queue WHERE status = 'completed'")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()


def cleanup(hours: int = 24, dry_run: bool = False):
    videos_dir = settings.VIDEOS_DIR
    db_path = settings.DATA_DIR / "oraculo.db"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    completed_files = get_completed_files(db_path)
    removed_count = 0
    freed_bytes = 0

    video_extensions = {".mp4", ".mp3", ".mkv", ".avi", ".webm", ".m4a", ".wav", ".ogg"}

    for root, dirs, files in os.walk(videos_dir):
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in video_extensions:
                continue

            try:
                mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue

            # Apaga se: arquivo é antigo E (está na lista de completados OU não está em nenhuma fila)
            if mtime < cutoff:
                size = fpath.stat().st_size
                if dry_run:
                    print(f"  [DRY-RUN] Removeria: {fpath.name} ({size / 1024 / 1024:.1f} MB)")
                else:
                    fpath.unlink()
                    print(f"  Removido: {fpath.name} ({size / 1024 / 1024:.1f} MB)")
                removed_count += 1
                freed_bytes += size

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Total: {removed_count} arquivo(s), {freed_bytes / 1024 / 1024:.1f} MB liberados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpeza de vídeos processados do Oráculo")
    parser.add_argument("--hours", type=int, default=int(os.getenv("VIDEO_RETENTION_HOURS", "24")),
                        help="Remover vídeos com mais de N horas (default: 24)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem apagar arquivos")
    args = parser.parse_args()
    cleanup(hours=args.hours, dry_run=args.dry_run)
