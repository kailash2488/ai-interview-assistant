import pytest

from app.core.db import SessionLocal
from app.models import Evaluation, Report
from app.schemas.interview import AnswerAnalysis
from app.services.interview.engine import InterviewEngine
from app.services.llm.client import LLMInvalidOutput, LLMUnavailable
from tests.fakes import FakeLLM, fake_evaluation
from tests.test_analysis_api import _ready_session
from tests.test_engine import LONG, play, run


@pytest.fixture()
def planned(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda: FakeLLM())
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    assert client.post(f"/sessions/{sid}/plan").status_code == 201
    return sid


@pytest.fixture()
def done(planned):
    """A finished interview (10 planned topics, every answer long and not flagged)."""
    play(InterviewEngine(planned, FakeLLM(analyses=[AnswerAnalysis(answer_quality="strong")] * 30)))
    return planned


def use_llm(monkeypatch, llm):
    monkeypatch.setattr("app.services.feedback.report_service.get_llm", lambda: llm)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return llm


def generate(client, sid):
    r = client.post(f"/sessions/{sid}/report")
    assert r.status_code == 202, r.text
    return client.get(f"/sessions/{sid}/report").json()


def test_reports_are_never_created_automatically(client, done):
    assert client.get(f"/sessions/{done}").json()["status"] == "completed"
    r = client.get(f"/sessions/{done}/report")
    assert r.status_code == 404 and "Generate" in r.json()["detail"]


def test_cannot_generate_before_the_interview_is_finished(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    assert client.post(f"/sessions/{planned}/report").status_code == 409  # nothing asked yet
    run(InterviewEngine(planned, FakeLLM()).start())
    r = client.post(f"/sessions/{planned}/report")
    assert r.status_code == 409 and "Finish the interview" in r.json()["detail"]


def test_unknown_session(client):
    assert client.post("/sessions/nope/report").status_code == 404
    assert client.get("/sessions/nope/report").status_code == 404


def test_only_the_introduction_answered_is_not_enough(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    engine = InterviewEngine(planned, FakeLLM())
    run(engine.start())
    run(engine.answer(LONG))  # intro, now a core question is open and unanswered
    engine.finish()
    r = client.post(f"/sessions/{planned}/report")
    assert r.status_code == 409 and "Answer at least one question" in r.json()["detail"]


def test_full_report(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    r = client.post(f"/sessions/{done}/report")
    assert r.status_code == 202 and r.json()["status"] == "running" and r.json()["progress_total"] == 8

    body = client.get(f"/sessions/{done}/report").json()
    assert body["status"] == "ready" and body["error"] is None and body["warnings"] == []
    report = body["report"]
    qs = report["questions"]
    assert len(qs) == 8 and body["progress_done"] == 8  # 10 topics minus intro and closing
    assert [q["order_no"] for q in qs] == sorted(q["order_no"] for q in qs)
    assert report["overall_score"] == body["overall_score"] == round(sum(q["score_percent"] for q in qs) / 8) == 75
    assert report["verdict"].startswith("Good") and "8 evaluated" in report["verdict_basis"]
    assert len(report["strengths"]) == 3 and len(report["improvements"]) == 3
    assert [s["timeframe"] for s in report["improvement_plan"]] == ["Week 1", "Week 2"]
    assert {a["name"] for a in report["areas"]} >= {"Python", "Interview Bot"}
    assert set(report["dimension_scores"]) == {"technical_accuracy", "depth", "relevance", "structure_clarity", "evidence"}
    assert report["coverage"] == {"planned_topics": 10, "questions_asked": 10, "evaluated": 8, "unanswered": 0}
    assert report["communication"]["answers"] == 8 and report["communication"]["avg_words"] > 10
    first = qs[0]
    assert first["answer"] == LONG and first["question"] and first["feedback"]
    assert first["dimensions"]["depth"]["score"] == 4 and first["sample_answer"]  # 75 < 85: a sample answer is written
    assert client.get(f"/sessions/{done}").json()["status"] == "reported"
    schemas = [c[0] for c in llm.calls]
    assert schemas.count("AnswerEvaluation") == 8 and schemas.count("ReportNarrative") == 1 and schemas.count("sample") == 8


def test_inflated_scores_are_caught_by_the_guards(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(5, quote="a quote the candidate never said at all")] * 8
    qs = generate(client, done)["report"]["questions"]
    assert all(q["dimensions"][d]["score"] == 3 for q in qs for d in q["dimensions"])
    assert all(q["score_percent"] == 50 and q["notes"] and not q["dimensions"]["depth"]["verified"] for q in qs)


def test_excellent_verified_answers_get_no_sample_answer(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(5)] * 8
    report = generate(client, done)["report"]
    assert report["overall_score"] == 100 and report["verdict"].startswith("Strong")
    assert all(q["sample_answer"] == "" for q in report["questions"]) and [c[0] for c in llm.calls].count("sample") == 0


def test_short_answers_score_minimum_without_model_calls(client, planned, monkeypatch):
    use_llm(monkeypatch, llm := FakeLLM())
    engine = InterviewEngine(planned, FakeLLM(analyses=[AnswerAnalysis(answer_quality="strong")] * 30))
    run(engine.start()); run(engine.answer(LONG)); run(engine.answer("I don't know")); engine.finish()
    report = generate(client, planned)["report"]
    assert len(report["questions"]) == 1 and report["questions"][0]["score_percent"] == 0
    assert "too short" in report["questions"][0]["notes"][0]
    assert "AnswerEvaluation" not in [c[0] for c in llm.calls]
    assert "ended early" in report["verdict_basis"] and report["coverage"]["unanswered"] == 1


def test_narrative_failure_falls_back_to_computed_text(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.narratives = [LLMInvalidOutput("bad json")]
    body = generate(client, done)
    assert body["status"] == "ready" and "could not be generated" in body["warnings"][0]
    report = body["report"]
    assert len(report["strengths"]) == 3 and len(report["improvements"]) == 3 and len(report["improvement_plan"]) == 2
    assert "75/100" in report["summary"]


def test_incomplete_narrative_also_falls_back(client, done, monkeypatch):
    from app.schemas.report import ReportNarrative
    llm = use_llm(monkeypatch, FakeLLM())
    llm.narratives = [ReportNarrative(summary="Only a summary")]
    assert generate(client, done)["warnings"]


def test_sample_answer_failure_does_not_sink_the_report(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.samples = [LLMInvalidOutput("x")] + ["ok sample"] * 7
    qs = generate(client, done)["report"]["questions"]
    assert qs[0]["sample_answer"] == "" and qs[1]["sample_answer"] == "ok sample"


def test_outage_fails_the_report_and_retry_reuses_finished_evaluations(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(), fake_evaluation(), LLMUnavailable("Cannot reach Ollama")]
    body = generate(client, done)
    assert body["status"] == "failed" and body["error"] == "Cannot reach Ollama" and body["report"] is None
    assert body["progress_done"] == 2
    with SessionLocal() as db:
        assert db.query(Evaluation).count() == 2

    healthy = use_llm(monkeypatch, FakeLLM())
    body = generate(client, done)
    assert body["status"] == "ready" and len(body["report"]["questions"]) == 8
    assert [c[0] for c in healthy.calls].count("AnswerEvaluation") == 6  # the two finished ones were reused


def test_transient_rate_limit_is_waited_out(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    llm.evaluations = [LLMUnavailable("Gemini free-tier rate limit reached. Wait a minute and try again."), fake_evaluation()]
    assert generate(client, done)["status"] == "ready" and sleeps == [20]


def test_permanent_errors_are_not_retried(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    llm.evaluations = [LLMUnavailable("Gemini rejected the API key. Check it on the Settings page.")]
    body = generate(client, done)
    assert body["status"] == "failed" and "rejected the API key" in body["error"] and sleeps == []


def test_regenerate_replaces_the_report_but_not_while_running(client, done, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    generate(client, done)
    with SessionLocal() as db:
        row = db.query(Report).one()
        row.status = "running"
        db.commit()
    assert client.post(f"/sessions/{done}/report").status_code == 409
    with SessionLocal() as db:
        row = db.query(Report).one()
        row.status = "ready"
        db.commit()
    assert generate(client, done)["status"] == "ready"
    with SessionLocal() as db:
        assert db.query(Report).count() == 1 and db.query(Evaluation).count() == 8


def test_deleting_a_session_removes_report_data(client, done, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    generate(client, done)
    assert client.delete(f"/sessions/{done}").status_code == 204
    with SessionLocal() as db:
        assert db.query(Report).count() == 0 and db.query(Evaluation).count() == 0


def test_strengths_only_come_from_topics_that_scored_well(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(5)] * 4 + [fake_evaluation(1, quote="")] * 4
    report = generate(client, done)["report"]
    prompt = next(c[2] for c in llm.calls if c[0] == "ReportNarrative")
    candidates = prompt.split("Strength candidates")[1].split("Communication facts")[0]
    scores = {a["name"]: a["score_percent"] for a in report["areas"]}
    assert any(score >= 60 for score in scores.values()) and "area score" in candidates
    for name, score in scores.items():
        if score < 60:
            assert name not in candidates, (name, score)  # a low-scoring topic must never be offered as a strength
    assert candidates.count("area score") <= 3


def test_no_strengths_when_nothing_scored_well(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(1, quote="")] * 8
    report = generate(client, done)["report"]
    prompt = next(c[2] for c in llm.calls if c[0] == "ReportNarrative")
    assert "(none)" in prompt.split("Strength candidates")[1].split("Communication facts")[0]
    assert report["strengths"] == [] and len(report["improvements"]) == 3  # a hallucinated strength would be dropped


def test_fallback_strengths_also_respect_the_threshold(client, done, monkeypatch):
    llm = use_llm(monkeypatch, FakeLLM())
    llm.evaluations = [fake_evaluation(1, quote="")] * 8
    llm.narratives = [LLMInvalidOutput("x")]
    report = generate(client, done)["report"]
    assert report["strengths"] == [] and len(report["improvements"]) == 3
