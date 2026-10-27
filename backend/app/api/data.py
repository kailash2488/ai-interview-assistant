"""Privacy controls: see what is stored and delete all of it."""
import logging
import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import Answer, Document, InterviewSession, Report
from app.services import vectorstore

log = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])
CONFIRM_PHRASE = "DELETE ALL"


class DataSummary(BaseModel):
    sessions: int
    documents: int
    answers: int
    reports: int
    upload_bytes: int


class DeleteRequest(BaseModel):
    confirm: str


def _upload_bytes() -> int:
    root = settings.upload_dir
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file()) if root.exists() else 0


def _summary(db: Session) -> DataSummary:
    count = lambda model: db.scalar(select(func.count()).select_from(model)) or 0  # noqa: E731
    return DataSummary(sessions=count(InterviewSession), documents=count(Document), answers=count(Answer),
                       reports=count(Report), upload_bytes=_upload_bytes())


@router.get("", response_model=DataSummary)
def data_summary(db: Session = Depends(get_db)):
    return _summary(db)


@router.delete("", response_model=DataSummary)
def delete_all_data(payload: DeleteRequest, db: Session = Depends(get_db)):
    """Removes every interview, document, answer, report, uploaded file and search index. Settings and the API key stay."""
    if payload.confirm != CONFIRM_PHRASE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f'Send {{"confirm": "{CONFIRM_PHRASE}"}} to confirm')
    ids = list(db.scalars(select(InterviewSession.id)))
    for session in db.scalars(select(InterviewSession)):
        db.delete(session)
    db.commit()
    for sid in ids:
        try:
            vectorstore.delete_session(sid)
        except Exception:
            log.warning("Could not clear vectors for session %s", sid, exc_info=True)
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return _summary(db)
