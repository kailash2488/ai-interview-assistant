"""Per-account model choice. Each user picks the model and brings their own Gemini key; the server's environment
values are only the defaults for accounts that have not chosen anything."""
import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models import UserLLMSettings

log = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
# Models offered in the Settings screen (from Google AI Studio's list). `tier` is a hint only: Google's pricing page
# lists a free tier for the first two; the others are paid. Check your own limits in AI Studio.
GEMINI_MODELS = [
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "note": "Fastest and cheapest. Recommended", "tier": "free"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "note": "Newest and most capable Flash model, but often busy on the free tier", "tier": "free"},
    {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "note": "Balanced speed and quality", "tier": "paid"},
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (preview)", "note": "Strongest reasoning, slowest", "tier": "paid"},
]
GEMINI_MODEL_IDS = [m["id"] for m in GEMINI_MODELS]


@dataclass(frozen=True)
class LLMConfig:
    provider: str                 # "ollama" | "gemini"
    gemini_model: str
    gemini_api_key: str | None
    key_source: str               # "settings" (the user's own key) | "environment" (server default) | "none"

    @property
    def key_hint(self) -> str | None:
        key = (self.gemini_api_key or "").strip()
        return f"…{key[-4:]}" if len(key) >= 8 else None


def _env_key() -> str | None:
    return settings.gemini_api_key.get_secret_value().strip() or None if settings.gemini_api_key else None


def server_default() -> LLMConfig:
    key = _env_key()
    return LLMConfig(settings.llm_provider, settings.gemini_model, key, "environment" if key else "none")


def config_for_user(db: Session, user_id: str | None) -> LLMConfig:
    row = db.get(UserLLMSettings, user_id) if user_id else None
    if row is None:
        return server_default()
    own = decrypt_secret(row.gemini_key_enc) if row.gemini_key_enc else None
    key = own or _env_key()
    model = row.gemini_model if row.gemini_model in GEMINI_MODEL_IDS else DEFAULT_GEMINI_MODEL
    return LLMConfig(row.provider, model, key, "settings" if own else ("environment" if key else "none"))


def save_for_user(db: Session, user_id: str, *, provider: str, gemini_model: str, api_key: str | None = None, clear_key: bool = False) -> None:
    row = db.get(UserLLMSettings, user_id)
    if row is None:
        row = UserLLMSettings(user_id=user_id)
        db.add(row)
    row.provider, row.gemini_model = provider, gemini_model
    if clear_key:
        row.gemini_key_enc = None
    elif api_key:
        row.gemini_key_enc = encrypt_secret(api_key.strip())
    db.commit()


def import_legacy_file(db: Session, user_id: str) -> bool:
    """Before accounts existed the Settings page wrote one global file. The first account adopts it (key included,
    now encrypted in the database) and the plain-text file is removed."""
    path = settings.runtime_settings_path
    try:
        saved = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    provider = saved.get("provider") if saved.get("provider") in ("ollama", "gemini") else settings.llm_provider
    model = saved.get("gemini_model") if saved.get("gemini_model") in GEMINI_MODEL_IDS else DEFAULT_GEMINI_MODEL
    key = saved.get("gemini_api_key")
    save_for_user(db, user_id, provider=provider, gemini_model=model, api_key=key)
    try:
        path.unlink()
    except OSError:
        log.warning("Could not remove the old settings file %s", path)
    log.info("Imported legacy LLM settings into the first account")
    return True
