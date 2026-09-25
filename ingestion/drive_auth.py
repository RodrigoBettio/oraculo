"""Script interativo de autenticação OAuth 2.0 pessoal com o Google Drive.
Permite conectar diretamente a conta pessoal do usuário para acessar pastas privadas
compartilhadas diretamente com ele ("Compartilhados comigo")."""

import os
import sys
import json
from pathlib import Path

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

def main():
    print("=" * 70)
    print("🔐 ORÁCULO - AUTENTICAÇÃO GOOGLE DRIVE (CONTA PESSOAL OAUTH 2.0)")
    print("=" * 70)
    print("Este assistente conectará a sua conta do Google para acessar pastas")
    print("privadas que foram compartilhadas diretamente com você.")
    print("-" * 70)

    oauth_path = settings.GOOGLE_DRIVE_OAUTH_FILE
    token_path = settings.GOOGLE_DRIVE_TOKEN_FILE

    # 1. Checa se credentials.json existe
    if not oauth_path.exists():
        print(f"❌ Arquivo de credenciais OAuth não encontrado em:")
        print(f"   {oauth_path}")
        print("\n👉 COMO OBTER O ARQUIVO (Levará ~2 minutos):")
        print("1. Acesse: https://console.cloud.google.com/")
        print("2. Ative a 'Google Drive API' em 'APIs e Serviços' -> 'Biblioteca'")
        print("3. Em 'Tela de permissão OAuth' (OAuth consent screen), escolha 'Externo',")
        print("   coloque seu e-mail e adicione seu e-mail como 'Usuário de teste'.")
        print("4. Em 'Credenciais' -> '+ Criar Credenciais' -> 'ID do cliente OAuth':")
        print("   - Tipo de aplicativo: 'App para Computador' (Desktop App)")
        print("   - Nome: 'Oráculo'")
        print("5. Clique em 'Criar', faça o download do JSON e salve como:")
        print(f"   {oauth_path}")
        print("=" * 70)
        return

    print(f"✅ Arquivo OAuth encontrado: {oauth_path.name}")
    print("🌐 Abrindo seu navegador padrão para você autorizar o acesso à sua conta Google...")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        flow = InstalledAppFlow.from_client_secrets_file(str(oauth_path), SCOPES)
        creds = flow.run_local_server(port=0)

        # Salva o token para reutilização permanente
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

        print(f"✅ Login realizado com sucesso! Token gravado em: {token_path.name}")

        # Testa conexão e obtém informações do usuário
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        about = service.about().get(fields="user(displayName, emailAddress)").execute()
        user_info = about.get("user", {})
        user_name = user_info.get("displayName", "Usuário")
        user_email = user_info.get("emailAddress", "")

        print(f"\n👤 Conectado como: {user_name} ({user_email})")

        # 2. Busca pastas privadas compartilhadas com o usuário
        print("\n🔍 Buscando pastas compartilhadas diretamente com você ('Compartilhados comigo')...")
        response = service.files().list(
            q="sharedWithMe = true and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            spaces='drive',
            fields='files(id, name, owners, modifiedTime)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=30
        ).execute()

        shared_folders = response.get('files', [])

        if not shared_folders:
            print("ℹ️ Nenhuma pasta compartilhada encontrada via 'sharedWithMe'.")
            print("   Se você já possui o link da pasta, basta colar o ID dela no arquivo .env:")
            print("   GOOGLE_DRIVE_FOLDER_ID=<ID_DA_PASTA>")
        else:
            print(f"📁 Encontradas {len(shared_folders)} pastas compartilhadas:")
            for idx, f in enumerate(shared_folders, start=1):
                owner = (f.get("owners") or [{}])[0].get("displayName", "Outro usuário")
                print(f"   [{idx}] {f['name']} (Compartilhada por: {owner}) -> ID: {f['id']}")

            choice = input("\n👉 Digite o número da pasta de cursos que deseja usar (ou Enter para colar um ID): ").strip()
            selected_id = None
            if choice.isdigit() and 1 <= int(choice) <= len(shared_folders):
                chosen = shared_folders[int(choice) - 1]
                selected_id = chosen["id"]
                print(f"🎯 Pasta selecionada: '{chosen['name']}' ({selected_id})")
            else:
                manual = input("Cole a URL ou ID da pasta do Google Drive (ou Enter para pular): ").strip()
                if manual:
                    selected_id = manual.split("/folders/")[1].split("?")[0].split("/")[0] if "/folders/" in manual else manual

            if selected_id:
                # Grava no .env
                env_path = settings.BASE_DIR / ".env"
                env_lines = []
                if env_path.exists():
                    with open(env_path, "r", encoding="utf-8") as ef:
                        env_lines = ef.readlines()

                found = False
                new_lines = []
                for line in env_lines:
                    if line.startswith("GOOGLE_DRIVE_FOLDER_ID="):
                        new_lines.append(f"GOOGLE_DRIVE_FOLDER_ID={selected_id}\n")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"GOOGLE_DRIVE_FOLDER_ID={selected_id}\n")

                with open(env_path, "w", encoding="utf-8") as ef:
                    ef.writelines(new_lines)

                print(f"💾 Configuração salva no .env! GOOGLE_DRIVE_FOLDER_ID={selected_id}")

        print("\n🎉 Tudo pronto! O Oráculo agora tem acesso completo à sua pasta privada.")
        print("Abra o navegador em http://127.0.0.1:8000 para começar a estudar!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Erro durante o fluxo OAuth: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
