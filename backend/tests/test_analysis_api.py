import pytest

from app.services.llm.client import LLMUnavailable
from app.services.vectorstore import get_client
from tests.fakes import FakeLLM
from tests.samples import JD, RESUMES
from tests.test_api import _create_session, _upload


@pytest.fixture()
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: fake)
    return fake


RESUME = "Asha Verma\nSKILLS\nPython, FastAPI, Kubernetes. Built an interview bot.\n"


def _ready_session(client, resume: str = RESUME):
    sid = _create_session(client)
    _upload(client, sid, "resume", "r.txt", resume.encode())
    _upload(client, sid, "jd", "jd.txt", JD.encode())
    return sid


def test_analyze_requires_ready_documents(client, llm):
    sid = _create_session(client)
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 409 and "resume" in r.json()["detail"] and "jd" in r.json()["detail"]
    assert client.get(f"/sessions/{sid}/analysis").status_code == 404
    assert client.post("/sessions/nope/analyze").status_code == 404


def test_analyze_end_to_end(client, llm):
    sid = _ready_session(client)
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 202 and r.json()["status"] == "running"

    body = client.get(f"/sessions/{sid}/analysis").json()
    assert body["status"] == "ready" and body["error"] is None
    assert body["profile"]["name"] == "Asha Verma"
    assert body["requirements"]["must_have_skills"][0] == "Python"
    assert body["gap"]["gaps"] == ["PostgreSQL", "Docker"]
    assert body["warnings"] == []
    assert client.get(f"/sessions/{sid}").json()["status"] == "analysed"

    # resume and JD text reach the prompts as delimited data
    schemas = [c[0] for c in llm.calls]
    assert schemas == ["CandidateProfile", "JDRequirements"]
    assert "Asha Verma" in llm.calls[0][2] and "<document>" in llm.calls[0][2]
    assert "Senior Python Developer" in llm.calls[1][2]


def test_analysis_indexes_documents_and_cleans_up(client, llm):
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    store = get_client()
    assert store.count("document_chunks").count >= 2
    client.delete(f"/sessions/{sid}")
    assert store.count("document_chunks").count == 0


def test_embedding_failure_is_a_warning_not_a_failure(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM(embed_fail=True))
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    body = client.get(f"/sessions/{sid}/analysis").json()
    assert body["status"] == "ready" and "not indexed" in body["warnings"][0]


def test_llm_failure_marks_analysis_failed_and_retry_works(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM(fail_with=LLMUnavailable("Cannot reach Ollama")))
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    body = client.get(f"/sessions/{sid}/analysis").json()
    assert body["status"] == "failed" and body["error"] == "Cannot reach Ollama" and body["profile"] is None

    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    assert client.post(f"/sessions/{sid}/analyze").status_code == 202
    assert client.get(f"/sessions/{sid}/analysis").json()["status"] == "ready"


def test_patch_recomputes_gap(client, llm):
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    analysis = client.get(f"/sessions/{sid}/analysis").json()

    profile = analysis["profile"]
    profile["skills"].append({"name": "Docker", "level": "advanced", "evidence": "Deployed services"})
    r = client.patch(f"/sessions/{sid}/analysis", json={"profile": profile})
    assert r.status_code == 200
    body = r.json()
    assert body["user_edited"] is True
    assert "Docker" in body["gap"]["matched_skills"] and body["gap"]["gaps"] == ["PostgreSQL"]

    reqs = analysis["requirements"]
    reqs["must_have_skills"] = ["Python"]
    body = client.patch(f"/sessions/{sid}/analysis", json={"requirements": reqs}).json()
    assert body["gap"]["match_percent"] == 100


def test_patch_rejected_unless_ready_and_validated(client, monkeypatch):
    sid = _ready_session(client)
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM(fail_with=LLMUnavailable("down")))
    client.post(f"/sessions/{sid}/analyze")
    assert client.patch(f"/sessions/{sid}/analysis", json={}).status_code == 409
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    client.post(f"/sessions/{sid}/analyze")
    assert client.patch(f"/sessions/{sid}/analysis", json={"profile": {"skills": "x"}}).status_code == 422


def test_deleting_a_document_removes_its_vectors(client, llm):
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    store = get_client()
    before = store.count("document_chunks").count
    docs = client.get(f"/sessions/{sid}/documents").json()
    client.delete(f"/sessions/{sid}/documents/{docs[0]['id']}")
    assert store.count("document_chunks").count < before


def test_resume_text_rescues_skill_the_model_missed(client, llm):
    sid = _ready_session(client, RESUMES["backend_dev"])  # mentions PostgreSQL and Docker in its skills line
    client.post(f"/sessions/{sid}/analyze")
    gap = client.get(f"/sessions/{sid}/analysis").json()["gap"]
    assert gap["gaps"] == [] and gap["match_percent"] == 100
