from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DIMENSIONS = ["technical_accuracy", "depth", "relevance", "structure_clarity", "evidence"]
DIMENSION_LABELS = {
    "technical_accuracy": "Technical accuracy",
    "depth": "Depth",
    "relevance": "Relevance",
    "structure_clarity": "Structure and clarity",
    "evidence": "Evidence",
}
DIMENSION_WEIGHTS = {"technical_accuracy": 0.30, "depth": 0.25, "relevance": 0.15, "structure_clarity": 0.15, "evidence": 0.15}


class DimScore(BaseModel):
    """One rubric dimension as returned by the model."""

    score: int = Field(ge=1, le=5)
    quote: str = ""  # short verbatim excerpt of the answer that justifies the score


class AnswerEvaluation(BaseModel):
    """Model output for one answer."""

    technical_accuracy: DimScore
    depth: DimScore
    relevance: DimScore
    structure_clarity: DimScore
    evidence: DimScore
    answer_summary: str = ""
    missing_points: list[str] = Field(default_factory=list)
    feedback: str = ""


class Insight(BaseModel):
    title: str
    detail: str


class PlanStep(BaseModel):
    timeframe: str
    focus: str
    actions: list[str] = Field(default_factory=list)


class ReportNarrative(BaseModel):
    """Model output for the final write-up. All numbers are computed in code, never by the model."""

    summary: str = ""
    strengths: list[Insight] = Field(default_factory=list)
    improvements: list[Insight] = Field(default_factory=list)
    improvement_plan: list[PlanStep] = Field(default_factory=list)


class DimensionResult(BaseModel):
    score: int  # 1-5
    quote: str
    verified: bool


class QuestionReport(BaseModel):
    order_no: int
    topic: str
    category: str
    is_follow_up: bool
    question: str
    answer: str
    answer_summary: str
    score_percent: int
    dimensions: dict[str, DimensionResult]
    missing_points: list[str]
    feedback: str
    sample_answer: str
    notes: list[str]  # rules the code applied, for example "evidence quote could not be verified"


class AreaScore(BaseModel):
    name: str
    category: str
    score_percent: int
    answers: int


class VoiceNotes(BaseModel):
    """Measured from recordings of spoken answers (only present when the interview used voice)."""

    answers: int
    avg_wpm: int | None
    total_pauses: int
    avg_pauses: float
    longest_pause: float


class CommunicationNotes(BaseModel):
    answers: int
    avg_words: int
    shortest_words: int
    longest_words: int
    one_line_answers: int
    rambling_answers: int
    filler_words: dict[str, int]
    vague_phrases: dict[str, int]
    avg_seconds: int | None
    observations: list[str]
    voice: VoiceNotes | None = None


class Coverage(BaseModel):
    planned_topics: int
    questions_asked: int
    evaluated: int
    unanswered: int


class ReportBody(BaseModel):
    overall_score: int
    verdict: str
    verdict_basis: str
    target_role: str
    summary: str
    dimension_scores: dict[str, int]  # percent per rubric dimension
    areas: list[AreaScore]
    strengths: list[Insight]
    improvements: list[Insight]
    questions: list[QuestionReport]
    communication: CommunicationNotes
    improvement_plan: list[PlanStep]
    coverage: Coverage


class ReportOut(BaseModel):
    session_id: str
    status: Literal["running", "ready", "failed"]
    error: str | None
    model: str | None
    warnings: list[str]
    progress_done: int
    progress_total: int
    overall_score: int | None
    report: ReportBody | None
    updated_at: datetime
