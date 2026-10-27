"""Privacy controls: see what the signed-in user has stored and delete all of it."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.core.db import get_db
from app.models import Answer, Document, InterviewSession, Question, Report, User
from app.services.account import delete_user_data

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


def _summary(db: Session, user: User) -> DataSummary:
    mine = select(InterviewSession.id).where(InterviewSession.user_id == user.id)
    count = lambda col, where: db.scalar(select(func.count()).select_from(col).where(where)) or 0  # noqa: E731
    ids = list(db.scalars(mine))
    size = 0
    for sid in ids:
        root = settings.upload_dir / sid
        if root.exists():
            size += sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    return DataSummary(
        sessions=len(ids),
        documents=count(Document, Document.session_id.in_(mine)),
        answers=db.scalar(select(func.count()).select_from(Answer).join(Question, Answer.question_id == Question.id).where(Question.session_id.in_(mine))) or 0,
        reports=count(Report, Report.session_id.in_(mine)),
        upload_bytes=size,
    )


@router.get("", response_model=DataSummary)
def data_summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _summary(db, user)


@router.delete("", response_model=DataSummary)
def delete_all_data(payload: DeleteRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Removes every interview, document, answer, report, uploaded file and search index of this account.
    The account itself and its model settings stay."""
    if payload.confirm != CONFIRM_PHRASE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f'Send {{"confirm": "{CONFIRM_PHRASE}"}} to confirm')
    delete_user_data(db, user.id)
    return _summary(db, user)
