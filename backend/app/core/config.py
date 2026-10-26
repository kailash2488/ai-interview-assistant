from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIA_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_mb: int = 10

    ollama_url: str = "http://localhost:11434"
    interviewer_model: str = "mistral:7b"
    evaluator_model: str = "mistral:7b"
    embed_model: str = "nomic-embed-text"
    llm_timeout_seconds: float = 600.0
    llm_num_ctx: int = 6144
    llm_max_retries: int = 1

    qdrant_path: str = str(BACKEND_DIR / "data" / "qdrant")  # ":memory:" for tests
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
