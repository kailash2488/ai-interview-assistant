"""Removing a user's interviews together with their uploaded files and search index."""
import logging
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import InterviewSession
from app.services import vectorstore

log = logging.getLogger(__name__)


def delete_session_files(session_id: str) -> None:
    shutil.rmtree(settings.upload_dir / session_id, ignore_errors=True)
    try:
        vectorstore.delete_session(session_id)
    except Exception:
        log.warning("Could not clear vectors for session %s", session_id, exc_info=True)


def delete_user_data(db: Session, user_id: str) -> int:
    """Deletes every interview the user owns (rows, files, vectors). Returns how many."""
    sessions = list(db.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id)))
    ids = [s.id for s in sessions]
    for s in sessions:
        db.delete(s)
    db.commit()
    for sid in ids:
        delete_session_files(sid)
    return len(ids)
