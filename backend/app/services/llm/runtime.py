"""LLM provider choice made on the Settings screen, kept in a small local file.

Precedence: values saved here override environment / .env defaults. The API key is stored only on this
machine (file mode 600) and is never returned by the API.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.core.config import settings

log = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
# Models offered in the Settings screen (taken from Google AI Studio's model list). `tier` is a hint only:
# Google's pricing page lists a free tier for the first two; the others are paid. Check your limits in AI Studio.
GEMINI_MODELS = [
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "note": "Fastest and cheapest. Recommended", "tier": "free"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "note": "Newest and most capable Flash model, but often busy on the free tier", "tier": "free"},
    {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "note": "Balanced speed and quality", "tier": "paid"},
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (preview)", "note": "Strongest reasoning, slowest", "tier": "paid"},
]
GEMINI_MODEL_IDS = [m["id"] for m in GEMINI_MODELS]
_ENV_DEFAULTS: dict[str, Any] = {}


def _path() -> Path:
    return Path(settings.runtime_settings_path)


def _snapshot_env_defaults() -> None:
    if not _ENV_DEFAULTS:
        _ENV_DEFAULTS.update(provider=settings.llm_provider, key=settings.gemini_api_key, model=settings.gemini_model)


def load() -> dict[str, Any]:
    try:
        return json.loads(_path().read_text())
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        log.warning("Ignoring unreadable LLM settings file %s", _path())
        return {}


def apply() -> None:
    """Copy saved choices onto the live settings object (call at startup and after every save)."""
    _snapshot_env_defaults()
    saved = load()
    settings.llm_provider = saved.get("provider", _ENV_DEFAULTS["provider"])
    saved_model = saved.get("gemini_model")
    # A model that is no longer offered (for example an old saved choice) falls back to the default.
    settings.gemini_model = saved_model if saved_model in GEMINI_MODEL_IDS else _ENV_DEFAULTS["model"]
    key = saved.get("gemini_api_key")
    settings.gemini_api_key = SecretStr(key) if key else _ENV_DEFAULTS["key"]


def save(*, provider: str, gemini_model: str, gemini_api_key: str | None = None, clear_key: bool = False) -> None:
    saved = load()
    saved["provider"], saved["gemini_model"] = provider, gemini_model
    if clear_key:
        saved.pop("gemini_api_key", None)
    elif gemini_api_key:
        saved["gemini_api_key"] = gemini_api_key.strip()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(saved, f)
    os.replace(tmp, path)
    apply()


def key_hint() -> str | None:
    """Last four characters only, so the user can recognise which key is saved."""
    key = settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else ""
    return f"…{key[-4:]}" if len(key) >= 8 else None


def key_source() -> str:
    saved = load()
    if saved.get("gemini_api_key"):
        return "settings"
    return "environment" if settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip() else "none"
