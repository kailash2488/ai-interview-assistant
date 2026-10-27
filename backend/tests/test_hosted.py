import httpx
from pydantic import BaseModel

from app.services.llm.hosted import AnthropicClient, OpenAICompatibleClient
from app.services.llm.user_settings import LLMConfig


class Reply(BaseModel):
    reply: str


def config(provider, model="cloud-model", endpoint=None):
    return LLMConfig(provider, "gemini-3.5-flash-lite", None, "settings", model=model, api_key="secret-key-1234", azure_endpoint=endpoint)


def test_openai_structured_request_uses_saved_model(monkeypatch):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"reply":"ok"}'}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    out = OpenAICompatibleClient(config("openai")).chat_json(system="system", user="user", schema=Reply, model="mistral:7b")
    assert out.reply == "ok" and seen["json"]["model"] == "cloud-model"
    assert seen["headers"]["Authorization"] == "Bearer secret-key-1234"
    assert seen["json"]["response_format"]["type"] == "json_schema"


def test_azure_builds_deployment_url_and_uses_api_key(monkeypatch):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"reply":"ok"}'}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    OpenAICompatibleClient(config("azure", "my-deployment", "https://example.openai.azure.com")).chat_json(system="s", user="u", schema=Reply)
    assert "/deployments/my-deployment/chat/completions" in seen["url"]
    assert "api-version=2024-10-21" in seen["url"] and seen["headers"]["api-key"] == "secret-key-1234"


def test_anthropic_structured_request(monkeypatch):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"content": [{"text": '{"reply":"ok"}'}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    out = AnthropicClient(config("anthropic", "claude-test")).chat_json(system="s", user="u", schema=Reply, model="mistral:7b")
    assert out.reply == "ok" and seen["json"]["model"] == "claude-test"
    assert seen["headers"]["x-api-key"] == "secret-key-1234"
