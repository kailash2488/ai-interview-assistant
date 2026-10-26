import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.api.sessions import get_session_or_404
from app.core.db import get_db
from app.models import InterviewPlanRow
from app.schemas.analysis import CandidateProfile, GapAnalysis, JDRequirements
from app.schemas.interview import InterviewPlan, InterviewStateOut, PlanOut, PlanTopicOut
from app.services.interview.engine import InterviewEngine, InterviewError
from app.services.interview.plan import build_plan
from app.services.llm.client import LLMError

log = logging.getLogger(__name__)
router = APIRouter(tags=["interview"])
_active: set[str] = set()  # one live interview connection per session


def _plan_out(session_id: str, plan: InterviewPlan) -> PlanOut:
    return PlanOut(
        session_id=session_id, followup_budget=plan.followup_budget,
        topics=[PlanTopicOut(index=i.index, category=i.category, topic=i.topic, difficulty=i.difficulty) for i in plan.items],
    )


@router.post("/sessions/{session_id}/plan", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(session_id, db)
    analysis = session.analysis
    if analysis is None or analysis.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Analyse the documents first")
    if session.questions:
        raise HTTPException(status.HTTP_409_CONFLICT, "The interview has already started; its plan can no longer change")
    plan = build_plan(
        question_count=session.question_count, interview_type=session.interview_type, difficulty=session.difficulty,
        role=session.target_role, profile=CandidateProfile.model_validate(analysis.profile_json),
        requirements=JDRequirements.model_validate(analysis.requirements_json), gap=GapAnalysis.model_validate(analysis.gap_json),
    )
    if session.plan is None:
        session.plan = InterviewPlanRow(plan_json=plan.model_dump(mode="json"))
    else:
        session.plan.plan_json = plan.model_dump(mode="json")
    session.status = "planned"
    db.commit()
    return _plan_out(session_id, plan)


@router.get("/sessions/{session_id}/plan", response_model=PlanOut)
def get_plan(session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(session_id, db)
    if session.plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No plan yet")
    return _plan_out(session_id, InterviewPlan.model_validate(session.plan.plan_json))


@router.get("/sessions/{session_id}/interview", response_model=InterviewStateOut)
def get_interview(session_id: str, db: Session = Depends(get_db)):
    get_session_or_404(session_id, db)
    return InterviewEngine(session_id).state()


@router.post("/sessions/{session_id}/finish", response_model=InterviewStateOut)
def finish_interview(session_id: str, db: Session = Depends(get_db)):
    get_session_or_404(session_id, db)
    engine = InterviewEngine(session_id)
    engine.finish()
    return engine.state()


async def _pump(ws: WebSocket, events, on_question=None) -> None:
    try:
        async for event in iterate_in_threadpool(events):
            if event["type"] == "question" and on_question:
                on_question()
            await ws.send_json(event)
    except InterviewError as exc:
        await ws.send_json({"type": "error", "message": str(exc), "retryable": False})
    except LLMError as exc:
        await ws.send_json({"type": "error", "message": str(exc), "retryable": True})
    except WebSocketDisconnect:
        raise
    except Exception:
        log.exception("Interview turn failed")
        await ws.send_json({"type": "error", "message": "Something went wrong. Please try again.", "retryable": True})


@router.websocket("/sessions/{session_id}/interview")
async def interview_socket(ws: WebSocket, session_id: str):
    """Messages in: {type: start|answer|end, text?}. Messages out: state, thinking, token, question, complete, error.
    A 'question' event is authoritative: it replaces any streamed tokens shown so far."""
    await ws.accept()
    if session_id in _active:
        await ws.send_json({"type": "error", "message": "This interview is already open in another tab", "retryable": False})
        await ws.close(code=1008)
        return
    engine = InterviewEngine(session_id)
    try:
        state = await run_in_threadpool(engine.state)
    except InterviewError as exc:
        await ws.send_json({"type": "error", "message": str(exc), "retryable": False})
        await ws.close(code=1008)
        return
    _active.add(session_id)
    asked_at: list[float | None] = [None]
    mark = lambda: asked_at.__setitem__(0, time.monotonic())  # noqa: E731
    try:
        await ws.send_json({"type": "state", **state})
        while True:
            try:
                message = json.loads(await ws.receive_text())
                kind = message.get("type")
            except (json.JSONDecodeError, AttributeError):
                await ws.send_json({"type": "error", "message": "Invalid message", "retryable": False})
                continue
            if kind == "start":
                await _pump(ws, engine.start(), mark)
            elif kind == "answer":
                text = message.get("text")
                if not isinstance(text, str):
                    await ws.send_json({"type": "error", "message": "Invalid message", "retryable": False})
                    continue
                duration = int(time.monotonic() - asked_at[0]) if asked_at[0] else None
                await _pump(ws, engine.answer(text, duration), mark)
            elif kind == "end":
                await run_in_threadpool(engine.finish)
                await ws.send_json({"type": "complete", "message": "Interview ended."})
            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type '{kind}'", "retryable": False})
    except WebSocketDisconnect:
        pass
    finally:
        _active.discard(session_id)
