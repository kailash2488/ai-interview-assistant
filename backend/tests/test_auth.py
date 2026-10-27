import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from starlette.websockets import WebSocketDisconnect

from app.api import auth
from app.core import migrate
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import decrypt_secret, hash_password, verify_password
from app.main import app
from app.models import AuthSession, InterviewSession, User, UserLLMSettings
from tests.conftest import OTHER, USER
from tests.fakes import FakeLLM
from tests.test_analysis_api import RESUME, _ready_session
from tests.test_api import _create_session, _upload
from tests.test_interview_api import analysed, planned  # noqa: F401  (fixtures)
from tests.samples import JD


# ---------- password hashing ----------

def test_password_hashing():
    a, b = hash_password("s3cret-passphrase"), hash_password("s3cret-passphrase")
    assert a != b and a.startswith("scrypt$") and "s3cret" not in a  # unique salt, never plain text
    assert verify_password("s3cret-passphrase", a) and not verify_password("S3cret-passphrase", a)
    assert not verify_password("x", "not-a-valid-hash") and not verify_password("x", "bcrypt$1$2$3$4$5")
    tampered = a[:-4] + "AAAA"
    assert not verify_password("s3cret-passphrase", tampered)


# ---------- signup ----------

def test_signup_creates_an_account_and_signs_you_in(anon_client):
    r = anon_client.post("/auth/signup", json={"email": "  New@Example.COM ", "name": "  Ada  ", "password": "long enough pw"})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com" and body["name"] == "Ada" and "password" not in str(body) and "hash" not in str(body)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie and "secure" not in cookie
    assert anon_client.get("/auth/me").json()["email"] == "new@example.com"


def test_secure_cookie_flag_follows_the_setting(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", True)
    r = anon_client.post("/auth/signup", json=USER)
    assert "secure" in r.headers["set-cookie"].lower()


def test_session_token_is_stored_hashed(client):
    token = client.cookies.get(settings.cookie_name)
    with SessionLocal() as db:
        row = db.query(AuthSession).one()
        assert token and row.token_hash != token and token not in row.token_hash and len(row.token_hash) == 64
        user = db.query(User).one()
        assert user.password_hash.startswith("scrypt$") and USER["password"] not in user.password_hash


@pytest.mark.parametrize("payload, field", [
    ({"email": "nope", "name": "A", "password": "long enough pw"}, "email"),
    ({"email": "a@b", "name": "A", "password": "long enough pw"}, "email"),
    ({"email": "a@example.com", "name": "A", "password": "short"}, "password"),
    ({"email": "a@example.com", "name": "   ", "password": "long enough pw"}, "name"),
    ({"email": "a@example.com", "name": "A", "password": "x" * 200}, "password"),
    ({"email": "a@example.com", "password": "long enough pw"}, "name"),
])
def test_signup_validation(anon_client, payload, field):
    r = anon_client.post("/auth/signup", json=payload)
    assert r.status_code == 422 and field in r.text


def test_duplicate_email_is_rejected_case_insensitively(client, anon_client):
    r = TestClient(app).post("/auth/signup", json={**USER, "email": USER["email"].upper()})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_signup_can_be_closed(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "allow_signup", False)
    assert anon_client.get("/auth/config").json() == {"allow_signup": False}
    r = anon_client.post("/auth/signup", json=USER)
    assert r.status_code == 403 and "closed" in r.json()["detail"]
    monkeypatch.setattr(settings, "allow_signup", True)
    assert anon_client.get("/auth/config").json() == {"allow_signup": True}


# ---------- login / logout ----------

def test_login_and_logout(client):
    other_browser = TestClient(app)
    r = other_browser.post("/auth/login", json={"email": USER["email"].upper(), "password": USER["password"]})
    assert r.status_code == 200 and other_browser.get("/auth/me").status_code == 200

    old_token = other_browser.cookies.get(settings.cookie_name)
    assert other_browser.post("/auth/logout").status_code == 204
    assert other_browser.get("/auth/me").status_code == 401
    replay = TestClient(app, cookies={settings.cookie_name: old_token})
    assert replay.get("/auth/me").status_code == 401  # the old token is dead on the server, not just forgotten
    assert client.get("/auth/me").status_code == 200   # the other browser stays signed in


def test_wrong_credentials_give_the_same_generic_error(client):
    c = TestClient(app)
    wrong_pw = c.post("/auth/login", json={"email": USER["email"], "password": "wrong password"})
    no_user = c.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever pw"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json() == {"detail": "Wrong email or password"}
    assert settings.cookie_name not in wrong_pw.headers.get("set-cookie", "")


def test_repeated_failures_lock_the_login_then_reset_on_success(client):
    c = TestClient(app)
    bad = {"email": USER["email"], "password": "wrong password"}
    for _ in range(settings.max_login_failures):
        assert c.post("/auth/login", json=bad).status_code == 401
    locked = c.post("/auth/login", json=bad)
    assert locked.status_code == 429 and "Try again in" in locked.json()["detail"]
    # even the right password is refused while locked, so guessing cannot continue through the lock
    assert c.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 429
    # another account is unaffected
    assert c.post("/auth/signup", json=OTHER).status_code == 201
    auth._failures.clear()
    assert c.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 200


def test_success_clears_earlier_failures(client):
    c = TestClient(app)
    for _ in range(settings.max_login_failures - 1):
        c.post("/auth/login", json={"email": USER["email"], "password": "nope nope nope"})
    assert c.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 200
    for _ in range(settings.max_login_failures - 1):
        assert c.post("/auth/login", json={"email": USER["email"], "password": "nope nope nope"}).status_code == 401


def test_me_needs_a_valid_session(anon_client):
    assert anon_client.get("/auth/me").status_code == 401
    garbage = TestClient(app, cookies={settings.cookie_name: "not-a-real-token"})
    assert garbage.get("/auth/me").status_code == 401


def test_expired_sessions_are_rejected_and_removed(client):
    with SessionLocal() as db:
        row = db.query(AuthSession).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me").status_code == 401
    with SessionLocal() as db:
        assert db.query(AuthSession).count() == 0


# ---------- password change and account deletion ----------

def test_change_password(client):
    second = TestClient(app)
    second.post("/auth/login", json={"email": USER["email"], "password": USER["password"]})
    assert client.post("/auth/change-password", json={"current_password": "wrong", "new_password": "a brand new password"}).status_code == 403
    assert client.post("/auth/change-password", json={"current_password": USER["password"], "new_password": "short"}).status_code == 422
    assert client.post("/auth/change-password", json={"current_password": USER["password"], "new_password": "a brand new password"}).status_code == 204

    assert client.get("/auth/me").status_code == 200       # this browser stays signed in
    assert second.get("/auth/me").status_code == 401        # every other browser is signed out
    fresh = TestClient(app)
    assert fresh.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 401
    assert fresh.post("/auth/login", json={"email": USER["email"], "password": "a brand new password"}).status_code == 200


def test_delete_account_removes_everything_and_frees_the_email(client):
    sid = _create_session(client)
    _upload(client, sid, "resume", "r.txt", RESUME.encode())
    upload_dir = settings.upload_dir / sid
    assert upload_dir.exists()

    assert client.request("DELETE", "/auth/me", json={"password": "wrong"}).status_code == 403
    assert client.get("/auth/me").status_code == 200
    assert client.request("DELETE", "/auth/me", json={"password": USER["password"]}).status_code == 204
    assert not upload_dir.exists()
    with SessionLocal() as db:
        assert db.query(User).count() == 0 and db.query(InterviewSession).count() == 0 and db.query(AuthSession).count() == 0
    assert client.get("/auth/me").status_code == 401
    assert TestClient(app).post("/auth/signup", json=USER).status_code == 201


def test_deleting_an_account_does_not_touch_other_accounts(client, other_client):
    mine, theirs = _create_session(client), _create_session(other_client)
    assert client.request("DELETE", "/auth/me", json={"password": USER["password"]}).status_code == 204
    assert [s["id"] for s in other_client.get("/sessions").json()] == [theirs] and mine != theirs


# ---------- the first account adopts what existed before accounts ----------

def test_first_account_adopts_old_interviews_and_settings(anon_client):
    with SessionLocal() as db:
        db.add(InterviewSession(title="Old", target_role="Dev", interview_type="mixed", difficulty="medium", question_count=8))
        db.commit()
    settings.runtime_settings_path.write_text(json.dumps({"provider": "gemini", "gemini_model": "gemini-3.8-flash", "gemini_api_key": "AIzaLEGACYKEY1234567890abcd"}))

    assert anon_client.post("/auth/signup", json=USER).status_code == 201
    assert [s["title"] for s in anon_client.get("/sessions").json()] == ["Old"]
    cfg = anon_client.get("/settings/llm").json()
    assert cfg["provider"] == "gemini" and cfg["gemini_model"] == "gemini-3.8-flash" and cfg["gemini_key_hint"] == "…abcd"
    assert not settings.runtime_settings_path.exists()  # the plain-text key file is gone
    with SessionLocal() as db:
        assert "LEGACY" not in db.query(UserLLMSettings).one().gemini_key_enc
        assert decrypt_secret(db.query(UserLLMSettings).one().gemini_key_enc) == "AIzaLEGACYKEY1234567890abcd"


def test_second_account_adopts_nothing(client, other_client):
    assert other_client.get("/sessions").json() == []
    assert other_client.get("/settings/llm").json()["gemini_key_set"] is False


def test_old_databases_get_the_owner_column():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE sessions (id VARCHAR(32) PRIMARY KEY, title VARCHAR(200))"))
        conn.execute(text("INSERT INTO sessions (id, title) VALUES ('a', 'old')"))
    migrate.upgrade(engine)
    migrate.upgrade(engine)  # idempotent
    assert "user_id" in {c["name"] for c in inspect(engine).get_columns("sessions")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT user_id FROM sessions")).scalar() is None


# ---------- every API route needs a sign-in ----------

PROTECTED = [
    ("GET", "/sessions"), ("POST", "/sessions"), ("GET", "/sessions/x"), ("DELETE", "/sessions/x"),
    ("GET", "/sessions/x/documents"), ("POST", "/sessions/x/documents"), ("GET", "/sessions/x/documents/y"), ("DELETE", "/sessions/x/documents/y"),
    ("POST", "/sessions/x/analyze"), ("GET", "/sessions/x/analysis"), ("PATCH", "/sessions/x/analysis"),
    ("POST", "/sessions/x/plan"), ("GET", "/sessions/x/plan"), ("GET", "/sessions/x/interview"), ("POST", "/sessions/x/finish"),
    ("POST", "/sessions/x/report"), ("GET", "/sessions/x/report"), ("GET", "/sessions/x/report/pdf"),
    ("GET", "/history"), ("GET", "/history/compare?a=1&b=2"), ("GET", "/data"), ("DELETE", "/data"),
    ("GET", "/settings/llm"), ("PUT", "/settings/llm"), ("DELETE", "/settings/llm/key"), ("POST", "/settings/llm/test"),
    ("GET", "/auth/me"), ("POST", "/auth/change-password"), ("DELETE", "/auth/me"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_routes_require_a_session(anon_client, method, path):
    assert anon_client.request(method, path, json={}).status_code == 401, f"{method} {path} is not protected"


def test_only_the_expected_routes_are_public(anon_client):
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/auth/config").status_code == 200
    public = {("GET", "/health"), ("GET", "/auth/config"), ("POST", "/auth/signup"), ("POST", "/auth/login"), ("POST", "/auth/logout")}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            continue
        for m in methods - {"HEAD", "OPTIONS"}:
            if (m, path) in public:
                continue
            probe = path.replace("{session_id}", "x").replace("{document_id}", "y")
            if "compare" in probe:
                probe += "?a=1&b=2"
            assert anon_client.request(m, probe, json={}).status_code in (401, 405), f"{m} {path} is reachable without signing in"


# ---------- accounts cannot see each other's data ----------

def test_users_cannot_reach_each_others_interviews(client, other_client):
    sid = _create_session(client)
    _upload(client, sid, "resume", "r.txt", RESUME.encode())
    doc = client.get(f"/sessions/{sid}/documents").json()[0]["id"]

    assert other_client.get("/sessions").json() == []
    probes = [
        ("GET", f"/sessions/{sid}"), ("DELETE", f"/sessions/{sid}"), ("GET", f"/sessions/{sid}/documents"),
        ("GET", f"/sessions/{sid}/documents/{doc}"), ("DELETE", f"/sessions/{sid}/documents/{doc}"),
        ("POST", f"/sessions/{sid}/analyze"), ("GET", f"/sessions/{sid}/analysis"), ("POST", f"/sessions/{sid}/plan"),
        ("GET", f"/sessions/{sid}/plan"), ("GET", f"/sessions/{sid}/interview"), ("POST", f"/sessions/{sid}/finish"),
        ("POST", f"/sessions/{sid}/report"), ("GET", f"/sessions/{sid}/report"), ("GET", f"/sessions/{sid}/report/pdf"),
    ]
    for method, path in probes:
        r = other_client.request(method, path)
        assert r.status_code == 404, f"{method} {path} -> {r.status_code}"
        assert r.json()["detail"] in ("Session not found",), (method, path)  # same answer as for an interview that does not exist
    assert other_client.post(f"/sessions/{sid}/documents", data={"kind": "resume"}, files={"file": ("x.txt", b"hello hello hello", "text/plain")}).status_code == 404
    # nothing changed for the owner
    assert client.get(f"/sessions/{sid}").status_code == 200 and len(client.get(f"/sessions/{sid}/documents").json()) == 1


def test_history_and_compare_are_per_account(client, other_client, monkeypatch):
    from tests.test_phase5 import finished_report

    mine = finished_report(client, monkeypatch, 4, title="Mine A")
    mine2 = finished_report(client, monkeypatch, 5, title="Mine B")
    assert [i["session_id"] for i in client.get("/history").json()] == [mine, mine2]
    assert other_client.get("/history").json() == []
    r = other_client.get("/history/compare", params={"a": mine, "b": mine2})
    assert r.status_code == 404
    assert other_client.get("/data").json()["sessions"] == 0 and client.get("/data").json()["sessions"] == 2


def test_delete_all_data_only_deletes_the_callers_data(client, other_client):
    mine, theirs = _create_session(client), _create_session(other_client)
    assert client.request("DELETE", "/data", json={"confirm": "DELETE ALL"}).status_code == 200
    assert client.get("/sessions").json() == []
    assert [s["id"] for s in other_client.get("/sessions").json()] == [theirs] and mine != theirs
    assert client.get("/auth/me").status_code == 200  # the account and its settings remain


# ---------- WebSocket access ----------

def _connect(c, sid, **kw):
    return c.websocket_connect(f"/sessions/{sid}/interview", **kw)


def test_websocket_needs_the_owner(planned, client, other_client, anon_client, monkeypatch):
    monkeypatch.setattr("app.services.interview.engine.get_llm", lambda *a, **k: FakeLLM())
    with _connect(client, planned) as ws:
        assert ws.receive_json()["type"] == "state"
    for stranger in (other_client, TestClient(app)):
        with pytest.raises(WebSocketDisconnect):
            with _connect(stranger, planned):
                pass


def test_websocket_rejects_foreign_origins(planned, client):
    with pytest.raises(WebSocketDisconnect):
        with _connect(client, planned, headers={"origin": "https://evil.example"}):
            pass
    with _connect(client, planned, headers={"origin": "http://testserver"}) as ws:  # same host name as the app
        assert ws.receive_json()["type"] == "state"
    with _connect(client, planned, headers={"origin": "http://localhost:5173"}) as ws:  # a configured dev origin
        assert ws.receive_json()["type"] == "state"


# ---------- owner tool: password reset ----------

def test_owner_can_reset_a_password_and_it_signs_everyone_out(client):
    from scripts.reset_password import reset

    assert reset(USER["email"].upper(), "a brand new password") is True
    assert client.get("/auth/me").status_code == 401  # the browser that was signed in is signed out
    fresh = TestClient(app)
    assert fresh.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 401
    assert fresh.post("/auth/login", json={"email": USER["email"], "password": "a brand new password"}).status_code == 200


def test_reset_rejects_bad_passwords_and_unknown_accounts(client):
    from scripts.reset_password import reset

    assert reset("nobody@example.com", "a long enough password") is False
    with pytest.raises(ValueError):
        reset(USER["email"], "short")
    assert TestClient(app).post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 200
