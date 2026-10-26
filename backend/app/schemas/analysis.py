from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SkillLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    unknown = "unknown"


class SkillItem(BaseModel):
    name: str
    level: SkillLevel = SkillLevel.unknown
    evidence: str = ""


class Employer(BaseModel):
    company: str = ""
    role: str = ""
    duration: str = ""


class Project(BaseModel):
    title: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    claimed_outcome: str = ""


class CandidateProfile(BaseModel):
    name: str | None = None
    total_experience_years: float | None = None
    current_role: str | None = None
    skills: list[SkillItem] = Field(default_factory=list)
    employers: list[Employer] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class JDRequirements(BaseModel):
    role_title: str | None = None
    seniority: str = "unknown"
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    domain: str = ""
    soft_skills: list[str] = Field(default_factory=list)


class ProbeClaim(BaseModel):
    text: str
    reason: str


class GapAnalysis(BaseModel):
    matched_skills: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    nice_to_have_matched: list[str] = Field(default_factory=list)
    nice_to_have_missing: list[str] = Field(default_factory=list)
    claims_to_probe: list[ProbeClaim] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    match_percent: int | None = None  # share of must-have skills matched; None if the JD lists none


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    status: str  # running | ready | failed
    error: str | None
    model: str | None
    user_edited: bool
    warnings: list[str]
    profile: CandidateProfile | None
    requirements: JDRequirements | None
    gap: GapAnalysis | None
    updated_at: datetime


class AnalysisPatch(BaseModel):
    profile: CandidateProfile | None = None
    requirements: JDRequirements | None = None
