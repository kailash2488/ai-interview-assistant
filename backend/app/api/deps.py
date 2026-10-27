from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_token
from app.models import AuthSession, User


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if auth is None:
        return None
    expires = auth.expires_at if auth.expires_at.tzinfo else auth.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        db.delete(auth)
        db.commit()
        return None
    return db.get(User, auth.user_id)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_token(db, request.cookies.get(settings.cookie_name))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    return user
