"""Thin Ollama client: structured (JSON-schema) chat with validation + retry, and embeddings."""
import json
import logging
from collections.abc import Iterator
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
        self, *, system: str, user: str, schema: type[T], model: str | None = None, temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> T: ...

    def stream_text(
        self, *, system: str, user: str, model: str | None = None, temperature: float = 0.6, max_tokens: int | None = None
    ) -> Iterator[str]: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaClient:
    supports_embeddings = True

    @property
    def model_name(self) -> str:
        return settings.evaluator_model

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
        self, *, system: str, user: str, schema: type[T], model: str | None = None, temperature: float = 0.1,
        max_tokens: int | None = None,
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
                    "options": self._options(temperature, max_tokens),
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

    @staticmethod
    def _options(temperature: float, max_tokens: int | None) -> dict:
        options: dict = {"temperature": temperature, "num_ctx": settings.llm_num_ctx}
        if max_tokens:
            options["num_predict"] = max_tokens
        return options

    def stream_text(
        self, *, system: str, user: str, model: str | None = None, temperature: float = 0.6, max_tokens: int | None = None
    ) -> Iterator[str]:
        """Yield text pieces as the model produces them (for live token streaming)."""
        payload = {
            "model": model or settings.interviewer_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": True,
            "options": self._options(temperature, max_tokens),
        }
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=self.timeout) as res:
                if res.status_code == 404:
                    raise LLMUnavailable(f"Model '{payload['model']}' is not installed. Run: ollama pull {payload['model']}")
                if res.status_code >= 400:
                    raise LLMError(f"Ollama returned HTTP {res.status_code}")
                for line in res.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        return
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.base_url}. Is it running?") from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailable("Ollama took too long to respond") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/api/embed", {"model": settings.embed_model, "input": texts})
        vectors = data.get("embeddings")
        if not vectors or len(vectors) != len(texts):
            raise LLMError("Ollama returned an unexpected embeddings response")
        return vectors


def get_llm(config=None) -> LLMClient:
    """`config` (an LLMConfig) is the signed-in user's choice; without it the server defaults are used."""
    from app.services.llm.user_settings import server_default

    config = config or server_default()
    if config.provider == "gemini":
        from app.services.llm.gemini import GeminiClient

        return GeminiClient(config)
    return OllamaClient()
