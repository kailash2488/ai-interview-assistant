from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app.api.dashboard import streak, topic_stats
from app.core import migrate
from app.core.db import SessionLocal
from app.models import Document, InterviewSession, Report
from app.schemas.report import AreaScore, ReportBody
from app.services.interview.engine import InterviewEngine
from app.services.interview.plan import build_plan, clean_topic
from app.services.analysis.gap import analyse_gap
from app.services.vectorstore import get_client
from tests.fakes import FakeLLM, fake_profile, fake_requirements
from tests.test_analysis_api import RESUME, _ready_session
from tests.test_api import _create_session, _upload
from tests.test_engine import run
from tests.test_phase5 import finished_report
from tests.samples import JD


# ---------- pure helpers ----------

def test_streak_counts_consecutive_days_and_forgives_today():
    today = date(2026, 10, 27)
    day = lambda n: today - timedelta(days=n)  # noqa: E731
    assert streak(set(), today) == 0
    assert streak({today}, today) == 1
    assert streak({today, day(1), day(2)}, today) == 3
    assert streak({day(1), day(2)}, today) == 2      # nothing yet today, but the streak is still alive
    assert streak({day(2), day(3)}, today) == 0      # a day was missed
    assert streak({today, day(2)}, today) == 1       # a gap ends it


def body(areas: dict[str, int]) -> ReportBody:
    base = {"overall_score": 50, "verdict": "x", "verdict_basis": "x", "target_role": "r", "summary": "s", "dimension_scores": {}, "strengths": [],
            "improvements": [], "questions": [], "improvement_plan": [],
            "communication": {"answers": 0, "avg_words": 0, "shortest_words": 0, "longest_words": 0, "one_line_answers": 0, "rambling_answers": 0,
                              "filler_words": {}, "vague_phrases": {}, "avg_seconds": None, "observations": []},
            "coverage": {"planned_topics": 1, "questions_asked": 1, "evaluated": 1, "unanswered": 0}}
    return ReportBody(**base, areas=[AreaScore(name=n, category="core", score_percent=v, answers=1) for n, v in areas.items()])


def test_topic_stats_average_across_reports_and_ignore_the_suffix():
    reports = [body({"Docker (gap area)": 20, "Python": 90}), body({"Docker": 40, "Python": 70, "SQL": 10})]
    weakest, strongest = topic_stats(reports)
    assert [(t.name, t.score, t.attempts) for t in weakest] == [("SQL", 10, 1), ("Docker", 30, 2), ("Python", 80, 2)]
    assert [(t.name, t.score) for t in strongest] == [("Python", 80)]  # only topics at 60 or more count as strengths


def test_topic_stats_only_use_the_latest_reports():
    old = body({"Legacy": 5})
    recent = [body({"Python": 50}) for _ in range(5)]
    weakest, _ = topic_stats([old, *recent])
    assert [t.name for t in weakest] == ["Python"]


# ---------- the endpoint ----------

def test_dashboard_requires_sign_in(anon_client):
    assert anon_client.get("/dashboard").status_code == 401


def test_empty_dashboard(client):
    d = client.get("/dashboard").json()
    assert d["stats"] == {"interviews": 0, "finished": 0, "reports": 0, "avg_score": None, "best_score": None, "latest_score": None,
                          "change": None, "streak_days": 0, "practice_days_30": 0, "answers": 0}
    assert d["trend"] == d["weakest"] == d["strongest"] == d["dimensions"] == d["recent"] == []
    assert d["next_action"]["kind"] == "new" and d["next_action"]["href"] == "/new"
    assert not any(b["earned"] for b in d["badges"])


def test_next_action_follows_the_interview_through_its_stages(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    kind = lambda: client.get("/dashboard").json()["next_action"]  # noqa: E731
    sid = _create_session(client)
    assert kind()["kind"] == "upload" and kind()["href"] == f"/sessions/{sid}/upload"
    _upload(client, sid, "resume", "r.txt", RESUME.encode())
    assert kind()["kind"] == "upload"  # the job description is still missing
    _upload(client, sid, "jd", "jd.txt", JD.encode())
    assert kind()["kind"] == "analyse"
    client.post(f"/sessions/{sid}/analyze")
    assert kind()["kind"] == "plan" and kind()["href"] == f"/sessions/{sid}/analysis"
    client.post(f"/sessions/{sid}/plan")
    assert kind()["kind"] == "start" and kind()["href"] == f"/sessions/{sid}/plan"
    run(InterviewEngine(sid, FakeLLM()).start())
    assert kind()["kind"] == "continue" and kind()["href"] == f"/sessions/{sid}/interview"
    client.post(f"/sessions/{sid}/finish")
    assert kind()["kind"] == "report" and kind()["href"] == f"/sessions/{sid}/report"


def test_stats_trend_dimensions_and_badges_with_two_reports(client, monkeypatch):
    first = finished_report(client, monkeypatch, 3, title="Attempt A")
    second = finished_report(client, monkeypatch, 5, title="Attempt B")
    d = client.get("/dashboard").json()
    s = d["stats"]
    assert (s["reports"], s["finished"], s["interviews"]) == (2, 2, 2)
    assert (s["avg_score"], s["best_score"], s["latest_score"], s["change"]) == (75, 100, 100, 50)
    assert s["answers"] >= 16 and s["streak_days"] == 1 and s["practice_days_30"] == 1
    assert [t["session_id"] for t in d["trend"]] == [first, second] and [t["score"] for t in d["trend"]] == [50, 100]
    assert all(x["score"] == 100 and x["change"] == 50 for x in d["dimensions"]) and d["dimensions"][0]["label"] == "Technical accuracy"
    assert d["weakest"] and all(t["score"] == 75 and t["attempts"] in (2, 4) for t in d["weakest"])  # averaged over both reports (a skill that is both core and gap counts both answers)
    earned = {b["id"] for b in d["badges"] if b["earned"]}
    assert earned == {"first", "report", "strong", "improver", "all_round"}
    assert [r["session_id"] for r in d["recent"]][0] == second and d["recent"][0]["score"] == 100
    assert d["next_action"]["kind"] == "new"  # everything is finished


def test_dashboards_are_per_account(client, other_client, monkeypatch):
    finished_report(client, monkeypatch, 4)
    mine, theirs = client.get("/dashboard").json(), other_client.get("/dashboard").json()
    assert mine["stats"]["reports"] == 1 and theirs["stats"]["reports"] == 0 and theirs["recent"] == [] and theirs["next_action"]["kind"] == "new"


def test_trend_is_capped_to_the_latest_points(client, monkeypatch):
    for i in range(3):
        finished_report(client, monkeypatch, 3, title=f"T{i}")
    monkeypatch.setattr("app.api.dashboard.TREND_POINTS", 2)
    assert [t["title"] for t in client.get("/dashboard").json()["trend"]] == ["T1", "T2"]


# ---------- practise again ----------

@pytest.fixture()
def analysed_session(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    return sid


def test_retry_needs_an_analysed_interview(client, monkeypatch):
    sid = _create_session(client)
    r = client.post(f"/sessions/{sid}/retry", json={})
    assert r.status_code == 409 and "Analyse" in r.json()["detail"]
    assert client.post("/sessions/nope/retry", json={}).status_code == 404


def test_retry_copies_documents_and_analysis_without_calling_the_model(client, analysed_session, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call expected")))
    # (reindexing in the background is allowed to skip quietly; it must not break the copy)
    new = client.post(f"/sessions/{analysed_session}/retry", json={"focus": "same"})
    assert new.status_code == 201
    body = new.json()
    assert body["title"] == "Practice 1 · attempt 2"[:0] + body["title"] and body["title"].endswith("· attempt 2")
    assert body["status"] == "analysed" and body["focus_topics"] is None and body["id"] != analysed_session
    assert (body["target_role"], body["interview_type"], body["question_count"]) == ("Python Developer", "mixed", 10)

    docs = client.get(f"/sessions/{body['id']}/documents").json()
    assert sorted(d["kind"] for d in docs) == ["jd", "resume"] and all(d["status"] == "ready" for d in docs)
    detail = client.get(f"/sessions/{body['id']}/documents/{docs[0]['id']}").json()
    assert detail["raw_text"] and detail["sections_json"]
    a = client.get(f"/sessions/{body['id']}/analysis").json()
    assert a["status"] == "ready" and a["profile"]["name"] == "Asha Verma"
    assert client.post(f"/sessions/{body['id']}/plan").status_code == 201  # straight to a plan, no new analysis

    again = client.post(f"/sessions/{analysed_session}/retry", json={}).json()
    assert again["title"].endswith("· attempt 3")
    from_copy = client.post(f"/sessions/{body['id']}/retry", json={}).json()
    assert from_copy["title"].endswith("· attempt 4") and from_copy["title"].count("attempt") == 1  # no "attempt 2 · attempt 3"


def test_retry_files_are_independent_copies(client, analysed_session):
    new = client.post(f"/sessions/{analysed_session}/retry", json={}).json()
    with SessionLocal() as db:
        original = {d.kind: d.stored_path for d in db.query(Document).filter_by(session_id=analysed_session)}
        copy = {d.kind: d.stored_path for d in db.query(Document).filter_by(session_id=new["id"])}
    assert original.keys() == copy.keys() and all(original[k] != copy[k] for k in original)
    import os
    assert all(os.path.exists(p) for p in copy.values())
    client.delete(f"/sessions/{analysed_session}")  # deleting the original must not break the copy
    assert all(os.path.exists(p) for p in copy.values())
    assert client.post(f"/sessions/{new['id']}/plan").status_code == 201


def test_retry_reindexes_documents_for_search(client, analysed_session):
    new = client.post(f"/sessions/{analysed_session}/retry", json={}).json()
    from qdrant_client import models as qm
    count = get_client().count("document_chunks", count_filter=qm.Filter(must=[qm.FieldCondition(key="session_id", match=qm.MatchValue(value=new["id"]))]))
    assert count.count >= 2


def test_weak_retry_needs_a_report_and_weak_topics(client, analysed_session, monkeypatch):
    assert client.get(f"/sessions/{analysed_session}/weak-topics").json() == []
    r = client.post(f"/sessions/{analysed_session}/retry", json={"focus": "weak"})
    assert r.status_code == 409 and "report" in r.json()["detail"]

    sid = finished_report(client, monkeypatch, 5, title="Strong run")  # every topic scores 100
    assert client.get(f"/sessions/{sid}/weak-topics").json() == []
    r = client.post(f"/sessions/{sid}/retry", json={"focus": "weak"})
    assert r.status_code == 409 and "no weak spots" in r.json()["detail"]


def set_areas(session_id: str, areas: dict[str, int]):
    with SessionLocal() as db:
        row = db.query(Report).filter_by(session_id=session_id).one()
        data = dict(row.report_json)
        data["areas"] = [{"name": n, "category": "core", "score_percent": v, "answers": 1} for n, v in areas.items()]
        row.report_json = data
        db.commit()


def test_weak_retry_focuses_the_plan_on_the_weakest_topics(client, monkeypatch):
    sid = finished_report(client, monkeypatch, 4)
    set_areas(sid, {"Python": 90, "Docker (gap area)": 20, "Kubernetes": 45, "PostgreSQL": 55, "Interview Bot": 70, "FastAPI": 59})
    assert client.get(f"/sessions/{sid}/weak-topics").json() == ["Docker", "Kubernetes", "PostgreSQL"]
    new = client.post(f"/sessions/{sid}/retry", json={"focus": "weak"}).json()
    assert new["focus_topics"] == ["Docker", "Kubernetes", "PostgreSQL"]
    plan = client.post(f"/sessions/{new['id']}/plan").json()
    gap_topics = [t["topic"] for t in plan["topics"] if t["category"] == "gap"]
    assert gap_topics[0] == "Docker"  # the focus topic comes first in its category
    plain = client.post(f"/sessions/{sid}/retry", json={"focus": "same"}).json()
    plain_gaps = [t["topic"] for t in client.post(f"/sessions/{plain['id']}/plan").json()["topics"] if t["category"] == "gap"]
    assert plain_gaps[0] == "PostgreSQL"  # without focus the order is the normal one


def test_retry_is_per_account(client, other_client, analysed_session):
    assert other_client.post(f"/sessions/{analysed_session}/retry", json={}).status_code == 404
    assert other_client.get(f"/sessions/{analysed_session}/weak-topics").status_code == 404


def test_retry_requires_sign_in(anon_client):
    assert anon_client.post("/sessions/x/retry", json={}).status_code == 401
    assert anon_client.get("/sessions/x/weak-topics").status_code == 401


# ---------- plan builder focus (unit) ----------

def plan_for(focus=None, kind="mixed", n=10):
    profile, reqs = fake_profile(), fake_requirements()
    return build_plan(question_count=n, interview_type=kind, difficulty="medium", role="Dev", profile=profile, requirements=reqs,
                      gap=analyse_gap(profile, reqs), focus_topics=focus)


def test_clean_topic_strips_report_suffixes():
    assert clean_topic("Docker (gap area)") == "docker" and clean_topic("Python (core skill)") == "python" and clean_topic("Interview Bot") == "interview bot"


def test_focus_topics_move_first_within_their_category():
    plain = [i.topic for i in plan_for().items if i.category.value == "core"]
    focused = [i.topic for i in plan_for(["Docker"]).items if i.category.value == "core"]
    assert plain[0] != "Docker" and focused[0] == "Docker"
    assert [i.topic for i in plan_for(["Teamwork and conflict"]).items if i.category.value == "behavioural"][0] == "Teamwork and conflict"


def test_focus_gives_the_focused_category_a_larger_share_and_keeps_the_plan_valid():
    plan = plan_for(["Docker"], n=12)
    assert len(plan.items) == 12 and plan.items[0].category.value == "intro" and plan.items[-1].category.value == "closing"
    count = lambda p: sum(1 for i in p.items if i.category.value == "gap")  # noqa: E731
    assert count(plan_for(["Docker"], n=12)) >= count(plan_for(n=12))


def test_unknown_or_empty_focus_changes_nothing():
    base = [(i.category, i.topic) for i in plan_for().items]
    assert [(i.category, i.topic) for i in plan_for(["Nothing like this"]).items] == base
    assert [(i.category, i.topic) for i in plan_for([]).items] == base


# ---------- migration ----------

def test_old_databases_get_the_new_columns():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE sessions (id VARCHAR(32) PRIMARY KEY, title VARCHAR(200))"))
        conn.execute(text("CREATE TABLE answers (id VARCHAR(32) PRIMARY KEY, text TEXT)"))
    migrate.upgrade(engine)
    migrate.upgrade(engine)
    insp = inspect(engine)
    assert {"user_id", "focus_topics"} <= {c["name"] for c in insp.get_columns("sessions")}
    assert "voice_json" in {c["name"] for c in insp.get_columns("answers")}


def test_focus_topics_are_ordered_weakest_first():
    gaps = [i.topic for i in plan_for(["Docker", "PostgreSQL"], n=14).items if i.category.value == "gap"]
    assert gaps[:2] == ["Docker", "PostgreSQL"]
    gaps = [i.topic for i in plan_for(["PostgreSQL", "Docker"], n=14).items if i.category.value == "gap"]
    assert gaps[:2] == ["PostgreSQL", "Docker"]


# ---------- the dashboard passes its own weak-topic list ----------

def test_weak_retry_uses_the_topics_the_dashboard_showed(client, monkeypatch):
    sid = finished_report(client, monkeypatch, 5)  # the latest report has no weak topics of its own
    r = client.post(f"/sessions/{sid}/retry", json={"focus": "weak", "topics": [" Docker ", "SQL", ""]})
    assert r.status_code == 201
    assert r.json()["focus_topics"] == ["Docker", "SQL"]  # whitespace trimmed, blanks dropped
    plan = client.post(f"/sessions/{r.json()['id']}/plan")
    assert plan.status_code == 201


def test_retry_topics_are_validated(client, monkeypatch):
    sid = finished_report(client, monkeypatch, 5)
    assert client.post(f"/sessions/{sid}/retry", json={"focus": "weak", "topics": ["a", "b", "c", "d"]}).status_code == 422
    assert client.post(f"/sessions/{sid}/retry", json={"focus": "weak", "topics": ["x" * 81]}).status_code == 422
    assert client.post(f"/sessions/{sid}/retry", json={"focus": "weak", "topics": [1, 2]}).status_code == 422


def test_topics_are_ignored_for_a_plain_retry(client, monkeypatch):
    sid = finished_report(client, monkeypatch, 5)
    r = client.post(f"/sessions/{sid}/retry", json={"focus": "same", "topics": ["Docker"]})
    assert r.status_code == 201 and r.json()["focus_topics"] is None
