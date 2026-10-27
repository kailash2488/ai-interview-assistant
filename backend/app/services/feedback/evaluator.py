import logging

from app.core.config import settings
from app.schemas.analysis import CandidateProfile
from app.schemas.report import AnswerEvaluation, DimensionResult
from app.services.feedback import rubric
from app.services.interview.text import word_count
from app.services.llm.client import LLMClient
from app.services.llm.prompts import render, wrap_document

log = logging.getLogger(__name__)
MAX_ANSWER_CHARS = 3000
SAMPLE_SKIP_AT = 85  # no sample answer when the candidate already scored this well


def evaluate_answer(llm: LLMClient, *, question: str, goal: str, answer: str, off_topic: bool = False
                    ) -> tuple[dict[str, DimensionResult], AnswerEvaluation | None, list[str]]:
    """Returns (guarded dimensions, raw model output or None, notes). One task per call, temperature 0."""
    if word_count(answer) < rubric.SHORT_ANSWER_WORDS:
        return rubric.too_short_result(), None, ["The answer was too short to evaluate, so it scored the minimum"]
    system, user = render("evaluate_answer.v1", question=question, goal=goal, answer=wrap_document(answer[:MAX_ANSWER_CHARS], "answer"))
    raw = llm.chat_json(system=system, user=user, schema=AnswerEvaluation, model=settings.evaluator_model, temperature=0.0)
    dims, notes = rubric.apply_guards(raw, answer, off_topic)
    return dims, raw, notes


def _background(profile: CandidateProfile, topic: str) -> str:
    lines = []
    if profile.current_role:
        lines.append(f"- Current role: {profile.current_role}")
    for s in profile.skills:
        if s.name.lower() == topic.lower() and s.evidence:
            lines.append(f"- {s.name}: {s.evidence}")
    for p in profile.projects:
        if p.title.lower() == topic.lower():
            lines.append(f"- Project {p.title} using {', '.join(p.tech_stack) or 'unspecified technologies'}")
    return "\n".join(lines) or "- (no extra details)"


def sample_answer(llm: LLMClient, *, role: str, question: str, answer: str, topic: str, missing: list[str], profile: CandidateProfile) -> str:
    system, user = render(
        "sample_answer.v1", role=role, question=question, background=_background(profile, topic),
        missing="\n".join(f"- {m}" for m in missing) or "- a clear, specific, example-backed answer",
        answer=wrap_document(answer[:1500], "answer"),
    )
    text = "".join(llm.stream_text(system=system, user=user, model=settings.evaluator_model, temperature=0.3, max_tokens=300))
    return text.strip().strip('"')
