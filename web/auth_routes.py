from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import json
from pathlib import Path
from config import settings
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix='/auth/google', tags=['Google OAuth'])

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

@router.get('/login')
def google_login(request: Request):
    """Redireciona o usuário para a tela de consentimento do Google."""
    if not settings.GOOGLE_DRIVE_OAUTH_FILE.exists():
        return {"error": "credentials.json não encontrado. Configure no Google Cloud Console e salve em credentials/credentials.json."}

    flow = Flow.from_client_secrets_file(
        str(settings.GOOGLE_DRIVE_OAUTH_FILE),
        scopes=SCOPES,
        redirect_uri=settings.OAUTH_REDIRECT_URI
    )

    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    state_file = settings.DATA_DIR / "temp" / f"oauth_state_{state}.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_data = {
        "state": state,
        "code_verifier": getattr(flow, 'code_verifier', None)
    }
    with open(state_file, 'w', encoding='utf-8') as sf:
        json.dump(state_data, sf)

    return RedirectResponse(auth_url)

@router.get('/callback')
def google_callback(request: Request, code: str = None, state: str = '', error: str = None):
    """Callback após o usuário autorizar no Google."""
    if error:
        return {"error": error}
        
    if not code:
        raise HTTPException(status_code=400, detail="Código de autorização não fornecido.")

    state_file = settings.DATA_DIR / "temp" / f"oauth_state_{state}.json"
    old_state_file = settings.DATA_DIR / "temp" / f"oauth_state_{state}.txt"
    code_verifier = None
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as sf:
                sdata = json.load(sf)
                code_verifier = sdata.get('code_verifier')
        except Exception:
            pass
        state_file.unlink(missing_ok=True)
    elif old_state_file.exists():
        old_state_file.unlink(missing_ok=True)

    if not settings.GOOGLE_DRIVE_OAUTH_FILE.exists():
        raise HTTPException(status_code=500, detail="credentials.json não encontrado.")

    try:
        flow = Flow.from_client_secrets_file(
            str(settings.GOOGLE_DRIVE_OAUTH_FILE),
            scopes=SCOPES,
            redirect_uri=settings.OAUTH_REDIRECT_URI,
            state=state
        )
        if code_verifier:
            flow.code_verifier = code_verifier

        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        settings.GOOGLE_DRIVE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(settings.GOOGLE_DRIVE_TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
            
        return RedirectResponse(url='/')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o callback do Google: {str(e)}")

@router.get('/status')
def google_auth_status():
    """Retorna o status da conexão OAuth."""
    from ingestion.drive_client import GoogleDriveManager
    dm = GoogleDriveManager()
    return dm.get_status()

@router.post('/disconnect')
def google_disconnect():
    """Remove o token e desconecta."""
    token_path = settings.GOOGLE_DRIVE_TOKEN_FILE
    if token_path.exists():
        token_path.unlink()
    return {'message': 'Desconectado do Google Drive'}
