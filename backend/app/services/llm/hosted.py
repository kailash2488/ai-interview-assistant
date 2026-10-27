"""OpenAI, Anthropic and Azure OpenAI clients behind the project's small LLM interface."""
import json
from collections.abc import Iterator
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.services.llm.client import LLMError, LLMInvalidOutput, LLMUnavailable
from app.services.llm.user_settings import LLMConfig

T = TypeVar("T", bound=BaseModel)


def _validated(content: str, schema: type[T]) -> T:
    try:
        return schema.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMInvalidOutput("The model returned an invalid structured response. Try again.") from exc


def _strict_schema(value):
    """OpenAI strict mode requires every object to forbid extras and require every declared field."""
    if isinstance(value, list):
        return [_strict_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = {key: _strict_schema(item) for key, item in value.items()}
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
    return out


class OpenAICompatibleClient:
    supports_embeddings = False

    def __init__(self, config: LLMConfig):
        if not config.api_key:
            raise LLMUnavailable(f"{config.provider.title()} is selected but no API key is saved. Add one in Settings.")
        self.provider = config.provider
        self._key = config.api_key
        self.model = config.model or "gpt-4o-mini"
        if config.provider == "azure":
            if not config.azure_endpoint:
                raise LLMUnavailable("Azure OpenAI needs an endpoint URL. Add it in Settings.")
            version = config.azure_api_version or "2024-10-21"
            self.url = f"{config.azure_endpoint.rstrip('/')}/openai/deployments/{self.model}/chat/completions?api-version={version}"
            self.headers = {"api-key": self._key, "Content-Type": "application/json"}
        else:
            self.url = "https://api.openai.com/v1/chat/completions"
            self.headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    @property
    def model_name(self) -> str:
        return self.model

    def _raise(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise LLMUnavailable(f"{self.provider.title()} rejected the API key. Check it in Settings.")
        if response.status_code == 429:
            raise LLMUnavailable(f"{self.provider.title()} rate limit reached. Wait a moment and try again.")
        if response.status_code >= 400:
            raise LLMError(f"{self.provider.title()} returned HTTP {response.status_code}.")

    def _request(self, body: dict) -> httpx.Response:
        try:
            response = httpx.post(self.url, headers=self.headers, json=body, timeout=90)
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"{self.provider.title()} did not answer in time.") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Cannot reach {self.provider.title()}. Check your connection.") from exc
        self._raise(response)
        return response

    def chat_json(self, *, system: str, user: str, schema: type[T], model: str | None = None,
                  temperature: float = 0.1, max_tokens: int | None = None) -> T:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_schema", "json_schema": {"name": schema.__name__, "strict": True, "schema": _strict_schema(schema.model_json_schema())}},
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        data = self._request(body).json()
        try:
            return _validated(data["choices"][0]["message"]["content"], schema)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.provider.title()} returned an unexpected response.") from exc

    def stream_text(self, *, system: str, user: str, model: str | None = None,
                    temperature: float = 0.6, max_tokens: int | None = None) -> Iterator[str]:
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": temperature, "stream": True}
        if max_tokens:
            body["max_tokens"] = max_tokens
        try:
            with httpx.stream("POST", self.url, headers=self.headers, json=body, timeout=90) as response:
                self._raise(response)
                for line in response.iter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    piece = json.loads(line[6:]).get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if piece:
                        yield piece
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Cannot reach {self.provider.title()} during streaming.") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Cloud embeddings are not enabled; core documents are still passed directly to the model.")


class AnthropicClient:
    supports_embeddings = False

    def __init__(self, config: LLMConfig):
        if not config.api_key:
            raise LLMUnavailable("Anthropic is selected but no API key is saved. Add one in Settings.")
        self._key = config.api_key
        self.model = config.model or "claude-3-5-haiku-latest"
        self.url = "https://api.anthropic.com/v1/messages"
        self.headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}

    @property
    def model_name(self) -> str:
        return self.model

    def _post(self, body: dict) -> dict:
        try:
            response = httpx.post(self.url, headers=self.headers, json=body, timeout=90)
        except httpx.HTTPError as exc:
            raise LLMUnavailable("Cannot reach Anthropic. Check your connection.") from exc
        if response.status_code in (401, 403):
            raise LLMUnavailable("Anthropic rejected the API key. Check it in Settings.")
        if response.status_code == 429:
            raise LLMUnavailable("Anthropic rate limit reached. Wait a moment and try again.")
        if response.status_code >= 400:
            raise LLMError(f"Anthropic returned HTTP {response.status_code}.")
        return response.json()

    def chat_json(self, *, system: str, user: str, schema: type[T], model: str | None = None,
                  temperature: float = 0.1, max_tokens: int | None = None) -> T:
        prompt = f"{user}\n\nReturn only JSON matching this schema:\n{json.dumps(schema.model_json_schema())}"
        data = self._post({"model": self.model, "system": system, "messages": [{"role": "user", "content": prompt}],
                           "temperature": temperature, "max_tokens": max(max_tokens or 1024, 256)})
        try:
            return _validated(data["content"][0]["text"], schema)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Anthropic returned an unexpected response.") from exc

    def stream_text(self, *, system: str, user: str, model: str | None = None,
                    temperature: float = 0.6, max_tokens: int | None = None) -> Iterator[str]:
        body = {"model": self.model, "system": system, "messages": [{"role": "user", "content": user}],
                "temperature": temperature, "max_tokens": max_tokens or 1024, "stream": True}
        try:
            with httpx.stream("POST", self.url, headers=self.headers, json=body, timeout=90) as response:
                if response.status_code >= 400:
                    raise LLMError(f"Anthropic returned HTTP {response.status_code}.")
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    piece = event.get("delta", {}).get("text", "")
                    if piece:
                        yield piece
        except httpx.HTTPError as exc:
            raise LLMUnavailable("Cannot reach Anthropic during streaming.") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Anthropic does not provide embeddings; core documents are still passed directly to the model.")
