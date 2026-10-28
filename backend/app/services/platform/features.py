"""Server-side feature flags. Unknown flags are ignored and never become capabilities."""
from app.core.config import settings

KNOWN_FEATURES = frozenset({
    "job_tracker",
    "resume_alignment",
    "resume_studio",
    "star_stories",
    "preparation_calendar",
    "company_research",
    "technical_assessments",
    "readiness_score",
    "job_analytics",
    "communication_tools",
})


def enabled_features() -> frozenset[str]:
    return frozenset(settings.feature_flags) & KNOWN_FEATURES


def enabled(name: str) -> bool:
    return name in enabled_features()
