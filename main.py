import asyncio
import sys
from pathlib import Path
from config import settings
from ingestion.telegram_client import TelegramManager
from models.agent import AgentProfile, AgentStatus

async def interactive_menu():
    print("=" * 60)
    print("🔮 ORÁCULO - Painel de Controle de Estudos e Agentes")
    print("=" * 60)

    # Verifica se as credenciais foram preenchidas
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        print("\n⚠️ AVISO: Configure TELEGRAM_API_ID e TELEGRAM_API_HASH no arquivo .env!")
        print("Obtenha suas credenciais gratuitamente em: https://my.telegram.org")
        return

    tg = TelegramManager()
    client = await tg.get_client()

    # Autenticação no Telegram
    if not await tg.is_authorized():
        print("\n📱 Autenticação necessária no Telegram:")
        phone = input("Digite seu número de telefone com DDI e DDD (ex: +5511999999999): ")
        await client.send_code_request(phone)
        code = input("Digite o código recebido no Telegram: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            password = input("Senha de verificação em duas etapas (2FA) necessária: ")
            await client.sign_in(password=password)
        print("✅ Autenticado com sucesso no Telegram!\n")

    while True:
        print("\nEscolha uma opção:")
        print("1. 📂 Listar todas as Pastas de Chat da sua conta")
        print("2. 👥 Listar grupos dentro da pasta alvo configurada ('" + settings.TELEGRAM_TARGET_FOLDER + "')")
        print("3. 📹 Listar vídeos de um grupo")
        print("4. 🚪 Sair")
        
        choice = input("\nOpção: ").strip()

        if choice == "1":
            print("\nBuscando pastas de chat...")
            folders = await tg.list_folders()
            if not folders:
                print("Nenhuma pasta de chat encontrada na sua conta.")
            for f in folders:
                print(f" - 📁 ID: {f['id']} | Nome: '{f['title']}' | Grupos/Canais incluídos: {f['include_peers']}")

        elif choice == "2":
            target = settings.TELEGRAM_TARGET_FOLDER
            print(f"\nBuscando grupos dentro da pasta '{target}'...")
            try:
                groups = await tg.list_groups_in_folder(target)
                if not groups:
                    print(f"Nenhum grupo encontrado na pasta '{target}'.")
                for g in groups:
                    tipo = "Canal" if g["is_channel"] else "Grupo"
                    print(f" - [{tipo}] ID: {g['id']} | Nome: '{g['title']}'")
            except Exception as e:
                print(f"Erro: {e}")

        elif choice == "3":
            group_id_str = input("Digite o ID do grupo/canal: ").strip()
            if group_id_str:
                try:
                    group_id = int(group_id_str)
                    print("Buscando mensagens de vídeo...")
                    videos = await tg.list_videos_in_group(group_id, limit=20)
                    if not videos:
                        print("Nenhum vídeo encontrado.")
                    for v in videos:
                        dur_min = round(v["duration_seconds"] / 60, 1)
                        tam_mb = round(v["file_size_bytes"] / (1024 * 1024), 1)
                        print(f" - Msg ID: {v['message_id']} | Arquivo: {v['file_name']} | Duração: {dur_min} min | Tamanho: {tam_mb} MB")
                except Exception as e:
                    print(f"Erro: {e}")

        elif choice == "4":
            print("Até logo!")
            break

if __name__ == "__main__":
    asyncio.run(interactive_menu())
