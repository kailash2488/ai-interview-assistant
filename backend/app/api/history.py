from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import InterviewSession, Report, User
from app.schemas.report import DIMENSION_LABELS, ReportBody

router = APIRouter(prefix="/history", tags=["history"])


class HistoryItem(BaseModel):
    session_id: str
    title: str
    target_role: str
    created_at: datetime
    overall_score: int
    verdict: str
    evaluated: int


class DeltaRow(BaseModel):
    name: str
    a: int | None
    b: int | None
    delta: int | None  # b minus a; None when a topic appears in only one attempt


class Attempt(BaseModel):
    session_id: str
    title: str
    target_role: str
    created_at: datetime
    overall_score: int
    verdict: str
    avg_words: int


class Comparison(BaseModel):
    a: Attempt
    b: Attempt
    overall_delta: int
    dimensions: list[DeltaRow]
    areas: list[DeltaRow]
    same_role: bool


@router.get("", response_model=list[HistoryItem])
def history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Interviews that have a finished report, oldest first (so the list reads as progress over time)."""
    rows = db.execute(
        select(InterviewSession, Report).join(Report, Report.session_id == InterviewSession.id)
        .where(Report.status == "ready", InterviewSession.user_id == user.id).order_by(InterviewSession.created_at)
    ).all()
    out = []
    for session, report in rows:
        body = ReportBody.model_validate(report.report_json)
        out.append(HistoryItem(session_id=session.id, title=session.title, target_role=session.target_role, created_at=session.created_at,
                               overall_score=body.overall_score, verdict=body.verdict, evaluated=body.coverage.evaluated))
    return out


def _load(db: Session, session_id: str, user: User) -> tuple[InterviewSession, ReportBody]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    if session.report is None or session.report.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, f'"{session.title}" has no finished report yet')
    return session, ReportBody.model_validate(session.report.report_json)


def _attempt(session: InterviewSession, body: ReportBody) -> Attempt:
    return Attempt(session_id=session.id, title=session.title, target_role=session.target_role, created_at=session.created_at,
                   overall_score=body.overall_score, verdict=body.verdict, avg_words=body.communication.avg_words)


def _delta(a: int | None, b: int | None) -> int | None:
    return b - a if a is not None and b is not None else None


@router.get("/compare", response_model=Comparison)
def compare(a: str = Query(...), b: str = Query(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Side by side: b is the attempt being judged against a, so a positive delta means b did better."""
    if a == b:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick two different interviews to compare")
    sa, ra = _load(db, a, user)
    sb, rb = _load(db, b, user)
    dims = [DeltaRow(name=DIMENSION_LABELS[k], a=ra.dimension_scores.get(k), b=rb.dimension_scores.get(k),
                     delta=_delta(ra.dimension_scores.get(k), rb.dimension_scores.get(k))) for k in DIMENSION_LABELS]
    area_a = {x.name: x.score_percent for x in ra.areas}
    area_b = {x.name: x.score_percent for x in rb.areas}
    names = list(dict.fromkeys([*area_a, *area_b]))
    areas = [DeltaRow(name=n, a=area_a.get(n), b=area_b.get(n), delta=_delta(area_a.get(n), area_b.get(n))) for n in names]
    return Comparison(a=_attempt(sa, ra), b=_attempt(sb, rb), overall_delta=rb.overall_score - ra.overall_score,
                      dimensions=dims, areas=areas, same_role=sa.target_role.strip().lower() == sb.target_role.strip().lower())
