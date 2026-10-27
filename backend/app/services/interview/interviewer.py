"""The LLM-facing half of the interview: writes questions and analyses answers.
All flow control stays in engine.py."""
import logging
from collections.abc import Iterator

from app.core.config import settings
from app.schemas.analysis import CandidateProfile
from app.schemas.interview import AnswerAnalysis, Category, PlanItem
from app.services.analysis.gap import normalize
from app.services import vectorstore
from app.services.interview.text import clean_question, is_duplicate
from app.services.llm.client import LLMClient
from app.services.llm.prompts import render, wrap_document

log = logging.getLogger(__name__)
HISTORY_TURNS = 3
MAX_ANSWER_CHARS = 700


def _facts(profile: CandidateProfile, item: PlanItem) -> str:
    """Only facts relevant to this topic. Listing every skill makes small models cram them into one question."""
    lines = []
    if profile.current_role:
        lines.append(f"- Current role: {profile.current_role}")
    if profile.total_experience_years is not None:
        lines.append(f"- Experience: {profile.total_experience_years} years")
    if item.category is Category.core:
        skill = next((x for x in profile.skills if normalize(x.name) == normalize(item.topic)), None)
        if skill and skill.evidence:
            lines.append(f"- {skill.name}: {skill.evidence}")
    elif item.category is Category.project:
        project = next((p for p in profile.projects if p.title.lower() == item.topic.lower()), None)
        if project:
            lines.append(
                f"- Project '{project.title}': technologies {', '.join(project.tech_stack) or 'not stated'}; "
                f"claimed result: {project.claimed_outcome or 'none stated'}"
            )
    return "\n".join(lines) or "- (no extra details)"


def _context(session_id: str, item: PlanItem, llm: LLMClient) -> str:
    """Top resume/document chunks for the topic. Retrieval problems never break the interview."""
    if not getattr(llm, "supports_embeddings", True):
        return "(none)"
    try:
        vector = llm.embed([f"{item.topic}. {item.goal}"])[0]
        hits = vectorstore.search(session_id, vector, limit=3)
    except Exception as exc:
        log.info("Context retrieval skipped: %s", exc)
        return "(none)"
    return wrap_document("\n---\n".join(h["text"][:600] for h in hits)) if hits else "(none)"


def _history(turns: list[tuple[str, str | None]]) -> str:
    if not turns:
        return "(interview just started)"
    body = "\n".join(
        f"Interviewer: {q}\nCandidate: {(a or '(no answer)')[:MAX_ANSWER_CHARS]}" for q, a in turns[-HISTORY_TURNS:]
    )
    return wrap_document(body, "history")


def question_prompt(*, session_id, role, difficulty, item, profile, turns, asked, llm, use_retrieval) -> tuple[str, str]:
    return render(
        "interview_question.v1",
        role=role, difficulty=item.difficulty if item.difficulty else difficulty, topic=item.topic, goal=item.goal,
        facts=_facts(profile, item),
        context=_context(session_id, item, llm) if use_retrieval else "(none)",
        history=_history(turns), asked="\n".join(f"- {q}" for q in asked) or "(nothing yet)",
    )


def generate_question(*, llm: LLMClient, session_id: str, role: str, difficulty: str, item: PlanItem,
                      profile: CandidateProfile, turns, asked: list[str], use_retrieval: bool) -> Iterator[str]:
    """Yield tokens of a new question. Duplicates are detected after the fact: the caller gets
    a final 'replace' decision from `finalize_question`, so tokens are streamed once."""
    system, user = question_prompt(session_id=session_id, role=role, difficulty=difficulty, item=item,
                                   profile=profile, turns=turns, asked=asked, llm=llm, use_retrieval=use_retrieval)
    yield from llm.stream_text(system=system, user=user, model=settings.interviewer_model, temperature=0.6, max_tokens=90)


def finalize_question(raw: str, item: PlanItem, asked: list[str]) -> tuple[str, bool]:
    """Clean the model output. Returns (question, used_fallback)."""
    text = clean_question(raw)
    if len(text) < 12 or "?" not in text or is_duplicate(text, asked):
        return item.fallback_question, True
    return text, False


def analyse_answer(*, llm: LLMClient, question: str, goal: str, answer: str) -> AnswerAnalysis:
    system, user = render(
        "analyse_answer.v1", question=question, goal=goal, answer=wrap_document(answer[:2000], "answer"),
    )
    return llm.chat_json(system=system, user=user, schema=AnswerAnalysis, model=settings.interviewer_model,
                         temperature=0.0, max_tokens=180)
