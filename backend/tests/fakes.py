import hashlib

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


class FakeLLM:
    def __init__(self, fail_with: Exception | None = None, embed_fail: bool = False):
        self.fail_with, self.embed_fail = fail_with, embed_fail
        self.calls: list[tuple[str, str, str]] = []

    def chat_json(self, *, system, user, schema, model=None, temperature=0.1):
        if self.fail_with:
            raise self.fail_with
        self.calls.append((schema.__name__, system, user))
        return fake_profile() if schema is CandidateProfile else fake_requirements()

    def embed(self, texts):
        if self.embed_fail:
            raise RuntimeError("embedding model missing")
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[:8]] for t in texts]
