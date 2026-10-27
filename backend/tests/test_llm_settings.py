import json
import os
import stat

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services.llm import runtime

KEY = "AIzaSyTESTKEY1234567890abcdef"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    path = settings.runtime_settings_path
    path.unlink(missing_ok=True)
    runtime._ENV_DEFAULTS.clear()
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.5-flash-lite")
    yield
    path.unlink(missing_ok=True)
    runtime._ENV_DEFAULTS.clear()


def test_defaults_to_local_without_a_key(client):
    body = client.get("/settings/llm").json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is False and body["gemini_key_hint"] is None
    assert [m["id"] for m in body["gemini_models"]] == ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview"]
    assert {m["tier"] for m in body["gemini_models"]} == {"free", "paid"}
    assert body["gemini_model"] == "gemini-3.5-flash-lite"


def test_gemini_requires_a_key(client):
    assert client.put("/settings/llm", json={"provider": "gemini"}).status_code == 422
    assert client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": "has space"}).status_code == 422
    assert client.put("/settings/llm", json={"provider": "claude"}).status_code == 422


def test_save_key_never_comes_back_and_file_is_private(client):
    r = client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": f"  {KEY} ", "gemini_model": "gemini-3.5-flash-lite"})
    body = r.json()
    assert r.status_code == 200 and body["provider"] == "gemini" and body["gemini_key_source"] == "settings"
    assert body["gemini_key_hint"] == "…cdef" and body["gemini_model"] == "gemini-3.5-flash-lite"
    assert KEY not in r.text and KEY not in client.get("/settings/llm").text
    assert settings.gemini_api_key.get_secret_value() == KEY  # live settings updated without a restart
    path = settings.runtime_settings_path
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["gemini_api_key"] == KEY


def test_omitting_the_key_keeps_the_saved_one(client):
    client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": KEY})
    body = client.put("/settings/llm", json={"provider": "gemini", "gemini_model": "gemini-3.1-pro-preview"}).json()
    assert body["gemini_key_hint"] == "…cdef" and body["gemini_model"] == "gemini-3.1-pro-preview"
    body = client.put("/settings/llm", json={"provider": "ollama"}).json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is True  # key stays saved, just unused


def test_removing_the_key_switches_back_to_local(client):
    client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": KEY})
    body = client.delete("/settings/llm/key").json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is False
    assert "gemini_api_key" not in json.loads(settings.runtime_settings_path.read_text())


def test_settings_survive_a_restart(client):
    client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": KEY})
    settings.llm_provider, settings.gemini_api_key = "ollama", None  # simulate a fresh process
    runtime.apply()
    assert settings.llm_provider == "gemini" and settings.gemini_api_key.get_secret_value() == KEY


def test_environment_key_is_reported_as_such(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr(KEY))
    body = client.get("/settings/llm").json()
    assert body["gemini_key_source"] == "environment" and body["gemini_key_set"] is True and KEY not in json.dumps(body)


def test_corrupt_settings_file_is_ignored(client):
    settings.runtime_settings_path.write_text("{not json")
    assert client.get("/settings/llm").json()["provider"] == "ollama"
    runtime.apply()


def test_connection_test_ollama_and_gemini(client, monkeypatch):
    def reply(content):
        return httpx.Response(200, json={"message": {"content": content}}, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx, "post", lambda *a, **k: reply('{"reply": "ok"}'))
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is True and r["provider"] == "ollama" and r["seconds"] is not None

    def refuse(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", refuse)
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is False and "Ollama" in r["message"]

    client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": KEY})
    gem = httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"reply": "ok"}'}]}}]}, request=httpx.Request("POST", "http://x"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: gem)
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is True and r["model"] == "gemini-3.5-flash-lite"

    bad = httpx.Response(403, json={"error": {"message": "denied"}}, request=httpx.Request("POST", "http://x"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: bad)
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is False and "rejected the API key" in r["message"] and KEY not in json.dumps(r)


def test_test_with_gemini_but_no_key_explains_what_to_do(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is False and "Settings page" in r["message"]


def test_unknown_model_is_rejected(client):
    r = client.put("/settings/llm", json={"provider": "gemini", "gemini_api_key": KEY, "gemini_model": "gemini-2.5-flash"})
    assert r.status_code == 422 and "Unknown model" in r.text


def test_old_saved_model_falls_back_to_default(client):
    settings.runtime_settings_path.write_text(json.dumps({"provider": "ollama", "gemini_model": "gemini-2.5-flash"}))
    runtime._ENV_DEFAULTS.clear()
    runtime.apply()
    assert settings.gemini_model == "gemini-3.5-flash-lite"
