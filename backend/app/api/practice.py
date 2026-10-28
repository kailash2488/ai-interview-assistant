"""Practise again: start a new interview from an earlier one without uploading or analysing anything twice."""
import re
import shutil
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.sessions import get_session_or_404
from app.core.config import settings
from app.core.db import get_db
from app.models import Document, InterviewSession, SessionAnalysis, User
from app.schemas.report import ReportBody
from app.schemas.session import SessionOut
from app.services.analysis.service import reindex_session
from app.services.interview.plan import clean_topic

router = APIRouter(prefix="/sessions/{session_id}", tags=["practice"])
WEAK_BELOW = 60
MAX_FOCUS = 3
_ATTEMPT = re.compile(r"\s*·\s*attempt\s+\d+$")


class RetryIn(BaseModel):
    focus: Literal["same", "weak"] = "same"
    # The dashboard averages weak topics over recent reports; it passes that list so the button does what the screen says.
    topics: list[str] | None = Field(default=None, max_length=MAX_FOCUS)

    @field_validator("topics")
    @classmethod
    def _clean(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [t.strip() for t in v if isinstance(t, str) and t.strip()]
        if any(len(t) > 80 for t in cleaned):
            raise ValueError("Topic names are limited to 80 characters")
        return list(dict.fromkeys(cleaned)) or None


def weak_topics(report: ReportBody) -> list[str]:
    """The lowest-scoring topics of a report (below 60), without the (core skill) style suffix."""
    areas = sorted(report.areas, key=lambda a: a.score_percent)
    names = [re.sub(r"\s*\((core skill|gap area|project|behavioural)\)$", "", a.name) for a in areas if a.score_percent < WEAK_BELOW]
    return list(dict.fromkeys(names))[:MAX_FOCUS]


def _next_title(db: Session, user: User, source_title: str) -> str:
    base = _ATTEMPT.sub("", source_title)
    existing = db.scalars(select(InterviewSession.title).where(InterviewSession.user_id == user.id)).all()
    n = sum(1 for t in existing if _ATTEMPT.sub("", t) == base)
    return f"{base} · attempt {n + 1}"[:200]


@router.post("/retry", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def retry(session_id: str, payload: RetryIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    src = get_session_or_404(session_id, db, user)
    if src.analysis is None or src.analysis.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Analyse the documents of this interview first")

    focus: list[str] | None = None
    if payload.focus == "weak" and payload.topics:
        focus = payload.topics
    elif payload.focus == "weak":
        if src.report is None or src.report.status != "ready" or not src.report.report_json:
            raise HTTPException(status.HTTP_409_CONFLICT, "Generate the report first so the weak topics are known")
        focus = weak_topics(ReportBody.model_validate(src.report.report_json))
        if not focus:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Every topic scored {WEAK_BELOW} or more, so there are no weak spots to focus on")

    new = InterviewSession(
        user_id=user.id, title=_next_title(db, user, src.title), target_role=src.target_role, interview_type=src.interview_type,
        difficulty=src.difficulty, question_count=src.question_count, practice_mode=src.practice_mode,
        status="analysed", focus_topics=focus,
    )
    db.add(new)
    db.flush()  # the new id names the upload folder

    dest = settings.upload_dir / new.id
    dest.mkdir(parents=True, exist_ok=True)
    for doc in db.scalars(select(Document).where(Document.session_id == src.id, Document.status == "ready")):
        target = dest / doc.stored_path.rsplit("/", 1)[-1]
        try:
            shutil.copy2(doc.stored_path, target)
        except OSError:
            # Never point the new attempt at the old session's file: deleting the old attempt must remain safe.
            target = target.with_suffix(".txt")
            target.write_text(doc.raw_text or "", encoding="utf-8")
        db.add(Document(session_id=new.id, kind=doc.kind, filename=doc.filename, stored_path=str(target), status="ready",
                        raw_text=doc.raw_text, sections_json=doc.sections_json))
    a = src.analysis
    db.add(SessionAnalysis(session_id=new.id, status="ready", model=a.model, user_edited=a.user_edited, warnings_json=list(a.warnings_json or []),
                           profile_json=a.profile_json, requirements_json=a.requirements_json, gap_json=a.gap_json))
    db.commit()
    background.add_task(reindex_session, new.id)
    return new


@router.get("/weak-topics", response_model=list[str])
def get_weak_topics(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Which topics 'practise my weak spots' would focus on (empty until a report exists)."""
    src = get_session_or_404(session_id, db, user)
    if src.report is None or src.report.status != "ready" or not src.report.report_json:
        return []
    return weak_topics(ReportBody.model_validate(src.report.report_json))
