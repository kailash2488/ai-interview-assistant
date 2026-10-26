import logging
import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import InterviewSession
from app.schemas.session import SessionCreate, SessionOut
from app.services import vectorstore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_or_404(session_id: str, db: Session) -> InterviewSession:
    obj = db.get(InterviewSession, session_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return obj


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    obj = InterviewSession(**payload.model_dump(mode="json"))
    db.add(obj)
    db.commit()
    return obj


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.scalars(select(InterviewSession).order_by(InterviewSession.created_at.desc())).all()


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    return get_session_or_404(session_id, db)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    obj = get_session_or_404(session_id, db)
    db.delete(obj)
    db.commit()
    shutil.rmtree(settings.upload_dir / session_id, ignore_errors=True)
    try:
        vectorstore.delete_session(session_id)
    except Exception:
        log.warning("Could not delete vectors for session %s", session_id, exc_info=True)
