import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.sessions import get_session_or_404
from app.core.db import get_db
from app.models import Report, User
from app.schemas.report import ReportBody, ReportOut
from app.services.feedback.pdf import render_report_pdf
from app.services.feedback.report_service import evaluable_questions, run_report

router = APIRouter(prefix="/sessions/{session_id}/report", tags=["report"])


def _out(row: Report) -> ReportOut:
    return ReportOut(
        session_id=row.session_id, status=row.status, error=row.error, model=row.model, warnings=row.warnings_json or [],
        progress_done=row.progress_done, progress_total=row.progress_total, overall_score=row.overall_score,
        report=ReportBody.model_validate(row.report_json) if row.report_json else None, updated_at=row.updated_at,
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_202_ACCEPTED)
def generate_report(session_id: str, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Starts report generation. Reports are never created automatically: the user asks for them."""
    session = get_session_or_404(session_id, db, user)
    if session.plan is None or session.analysis is None or not session.questions:
        raise HTTPException(status.HTTP_409_CONFLICT, "Take the interview first")
    if session.status not in ("completed", "reported"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the interview before generating a report")
    evaluable = evaluable_questions(session)
    if not evaluable:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer at least one question (other than the introduction) to get a report")

    row = session.report
    if row is not None and row.status == "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "The report is already being generated")
    retry_after_failure = False
    if row is None:
        row = Report(session_id=session_id)
        session.report = row
    retry_after_failure = row.status == "failed"  # keep finished evaluations so a retry does not repeat the work
    row.status, row.error, row.report_json, row.overall_score, row.warnings_json = "running", None, None, None, []
    row.progress_done, row.progress_total = 0, len(evaluable)
    db.commit()
    background.add_task(run_report, session_id, retry_after_failure)
    return _out(row)


@router.get("", response_model=ReportOut)
def get_report(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_session_or_404(session_id, db, user)
    row = db.scalar(select(Report).where(Report.session_id == session_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report yet. Generate one first.")
    return _out(row)


@router.get("/pdf")
def download_pdf(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user)
    row = session.report
    if row is None or row.status != "ready" or not row.report_json:
        raise HTTPException(status.HTTP_409_CONFLICT, "Generate the report first")
    pdf = render_report_pdf(ReportBody.model_validate(row.report_json), session.title, session.created_at.strftime("%Y-%m-%d"))
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", session.title).strip("-")[:60] or "report"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="feedback-{name}.pdf"'})
