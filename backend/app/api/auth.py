import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import burn_password_check, hash_password, hash_token, new_token, verify_password
from app.models import AuthSession, InterviewSession, User
from app.services.account import delete_user_data
from app.services.llm import user_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_failures: dict[tuple[str, str], list[float]] = defaultdict(list)  # (client ip, email) -> failure times (per process)


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value


class SignupIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    _check_email = field_validator("email")(_email)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Enter your name")
        return v


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    _check_email = field_validator("email")(_email)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime


class AuthConfig(BaseModel):
    allow_signup: bool


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate(ip: str, email: str) -> None:
    window = settings.login_lockout_minutes * 60
    now = time.time()
    recent = [t for t in _failures[(ip, email)] if now - t < window]
    _failures[(ip, email)] = recent
    if len(recent) >= settings.max_login_failures:
        wait = int((recent[0] + window - now) / 60) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many failed attempts. Try again in {wait} minute{'s' if wait != 1 else ''}.")


def _start_session(response: Response, db: Session, user: User) -> None:
    token = new_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.session_days)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires))
    db.commit()
    response.set_cookie(settings.cookie_name, token, max_age=settings.session_days * 86400, httponly=True,
                        samesite="lax", secure=settings.cookie_secure, path="/")


@router.get("/config", response_model=AuthConfig)
def auth_config():
    return AuthConfig(allow_signup=settings.allow_signup)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupIn, response: Response, db: Session = Depends(get_db)):
    if not settings.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-ups are closed on this server")
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Log in instead.")
    first_account = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    user = User(email=payload.email, name=payload.name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    if first_account:
        # Interviews and settings from before accounts existed belong to whoever set the app up.
        adopted = db.execute(update(InterviewSession).where(InterviewSession.user_id.is_(None)).values(user_id=user.id)).rowcount
        db.commit()
        migrated = user_settings.import_legacy_file(db, user.id)
        log.info("First account created; adopted %d interviews, imported settings: %s", adopted, migrated)
    _start_session(response, db, user)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _check_rate(ip, payload.email)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        burn_password_check(payload.password)
    if user is None or not verify_password(payload.password, user.password_hash):
        _failures[(ip, payload.email)].append(time.time())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    _failures.pop((ip, payload.email), None)
    _start_session(response, db, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.cookie_name)
    if token:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        if row is not None:
            db.delete(row)
            db.commit()
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChangeIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password is wrong")
    user.password_hash = hash_password(payload.new_password)
    # Sign out every other browser; keep this one.
    keep = hash_token(request.cookies.get(settings.cookie_name, ""))
    for row in list(user.auth_sessions):
        if row.token_hash != keep:
            db.delete(row)
    db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(payload: DeleteAccountIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your password is wrong")
    delete_user_data(db, user.id)
    db.delete(user)
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
