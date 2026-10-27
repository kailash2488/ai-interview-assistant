"""Gemini (Google AI Studio) client with the same interface as OllamaClient.

Optional provider. Resume and job-description text is sent to Google, so it is off by default
(AIA_LLM_PROVIDER=gemini turns it on). The free tier may use content to improve Google products.
"""
import json
import logging
import time
from collections.abc import Iterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.llm.client import LLMError, LLMInvalidOutput, LLMUnavailable

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
MIN_JSON_TOKENS = 256
MIN_OUTPUT_TOKENS = 1024  # thinking shares the output budget
_DROP_KEYS = {"title", "default", "additionalProperties", "$defs", "definitions", "examples"}


def to_gemini_schema(schema: dict) -> dict:
    """Pydantic JSON Schema -> the OpenAPI-style subset Gemini's responseSchema accepts:
    inline $ref, drop unsupported keys, turn `anyOf: [X, null]` into `nullable`."""
    defs = {**schema.get("$defs", {}), **schema.get("definitions", {})}

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return convert(defs[node["$ref"].split("/")[-1]])
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            out = convert(options[0]) if len(options) == 1 else {"anyOf": [convert(o) for o in options]}
            if len(options) != len(node["anyOf"]):
                out = {**out, "nullable": True}
            return out
        out = {k: convert(v) for k, v in node.items() if k not in _DROP_KEYS}
        if isinstance(out.get("properties"), dict):  # property *names* may collide with dropped keywords
            out["properties"] = {k: convert(v) for k, v in node["properties"].items()}
            # Optional fields let small models skip ahead and spill key names into arrays, so require every
            # field and fix the order. Pydantic still supplies defaults when validating.
            names = list(out["properties"])
            out["required"], out["propertyOrdering"] = names, names
        return out

    return convert({k: v for k, v in schema.items() if k not in ("$defs", "definitions")})


def _rejects_thinking_config(res: httpx.Response) -> bool:
    """Models differ in which thinking settings they accept, and Google's 400 does not always name the
    field ("Request contains an invalid argument"), so any 400 is worth one retry without thinkingConfig."""
    return res.status_code == 400


class GeminiClient:
    supports_embeddings = False
    _thinking_unsupported: set[str] = set()  # models that rejected thinkingConfig; remembered for the process

    def __init__(self) -> None:
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
            raise LLMUnavailable(
                "Gemini is selected but no API key is set. Add your key on the Settings page "
                "(or set AIA_GEMINI_API_KEY in backend/.env). Create a free key at https://aistudio.google.com/apikey."
            )
        self._key = settings.gemini_api_key.get_secret_value().strip()
        self.supports_embeddings = bool(settings.gemini_embed_model)

    @property
    def model_name(self) -> str:
        return settings.gemini_model

    # ---------- request plumbing ----------

    def _url(self, method: str) -> str:
        return f"{settings.gemini_base_url.rstrip('/')}/models/{settings.gemini_model}:{method}"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._key, "Content-Type": "application/json"}

    def _body(self, system: str, messages: list[dict], temperature: float, max_tokens: int | None, schema: dict | None) -> dict:
        config: dict[str, Any] = {"temperature": temperature}
        thinking_off = settings.gemini_thinking_level is not None and settings.gemini_model not in self._thinking_unsupported
        if max_tokens:
            # Hidden "thinking" tokens count against maxOutputTokens, so a small limit can cut the answer to a
            # few words. Prompts already ask for brevity; the limit is only a safety ceiling.
            floor = MIN_JSON_TOKENS if schema and not settings.gemini_thinking_level else MIN_OUTPUT_TOKENS
            config["maxOutputTokens"] = max(max_tokens, floor)
        if schema is not None:
            config["responseMimeType"] = "application/json"
            config["responseSchema"] = schema
        if thinking_off:
            config["thinkingConfig"] = {"thinkingLevel": settings.gemini_thinking_level}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": messages,
            "generationConfig": config,
        }

    @staticmethod
    def _without_thinking(body: dict) -> dict:
        config = {k: v for k, v in body["generationConfig"].items() if k != "thinkingConfig"}
        if "maxOutputTokens" in config and "responseSchema" in config:
            config["maxOutputTokens"] = max(config["maxOutputTokens"], MIN_OUTPUT_TOKENS)
        return {**body, "generationConfig": config}

    @staticmethod
    def _raise_for_status(res: httpx.Response) -> None:
        if res.status_code < 400:
            return
        try:
            detail = res.json()["error"]["message"]
        except Exception:
            detail = res.text[:200]
        code = res.status_code
        if code in (401, 403) or (code == 400 and "API key" in detail):
            raise LLMUnavailable("Gemini rejected the API key. Check it on the Settings page.")
        if code == 404:
            raise LLMUnavailable(f"Gemini model '{settings.gemini_model}' was not found. Pick another model on the Settings page.")
        if code == 429:
            raise LLMUnavailable("Gemini free-tier rate limit reached. Wait a minute and try again.")
        if code == 503:
            raise LLMUnavailable(
                f"Google says {settings.gemini_model} is overloaded right now. Try again in a minute, "
                "or choose Gemini 3.5 Flash-Lite on the Settings page."
            )
        if code >= 500:
            raise LLMUnavailable("Gemini is temporarily unavailable. Try again shortly.")
        raise LLMError(f"Gemini returned HTTP {code}: {detail}")

    def _post(self, method: str, body: dict) -> dict:
        retries_left = settings.gemini_rate_limit_retries
        wait = 5
        while True:
            try:
                res = httpx.post(self._url(method), headers=self._headers(), json=body, timeout=settings.gemini_timeout_seconds)
            except httpx.ConnectError as exc:
                raise LLMUnavailable("Cannot reach the Gemini API. Check your internet connection.") from exc
            except httpx.TimeoutException as exc:
                raise LLMUnavailable(
                    f"{settings.gemini_model} did not answer in time (Google may be overloaded). "
                    "Try again, or choose Gemini 3.5 Flash-Lite on the Settings page."
                ) from exc
            if _rejects_thinking_config(res) and "thinkingConfig" in body["generationConfig"]:
                log.info("%s does not accept thinkingConfig; retrying without it", settings.gemini_model)
                self._thinking_unsupported.add(settings.gemini_model)
                body = self._without_thinking(body)
                continue  # happens at most once per call: the key is gone on the next pass
            if res.status_code in (429, 503) and retries_left > 0:
                log.warning("Gemini returned %d; retrying in %ds", res.status_code, wait)
                time.sleep(wait)
                retries_left, wait = retries_left - 1, wait * 2
                continue
            self._raise_for_status(res)
            return res.json()

    @staticmethod
    def _text(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise LLMError(f"Gemini returned no answer ({reason})")
        cand = candidates[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
        if not text and cand.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            raise LLMError("Gemini blocked this response for safety reasons")
        return text

    # ---------- public API (same as OllamaClient) ----------

    def chat_json(
        self, *, system: str, user: str, schema: type[T], model: str | None = None, temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> T:
        json_schema = to_gemini_schema(schema.model_json_schema())
        messages = [{"role": "user", "parts": [{"text": user}]}]
        last_error = ""
        for attempt in range(settings.llm_max_retries + 1):
            data = self._post("generateContent", self._body(system, messages, temperature, max_tokens, json_schema))
            content = self._text(data)
            try:
                return schema.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)[:300]
                log.warning("Invalid Gemini output (attempt %d): %s", attempt + 1, last_error)
                messages = messages + [
                    {"role": "model", "parts": [{"text": content}]},
                    {"role": "user", "parts": [{"text": f"That output was invalid. Return ONLY valid JSON matching the schema. Problem: {last_error}"}]},
                ]
        raise LLMInvalidOutput(f"The model returned invalid output after retrying: {last_error}")

    def stream_text(
        self, *, system: str, user: str, model: str | None = None, temperature: float = 0.6, max_tokens: int | None = None
    ) -> Iterator[str]:
        body = self._body(system, [{"role": "user", "parts": [{"text": user}]}], temperature, max_tokens, None)
        try:
            for _ in range(2):  # second pass only if the model rejects thinkingConfig
                retry = False
                with httpx.stream("POST", self._url("streamGenerateContent") + "?alt=sse", headers=self._headers(), json=body,
                                  timeout=settings.gemini_timeout_seconds) as res:
                    if res.status_code >= 400:
                        res.read()
                        if _rejects_thinking_config(res) and "thinkingConfig" in body["generationConfig"]:
                            self._thinking_unsupported.add(settings.gemini_model)
                            body, retry = self._without_thinking(body), True
                        else:
                            self._raise_for_status(res)
                    else:
                        for line in res.iter_lines():
                            if not line.startswith("data:"):
                                continue
                            payload = line[5:].strip()
                            if not payload:
                                continue
                            piece = self._text_or_empty(json.loads(payload))
                            if piece:
                                yield piece
                if not retry:
                    return
        except httpx.ConnectError as exc:
            raise LLMUnavailable("Cannot reach the Gemini API. Check your internet connection.") from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(
                    f"{settings.gemini_model} did not answer in time (Google may be overloaded). "
                    "Try again, or choose Gemini 3.5 Flash-Lite on the Settings page."
                ) from exc

    def _text_or_empty(self, data: dict) -> str:
        try:
            return self._text(data)
        except LLMError:
            if data.get("candidates"):  # a safety stop mid-stream: keep what we already streamed
                return ""
            raise

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.gemini_embed_model:
            raise LLMError("No Gemini embedding model is configured (AIA_GEMINI_EMBED_MODEL)")
        url = f"{settings.gemini_base_url.rstrip('/')}/models/{settings.gemini_embed_model}:batchEmbedContents"
        body = {"requests": [{"model": f"models/{settings.gemini_embed_model}", "content": {"parts": [{"text": t}]}} for t in texts]}
        try:
            res = httpx.post(url, headers=self._headers(), json=body, timeout=settings.gemini_timeout_seconds)
        except httpx.HTTPError as exc:
            raise LLMUnavailable("Could not reach the Gemini embeddings API") from exc
        self._raise_for_status(res)
        vectors = [e["values"] for e in res.json().get("embeddings", [])]
        if len(vectors) != len(texts):
            raise LLMError("Gemini returned an unexpected embeddings response")
        return vectors
