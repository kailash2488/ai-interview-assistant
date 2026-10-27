from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import InterviewSession, User
from app.schemas.session import SessionCreate, SessionOut
from app.services.account import delete_session_files

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_or_404(session_id: str, db: Session, user: User) -> InterviewSession:
    """Someone else's interview looks exactly like one that does not exist."""
    obj = db.get(InterviewSession, session_id)
    if obj is None or obj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return obj


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = InterviewSession(user_id=user.id, **payload.model_dump(mode="json"))
    db.add(obj)
    db.commit()
    return obj


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id).order_by(InterviewSession.created_at.desc())).all()


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_session_or_404(session_id, db, user)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = get_session_or_404(session_id, db, user)
    db.delete(obj)
    db.commit()
    delete_session_files(session_id)
