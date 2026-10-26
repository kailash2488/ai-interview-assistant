from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sessions import get_session_or_404
from app.core.db import get_db
from app.models import Document, SessionAnalysis
from app.schemas.analysis import (
    AnalysisOut, AnalysisPatch, CandidateProfile, GapAnalysis, JDRequirements,
)
from app.services.analysis.gap import analyse_gap
from app.services.analysis.service import run_analysis

router = APIRouter(prefix="/sessions/{session_id}", tags=["analysis"])


def _out(row: SessionAnalysis) -> AnalysisOut:
    return AnalysisOut(
        session_id=row.session_id, status=row.status, error=row.error, model=row.model,
        user_edited=row.user_edited, warnings=row.warnings_json or [],
        profile=CandidateProfile.model_validate(row.profile_json) if row.profile_json else None,
        requirements=JDRequirements.model_validate(row.requirements_json) if row.requirements_json else None,
        gap=GapAnalysis.model_validate(row.gap_json) if row.gap_json else None,
        updated_at=row.updated_at,
    )


def _get_row(session_id: str, db: Session) -> SessionAnalysis:
    get_session_or_404(session_id, db)
    row = db.scalar(select(SessionAnalysis).where(SessionAnalysis.session_id == session_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No analysis yet. Run POST /analyze first.")
    return row


@router.post("/analyze", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def analyze(session_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    get_session_or_404(session_id, db)
    ready = {d.kind for d in db.scalars(select(Document).where(Document.session_id == session_id, Document.status == "ready"))}
    missing = [k for k in ("resume", "jd") if k not in ready]
    if missing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Upload and wait for these to be ready first: {', '.join(missing)}")

    row = db.scalar(select(SessionAnalysis).where(SessionAnalysis.session_id == session_id))
    if row is not None and row.status == "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "Analysis is already running")
    if row is None:
        row = SessionAnalysis(session_id=session_id)
        db.add(row)
    row.status, row.error, row.user_edited, row.warnings_json = "running", None, False, []
    row.profile_json = row.requirements_json = row.gap_json = None
    db.commit()
    background.add_task(run_analysis, session_id)
    return _out(row)


@router.get("/analysis", response_model=AnalysisOut)
def get_analysis(session_id: str, db: Session = Depends(get_db)):
    return _out(_get_row(session_id, db))


@router.patch("/analysis", response_model=AnalysisOut)
def patch_analysis(session_id: str, payload: AnalysisPatch, db: Session = Depends(get_db)):
    row = _get_row(session_id, db)
    if row.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Analysis is not ready to edit")
    if payload.profile is not None:
        row.profile_json = payload.profile.model_dump(mode="json")
    if payload.requirements is not None:
        row.requirements_json = payload.requirements.model_dump(mode="json")
    resume = db.scalar(select(Document.raw_text).where(Document.session_id == session_id, Document.kind == "resume"))
    row.gap_json = analyse_gap(
        CandidateProfile.model_validate(row.profile_json), JDRequirements.model_validate(row.requirements_json), resume or ""
    ).model_dump(mode="json")
    row.user_edited = True
    db.commit()
    return _out(row)
