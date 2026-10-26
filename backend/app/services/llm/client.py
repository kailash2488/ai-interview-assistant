"""Thin Ollama client: structured (JSON-schema) chat with validation + retry, and embeddings."""
import json
import logging
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class for LLM failures; the message is safe to show to the user."""


class LLMUnavailable(LLMError):
    """Ollama is unreachable or the model is missing."""


class LLMInvalidOutput(LLMError):
    """The model kept returning output that does not match the schema."""


class LLMClient(Protocol):
    def chat_json(
        self, *, system: str, user: str, schema: type[T], model: str | None = None, temperature: float = 0.1
    ) -> T: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.timeout = timeout or settings.llm_timeout_seconds

    def _post(self, path: str, payload: dict) -> dict:
        try:
            res = httpx.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.base_url}. Is it running?") from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailable("Ollama took too long to respond") from exc
        if res.status_code == 404:
            raise LLMUnavailable(f"Model '{payload.get('model')}' is not installed. Run: ollama pull {payload.get('model')}")
        if res.status_code >= 400:
            raise LLMError(f"Ollama returned HTTP {res.status_code}: {res.text[:200]}")
        return res.json()

    def chat_json(
        self, *, system: str, user: str, schema: type[T], model: str | None = None, temperature: float = 0.1
    ) -> T:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_error = ""
        for attempt in range(settings.llm_max_retries + 1):
            data = self._post(
                "/api/chat",
                {
                    "model": model or settings.evaluator_model,
                    "messages": messages,
                    "stream": False,
                    "format": schema.model_json_schema(),
                    "options": {"temperature": temperature, "num_ctx": settings.llm_num_ctx},
                },
            )
            content = data.get("message", {}).get("content", "")
            try:
                return schema.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)[:300]
                log.warning("Invalid LLM output (attempt %d): %s", attempt + 1, last_error)
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "That output was invalid. Return ONLY valid JSON matching the schema. "
                        f"Problem: {last_error}",
                    },
                ]
        raise LLMInvalidOutput(f"The model returned invalid output after retrying: {last_error}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/api/embed", {"model": settings.embed_model, "input": texts})
        vectors = data.get("embeddings")
        if not vectors or len(vectors) != len(texts):
            raise LLMError("Ollama returned an unexpected embeddings response")
        return vectors


def get_llm() -> LLMClient:
    return OllamaClient()
