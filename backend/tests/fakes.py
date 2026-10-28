import hashlib

from app.schemas.interview import AnswerAnalysis, MCQDraft
from app.schemas.report import AnswerEvaluation, DimScore, Insight, PlanStep, ReportNarrative
from app.schemas.analysis import CandidateProfile, Employer, JDRequirements, Project, SkillItem


def fake_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Asha Verma",
        total_experience_years=5,
        current_role="Senior Software Engineer",
        skills=[
            SkillItem(name="Python", level="advanced", evidence="FastAPI services at Acme"),
            SkillItem(name="FastAPI", level="advanced", evidence="Acme microservices"),
            SkillItem(name="Kubernetes", level="intermediate", evidence=""),
        ],
        employers=[Employer(company="Acme Corp", role="Senior Software Engineer", duration="2021-Present")],
        projects=[Project(title="Interview Bot", tech_stack=["Python", "Qdrant"], claimed_outcome="Cut latency by 40%")],
    )


def fake_requirements() -> JDRequirements:
    return JDRequirements(
        role_title="Senior Python Developer", seniority="senior",
        must_have_skills=["Python", "PostgreSQL", "Docker", "K8s"],
        nice_to_have_skills=["LangChain", "Qdrant"],
    )


GOOD_QUOTE = "handling retries, monitoring and capacity planning"


def fake_evaluation(score: int = 4, quote: str = GOOD_QUOTE, **kw) -> AnswerEvaluation:
    dim = DimScore(score=score, quote=quote)
    return AnswerEvaluation(
        technical_accuracy=dim, depth=dim, relevance=dim, structure_clarity=dim, evidence=dim,
        answer_summary=kw.get("summary", "Ran the service in production."), missing_points=kw.get("missing", ["failure modes", "metrics"]),
        feedback=kw.get("feedback", "You gave a production example. Add the metrics you tracked."),
    )


def fake_narrative() -> ReportNarrative:
    return ReportNarrative(
        summary="You showed solid production experience with room to go deeper on trade-offs.",
        strengths=[Insight(title=f"Strength {i}", detail="Specific detail.") for i in range(3)],
        improvements=[Insight(title=f"Improve {i}", detail="Specific detail.") for i in range(3)],
        improvement_plan=[PlanStep(timeframe="Week 1", focus="Depth", actions=["a", "b", "c"]),
                          PlanStep(timeframe="Week 2", focus="Practice", actions=["d", "e", "f"])],
    )


class FakeLLM:
    def __init__(self, fail_with: Exception | None = None, embed_fail: bool = False,
                 questions: list | None = None, analyses: list | None = None):
        self.fail_with, self.embed_fail = fail_with, embed_fail
        self.questions = list(questions or [])  # strings to stream, or Exceptions to raise
        self.analyses = list(analyses or [])  # AnswerAnalysis, or Exceptions to raise
        self.evaluations: list = []  # AnswerEvaluation or Exception, consumed in order; default = a good verified evaluation
        self.narratives: list = []
        self.samples: list = []
        self.calls: list[tuple[str, str, str]] = []
        self.question_calls = 0
        self.embed_calls = 0

    def chat_json(self, *, system, user, schema, model=None, temperature=0.1, max_tokens=None):
        if self.fail_with:
            raise self.fail_with
        if schema is AnswerEvaluation:
            self.calls.append((schema.__name__, system, user))
            item = self.evaluations.pop(0) if self.evaluations else fake_evaluation()
            if isinstance(item, Exception):
                raise item
            return item
        if schema is ReportNarrative:
            self.calls.append((schema.__name__, system, user))
            item = self.narratives.pop(0) if self.narratives else fake_narrative()
            if isinstance(item, Exception):
                raise item
            return item
        if schema is AnswerAnalysis:
            self.calls.append((schema.__name__, system, user))
            item = self.analyses.pop(0) if self.analyses else AnswerAnalysis(answer_quality="strong")
            if isinstance(item, Exception):
                raise item
            return item
        if schema is MCQDraft:
            self.calls.append((schema.__name__, system, user))
            return MCQDraft(
                question="Which option best demonstrates the topic in practice?",
                options=["The correct practical approach", "An unrelated shortcut", "Ignoring the requirement", "A clearly unsafe approach"],
                correct_index=0,
                explanation="The first option directly applies the topic while the other choices miss the stated requirement.",
            )
        self.calls.append((schema.__name__, system, user))
        return fake_profile() if schema is CandidateProfile else fake_requirements()

    def stream_text(self, *, system, user, model=None, temperature=0.6, max_tokens=None):
        if "Write the stronger sample answer" in user:
            self.calls.append(("sample", system, user))
            item = self.samples.pop(0) if self.samples else "A stronger answer would name the metrics you tracked."
            if isinstance(item, Exception):
                raise item
            yield item
            return
        self.calls.append(("question", system, user))
        self.question_calls += 1
        item = self.questions.pop(0) if self.questions else f"Generated question number {self.question_calls} about topics?"
        if isinstance(item, Exception):
            raise item
        for word in item.split(" "):
            yield word + " "

    def embed(self, texts):
        self.embed_calls += 1
        if self.embed_fail:
            raise RuntimeError("embedding model missing")
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[:8]] for t in texts]
