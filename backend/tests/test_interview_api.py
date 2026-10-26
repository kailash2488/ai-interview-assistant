import json

import pytest

from app.schemas.interview import AnswerAnalysis
from tests.fakes import FakeLLM
from tests.test_analysis_api import _ready_session
from tests.test_engine import LONG


@pytest.fixture()
def analysed(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda: FakeLLM())
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    return sid


@pytest.fixture()
def planned(client, analysed):
    assert client.post(f"/sessions/{analysed}/plan").status_code == 201
    return analysed


def use_llm(monkeypatch, llm):
    monkeypatch.setattr("app.services.interview.engine.get_llm", lambda: llm)
    return llm


def recv_until(ws, *types):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] in types:
            return seen


def test_plan_requires_analysis(client):
    from tests.test_api import _create_session
    sid = _create_session(client)
    assert client.post(f"/sessions/{sid}/plan").status_code == 409
    assert client.get(f"/sessions/{sid}/plan").status_code == 404
    assert client.post("/sessions/nope/plan").status_code == 404


def test_plan_shows_topics_but_never_questions(client, analysed):
    r = client.post(f"/sessions/{analysed}/plan")
    body = r.json()
    assert r.status_code == 201 and len(body["topics"]) == 10
    assert set(body["topics"][0]) == {"index", "category", "topic", "difficulty"}
    assert "fallback_question" not in json.dumps(body) and "goal" not in json.dumps(body)
    assert client.get(f"/sessions/{analysed}/plan").json() == body
    assert client.get(f"/sessions/{analysed}").json()["status"] == "planned"


def test_plan_can_be_rebuilt_until_the_interview_starts(client, planned, monkeypatch):
    assert client.post(f"/sessions/{planned}/plan").status_code == 201
    use_llm(monkeypatch, FakeLLM())
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        recv_until(ws, "question")
    assert client.post(f"/sessions/{planned}/plan").status_code == 409


def test_websocket_full_interview(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM(analyses=[AnswerAnalysis(answer_quality="strong")] * 20))
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        state = ws.receive_json()
        assert state["type"] == "state" and state["turns"] == [] and state["main_total"] == 10
        ws.send_text(json.dumps({"type": "start"}))
        msgs = recv_until(ws, "question")
        assert "introduce yourself" in msgs[-1]["text"]

        asked = 1
        while True:
            ws.send_text(json.dumps({"type": "answer", "text": LONG}))
            msgs = recv_until(ws, "question", "complete", "error")
            assert msgs[-1]["type"] != "error", msgs[-1]
            if msgs[-1]["type"] == "complete":
                break
            asked += 1
            if 2 < asked < 10:  # generated questions stream tokens first (intro and closing are fixed text)
                assert [m["type"] for m in msgs[:2]] == ["thinking", "token"]
        assert asked == 10

    state = client.get(f"/sessions/{planned}/interview").json()
    assert state["status"] == "completed" and len(state["turns"]) == 10
    assert all(t["answer"] == LONG for t in state["turns"])
    assert "analysis" not in json.dumps(state)
    assert client.get(f"/sessions/{planned}").json()["status"] == "completed"


def test_websocket_reconnect_restores_transcript(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        first = recv_until(ws, "question")[-1]
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        state = ws.receive_json()
        assert state["turns"][0]["question_id"] == first["question_id"] and state["turns"][0]["answer"] is None
        ws.send_text(json.dumps({"type": "start"}))
        replay = recv_until(ws, "question")[-1]
        assert replay["question_id"] == first["question_id"] and replay["replay"] is True


def test_websocket_errors_are_reported_not_fatal(client, planned, monkeypatch):
    from app.services.llm.client import LLMUnavailable
    use_llm(monkeypatch, FakeLLM(questions=[LLMUnavailable("Cannot reach Ollama")]))
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["message"] == "Invalid message"
        ws.send_text(json.dumps({"type": "dance"}))
        assert "Unknown message type" in ws.receive_json()["message"]
        ws.send_text(json.dumps({"type": "answer", "text": "hello hello hello"}))
        assert "no open question" in ws.receive_json()["message"]
        ws.send_text(json.dumps({"type": "start"}))
        recv_until(ws, "question")
        ws.send_text(json.dumps({"type": "answer", "text": LONG}))
        err = recv_until(ws, "error")[-1]
        assert err["retryable"] is True and "Ollama" in err["message"]
        ws.send_text(json.dumps({"type": "start"}))  # retry after the outage
        assert recv_until(ws, "question", "error")[-1]["type"] == "question"


def test_websocket_without_a_plan_and_second_tab(client, analysed, monkeypatch):
    with client.websocket_connect(f"/sessions/{analysed}/interview") as ws:
        assert ws.receive_json()["type"] == "state"
        ws.send_text(json.dumps({"type": "start"}))
        assert "plan" in ws.receive_json()["message"]
    client.post(f"/sessions/{analysed}/plan")
    use_llm(monkeypatch, FakeLLM())
    with client.websocket_connect(f"/sessions/{analysed}/interview") as first:
        first.receive_json()
        with client.websocket_connect(f"/sessions/{analysed}/interview") as second:
            assert "another tab" in second.receive_json()["message"]


def test_end_early_and_finish_endpoint(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        recv_until(ws, "question")
        ws.send_text(json.dumps({"type": "end"}))
        assert ws.receive_json()["type"] == "complete"
    assert client.get(f"/sessions/{planned}/interview").json()["status"] == "completed"
    assert client.post(f"/sessions/{planned}/finish").json()["status"] == "completed"
    assert client.post("/sessions/nope/finish").status_code == 404


def test_deleting_session_removes_interview_data(client, planned, monkeypatch):
    use_llm(monkeypatch, FakeLLM())
    with client.websocket_connect(f"/sessions/{planned}/interview") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        recv_until(ws, "question")
    assert client.delete(f"/sessions/{planned}").status_code == 204
    from app.core.db import SessionLocal
    from app.models import InterviewPlanRow, Question
    with SessionLocal() as db:
        assert db.query(Question).count() == 0 and db.query(InterviewPlanRow).count() == 0
