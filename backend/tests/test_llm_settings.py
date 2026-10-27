import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import decrypt_secret
from app.models import UserLLMSettings
from app.services.llm import user_settings as us

KEY = "AIzaSyTESTKEY1234567890abcdef"


@pytest.fixture(autouse=True)
def server_defaults(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.5-flash-lite")


def save(client, **body):
    return client.put("/settings/llm", json=body)


def test_requires_sign_in(anon_client):
    assert anon_client.get("/settings/llm").status_code == 401
    assert anon_client.put("/settings/llm", json={"provider": "ollama"}).status_code == 401
    assert anon_client.post("/settings/llm/test").status_code == 401


def test_defaults_to_local_without_a_key(client):
    body = client.get("/settings/llm").json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is False and body["gemini_key_hint"] is None
    assert [m["id"] for m in body["gemini_models"]] == ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview"]
    assert {m["tier"] for m in body["gemini_models"]} == {"free", "paid"}
    assert body["gemini_model"] == "gemini-3.5-flash-lite"


def test_validation(client):
    assert save(client, provider="gemini").status_code == 422  # needs a key
    assert save(client, provider="gemini", gemini_api_key="has space").status_code == 422
    assert save(client, provider="claude").status_code == 422
    r = save(client, provider="gemini", gemini_api_key=KEY, gemini_model="gemini-2.5-flash")
    assert r.status_code == 422 and "Unknown model" in r.text


def test_key_is_never_returned_and_is_encrypted_at_rest(client):
    r = save(client, provider="gemini", gemini_api_key=f"  {KEY} ", gemini_model="gemini-3.1-pro-preview")
    body = r.json()
    assert r.status_code == 200 and body["provider"] == "gemini" and body["gemini_key_source"] == "settings"
    assert body["gemini_key_hint"] == "…cdef" and body["gemini_model"] == "gemini-3.1-pro-preview"
    assert KEY not in r.text and KEY not in client.get("/settings/llm").text
    with SessionLocal() as db:
        row = db.query(UserLLMSettings).one()
        assert KEY not in row.gemini_key_enc and decrypt_secret(row.gemini_key_enc) == KEY


def test_omitting_the_key_keeps_it(client):
    save(client, provider="gemini", gemini_api_key=KEY)
    body = save(client, provider="gemini", gemini_model="gemini-3.6-flash").json()
    assert body["gemini_key_hint"] == "…cdef" and body["gemini_model"] == "gemini-3.6-flash"
    body = save(client, provider="ollama").json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is True  # saved but unused


def test_removing_the_key_switches_back_to_local(client):
    save(client, provider="gemini", gemini_api_key=KEY)
    body = client.delete("/settings/llm/key").json()
    assert body["provider"] == "ollama" and body["gemini_key_set"] is False
    with SessionLocal() as db:
        assert db.query(UserLLMSettings).one().gemini_key_enc is None


def test_each_account_has_its_own_settings_and_key(client, other_client):
    save(client, provider="gemini", gemini_api_key=KEY, gemini_model="gemini-3.8-flash")
    theirs = other_client.get("/settings/llm").json()
    assert theirs["provider"] == "ollama" and theirs["gemini_key_set"] is False
    assert other_client.put("/settings/llm", json={"provider": "gemini"}).status_code == 422  # cannot borrow my key
    assert client.get("/settings/llm").json()["gemini_key_hint"] == "…cdef"


def test_server_key_is_a_default_and_reported_as_such(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr(KEY))
    body = client.get("/settings/llm").json()
    assert body["gemini_key_source"] == "environment" and body["gemini_key_set"] is True and KEY not in str(body)
    own = "AIzaOWNKEY0000000000000zzzz"
    assert save(client, provider="gemini", gemini_api_key=own).json()["gemini_key_source"] == "settings"


def test_changed_secret_key_means_the_user_re_enters_their_key(client, monkeypatch):
    save(client, provider="gemini", gemini_api_key=KEY)
    monkeypatch.setattr(settings, "secret_key", SecretStr("a-different-server-secret"))
    body = client.get("/settings/llm").json()
    assert body["gemini_key_set"] is False  # undecryptable, so treated as not set instead of crashing


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

    save(client, provider="gemini", gemini_api_key=KEY)
    gem = httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"reply": "ok"}'}]}}]}, request=httpx.Request("POST", "http://x"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: gem)
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is True and r["model"] == "gemini-3.5-flash-lite"

    bad = httpx.Response(403, json={"error": {"message": "denied"}}, request=httpx.Request("POST", "http://x"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: bad)
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is False and "rejected the API key" in r["message"] and KEY not in str(r)


def test_gemini_without_a_key_explains_what_to_do(client):
    with SessionLocal() as db:
        from app.models import User
        uid = db.query(User).one().id
        db.add(UserLLMSettings(user_id=uid, provider="gemini", gemini_model="gemini-3.5-flash-lite"))
        db.commit()
    r = client.post("/settings/llm/test").json()
    assert r["ok"] is False and "Settings page" in r["message"]


def test_config_lookup_for_legacy_sessions_uses_server_defaults():
    with SessionLocal() as db:
        cfg = us.config_for_user(db, None)
    assert cfg.provider == "ollama" and cfg.key_source == "none"
