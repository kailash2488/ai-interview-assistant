from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIA_", env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_mb: int = 10
    max_other_documents: int = 10

    # Keep local models available for source-based development, but allow deployments to disable them.
    enable_ollama: bool = True
    llm_provider: Literal["ollama", "gemini", "openai", "anthropic", "azure"] = "ollama"

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_thinking_level: str | None = "low"  # Gemini 3 models take a level (not a token budget); None = model default
    gemini_embed_model: str = ""  # empty = no embeddings with Gemini (retrieval is optional)
    gemini_timeout_seconds: float = 45.0
    gemini_rate_limit_retries: int = 2

    ollama_url: str = "http://localhost:11434"
    interviewer_model: str = "mistral:7b"
    evaluator_model: str = "mistral:7b"
    embed_model: str = "nomic-embed-text"
    llm_timeout_seconds: float = 600.0
    llm_num_ctx: int = 6144
    llm_max_retries: int = 1

    # --- voice (optional; needs `pip install ".[voice]"` and the models from scripts/download_voice.py) ---
    voice_dir: Path = BACKEND_DIR / "data" / "voice"
    whisper_model: str = "base.en"       # speech-to-text; "small.en" is more accurate and slower
    piper_voice: str = "en_US-lessac-medium"
    voice_max_audio_mb: int = 15
    voice_max_seconds: int = 300
    voice_pause_seconds: float = 1.5     # a silence this long between phrases counts as a pause

    # --- accounts ---
    allow_signup: bool = True            # set AIA_ALLOW_SIGNUP=false once your accounts exist
    session_days: int = 30
    cookie_name: str = "aia_session"
    cookie_secure: bool = False          # set AIA_COOKIE_SECURE=true when serving over HTTPS
    secret_key: SecretStr | None = None  # encrypts stored API keys; generated into data/secret.key if unset
    secret_key_path: Path = BACKEND_DIR / "data" / "secret.key"
    max_login_failures: int = 5
    login_lockout_minutes: int = 15

    runtime_settings_path: Path = BACKEND_DIR / "data" / "llm_settings.json"  # written by the Settings screen

    qdrant_path: str = str(BACKEND_DIR / "data" / "qdrant")  # ":memory:" for tests
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
