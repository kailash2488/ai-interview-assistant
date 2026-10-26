from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Category(str, Enum):
    intro = "intro"
    core = "core"
    project = "project"
    gap = "gap"
    behavioural = "behavioural"
    closing = "closing"


class PlanItem(BaseModel):
    index: int
    category: Category
    topic: str
    goal: str
    difficulty: Literal["easy", "medium", "hard"]
    max_followups: int = Field(ge=0, le=3)
    fallback_question: str


class InterviewPlan(BaseModel):
    items: list[PlanItem]
    followup_budget: int  # total follow-ups allowed in the whole interview


class PlanTopicOut(BaseModel):
    """What the candidate may see: the topic outline, never the questions."""

    index: int
    category: Category
    topic: str
    difficulty: str


class PlanOut(BaseModel):
    session_id: str
    topics: list[PlanTopicOut]
    followup_budget: int


class AnswerAnalysis(BaseModel):
    answer_quality: Literal["weak", "ok", "strong"] = "ok"
    missing_points: list[str] = Field(default_factory=list)
    is_off_topic: bool = False
    needs_follow_up: bool = False
    suggested_follow_up: str = ""


class TurnOut(BaseModel):
    """One question and its answer, without any evaluation data."""

    question_id: str
    order_no: int
    topic: str
    ack: str
    text: str
    is_follow_up: bool
    answer: str | None


class InterviewStateOut(BaseModel):
    session_id: str
    status: str
    main_total: int
    main_asked: int
    turns: list[TurnOut]
