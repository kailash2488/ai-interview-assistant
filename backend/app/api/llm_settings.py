import time
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.core.db import get_db
from app.models import User
from app.services.llm import user_settings as us
from app.services.llm.client import LLMError, get_llm

router = APIRouter(prefix="/settings/llm", tags=["settings"])


class GeminiModelOut(BaseModel):
    id: str
    label: str
    note: str
    tier: Literal["free", "paid"]


class LLMSettingsOut(BaseModel):
    provider: Literal["ollama", "gemini", "openai", "anthropic", "azure"]
    gemini_model: str
    gemini_models: list[GeminiModelOut]
    gemini_key_set: bool
    gemini_key_hint: str | None
    gemini_key_source: Literal["settings", "environment", "none"]
    ollama_model: str
    ollama_enabled: bool
    openai_model: str
    anthropic_model: str
    azure_model: str
    azure_endpoint: str
    azure_api_version: str
    key_set: dict[str, bool]
    key_hint: dict[str, str | None]


class LLMSettingsIn(BaseModel):
    provider: Literal["ollama", "gemini", "openai", "anthropic", "azure"]
    gemini_model: str = Field(default=us.DEFAULT_GEMINI_MODEL, max_length=80)
    gemini_api_key: str | None = Field(default=None, max_length=300)  # omit to keep the saved key
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    azure_endpoint: str | None = Field(default=None, max_length=500)
    azure_api_version: str = Field(default="2024-10-21", max_length=40)

    @field_validator("gemini_model")
    @classmethod
    def _known_model(cls, v: str) -> str:
        if v not in us.GEMINI_MODEL_IDS:
            raise ValueError(f"Unknown model. Choose one of: {', '.join(us.GEMINI_MODEL_IDS)}")
        return v

    @field_validator("gemini_api_key", "api_key")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        v = v.strip() if v else None
        if v and any(c.isspace() for c in v):
            raise ValueError("API keys do not contain spaces")
        return v or None

    @field_validator("azure_endpoint")
    @classmethod
    def _endpoint(cls, v: str | None) -> str | None:
        v = v.strip().rstrip("/") if v else None
        if v and not v.startswith("https://"):
            raise ValueError("Azure endpoint must start with https://")
        return v


class TestResult(BaseModel):
    ok: bool
    provider: str
    model: str | None
    seconds: float | None
    message: str


def _out(db: Session, user: User) -> LLMSettingsOut:
    cfg = us.config_for_user(db, user.id)
    row = db.get(us.UserLLMSettings, user.id)
    keys, hints = {}, {}
    for provider in ("gemini", "openai", "anthropic", "azure"):
        enc = getattr(row, f"{provider}_key_enc", None) if row else None
        key = us.decrypt_secret(enc) if enc else (us._env_key() if provider == "gemini" else None)
        keys[provider] = bool(key)
        hints[provider] = f"…{key[-4:]}" if key and len(key) >= 8 else None
    saved_gemini = us.decrypt_secret(row.gemini_key_enc) if row and row.gemini_key_enc else None
    gemini_source = "settings" if saved_gemini else ("environment" if us._env_key() else "none")
    return LLMSettingsOut(
        provider=cfg.provider, gemini_model=cfg.gemini_model, gemini_models=us.GEMINI_MODELS,
        gemini_key_set=keys["gemini"], gemini_key_hint=hints["gemini"], gemini_key_source=gemini_source,
        ollama_model=settings.interviewer_model,
        ollama_enabled=settings.enable_ollama,
        openai_model=(row.openai_model if row and row.openai_model else us.DEFAULT_MODELS["openai"]),
        anthropic_model=(row.anthropic_model if row and row.anthropic_model else us.DEFAULT_MODELS["anthropic"]),
        azure_model=(row.azure_model if row and row.azure_model else "your-deployment-name"),
        azure_endpoint=(row.azure_endpoint if row and row.azure_endpoint else ""),
        azure_api_version=(row.azure_api_version if row and row.azure_api_version else "2024-10-21"),
        key_set=keys, key_hint=hints,
    )


@router.get("", response_model=LLMSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _out(db, user)


@router.put("", response_model=LLMSettingsOut)
def update_settings(payload: LLMSettingsIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.provider == "ollama" and not settings.enable_ollama:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Local Ollama is disabled on this server. Choose a cloud provider.",
        )
    existing = _out(db, user)
    incoming_key = payload.gemini_api_key if payload.provider == "gemini" else payload.api_key
    if payload.provider != "ollama" and not incoming_key and not existing.key_set.get(payload.provider):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Enter an API key to use {payload.provider.title()}")
    if payload.provider in ("openai", "anthropic", "azure") and not payload.model:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a model or deployment name")
    if payload.provider == "azure" and not (payload.azure_endpoint or existing.azure_endpoint):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter your Azure OpenAI endpoint")
    us.save_for_user(
        db, user.id, provider=payload.provider, gemini_model=payload.gemini_model,
        api_key=incoming_key, model=payload.model,
        azure_endpoint=payload.azure_endpoint, azure_api_version=payload.azure_api_version,
    )
    return _out(db, user)


@router.delete("/key", response_model=LLMSettingsOut)
def remove_key(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Removing the key also switches back to the local model so nothing is left half-configured."""
    cfg = us.config_for_user(db, user.id)
    still_has_server_key = bool(us.server_default().gemini_api_key)
    us.save_for_user(db, user.id, provider="gemini", gemini_model=cfg.gemini_model, clear_key=True)
    row = db.get(us.UserLLMSettings, user.id)
    if row:
        row.provider = "gemini" if still_has_server_key or not settings.enable_ollama else "ollama"
        db.commit()
    return _out(db, user)


@router.delete("/key/{provider}", response_model=LLMSettingsOut)
def remove_provider_key(provider: Literal["gemini", "openai", "anthropic", "azure"], db: Session = Depends(get_db), user: User = Depends(current_user)):
    cfg = us.config_for_user(db, user.id)
    us.save_for_user(db, user.id, provider=provider, gemini_model=cfg.gemini_model, clear_key=True)
    row = db.get(us.UserLLMSettings, user.id)
    if row and row.provider == provider:
        row.provider = "gemini" if not settings.enable_ollama else "ollama"
        db.commit()
    return _out(db, user)


@router.post("/test", response_model=TestResult)
def test_connection(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """One tiny structured call with the user's chosen provider, so a bad key or a stopped Ollama shows up here."""

    class Ping(BaseModel):
        reply: str

    cfg = us.config_for_user(db, user.id)
    started = time.time()
    try:
        llm = get_llm(cfg)
        out = llm.chat_json(system="Reply with JSON only.", user='Return {"reply": "ok"}.', schema=Ping, temperature=0.0, max_tokens=30)
        return TestResult(ok=True, provider=cfg.provider, model=getattr(llm, "model_name", None),
                          seconds=round(time.time() - started, 1), message=f"Connected. Model replied: {out.reply!r}")
    except LLMError as exc:
        return TestResult(ok=False, provider=cfg.provider, model=None, seconds=None, message=str(exc))
    except httpx.HTTPError:
        return TestResult(ok=False, provider=cfg.provider, model=None, seconds=None, message="Network error while contacting the model")
