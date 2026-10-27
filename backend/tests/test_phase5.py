import json

import pymupdf
import pytest

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Document, InterviewSession, Report
from app.schemas.interview import AnswerAnalysis
from app.services.interview.engine import InterviewEngine
from tests.fakes import FakeLLM, fake_evaluation
from tests.samples import JD, RESUMES
from tests.test_analysis_api import RESUME, _ready_session
from tests.test_api import _create_session, _upload
from tests.test_engine import play, run
from tests.test_report_api import done, generate, planned, use_llm  # noqa: F401  (fixtures)


def finished_report(client, monkeypatch, score: int, title: str = "Practice 1", role: str = "Python Developer"):
    """A session with a finished interview and a ready report whose answers all scored `score` out of 5."""
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda: FakeLLM())
    sid = client.post("/sessions", json={"title": title, "target_role": role}).json()["id"]
    _upload(client, sid, "resume", "r.txt", RESUME.encode())
    _upload(client, sid, "jd", "jd.txt", JD.encode())
    client.post(f"/sessions/{sid}/analyze")
    client.post(f"/sessions/{sid}/plan")
    play(InterviewEngine(sid, FakeLLM(analyses=[AnswerAnalysis(answer_quality="strong")] * 30)))
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(score)] * 8
    assert generate(client, sid)["status"] == "ready"
    return sid


# ---------- stale analysis ----------

def test_replacing_the_resume_invalidates_analysis_and_plan(client, planned):
    assert client.get(f"/sessions/{planned}/analysis").status_code == 200
    r = _upload(client, planned, "resume", "new.txt", b"A different resume " * 10)
    assert r.status_code == 202
    assert client.get(f"/sessions/{planned}/analysis").status_code == 404
    assert client.get(f"/sessions/{planned}/plan").status_code == 404
    assert client.get(f"/sessions/{planned}").json()["status"] == "created"


def test_extra_documents_do_not_invalidate(client, planned):
    _upload(client, planned, "other", "notes.txt", b"project notes " * 10)
    assert client.get(f"/sessions/{planned}/analysis").status_code == 200


def test_deleting_the_jd_invalidates_too(client, planned):
    jd = next(d for d in client.get(f"/sessions/{planned}/documents").json() if d["kind"] == "jd")
    assert client.delete(f"/sessions/{planned}/documents/{jd['id']}").status_code == 204
    assert client.get(f"/sessions/{planned}/analysis").status_code == 404


def test_documents_are_locked_once_the_interview_has_started(client, planned):
    run(InterviewEngine(planned, FakeLLM()).start())
    r = _upload(client, planned, "resume", "new.txt", b"A different resume " * 10)
    assert r.status_code == 409 and "already started" in r.json()["detail"]
    resume = next(d for d in client.get(f"/sessions/{planned}/documents").json() if d["kind"] == "resume")
    assert client.delete(f"/sessions/{planned}/documents/{resume['id']}").status_code == 409
    assert _upload(client, planned, "other", "late.txt", b"extra " * 10).status_code == 202  # extras are still fine


def test_extra_document_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_other_documents", 2)
    sid = _create_session(client)
    for i in range(2):
        assert _upload(client, sid, "other", f"n{i}.txt", b"notes " * 10).status_code == 202
    r = _upload(client, sid, "other", "n3.txt", b"notes " * 10)
    assert r.status_code == 409 and "At most 2" in r.json()["detail"]


# ---------- data deletion ----------

def test_data_summary_and_delete_all(client, done, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    generate(client, done)
    summary = client.get("/data").json()
    assert summary["sessions"] == 1 and summary["documents"] == 2 and summary["answers"] == 10 and summary["reports"] == 1
    assert summary["upload_bytes"] > 0

    assert client.request("DELETE", "/data", json={"confirm": "yes"}).status_code == 422
    assert client.get("/data").json()["sessions"] == 1  # a wrong phrase deletes nothing

    r = client.request("DELETE", "/data", json={"confirm": "DELETE ALL"})
    assert r.status_code == 200 and r.json() == {"sessions": 0, "documents": 0, "answers": 0, "reports": 0, "upload_bytes": 0}
    assert client.get("/sessions").json() == []
    from app.services.vectorstore import COLLECTION, get_client
    store = get_client()
    assert not store.collection_exists(COLLECTION) or store.count(COLLECTION).count == 0


def test_delete_all_keeps_the_saved_provider_settings(client):
    settings.runtime_settings_path.write_text(json.dumps({"provider": "gemini"}))
    client.request("DELETE", "/data", json={"confirm": "DELETE ALL"})
    assert settings.runtime_settings_path.exists()
    settings.runtime_settings_path.unlink()


# ---------- history and compare ----------

def test_history_lists_only_finished_reports_oldest_first(client, monkeypatch):
    assert client.get("/history").json() == []
    _create_session(client)  # no report: must not appear
    first = finished_report(client, monkeypatch, 3, title="Attempt A")
    second = finished_report(client, monkeypatch, 5, title="Attempt B")
    items = client.get("/history").json()
    assert [i["session_id"] for i in items] == [first, second]
    assert [i["overall_score"] for i in items] == [50, 100] and items[0]["evaluated"] == 8
    sessions = {s["id"]: s for s in client.get("/sessions").json()}
    assert sessions[first]["overall_score"] == 50 and sessions[second]["overall_score"] == 100


def test_compare_two_attempts(client, monkeypatch):
    a = finished_report(client, monkeypatch, 3, title="Attempt A")
    b = finished_report(client, monkeypatch, 5, title="Attempt B")
    body = client.get("/history/compare", params={"a": a, "b": b}).json()
    assert body["overall_delta"] == 50 and body["a"]["title"] == "Attempt A" and body["b"]["overall_score"] == 100
    assert body["same_role"] is True
    assert [d["name"] for d in body["dimensions"]][:2] == ["Technical accuracy", "Depth"]
    assert all(d["a"] == 50 and d["b"] == 100 and d["delta"] == 50 for d in body["dimensions"])
    assert body["areas"] and all(r["delta"] == 50 for r in body["areas"])
    reverse = client.get("/history/compare", params={"a": b, "b": a}).json()
    assert reverse["overall_delta"] == -50


def test_compare_validation(client, monkeypatch):
    a = finished_report(client, monkeypatch, 4)
    unreported = _create_session(client)
    assert client.get("/history/compare", params={"a": a, "b": a}).status_code == 422
    r = client.get("/history/compare", params={"a": a, "b": unreported})
    assert r.status_code == 409 and "no finished report" in r.json()["detail"]
    assert client.get("/history/compare", params={"a": a, "b": "nope"}).status_code == 404
    assert client.get("/history/compare", params={"a": a}).status_code == 422


def test_compare_marks_topics_present_in_only_one_attempt(client, monkeypatch):
    a = finished_report(client, monkeypatch, 4, title="A")
    b = finished_report(client, monkeypatch, 4, title="B")
    with SessionLocal() as db:  # make attempt B miss one topic
        row = db.query(Report).filter(Report.session_id == b).one()
        body = dict(row.report_json)
        body["areas"] = body["areas"][1:]
        row.report_json = body
        db.commit()
    rows = client.get("/history/compare", params={"a": a, "b": b}).json()["areas"]
    missing = [r for r in rows if r["b"] is None]
    assert len(missing) == 1 and missing[0]["delta"] is None and missing[0]["a"] is not None


# ---------- PDF ----------

def test_pdf_export(client, monkeypatch):
    sid = finished_report(client, monkeypatch, 4, title="Round 1 / Backend <b>")
    r = client.get(f"/sessions/{sid}/report/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="feedback-Round-1-Backend-b.pdf"'
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    text = "".join(p.get_text() for p in doc)
    assert r.content.startswith(b"%PDF") and doc.page_count >= 2
    assert "Feedback report" in text and "75" in text and "Question by question" in text and "Round 1 / Backend <b>" in text
    assert "Top areas to improve" in text and "Week 1" in text


def test_pdf_requires_a_finished_report(client, done):
    assert client.get(f"/sessions/{done}/report/pdf").status_code == 409
    assert client.get("/sessions/nope/report/pdf").status_code == 404
