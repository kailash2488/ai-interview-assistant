"""Interview state machine. The LLM writes the words; this code controls the flow.

Rules enforced here (never left to the model):
- follow-ups per topic and across the interview are capped by the plan
- the planned topic count is fixed; follow-ups never replace planned topics
- a question already asked is never repeated (fallback to the planned question)
- scores and analysis are never sent to the candidate
- invalid model output: retry once (in the client), then fall back to the next planned question

State is derived from the database on every call, so a dropped connection can resume cleanly:
  INTRO -> TOPIC_QUESTION -> WAIT_ANSWER -> ANALYSE_ANSWER -> FOLLOW_UP | NEXT_TOPIC | WRAP_UP -> COMPLETE
"""
import logging
from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Answer, InterviewSession, Question
from app.schemas.analysis import CandidateProfile, GapAnalysis
from app.schemas.interview import AnswerAnalysis, Category, InterviewPlan, PlanItem
from app.services.interview import interviewer
from app.services.interview.text import is_duplicate, word_count
from app.services.llm.client import LLMClient, LLMInvalidOutput, get_llm
from app.services.llm.user_settings import config_for_user

log = logging.getLogger(__name__)

ANALYSED = {Category.core, Category.project, Category.gap, Category.behavioural}
SHORT_ANSWER_WORDS = 6
MAX_ANSWER_CHARS = 5000
GENERIC_FOLLOW_UP = "Could you give a concrete example from your own experience?"
ACK_NEXT = ["Thanks, let's move on.", "Got it. Moving on.", "Okay, thank you. Next topic."]
ACK_FOLLOW_UP = ["Thanks.", "Okay."]
CLOSING_TEXT = "Thank you, that completes the interview. Your feedback report will be prepared next."


class InterviewError(Exception):
    """A problem with the request itself (safe to show to the user)."""


class _Context:
    def __init__(self, session: InterviewSession, plan: InterviewPlan, profile: CandidateProfile, gap: GapAnalysis):
        self.session, self.plan, self.profile, self.gap = session, plan, profile, gap


class InterviewEngine:
    def __init__(self, session_id: str, llm: LLMClient | None = None, db_factory: Callable[[], Session] = SessionLocal):
        self.session_id = session_id
        self._llm = llm
        self._db_factory = db_factory

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            with self._db_factory() as db:
                owner = db.get(InterviewSession, self.session_id)
                self._llm = get_llm(config_for_user(db, owner.user_id if owner else None))
        return self._llm

    # ---------- loading ----------

    def _load(self, db: Session) -> _Context:
        session = db.get(InterviewSession, self.session_id)
        if session is None:
            raise InterviewError("Session not found")
        if session.plan is None or session.analysis is None or session.analysis.status != "ready":
            raise InterviewError("Build the interview plan first")
        return _Context(
            session,
            InterviewPlan.model_validate(session.plan.plan_json),
            CandidateProfile.model_validate(session.analysis.profile_json),
            GapAnalysis.model_validate(session.analysis.gap_json),
        )

    @staticmethod
    def _questions(session: InterviewSession) -> list[Question]:
        return sorted(session.questions, key=lambda q: q.order_no)

    # ---------- public API (generators of event dicts) ----------

    def state(self) -> dict:
        with self._db_factory() as db:
            session = db.get(InterviewSession, self.session_id)
            if session is None:
                raise InterviewError("Session not found")
            questions = self._questions(session)
            total = len(session.plan.plan_json["items"]) if session.plan else 0
            return {
                "session_id": session.id,
                "status": session.status,
                "main_total": session.question_count or total,
                "main_asked": min(len(questions), session.question_count),
                "turns": [
                    {"question_id": q.id, "order_no": q.order_no, "topic": q.topic, "ack": q.ack, "text": q.text,
                     "is_follow_up": q.is_follow_up, "answer": q.answer.text if q.answer else None}
                    for q in questions
                ],
            }

    def start(self) -> Iterator[dict]:
        """Begin the interview, or continue it after a reconnect."""
        with self._db_factory() as db:
            ctx = self._load(db)
            if ctx.session.status == "completed":
                yield {"type": "complete", "message": CLOSING_TEXT}
                return
            ctx.session.status = "in_progress"
            db.commit()
            questions = self._questions(ctx.session)
            if not questions:
                yield from self._ask_item(db, ctx, ctx.plan.items[0], ack="")
            elif questions[-1].answer is None:
                yield self._question_event(ctx, questions[-1], replay=True)
            else:
                yield from self._advance(db, ctx)

    def answer(self, text: str, duration_seconds: int | None = None, voice: dict | None = None) -> Iterator[dict]:
        text = text.strip()
        if not text:
            raise InterviewError("Please type an answer first")
        if len(text) > MAX_ANSWER_CHARS:
            raise InterviewError(f"Answers are limited to {MAX_ANSWER_CHARS} characters")
        with self._db_factory() as db:
            ctx = self._load(db)
            if ctx.session.status == "completed":
                raise InterviewError("The interview is already complete")
            questions = self._questions(ctx.session)
            if not questions or questions[-1].answer is not None:
                raise InterviewError("There is no open question to answer")
            questions[-1].answer = Answer(text=text, duration_seconds=duration_seconds, voice_json=voice or None)
            db.commit()
            yield from self._advance(db, ctx)

    def finish(self) -> None:
        """End early. Unanswered open question is left unanswered."""
        with self._db_factory() as db:
            session = db.get(InterviewSession, self.session_id)
            if session is None:
                raise InterviewError("Session not found")
            session.status = "completed"
            db.commit()

    # ---------- flow control ----------

    def _advance(self, db: Session, ctx: _Context) -> Iterator[dict]:
        questions = self._questions(ctx.session)
        last = questions[-1]
        # question_count is a hard user-facing cap, including adaptive follow-ups.
        if len(questions) >= ctx.session.question_count:
            ctx.session.status = "completed"
            db.commit()
            yield {"type": "complete", "message": CLOSING_TEXT}
            return
        item = ctx.plan.items[last.plan_index]
        analysis = self._analysis_for(db, last, item)

        followups_here = sum(1 for q in questions if q.plan_index == item.index and q.is_follow_up)
        followups_total = sum(1 for q in questions if q.is_follow_up)
        suggestion = analysis.suggested_follow_up.strip()
        can_follow_up = (
            analysis.needs_follow_up and not analysis.is_off_topic and suggestion
            and followups_here < item.max_followups and followups_total < ctx.plan.followup_budget
            and not is_duplicate(suggestion, [q.text for q in questions])
        )
        if can_follow_up:
            yield from self._ask_text(db, ctx, item, suggestion if suggestion.endswith("?") else suggestion + "?",
                                      ack=ACK_FOLLOW_UP[len(questions) % len(ACK_FOLLOW_UP)], parent=last)
        elif last.plan_index + 1 < len(ctx.plan.items):
            nxt = ctx.plan.items[last.plan_index + 1]
            ack = ACK_NEXT[len(questions) % len(ACK_NEXT)]
            yield from self._ask_item(db, ctx, nxt, ack=ack)
        else:
            ctx.session.status = "completed"
            db.commit()
            yield {"type": "complete", "message": CLOSING_TEXT}

    def _analysis_for(self, db: Session, question: Question, item: PlanItem) -> AnswerAnalysis:
        answer = question.answer
        if answer.analysis_json is not None:
            return AnswerAnalysis.model_validate(answer.analysis_json)
        if item.category not in ANALYSED:
            return AnswerAnalysis()
        if word_count(answer.text) < SHORT_ANSWER_WORDS:
            result = AnswerAnalysis(answer_quality="weak", needs_follow_up=True, suggested_follow_up=GENERIC_FOLLOW_UP,
                                    missing_points=["a substantive answer"])
        else:
            try:
                result = interviewer.analyse_answer(llm=self.llm, question=question.text, goal=item.goal, answer=answer.text)
            except LLMInvalidOutput:
                log.warning("Answer analysis invalid twice for question %s; moving on", question.id)
                result = AnswerAnalysis()
                answer.analysis_json = {**result.model_dump(), "fallback": True}
                db.commit()
                return result
        answer.analysis_json = result.model_dump()
        db.commit()
        return result

    # ---------- asking ----------

    def _ask_item(self, db: Session, ctx: _Context, item: PlanItem, ack: str) -> Iterator[dict]:
        if item.category not in ANALYSED:  # intro and closing use fixed wording: no model call needed
            yield from self._ask_text(db, ctx, item, item.fallback_question, ack=ack)
            return
        questions = self._questions(ctx.session)
        asked = [q.text for q in questions]
        turns = [(q.text, q.answer.text if q.answer else None) for q in questions]
        yield {"type": "thinking"}
        raw = ""
        for piece in interviewer.generate_question(
            llm=self.llm, session_id=ctx.session.id, role=ctx.session.target_role, difficulty=ctx.session.difficulty,
            item=item, profile=ctx.profile, turns=turns, asked=asked,
            # Resume text is already summarised in the facts; search only where it adds something.
            use_retrieval=item.category is Category.project or any(d.kind == "other" for d in ctx.session.documents),
        ):
            raw += piece
            yield {"type": "token", "text": piece}
        text, used_fallback = interviewer.finalize_question(raw, item, asked)
        if used_fallback:
            log.info("Using planned fallback question for topic %r", item.topic)
        yield from self._ask_text(db, ctx, item, text, ack=ack)

    def _ask_text(self, db: Session, ctx: _Context, item: PlanItem, text: str, ack: str,
                  parent: Question | None = None) -> Iterator[dict]:
        questions = self._questions(ctx.session)
        row = Question(
            session_id=ctx.session.id, order_no=len(questions) + 1, plan_index=item.index, topic=item.topic,
            text=text, ack=ack, is_follow_up=parent is not None, parent_question_id=parent.id if parent else None,
        )
        ctx.session.questions.append(row)
        db.commit()
        yield self._question_event(ctx, row)

    def _question_event(self, ctx: _Context, q: Question, replay: bool = False) -> dict:
        asked = min(len(self._questions(ctx.session)), ctx.session.question_count)
        return {
            "type": "question", "question_id": q.id, "order_no": q.order_no, "topic": q.topic, "text": q.text,
            "ack": q.ack, "is_follow_up": q.is_follow_up, "replay": replay,
            # Field names are retained for clients deployed before progress included follow-ups.
            "progress": {"main_asked": asked, "main_total": ctx.session.question_count},
        }
