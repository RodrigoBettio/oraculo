import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    BASE_DIR: Path = BASE_DIR

    # Environment
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')
    OAUTH_REDIRECT_URI: str = os.getenv('OAUTH_REDIRECT_URI', 'http://127.0.0.1:8000/auth/google/callback')
    # Governança de Execução Autônoma (em minutos)
    AUTONOMOUS_EXECUTION_DELAY_MINUTES: int = int(os.getenv("AUTONOMOUS_EXECUTION_DELAY_MINUTES", "5"))

    # Telegram
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID") or 0)
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_SESSION_NAME: str = os.getenv("TELEGRAM_SESSION_NAME", "oraculo_session")
    TELEGRAM_TARGET_FOLDER: str = os.getenv("TELEGRAM_TARGET_FOLDER", "Estudos")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_BOT_TOKEN_BRAIN: str = os.getenv("TELEGRAM_BOT_TOKEN_BRAIN", "").strip()

    # Relatório Diário Executivo
    DAILY_REPORT_HOUR: int = int(os.getenv("DAILY_REPORT_HOUR", "8"))
    DAILY_REPORT_MINUTE: int = int(os.getenv("DAILY_REPORT_MINUTE", "30"))

    # Obsidian Vault (2º Cérebro)
    OBSIDIAN_VAULT_PATH: Path = Path(os.getenv("OBSIDIAN_VAULT_PATH", ""))

    # Gemini API (Chave única ou Pool de múltiplas chaves rotativas)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    @property
    def GEMINI_API_KEYS(self) -> list[str]:
        keys_env = os.getenv("GEMINI_API_KEYS", "")
        keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        if not keys and self.GEMINI_API_KEY:
            keys = [self.GEMINI_API_KEY.strip()]
        return keys

    # Concorrência Assimétrica por Fonte (Dual-Engine: Drive em alta vazão na nuvem, Telegram seguro anti-flood)
    MAX_TELEGRAM_WORKERS: int = int(os.getenv("MAX_TELEGRAM_WORKERS", "4"))
    MAX_DRIVE_WORKERS: int = int(os.getenv("MAX_DRIVE_WORKERS", "16"))
    MAX_STUDY_WORKERS: int = int(os.getenv("MAX_STUDY_WORKERS", "20"))

    # Modelos Oficiais de Produção (com fallback resiliente de alta velocidade)
    STUDY_MODELS: list[str] = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.7-flash"]
    ORCHESTRATION_MODELS: list[str] = ["gemini-3.8-flash", "gemini-pro-latest", "gemini-flash-latest"]

    # Google Drive (Master Drive fixo como padrão: 💎 DRIVE PREMIUM - MESTRE DOS CURSOS)
    GOOGLE_DRIVE_FOLDER_ID: str = (os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "1cBDvRvFL4B5TmD7oXYfcTYvlHl40GXGG").strip()
    GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE: Path = BASE_DIR / os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "credentials/google_drive_service_account.json")
    GOOGLE_DRIVE_OAUTH_FILE: Path = BASE_DIR / os.getenv("GOOGLE_DRIVE_OAUTH_FILE", "credentials/credentials.json")
    GOOGLE_DRIVE_TOKEN_FILE: Path = BASE_DIR / os.getenv("GOOGLE_DRIVE_TOKEN_FILE", "credentials/token.json")
    CREDENTIALS_DIR: Path = BASE_DIR / "credentials"

    # Diretórios do Sistema
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
    VIDEOS_DIR: Path = BASE_DIR / os.getenv("VIDEOS_DIR", "data/videos")
    PROCESSED_DIR: Path = BASE_DIR / os.getenv("PROCESSED_DIR", "data/processed")
    AGENTS_DIR: Path = BASE_DIR / os.getenv("AGENTS_DIR", "data/agents")
    AREAS_DIR: Path = BASE_DIR / os.getenv("AREAS_DIR", "data/areas")
    WORKSPACES_DIR: Path = BASE_DIR / os.getenv("WORKSPACES_DIR", "data/workspaces")

    @classmethod
    def ensure_directories(cls):
        """Garante que as pastas de dados existam."""
        for directory in [cls.DATA_DIR, cls.VIDEOS_DIR, cls.PROCESSED_DIR, cls.AGENTS_DIR, cls.AREAS_DIR, cls.CREDENTIALS_DIR, cls.WORKSPACES_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
