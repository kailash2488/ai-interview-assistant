import logging
import time

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Evaluation, InterviewSession, Report
from app.schemas.analysis import CandidateProfile
from app.schemas.interview import Category, InterviewPlan
from app.schemas.report import (
    DIMENSION_LABELS, Coverage, QuestionReport, ReportBody, ReportNarrative,
)
from app.services.feedback import aggregate, communication, evaluator
from app.services.interview.engine import ANALYSED
from app.schemas.report import DimensionResult
from app.services.llm.client import LLMError, LLMInvalidOutput, LLMUnavailable, get_llm
from app.services.llm.user_settings import config_for_user
from app.services.llm.prompts import render

log = logging.getLogger(__name__)


BACKOFF_SECONDS = (20, 40, 60)
_TRANSIENT = ("rate limit", "overloaded", "did not answer in time")


def with_backoff(fn, *args, **kwargs):
    """Free-tier APIs rate-limit by the minute. A long report makes many calls, so wait and retry
    transient failures instead of failing the whole report."""
    for wait in (*BACKOFF_SECONDS, None):
        try:
            return fn(*args, **kwargs)
        except LLMUnavailable as exc:
            if wait is None or not any(t in str(exc) for t in _TRANSIENT):
                raise
            log.warning("Transient LLM failure (%s); waiting %ds", exc, wait)
            time.sleep(wait)


def evaluable_questions(session: InterviewSession) -> list:
    """Answered questions from scored categories (intro and the closing question are not scored)."""
    plan = InterviewPlan.model_validate(session.plan.plan_json)
    return [q for q in sorted(session.questions, key=lambda q: q.order_no)
            if q.answer is not None and plan.items[q.plan_index].category in ANALYSED]


def _progress(db, row: Report, done: int) -> None:
    row.progress_done = done
    db.commit()


def _narrative(llm, *, role, overall, verdict_label, areas, dims, questions, comm) -> ReportNarrative:
    ranked = sorted(questions, key=lambda q: q.score_percent)
    weak = "\n".join(f"- {q.topic} ({q.score_percent}/100): missing {', '.join(q.missing_points) or 'depth and specifics'}" for q in ranked[:4])
    strong = "\n".join(f"- {c}" for c in aggregate.strength_candidates(areas, dims))
    system, user = render(
        "report_synthesis.v1", role=role, overall=str(overall), verdict=verdict_label,
        areas="\n".join(f"- {a.name}: {a.score_percent}" for a in sorted(areas, key=lambda a: -a.score_percent)),
        dimensions="\n".join(f"- {DIMENSION_LABELS[k]}: {v}" for k, v in dims.items()),
        weak=weak or "- (none)", strong=strong or "(none)",
        communication="\n".join(f"- {o}" for o in comm.observations),
    )
    return llm.chat_json(system=system, user=user, schema=ReportNarrative, model=settings.evaluator_model, temperature=0.2)


def run_report(session_id: str, reuse: bool = False) -> None:
    """Background task. The caller created the 'running' row. Evaluates every scored answer, then writes the report.
    With reuse=True (retry after a failure) answers that already have a stored evaluation are not re-scored."""
    with SessionLocal() as db:
        row = db.scalar(select(Report).where(Report.session_id == session_id))
        session = db.get(InterviewSession, session_id)
        if row is None or session is None:
            return
        warnings: list[str] = []
        try:
            llm = get_llm(config_for_user(db, session.user_id))
            plan = InterviewPlan.model_validate(session.plan.plan_json)
            profile = CandidateProfile.model_validate(session.analysis.profile_json)
            questions = evaluable_questions(session)
            row.progress_total, row.progress_done = len(questions), 0
            db.commit()

            reports: list[QuestionReport] = []
            for i, q in enumerate(questions, start=1):
                item = plan.items[q.plan_index]
                stored = q.answer.evaluation if reuse else None
                if stored is not None:
                    reports.append(QuestionReport(
                        order_no=q.order_no, topic=item.topic, category=item.category.value, is_follow_up=q.is_follow_up,
                        question=q.text, answer=q.answer.text, answer_summary=stored.evidence_json.get("answer_summary", ""),
                        score_percent=stored.score_percent,
                        dimensions={k: DimensionResult(**v) for k, v in stored.scores_json.items()},
                        missing_points=stored.evidence_json.get("missing_points", []), feedback=stored.feedback_text,
                        sample_answer=stored.sample_answer, notes=stored.evidence_json.get("notes", []),
                    ))
                    _progress(db, row, i)
                    continue
                analysis = q.answer.analysis_json or {}
                dims, raw, notes = with_backoff(
                    evaluator.evaluate_answer, llm, question=q.text, goal=item.goal, answer=q.answer.text,
                    off_topic=bool(analysis.get("is_off_topic")))
                pct = evaluator.rubric.score_percent(dims)
                missing = raw.missing_points[:3] if raw else ["a substantive answer"]
                sample = ""
                if raw and pct < evaluator.SAMPLE_SKIP_AT:
                    try:
                        sample = with_backoff(evaluator.sample_answer, llm, role=session.target_role, question=q.text,
                                              answer=q.answer.text, topic=item.topic, missing=missing, profile=profile)
                    except LLMUnavailable:
                        raise
                    except LLMError as exc:  # a missing sample answer must not sink the report
                        log.warning("Sample answer failed for question %s: %s", q.id, exc)
                feedback = raw.feedback if raw else "Your answer was too short to evaluate. Add a reason and an example."
                summary = raw.answer_summary if raw else q.answer.text[:120]
                if q.answer.evaluation is not None:
                    db.delete(q.answer.evaluation)
                    db.flush()
                q.answer.evaluation = Evaluation(
                    scores_json={k: v.model_dump() for k, v in dims.items()},
                    evidence_json={"answer_summary": summary, "missing_points": missing, "notes": notes},
                    feedback_text=feedback, sample_answer=sample, score_percent=pct,
                )
                reports.append(QuestionReport(
                    order_no=q.order_no, topic=item.topic, category=item.category.value, is_follow_up=q.is_follow_up,
                    question=q.text, answer=q.answer.text, answer_summary=summary, score_percent=pct, dimensions=dims,
                    missing_points=missing, feedback=feedback, sample_answer=sample, notes=notes,
                ))
                _progress(db, row, i)

            overall = aggregate.overall_score(reports)
            planned_scored = sum(1 for it in plan.items if it.category in ANALYSED)
            label, basis = aggregate.verdict(overall, len(reports), planned_scored)
            areas, dims_avg = aggregate.area_scores(reports), aggregate.dimension_scores(reports)
            scored = [q for q in session.questions if q.answer is not None and plan.items[q.plan_index].category in ANALYSED]
            comm = communication.analyse([(q.answer.text, q.answer.duration_seconds) for q in scored], [q.answer.voice_json or {} for q in scored])
            try:
                narrative = with_backoff(_narrative, llm, role=session.target_role, overall=overall, verdict_label=label,
                                         areas=areas, dims=dims_avg, questions=reports, comm=comm)
                strengths, improvements, steps = narrative.strengths[:3], narrative.improvements[:3], narrative.improvement_plan[:2]
                if not aggregate.strength_candidates(areas, dims_avg):
                    strengths = []  # nothing scored well enough to praise
                summary = narrative.summary.strip()
                has_candidates = bool(aggregate.strength_candidates(areas, dims_avg))
                if not ((strengths or not has_candidates) and improvements and steps and summary):
                    raise LLMInvalidOutput("The summary was incomplete")
            except LLMError as exc:
                log.warning("Report narrative failed for session %s: %s", session_id, exc)
                warnings.append("The written summary could not be generated, so strengths, improvements and the study plan were built from your scores.")
                strengths, improvements, steps = aggregate.fallback_narrative(areas, dims_avg, reports)
                summary = f"You scored {overall}/100 across {len(reports)} answered questions for the {session.target_role} role."

            asked = len(session.questions)
            body = ReportBody(
                overall_score=overall, verdict=label, verdict_basis=basis, target_role=session.target_role, summary=summary,
                dimension_scores=dims_avg, areas=areas, strengths=strengths, improvements=improvements, questions=reports,
                communication=comm, improvement_plan=steps,
                coverage=Coverage(planned_topics=len(plan.items), questions_asked=asked, evaluated=len(reports),
                                  unanswered=sum(1 for q in session.questions if q.answer is None)),
            )
            row.report_json, row.overall_score = body.model_dump(mode="json"), overall
            row.model = getattr(llm, "model_name", settings.evaluator_model)
            row.warnings_json, row.status, row.error = warnings, "ready", None
            session.status = "reported"
        except LLMError as exc:
            row.status, row.error = "failed", str(exc)
        except Exception:
            log.exception("Report generation crashed for session %s", session_id)
            row.status, row.error = "failed", "Unexpected error while generating the report"
        db.commit()
