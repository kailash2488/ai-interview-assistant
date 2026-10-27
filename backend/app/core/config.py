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

    # "ollama" (local, private, default) or "gemini" (Google's hosted API; needs AIA_GEMINI_API_KEY)
    llm_provider: Literal["ollama", "gemini"] = "ollama"

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

    runtime_settings_path: Path = BACKEND_DIR / "data" / "llm_settings.json"  # written by the Settings screen

    qdrant_path: str = str(BACKEND_DIR / "data" / "qdrant")  # ":memory:" for tests
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
