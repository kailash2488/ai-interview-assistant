def test_question_banks_are_private_per_account(client, other_client):
    body = {"name": "Acme", "company": "Acme", "notes": "Public engineering research notes for interview practice."}
    created = client.post("/labs/question-banks", json=body)
    assert created.status_code == 201
    bank_id = created.json()["id"]
    assert [bank["id"] for bank in client.get("/labs/question-banks").json()] == [bank_id]
    assert other_client.get("/labs/question-banks").json() == []
    assert other_client.delete(f"/labs/question-banks/{bank_id}").status_code == 404


def test_code_runner_is_disabled_unless_isolation_is_configured(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "code_runner_url", "")
    monkeypatch.setattr(settings, "code_runner_token", None)
    assert client.get("/labs/coding").json()["enabled"] is False
    response = client.post("/labs/coding/run", json={"language": "python", "code": "print(1)"})
    assert response.status_code == 503


def test_system_design_rejects_svg_even_when_mislabeled(client):
    response = client.post(
        "/labs/system-designs",
        data={"title": "Unsafe", "prompt": "Design a safe notification service", "notes": ""},
        files={"diagram": ("diagram.png", b"<svg><script>alert(1)</script></svg>", "image/png")},
    )
    assert response.status_code == 415
