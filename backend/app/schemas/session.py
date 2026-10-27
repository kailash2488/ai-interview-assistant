from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InterviewType(str, Enum):
    technical = "technical"
    behavioural = "behavioural"
    mixed = "mixed"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    target_role: str = Field(min_length=1, max_length=200)
    interview_type: InterviewType = InterviewType.mixed
    difficulty: Difficulty = Difficulty.medium
    question_count: int = Field(default=10, ge=3, le=30)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    target_role: str
    interview_type: str
    difficulty: str
    question_count: int
    status: str
    created_at: datetime
    overall_score: int | None = None
