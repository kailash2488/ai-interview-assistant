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
    provider: Literal["ollama", "gemini"]
    gemini_model: str
    gemini_models: list[GeminiModelOut]
    gemini_key_set: bool
    gemini_key_hint: str | None
    gemini_key_source: Literal["settings", "environment", "none"]
    ollama_model: str


class LLMSettingsIn(BaseModel):
    provider: Literal["ollama", "gemini"]
    gemini_model: str = Field(default=us.DEFAULT_GEMINI_MODEL, max_length=80)
    gemini_api_key: str | None = Field(default=None, max_length=300)  # omit to keep the saved key

    @field_validator("gemini_model")
    @classmethod
    def _known_model(cls, v: str) -> str:
        if v not in us.GEMINI_MODEL_IDS:
            raise ValueError(f"Unknown model. Choose one of: {', '.join(us.GEMINI_MODEL_IDS)}")
        return v

    @field_validator("gemini_api_key")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        v = v.strip() if v else None
        if v and any(c.isspace() for c in v):
            raise ValueError("API keys do not contain spaces")
        return v or None


class TestResult(BaseModel):
    ok: bool
    provider: str
    model: str | None
    seconds: float | None
    message: str


def _out(db: Session, user: User) -> LLMSettingsOut:
    cfg = us.config_for_user(db, user.id)
    return LLMSettingsOut(
        provider=cfg.provider, gemini_model=cfg.gemini_model, gemini_models=us.GEMINI_MODELS,
        gemini_key_set=cfg.key_source != "none", gemini_key_hint=cfg.key_hint, gemini_key_source=cfg.key_source,
        ollama_model=settings.interviewer_model,
    )


@router.get("", response_model=LLMSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _out(db, user)


@router.put("", response_model=LLMSettingsOut)
def update_settings(payload: LLMSettingsIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.provider == "gemini" and not payload.gemini_api_key and us.config_for_user(db, user.id).key_source == "none":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a Gemini API key to use Gemini")
    us.save_for_user(db, user.id, provider=payload.provider, gemini_model=payload.gemini_model, api_key=payload.gemini_api_key)
    return _out(db, user)


@router.delete("/key", response_model=LLMSettingsOut)
def remove_key(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Removing the key also switches back to the local model so nothing is left half-configured."""
    cfg = us.config_for_user(db, user.id)
    still_has_server_key = cfg.key_source == "settings" and us.server_default().gemini_api_key
    us.save_for_user(db, user.id, provider=cfg.provider if still_has_server_key else "ollama", gemini_model=cfg.gemini_model, clear_key=True)
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
