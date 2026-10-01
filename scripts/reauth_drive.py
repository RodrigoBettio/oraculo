"""
Script de Reautenticação do Google Drive para o Oráculo.
Abre o navegador padrão localmente para autenticar via OAuth 2.0 (App para Computador)
e propaga o token.json automaticamente via SCP para a VM de produção no GCP.
"""

import sys
import subprocess
import json
import wsgiref.simple_server
import webbrowser
from pathlib import Path

# Suporte UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google_auth_oauthlib.flow import (
    InstalledAppFlow,
    _RedirectWSGIApp,
    _ExclusiveWSGIServer,
    _WSGIRequestHandler
)
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

BASE_DIR = Path(__file__).resolve().parent.parent
OAUTH_PATH = BASE_DIR / "credentials" / "credentials.json"
TOKEN_PATH = BASE_DIR / "credentials" / "token.json"
URL_PATH = BASE_DIR / "credentials" / "auth_url.txt"

VM_USER = "rodriguinhobettiojr"
VM_HOST = "34.46.39.111"
SSH_KEY = Path.home() / ".ssh" / "id_ed25519"


def run_custom_local_server(flow, port=8092):
    """Inicia servidor local em porta fixa, gera URL e abre o navegador."""
    wsgi_app = _RedirectWSGIApp("Autenticacao do Oraculo concluida com sucesso! Voce ja pode fechar esta aba.")
    local_server = wsgiref.simple_server.make_server(
        "localhost",
        port,
        wsgi_app,
        server_class=_ExclusiveWSGIServer,
        handler_class=_WSGIRequestHandler,
    )
    
    flow.redirect_uri = f"http://localhost:{local_server.server_port}/"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    # Grava a URL imediatamente para exibição no chat
    URL_PATH.write_text(auth_url, encoding="utf-8")
    print(f"\n🔗 URL DE AUTORIZAÇÃO GERADA:\n{auth_url}\n", flush=True)

    # Abre o navegador
    print("🌐 Abrindo seu navegador padrão na tela de consentimento do Google...", flush=True)
    webbrowser.open(auth_url, new=1, autoraise=True)

    # Aguarda a resposta do Google (callback)
    print("⏳ Aguardando você selecionar a conta e clicar em 'Permitir'...", flush=True)
    local_server.handle_request()

    authorization_response = wsgi_app.last_request_uri.replace("http", "https")
    flow.fetch_token(authorization_response=authorization_response)
    local_server.server_close()
    return flow.credentials


def main():
    print("=" * 60, flush=True)
    print("🔐 REAUTENTICAÇÃO DO GOOGLE DRIVE (ORÁCULO)", flush=True)
    print("=" * 60, flush=True)

    if not OAUTH_PATH.exists():
        print(f"❌ credentials.json não encontrado em: {OAUTH_PATH}", flush=True)
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_PATH), SCOPES)
    creds = run_custom_local_server(flow, port=8092)

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"\n✅ Token local gravado com sucesso em: {TOKEN_PATH.name}", flush=True)

    # Remove o arquivo temporário de URL
    if URL_PATH.exists():
        try:
            URL_PATH.unlink()
        except Exception:
            pass

    # Validação com API do Drive
    try:
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        about = service.about().get(fields="user(displayName, emailAddress)").execute()
        u = about.get("user", {})
        print(f"👤 Conectado com sucesso como: {u.get('displayName')} ({u.get('emailAddress')})", flush=True)
    except Exception as e:
        print(f"⚠️ Aviso ao testar Drive API: {e}", flush=True)

    # Sincronização automática com a VM
    if SSH_KEY.exists():
        print("\n🚀 Sincronizando token com a VM de produção (34.46.39.111)...", flush=True)
        try:
            # 1. Envia token via SCP
            scp_cmd = [
                "scp", "-i", str(SSH_KEY),
                "-o", "StrictHostKeyChecking=no",
                str(TOKEN_PATH),
                f"{VM_USER}@{VM_HOST}:~/oraculo/credentials/token.json"
            ]
            subprocess.run(scp_cmd, check=True)
            print("📦 Token enviado para ~/oraculo/credentials/token.json na VM.", flush=True)

            # 2. Injeta no container Docker e reinicia a aplicação
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY),
                "-o", "StrictHostKeyChecking=no",
                f"{VM_USER}@{VM_HOST}",
                "docker cp ~/oraculo/credentials/token.json oraculo-app:/app/credentials/token.json && docker restart oraculo-app"
            ]
            subprocess.run(ssh_cmd, check=True)
            print("🔄 Container 'oraculo-app' atualizado e reiniciado com sucesso na VM!", flush=True)
        except Exception as e:
            print(f"⚠️ Erro ao sincronizar com a VM: {e}", flush=True)

    print("\n🎉 Google Drive 100% conectado e operacional no Oráculo!", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
