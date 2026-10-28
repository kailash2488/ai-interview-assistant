import httpx
import pytest
from pydantic import SecretStr

from app.api import labs
from app.core.config import settings
from app.models import User


def test_diagram_signature_validation_rejects_active_or_fake_content():
    assert labs._image_type(b"<svg><script>alert(1)</script></svg>") is None
    assert labs._image_type(b"RIFF00000000NOTW") is None
    assert labs._image_type(b"\x89PNG\r\n\x1a\nrest") == (".png", "image/png")
    assert labs._image_type(b"\xff\xd8\xffrest") == (".jpg", "image/jpeg")
    assert labs._image_type(b"RIFF0000WEBPrest") == (".webp", "image/webp")


def test_code_execution_is_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "code_runner_url", "")
    monkeypatch.setattr(settings, "code_runner_token", None)
    with pytest.raises(labs.HTTPException) as caught:
        labs.run_code(labs.CodeRunIn(language="python", code="print(1)"), User(id="u"))
    assert caught.value.status_code == 503


def test_runner_receives_fixed_isolation_policy(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"exit_code": 0, "stdout": "ok", "stderr": "", "timed_out": False},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "code_runner_url", "https://runner.example.com")
    monkeypatch.setattr(settings, "code_runner_token", SecretStr("runner-secret"))
    monkeypatch.setattr(httpx, "post", post)
    labs._runs.clear()
    result = labs.run_code(labs.CodeRunIn(language="python", code="print(1)"), User(id="u"))
    assert result.stdout == "ok"
    assert captured["json"] | {"network": False, "read_only": True} == captured["json"]
    assert captured["json"]["memory_mb"] == 128 and captured["json"]["pids"] == 32
    assert captured["headers"]["Authorization"] == "Bearer runner-secret"


@pytest.mark.parametrize("url", ["http://public.example.com", "ftp://runner", "https://user:pass@runner.example.com"])
def test_runner_rejects_insecure_or_credentialed_urls(monkeypatch, url):
    monkeypatch.setattr(settings, "code_runner_url", url)
    monkeypatch.setattr(settings, "code_runner_token", SecretStr("secret"))
    assert labs._runner_configured() is False
