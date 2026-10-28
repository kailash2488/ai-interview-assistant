from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.sessions import get_session_or_404
from app.core.db import get_db
from app.models import InterviewSession, User
from app.schemas.interview import InterviewPlan, MCQAnswerIn, MCQQuestionOut, MCQStateOut
from app.services.interview import mcq
from app.services.llm.client import LLMError, get_llm
from app.services.llm.user_settings import config_for_user

router = APIRouter(prefix="/sessions/{session_id}/mcq", tags=["mcq"])


def _row(q, reveal: bool = False) -> MCQQuestionOut:
    analysis = q.answer.analysis_json if q.answer else {}
    selected = analysis.get("selected_index") if analysis else None
    return MCQQuestionOut(
        question_id=q.id, order_no=q.order_no, topic=q.topic, text=q.text,
        options=q.options_json or [], selected_index=selected,
        correct=analysis.get("correct") if reveal and analysis else None,
        correct_index=int(q.correct_answer) if reveal and q.correct_answer is not None else None,
        explanation=q.explanation if reveal else None,
    )


def _state(session: InterviewSession) -> MCQStateOut:
    all_questions = sorted(session.questions, key=lambda q: q.order_no)
    plan = InterviewPlan.model_validate(session.plan.plan_json) if session.plan else None
    total = len(plan.items) if plan else session.question_count
    questions = all_questions[:total]  # repairs old sessions that over-generated questions
    answered = sum(q.answer is not None for q in questions)
    complete = session.status == "completed"
    score = round(100 * sum(bool((q.answer.analysis_json or {}).get("correct")) for q in questions if q.answer) / total) if complete and total else None
    current = next((q for q in questions if q.answer is None), None)
    return MCQStateOut(
        session_id=session.id, status=session.status, total=total, answered=answered, score=score,
        current=_row(current) if current else None,
        results=[_row(q, reveal=True) for q in questions] if complete else [],
    )


def _check(session: InterviewSession):
    if session.practice_mode != "mcq":
        raise HTTPException(status.HTTP_409_CONFLICT, "This session uses the live interview format")
    if session.plan is None or session.analysis is None or session.analysis.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Build the interview plan first")


def _repair_existing(db: Session, session: InterviewSession) -> None:
    """Normalize sessions created by the older on-demand generator, which could exceed the plan count."""
    total = len(InterviewPlan.model_validate(session.plan.plan_json).items)
    questions = sorted(session.questions, key=lambda q: q.order_no)
    for surplus in questions[total:]:
        db.delete(surplus)
    if questions[:total] and all(q.answer is not None for q in questions[:total]):
        session.status = "completed"
    if len(questions) > total or session.status == "completed":
        db.commit()


@router.get("", response_model=MCQStateOut)
def get_mcq(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user); _check(session)
    _repair_existing(db, session)
    return _state(session)


@router.post("/start", response_model=MCQStateOut, status_code=status.HTTP_201_CREATED)
def start_mcq(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user); _check(session)
    _repair_existing(db, session)
    if session.status == "completed" or session.questions:
        return _state(session)
    try:
        llm = get_llm(config_for_user(db, user.id))
        plan = InterviewPlan.model_validate(session.plan.plan_json)
        # Generate the complete set up front so "next" is instant and the count cannot drift.
        for index in range(len(plan.items)):
            session.questions.append(mcq.generate_question(llm, session, index))
        session.status = "in_progress"; db.commit()
    except LLMError as exc:
        db.rollback(); raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return _state(session)


@router.post("/answer", response_model=MCQStateOut)
def submit_answer(session_id: str, payload: MCQAnswerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user); _check(session)
    if session.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quiz is already complete")
    plan = InterviewPlan.model_validate(session.plan.plan_json)
    current = next((q for q in sorted(session.questions, key=lambda q: q.order_no)[:len(plan.items)] if q.answer is None), None)
    if current is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the quiz first")
    if payload.question_id is not None and payload.question_id != current.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question was already answered. Refresh to continue.")
    try:
        mcq.answer_question(db, current, payload.selected_index)
        answered = sum(q.answer is not None for q in sorted(session.questions, key=lambda q: q.order_no)[:len(plan.items)])
        if answered >= len(plan.items):
            session.status = "completed"
        db.commit()
    except LLMError as exc:
        db.rollback(); raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return _state(session)
