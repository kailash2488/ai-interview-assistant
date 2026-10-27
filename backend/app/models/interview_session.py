import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InterviewSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    # Owner. NULL only for interviews created before accounts existed; the first account to sign up adopts them.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    target_role: Mapped[str] = mapped_column(String(200))
    interview_type: Mapped[str] = mapped_column(String(20))
    difficulty: Mapped[str] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Document.created_at"
    )
    analysis: Mapped["SessionAnalysis | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    plan: Mapped["InterviewPlanRow | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    questions: Mapped[list["Question"]] = relationship(
        cascade="all, delete-orphan", order_by="Question.order_no"
    )
    report: Mapped["Report | None"] = relationship(cascade="all, delete-orphan", uselist=False)

    @property
    def overall_score(self) -> int | None:
        return self.report.overall_score if self.report is not None and self.report.status == "ready" else None


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # resume | jd | other
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|parsing|ready|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[InterviewSession] = relationship(back_populates="documents")


class SessionAnalysis(Base):
    """Profile, JD requirements and gap analysis for a session (one row per session)."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | ready | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_edited: Mapped[bool] = mapped_column(default=False)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    requirements_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gap_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    session: Mapped[InterviewSession] = relationship(back_populates="analysis")


class InterviewPlanRow(Base):
    __tablename__ = "interview_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True)
    plan_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[InterviewSession] = relationship(back_populates="plan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    order_no: Mapped[int] = mapped_column(Integer)
    plan_index: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    ack: Mapped[str] = mapped_column(String(200), default="")
    is_follow_up: Mapped[bool] = mapped_column(default=False)
    parent_question_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    answer: Mapped["Answer | None"] = relationship(back_populates="question", cascade="all, delete-orphan", uselist=False)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Quick per-answer analysis used for flow control; never sent to the candidate during the interview.
    analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    question: Mapped[Question] = relationship(back_populates="answer")
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="answer", cascade="all, delete-orphan", uselist=False)


class Evaluation(Base):
    """Rubric scores for one answer (written by the report job, after the interview)."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), unique=True, index=True)
    scores_json: Mapped[dict] = mapped_column(JSON)  # {dimension: {score, quote, verified}}
    evidence_json: Mapped[dict] = mapped_column(JSON)  # {answer_summary, missing_points, guards}
    feedback_text: Mapped[str] = mapped_column(Text, default="")
    sample_answer: Mapped[str] = mapped_column(Text, default="")
    score_percent: Mapped[int] = mapped_column(Integer, default=0)

    answer: Mapped[Answer] = relationship(back_populates="evaluation")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | ready | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
