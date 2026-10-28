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


class MCQDraft(BaseModel):
    question: str = Field(min_length=12, max_length=500)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=800)


class MCQSetDraft(BaseModel):
    questions: list[MCQDraft] = Field(min_length=1, max_length=30)


class MCQQuestionOut(BaseModel):
    question_id: str
    order_no: int
    topic: str
    text: str
    options: list[str]
    selected_index: int | None = None
    correct: bool | None = None
    correct_index: int | None = None
    explanation: str | None = None


class MCQStateOut(BaseModel):
    session_id: str
    status: str
    total: int
    answered: int
    score: int | None = None
    current: MCQQuestionOut | None = None
    results: list[MCQQuestionOut] = Field(default_factory=list)


class MCQAnswerIn(BaseModel):
    selected_index: int = Field(ge=0, le=3)
    # Optional for compatibility with clients deployed before answer request IDs were introduced.
    question_id: str | None = Field(default=None, min_length=1, max_length=32)
