from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DocumentKind(str, Enum):
    resume = "resume"
    jd = "jd"
    other = "other"


class Section(BaseModel):
    name: str
    text: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    kind: str
    filename: str
    status: str
    error: str | None
    created_at: datetime


class DocumentDetail(DocumentOut):
    raw_text: str | None
    sections_json: list[Section] | None
