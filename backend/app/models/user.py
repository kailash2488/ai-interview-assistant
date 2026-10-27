import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # stored lower-case
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    auth_sessions: Mapped[list["AuthSession"]] = relationship(cascade="all, delete-orphan")
    llm_settings: Mapped["UserLLMSettings | None"] = relationship(cascade="all, delete-orphan", uselist=False)


class AuthSession(Base):
    """A signed-in browser. The cookie holds a random token; only its hash is stored here."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserLLMSettings(Base):
    """Which model a user's interviews run on. The Gemini key is stored encrypted."""

    __tablename__ = "user_llm_settings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), default="ollama")
    gemini_model: Mapped[str] = mapped_column(String(80), default="gemini-3.5-flash-lite")
    gemini_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
