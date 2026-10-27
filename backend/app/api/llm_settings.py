import time
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.services.llm import runtime
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
    gemini_model: str = Field(default=runtime.DEFAULT_GEMINI_MODEL, max_length=80)
    gemini_api_key: str | None = Field(default=None, max_length=300)  # omit to keep the saved key

    @field_validator("gemini_model")
    @classmethod
    def _known_model(cls, v: str) -> str:
        if v not in runtime.GEMINI_MODEL_IDS:
            raise ValueError(f"Unknown model. Choose one of: {', '.join(runtime.GEMINI_MODEL_IDS)}")
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


def _out() -> LLMSettingsOut:
    source = runtime.key_source()
    return LLMSettingsOut(
        provider=settings.llm_provider, gemini_model=settings.gemini_model, gemini_models=runtime.GEMINI_MODELS,
        gemini_key_set=source != "none", gemini_key_hint=runtime.key_hint(), gemini_key_source=source,
        ollama_model=settings.interviewer_model,
    )


@router.get("", response_model=LLMSettingsOut)
def get_settings():
    return _out()


@router.put("", response_model=LLMSettingsOut)
def update_settings(payload: LLMSettingsIn):
    if payload.provider == "gemini" and not payload.gemini_api_key and runtime.key_source() == "none":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a Gemini API key to use Gemini")
    runtime.save(provider=payload.provider, gemini_model=payload.gemini_model, gemini_api_key=payload.gemini_api_key)
    return _out()


@router.delete("/key", response_model=LLMSettingsOut)
def remove_key():
    saved = runtime.load()
    # Removing the key also switches back to the local model so nothing is left half-configured.
    runtime.save(provider="ollama" if runtime.key_source() != "environment" else settings.llm_provider,
                 gemini_model=settings.gemini_model if settings.gemini_model in runtime.GEMINI_MODEL_IDS else runtime.DEFAULT_GEMINI_MODEL,
                 clear_key=True)
    return _out()


@router.post("/test", response_model=TestResult)
def test_connection():
    """One tiny structured call with the active provider, so a bad key or a stopped Ollama shows up here."""
    from pydantic import BaseModel as _Model

    class Ping(_Model):
        reply: str

    provider = settings.llm_provider
    started = time.time()
    try:
        llm = get_llm()
        out = llm.chat_json(system="Reply with JSON only.", user='Return {"reply": "ok"}.', schema=Ping,
                            temperature=0.0, max_tokens=30)
        return TestResult(ok=True, provider=provider, model=getattr(llm, "model_name", None),
                          seconds=round(time.time() - started, 1), message=f"Connected. Model replied: {out.reply!r}")
    except LLMError as exc:
        return TestResult(ok=False, provider=provider, model=None, seconds=None, message=str(exc))
    except httpx.HTTPError:
        return TestResult(ok=False, provider=provider, model=None, seconds=None, message="Network error while contacting the model")
