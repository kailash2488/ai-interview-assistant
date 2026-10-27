"""One call that feeds the home dashboard: stats, trend, focus areas, a suggested next step and badges."""
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import Answer, InterviewSession, Question, Report, User
from app.schemas.report import DIMENSION_LABELS, ReportBody

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
TREND_POINTS = 12
FOCUS_REPORTS = 5          # topic averages use the latest few reports so old results fade out
STRENGTH_MIN = 60
_SUFFIX = re.compile(r"\s*\((core skill|gap area|project|behavioural)\)$", re.IGNORECASE)


class Stats(BaseModel):
    interviews: int
    finished: int
    reports: int
    avg_score: int | None
    best_score: int | None
    latest_score: int | None
    change: int | None           # latest minus the one before; None with fewer than two reports
    streak_days: int
    practice_days_30: int
    answers: int


class TrendPoint(BaseModel):
    session_id: str
    title: str
    target_role: str
    date: datetime
    score: int


class TopicStat(BaseModel):
    name: str
    score: int
    attempts: int


class DimensionStat(BaseModel):
    key: str
    label: str
    score: int
    change: int | None


class NextAction(BaseModel):
    kind: Literal["new", "upload", "analyse", "plan", "start", "continue", "report"]
    title: str | None
    label: str
    description: str
    session_id: str | None
    href: str


class Activity(BaseModel):
    session_id: str
    title: str
    status: str
    score: int | None
    at: datetime


class Badge(BaseModel):
    id: str
    label: str
    description: str
    earned: bool


class DashboardOut(BaseModel):
    stats: Stats
    trend: list[TrendPoint]
    weakest: list[TopicStat]
    strongest: list[TopicStat]
    dimensions: list[DimensionStat]
    next_action: NextAction
    recent: list[Activity]
    badges: list[Badge]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def streak(days: set[date], today: date) -> int:
    """Consecutive days of practice ending today (or yesterday, so the streak is not lost before you practise today)."""
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def topic_stats(reports: list[ReportBody]) -> tuple[list[TopicStat], list[TopicStat]]:
    scores: dict[str, list[int]] = defaultdict(list)
    for body in reports[-FOCUS_REPORTS:]:
        for area in body.areas:
            scores[_SUFFIX.sub("", area.name)].append(area.score_percent)
    stats = [TopicStat(name=n, score=round(sum(v) / len(v)), attempts=len(v)) for n, v in scores.items()]
    weakest = sorted(stats, key=lambda t: t.score)[:5]
    strongest = [t for t in sorted(stats, key=lambda t: -t.score) if t.score >= STRENGTH_MIN][:3]
    return weakest, strongest


def next_action(sessions: list[InterviewSession]) -> NextAction:
    """The most recent interview that is not finished off with a report decides what to suggest."""
    for s in sorted(sessions, key=lambda s: _aware(s.created_at), reverse=True):
        sid = s.id
        has = {d.kind for d in s.documents if d.status == "ready"}
        if s.status == "in_progress":
            return NextAction(kind="continue", title=s.title, label="Continue your interview", description=f"You are partway through “{s.title}”. Pick up where you stopped.", session_id=sid, href=f"/sessions/{sid}/interview")
        if s.status == "completed" and s.report is None:
            return NextAction(kind="report", title=s.title, label="Get your feedback report", description=f"“{s.title}” is finished. See how you did and what to work on.", session_id=sid, href=f"/sessions/{sid}/report")
        if s.status == "planned":
            return NextAction(kind="start", title=s.title, label="Start your interview", description=f"The plan for “{s.title}” is ready.", session_id=sid, href=f"/sessions/{sid}/plan")
        if s.status == "analysed":
            return NextAction(kind="plan", title=s.title, label="Review and build the plan", description=f"Check what was found in your documents for “{s.title}”.", session_id=sid, href=f"/sessions/{sid}/analysis")
        if s.status == "created":
            if {"resume", "jd"} <= has:
                return NextAction(kind="analyse", title=s.title, label="Analyse your documents", description=f"Your resume and job description for “{s.title}” are uploaded.", session_id=sid, href=f"/sessions/{sid}/upload")
            return NextAction(kind="upload", title=s.title, label="Finish uploading", description=f"“{s.title}” still needs a resume and a job description.", session_id=sid, href=f"/sessions/{sid}/upload")
    return NextAction(kind="new", title=None, label="Start a new interview", description="Upload a resume and a job description and practise for the real thing.", session_id=None, href="/new")


def badges(finished: int, bodies: list[ReportBody], streak_days: int) -> list[Badge]:
    scores = [b.overall_score for b in bodies]
    improved = len(scores) >= 2 and scores[-1] - scores[-2] >= 10
    all_round = any(min(b.dimension_scores.values(), default=0) >= STRENGTH_MIN for b in bodies)
    return [
        Badge(id="first", label="First interview", description="Finish your first mock interview", earned=finished >= 1),
        Badge(id="report", label="Know your level", description="Get your first feedback report", earned=bool(bodies)),
        Badge(id="strong", label="Strong showing", description="Score 70 or more in an interview", earned=any(s >= 70 for s in scores)),
        Badge(id="improver", label="On the up", description="Beat your previous score by 10 points or more", earned=improved),
        Badge(id="all_round", label="All-rounder", description="Score 60 or more in every rubric dimension", earned=all_round),
        Badge(id="regular", label="Regular", description="Get three reports", earned=len(bodies) >= 3),
        Badge(id="streak", label="On a roll", description="Practise three days in a row", earned=streak_days >= 3),
    ]


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    sessions = list(db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)))
    rows = db.execute(
        select(InterviewSession, Report).join(Report, Report.session_id == InterviewSession.id)
        .where(InterviewSession.user_id == user.id, Report.status == "ready").order_by(InterviewSession.created_at)
    ).all()
    bodies = [ReportBody.model_validate(r.report_json) for _, r in rows]
    scores = [b.overall_score for b in bodies]

    days = {_aware(s.created_at).date() for s in sessions} | {_aware(r.updated_at).date() for _, r in rows}
    today = datetime.now(timezone.utc).date()
    streak_days = streak(days, today)
    mine = select(InterviewSession.id).where(InterviewSession.user_id == user.id)
    answers = db.scalar(select(func.count()).select_from(Answer).join(Question, Answer.question_id == Question.id).where(Question.session_id.in_(mine))) or 0
    finished = sum(1 for s in sessions if s.status in ("completed", "reported"))

    dims: list[DimensionStat] = []
    if bodies:
        last, prev = bodies[-1], (bodies[-2] if len(bodies) > 1 else None)
        dims = [DimensionStat(key=k, label=DIMENSION_LABELS[k], score=last.dimension_scores.get(k, 0),
                              change=(last.dimension_scores.get(k, 0) - prev.dimension_scores.get(k, 0)) if prev else None) for k in DIMENSION_LABELS]
    weakest, strongest = topic_stats(bodies)
    scored = {s.id: s.overall_score for s in sessions}

    return DashboardOut(
        stats=Stats(
            interviews=len(sessions), finished=finished, reports=len(bodies),
            avg_score=round(sum(scores) / len(scores)) if scores else None, best_score=max(scores) if scores else None,
            latest_score=scores[-1] if scores else None, change=(scores[-1] - scores[-2]) if len(scores) >= 2 else None,
            streak_days=streak_days, practice_days_30=sum(1 for d in days if (today - d).days < 30), answers=answers,
        ),
        trend=[TrendPoint(session_id=s.id, title=s.title, target_role=s.target_role, date=s.created_at, score=b.overall_score)
               for (s, _), b in list(zip(rows, bodies))[-TREND_POINTS:]],
        weakest=weakest, strongest=strongest, dimensions=dims, next_action=next_action(sessions),
        recent=[Activity(session_id=s.id, title=s.title, status=s.status, score=scored.get(s.id), at=s.created_at)
                for s in sorted(sessions, key=lambda s: _aware(s.created_at), reverse=True)[:5]],
        badges=badges(finished, bodies, streak_days),
    )
