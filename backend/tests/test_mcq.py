from app.services.llm.client import LLMUnavailable
from tests.fakes import FakeLLM
from tests.test_analysis_api import _ready_session


def test_complete_quiz_is_generated_in_one_model_call():
    from app.models import InterviewPlanRow, InterviewSession, SessionAnalysis
    from app.services.interview.mcq import generate_questions
    from tests.fakes import fake_profile, fake_requirements
    from tests.test_plan import make

    session = InterviewSession(
        id="batch", title="Batch", target_role="Python Developer", interview_type="mixed",
        difficulty="medium", question_count=3, practice_mode="mcq",
    )
    session.plan = InterviewPlanRow(plan_json=make(3).model_dump(mode="json"))
    session.analysis = SessionAnalysis(
        status="ready", profile_json=fake_profile().model_dump(mode="json"),
        requirements_json=fake_requirements().model_dump(mode="json"), gap_json={},
    )
    fake = FakeLLM()
    questions = generate_questions(fake, session)
    assert len(questions) == 3
    assert [question.order_no for question in questions] == [1, 2, 3]
    assert [call[0] for call in fake.calls] == ["MCQSetDraft"]


def ready_mcq(client, monkeypatch, count=3):
    fake = FakeLLM()
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: fake)
    monkeypatch.setattr("app.api.mcq.get_llm", lambda *a, **k: fake)
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    # Update the mode directly through a dedicated MCQ session would repeat uploads; the API mode is covered at creation.
    from app.core.db import SessionLocal
    from app.models import InterviewSession
    with SessionLocal() as db:
        row = db.get(InterviewSession, sid)
        row.practice_mode, row.question_count = "mcq", count
        db.commit()
    assert client.post(f"/sessions/{sid}/plan").status_code == 201
    return sid, fake


def test_mcq_end_to_end_hides_answers_until_complete(client, monkeypatch):
    sid, fake = ready_mcq(client, monkeypatch)
    state = client.post(f"/sessions/{sid}/mcq/start").json()
    assert state["total"] == 3 and len(state["current"]["options"]) == 4
    assert state["current"]["correct_index"] is None and state["results"] == []
    for selected in (0, 1, 0):
        state = client.post(f"/sessions/{sid}/mcq/answer", json={"selected_index": selected}).json()
    assert state["status"] == "completed" and state["score"] == 67
    assert len(state["results"]) == 3 and state["results"][0]["correct_index"] == 0
    assert state["results"][1]["correct"] is False and state["results"][0]["explanation"]
    assert [c[0] for c in fake.calls].count("MCQSetDraft") == 1  # complete quiz in one provider request


def test_mcq_validates_mode_selection_and_answer(client, monkeypatch):
    sid = _ready_session(client)
    assert client.get(f"/sessions/{sid}/mcq").status_code == 409
    sid, _ = ready_mcq(client, monkeypatch)
    assert client.post(f"/sessions/{sid}/mcq/answer", json={"selected_index": 0}).status_code == 409
    client.post(f"/sessions/{sid}/mcq/start")
    assert client.post(f"/sessions/{sid}/mcq/answer", json={"selected_index": 4}).status_code == 422


def test_generation_failure_does_not_consume_answer(client, monkeypatch):
    sid, fake = ready_mcq(client, monkeypatch)
    fake.fail_with = LLMUnavailable("provider down")
    r = client.post(f"/sessions/{sid}/mcq/start")
    assert r.status_code == 503
    state = client.get(f"/sessions/{sid}/mcq").json()
    assert state["answered"] == 0 and state["current"] is None


def test_stale_answer_request_cannot_answer_the_next_question(client, monkeypatch):
    sid, _ = ready_mcq(client, monkeypatch)
    state = client.post(f"/sessions/{sid}/mcq/start").json()
    first_id = state["current"]["question_id"]
    assert client.post(f"/sessions/{sid}/mcq/answer", json={"question_id": first_id, "selected_index": 0}).status_code == 200
    stale = client.post(f"/sessions/{sid}/mcq/answer", json={"question_id": first_id, "selected_index": 0})
    assert stale.status_code == 409
    assert client.get(f"/sessions/{sid}/mcq").json()["answered"] == 1
