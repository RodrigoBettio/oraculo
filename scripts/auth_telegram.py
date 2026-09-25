"""
Script interativo para autenticação do Telegram diretamente na VM.
Gera um arquivo de sessão exclusivo para o IP da VM, evitando o erro AuthKeyDuplicatedError.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from telethon.sync import TelegramClient
from config import settings

def main():
    session_file = settings.DATA_DIR / f"{settings.TELEGRAM_SESSION_NAME}.session"
    print("=" * 60)
    print("🔮 ORÁCULO - Autenticação Direta do Telegram na VM")
    print("=" * 60)
    print(f"API_ID: {settings.TELEGRAM_API_ID}")
    print(f"Sessão alvo: {session_file}")

    # Remove arquivos da sessão antiga com erro
    for ext in [".session", ".session-shm", ".session-wal"]:
        p = settings.DATA_DIR / f"{settings.TELEGRAM_SESSION_NAME}{ext}"
        if p.exists():
            try:
                p.unlink()
                print(f"🗑️ Arquivo antigo removido: {p.name}")
            except Exception as e:
                print(f"Aviso ao remover {p.name}: {e}")

    print("\nConectando ao Telegram diretamente pelo IP desta VM...")
    print("Quando solicitado, informe seu número com DDI e DDD (Ex: +5511999999999)")
    print("e em seguida o código de 5 dígitos enviado no seu app do Telegram.\n")

    with TelegramClient(str(settings.DATA_DIR / settings.TELEGRAM_SESSION_NAME), settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH) as client:
        me = client.get_me()
        print("\n" + "=" * 60)
        print("✅ AUTENTICAÇÃO REALIZADA COM SUCESSO!")
        print(f"Nome: {me.first_name} {me.last_name or ''}")
        print(f"Telefone: +{me.phone}")
        print(f"Username: @{me.username or 'N/A'}")
        print(f"Sessão salva em: {session_file}")
        print("=" * 60)

if __name__ == "__main__":
    main()
