from tests.conftest import make_docx, make_pdf
from tests.samples import JD, RESUMES

SESSION = {"title": "Practice 1", "target_role": "Python Developer"}


def _create_session(client):
    r = client.post("/sessions", json=SESSION)
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client, sid, kind, name, content, mime="text/plain"):
    return client.post(
        f"/sessions/{sid}/documents", data={"kind": kind}, files={"file": (name, content, mime)}
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_session_crud(client):
    sid = _create_session(client)
    body = client.get(f"/sessions/{sid}").json()
    assert body["interview_type"] == "mixed" and body["question_count"] == 10
    assert len(client.get("/sessions").json()) == 1
    assert client.delete(f"/sessions/{sid}").status_code == 204
    assert client.get(f"/sessions/{sid}").status_code == 404


def test_session_validation(client):
    assert client.post("/sessions", json={**SESSION, "question_count": 1}).status_code == 422
    assert client.post("/sessions", json={**SESSION, "interview_type": "nope"}).status_code == 422
    assert client.post("/sessions", json={"title": "x"}).status_code == 422


def test_upload_txt_resume_and_jd_become_ready(client):
    sid = _create_session(client)
    r = _upload(client, sid, "resume", "resume.txt", RESUMES["backend_dev"].encode())
    assert r.status_code == 202 and r.json()["status"] == "uploaded"
    _upload(client, sid, "jd", "jd.txt", JD.encode())

    docs = client.get(f"/sessions/{sid}/documents").json()
    assert {d["kind"]: d["status"] for d in docs} == {"resume": "ready", "jd": "ready"}

    detail = client.get(f"/sessions/{sid}/documents/{docs[0]['id']}").json()
    assert "FastAPI" in detail["raw_text"]
    assert {s["name"] for s in detail["sections_json"]} >= {"experience", "skills"}


def test_upload_pdf_and_docx(client, tmp_path):
    sid = _create_session(client)
    pdf = make_pdf(tmp_path / "r.pdf", RESUMES["devops"]).read_bytes()
    docx = make_docx(tmp_path / "j.docx", JD).read_bytes()
    assert _upload(client, sid, "resume", "r.pdf", pdf, "application/pdf").status_code == 202
    assert _upload(client, sid, "jd", "j.docx", docx).status_code == 202
    statuses = {d["kind"]: d["status"] for d in client.get(f"/sessions/{sid}/documents").json()}
    assert statuses == {"resume": "ready", "jd": "ready"}


def test_reupload_replaces_resume(client):
    sid = _create_session(client)
    _upload(client, sid, "resume", "a.txt", b"first resume " * 10)
    _upload(client, sid, "resume", "b.txt", b"second resume " * 10)
    docs = client.get(f"/sessions/{sid}/documents").json()
    assert [d["filename"] for d in docs] == ["b.txt"]


def test_other_documents_accumulate(client):
    sid = _create_session(client)
    _upload(client, sid, "other", "a.txt", b"project notes " * 10)
    _upload(client, sid, "other", "b.txt", b"company notes " * 10)
    assert len(client.get(f"/sessions/{sid}/documents").json()) == 2


def test_rejects_bad_uploads(client):
    sid = _create_session(client)
    assert _upload(client, sid, "resume", "r.exe", b"x").status_code == 415
    assert _upload(client, sid, "resume", "r.pdf", b"not a pdf").status_code == 400
    assert _upload(client, sid, "resume", "r.txt", b"").status_code == 400
    assert _upload(client, sid, "bogus", "r.txt", b"hello").status_code == 422
    assert _upload(client, "missing", "resume", "r.txt", b"hello").status_code == 404


def test_rejects_oversized(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 0)
    sid = _create_session(client)
    assert _upload(client, sid, "resume", "r.txt", b"x").status_code == 413


def test_unparseable_document_is_marked_failed(client, tmp_path):
    import fitz

    blank = fitz.open()
    blank.new_page()
    path = tmp_path / "blank.pdf"
    blank.save(path)
    sid = _create_session(client)
    _upload(client, sid, "resume", "blank.pdf", path.read_bytes(), "application/pdf")
    doc = client.get(f"/sessions/{sid}/documents").json()[0]
    assert doc["status"] == "failed" and "No extractable text" in doc["error"]


def test_filename_path_traversal_is_neutralised(client):
    sid = _create_session(client)
    r = _upload(client, sid, "other", "../../etc/evil.txt", b"hello world " * 10)
    assert r.status_code == 202 and r.json()["filename"] == "evil.txt"


def test_delete_session_removes_files(client):
    from app.core.config import settings

    sid = _create_session(client)
    _upload(client, sid, "resume", "a.txt", b"hello resume " * 10)
    assert (settings.upload_dir / sid).exists()
    client.delete(f"/sessions/{sid}")
    assert not (settings.upload_dir / sid).exists()
