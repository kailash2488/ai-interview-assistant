import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.schemas.analysis import CandidateProfile
from app.schemas.interview import AnswerAnalysis
from app.services.llm.client import LLMError, LLMInvalidOutput, LLMUnavailable, OllamaClient, get_llm
from app.services.llm.gemini import GeminiClient, to_gemini_schema


@pytest.fixture(autouse=True)
def gemini_settings(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("test-key"))
    monkeypatch.setattr(settings, "gemini_rate_limit_retries", 1)
    monkeypatch.setattr("time.sleep", lambda s: None)


def resp(body, status=200):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "http://x"))


def ok(text):
    return resp({"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]})


class Recorder:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def collect_keys(node, found=None):
    found = found if found is not None else set()
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(k)
            if k != "properties":
                collect_keys(v, found)
            else:
                for pv in v.values():
                    collect_keys(pv, found)
    elif isinstance(node, list):
        for n in node:
            collect_keys(n, found)
    return found


def test_schema_conversion_inlines_refs_and_drops_unsupported_keys():
    schema = to_gemini_schema(CandidateProfile.model_json_schema())
    keys = collect_keys(schema)
    assert not keys & {"$ref", "$defs", "title", "default", "anyOf", "additionalProperties"}
    skill = schema["properties"]["skills"]["items"]
    assert skill["properties"]["level"]["enum"] == ["beginner", "intermediate", "advanced", "unknown"]
    assert schema["properties"]["name"] == {"type": "string", "nullable": True}
    assert schema["properties"]["total_experience_years"]["nullable"] is True


def test_schema_conversion_keeps_literals():
    schema = to_gemini_schema(AnswerAnalysis.model_json_schema())
    assert schema["properties"]["answer_quality"]["enum"] == ["weak", "ok", "strong"]


def test_chat_json_request_shape_and_parsing(monkeypatch):
    rec = Recorder(ok(json.dumps({"answer_quality": "strong", "needs_follow_up": False})))
    monkeypatch.setattr(httpx, "post", rec)
    out = GeminiClient().chat_json(system="sys", user="usr", schema=AnswerAnalysis, temperature=0.0, max_tokens=50)
    assert out.answer_quality == "strong"
    call = rec.calls[0]
    assert call["url"].endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert call["headers"]["x-goog-api-key"] == "test-key"
    cfg = call["json"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and "responseSchema" in cfg
    assert cfg["maxOutputTokens"] == 1024  # floor: hidden thinking tokens share this budget
    assert cfg["thinkingConfig"] == {"thinkingLevel": "low"}
    assert call["json"]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert call["json"]["contents"] == [{"role": "user", "parts": [{"text": "usr"}]}]


def test_invalid_json_retries_once_then_fails(monkeypatch):
    rec = Recorder(ok("nope"), ok("still nope"))
    monkeypatch.setattr(httpx, "post", rec)
    with pytest.raises(LLMInvalidOutput):
        GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)
    assert len(rec.calls) == 2
    assert rec.calls[1]["json"]["contents"][1]["role"] == "model"


def test_rate_limit_is_retried_then_reported(monkeypatch):
    rec = Recorder(resp({"error": {"message": "quota"}}, 429), ok(json.dumps({})))
    monkeypatch.setattr(httpx, "post", rec)
    assert GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis).answer_quality == "ok"
    monkeypatch.setattr(httpx, "post", Recorder(*[resp({"error": {"message": "quota"}}, 429)] * 2))
    with pytest.raises(LLMUnavailable, match="rate limit"):
        GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)


def test_error_messages_never_contain_the_key(monkeypatch):
    for status, body, match in [
        (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}, "rejected the API key"),
        (403, {"error": {"message": "denied"}}, "rejected the API key"),
        (404, {"error": {"message": "nf"}}, "not found"),
        (500, {"error": {"message": "boom"}}, "temporarily unavailable"),
        (503, {"error": {"message": "high demand"}}, "overloaded right now"),
        (400, {"error": {"message": "bad request body"}}, "HTTP 400"),
    ]:
        monkeypatch.setattr(httpx, "post", Recorder(resp(body, status), resp(body, status)))  # 400s are retried once without thinkingConfig
        with pytest.raises(LLMError, match=match) as exc:
            GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)
        assert "test-key" not in str(exc.value)


def test_network_failures_and_blocked_output(monkeypatch):
    monkeypatch.setattr(httpx, "post", Recorder(httpx.ConnectError("x")))
    with pytest.raises(LLMUnavailable, match="internet"):
        GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)
    monkeypatch.setattr(httpx, "post", Recorder(httpx.ReadTimeout("x")))
    with pytest.raises(LLMUnavailable, match="did not answer in time"):
        GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)
    monkeypatch.setattr(httpx, "post", Recorder(resp({"promptFeedback": {"blockReason": "SAFETY"}})))
    with pytest.raises(LLMError, match="SAFETY"):
        GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis)


class FakeStream:
    def __init__(self, lines, status=200):
        self.lines, self.status_code = lines, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        return iter(self.lines)

    def read(self):
        return b""

    def json(self):
        return {"error": {"message": "API key not valid"}}

    text = ""


def sse(text):
    return "data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_stream_text_parses_sse(monkeypatch):
    captured = {}

    def fake_stream(method, url, headers=None, json=None, timeout=None):
        captured.update(url=url, json=json)
        return FakeStream([sse("How do "), "", sse("you test?"), "data: "])

    monkeypatch.setattr(httpx, "stream", fake_stream)
    out = "".join(GeminiClient().stream_text(system="s", user="u", max_tokens=90))
    assert out == "How do you test?"
    assert captured["url"].endswith(":streamGenerateContent?alt=sse")
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 1024  # a tiny limit would be eaten by thinking
    assert "responseSchema" not in captured["json"]["generationConfig"]


def test_stream_errors(monkeypatch):
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStream([], 403))
    with pytest.raises(LLMUnavailable, match="API key"):
        list(GeminiClient().stream_text(system="s", user="u"))


def test_missing_key_gives_actionable_error(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    with pytest.raises(LLMUnavailable, match="Settings page"):
        GeminiClient()
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("  "))
    with pytest.raises(LLMUnavailable, match="Settings page"):
        GeminiClient()


def test_provider_selection_and_embeddings_flag(monkeypatch):
    assert isinstance(get_llm(), OllamaClient)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    client = get_llm()
    assert isinstance(client, GeminiClient) and client.model_name == "gemini-3.5-flash-lite"
    assert client.supports_embeddings is False
    with pytest.raises(LLMError, match="embedding model"):
        client.embed(["x"])
    monkeypatch.setattr(settings, "gemini_embed_model", "some-embed-model")
    assert GeminiClient().supports_embeddings is True


def test_secret_key_is_not_exposed_in_repr():
    assert "test-key" not in repr(settings.gemini_api_key) and "test-key" not in repr(settings)


def test_analysis_with_gemini_skips_indexing_without_warning(client, monkeypatch):
    from tests.fakes import FakeLLM
    from tests.test_analysis_api import _ready_session

    fake = FakeLLM()
    fake.supports_embeddings = False
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: fake)
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    body = client.get(f"/sessions/{sid}/analysis").json()
    assert body["status"] == "ready" and body["warnings"] == [] and fake.embed_calls == 0


def thinking_rejected():
    return resp({"error": {"message": "Request contains an invalid argument."}}, 400)  # real message: it does not name the field


def test_thinking_config_rejection_retries_without_it_and_is_remembered(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_thinking_unsupported", set())
    rec = Recorder(thinking_rejected(), ok(json.dumps({})), ok(json.dumps({})))
    monkeypatch.setattr(httpx, "post", rec)
    GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis, max_tokens=50)
    assert "thinkingConfig" in rec.calls[0]["json"]["generationConfig"]
    retry_cfg = rec.calls[1]["json"]["generationConfig"]
    assert "thinkingConfig" not in retry_cfg and retry_cfg["maxOutputTokens"] >= 1024  # thinking shares the budget now
    GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis, max_tokens=50)  # remembered: no probing again
    assert "thinkingConfig" not in rec.calls[2]["json"]["generationConfig"] and len(rec.calls) == 3


def test_thinking_rejection_does_not_consume_rate_limit_retries(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_thinking_unsupported", set())
    rec = Recorder(thinking_rejected(), resp({"error": {"message": "quota"}}, 429), ok(json.dumps({})))
    monkeypatch.setattr(httpx, "post", rec)
    assert GeminiClient().chat_json(system="s", user="u", schema=AnswerAnalysis).answer_quality == "ok"


def test_stream_retries_without_thinking_config(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_thinking_unsupported", set())
    bodies = []

    class Rejected(FakeStream):
        def json(self):
            return {"error": {"message": "Request contains an invalid argument."}}

    def fake_stream(method, url, headers=None, json=None, timeout=None):
        bodies.append(json)
        return Rejected([], 400) if len(bodies) == 1 else FakeStream([sse("Hello there?")])

    monkeypatch.setattr(httpx, "stream", fake_stream)
    assert "".join(GeminiClient().stream_text(system="s", user="u")) == "Hello there?"
    assert "thinkingConfig" in bodies[0]["generationConfig"] and "thinkingConfig" not in bodies[1]["generationConfig"]


def test_every_object_in_the_schema_is_fully_required_and_ordered():
    schema = to_gemini_schema(CandidateProfile.model_json_schema())

    def objects(node):
        if isinstance(node, dict):
            if "properties" in node:
                yield node
                for v in node["properties"].values():
                    yield from objects(v)
            for k in ("items",):
                if k in node:
                    yield from objects(node[k])

    found = list(objects(schema))
    assert len(found) >= 4  # profile, skill, employer, project
    for obj in found:
        assert obj["required"] == list(obj["properties"]) == obj["propertyOrdering"]
