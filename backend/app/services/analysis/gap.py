"""Gap analysis in plain code over the profile and JD objects (deterministic and testable)."""
import re

from app.schemas.analysis import CandidateProfile, GapAnalysis, JDRequirements, ProbeClaim, SkillLevel

ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python", "k8s": "kubernetes",
    "postgres": "postgresql", "psql": "postgresql", "mongo": "mongodb", "node": "node.js",
    "nodejs": "node.js", "reactjs": "react", "react.js": "react", "vuejs": "vue", "vue.js": "vue",
    "golang": "go", "gcp": "google cloud", "tf": "terraform", "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn", "huggingface": "hugging face", "ml": "machine learning",
    "dl": "deep learning", "ci/cd": "cicd", "ci cd": "cicd", "amazon web services": "aws",
}
_NUMBER_RE = re.compile(r"\d")


def normalize(skill: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", skill.lower())  # drop "(5 years)" style asides
    s = re.sub(r"[^a-z0-9+#./ -]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .-/")
    return ALIASES.get(s, s)


def _in_text(skill: str, haystack: str) -> bool:
    pattern = rf"(?<![a-z0-9+#]){re.escape(skill)}(?![a-z0-9+#])"
    return re.search(pattern, haystack) is not None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalize(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def has_skill(required: str, candidate_skills: set[str], resume_text: str) -> bool:
    """Match against extracted skills first, then fall back to a whole-word search of the resume."""
    key = normalize(required)
    if not key:
        return False
    if key in candidate_skills:
        return True
    return _in_text(key, resume_text.lower()) or _in_text(required.lower().strip(), resume_text.lower())


def analyse_gap(profile: CandidateProfile, jd: JDRequirements, resume_text: str = "") -> GapAnalysis:
    candidate = {normalize(s.name) for s in profile.skills}
    candidate |= {normalize(t) for p in profile.projects for t in p.tech_stack}
    candidate.discard("")

    must = _dedupe(jd.must_have_skills)
    nice = _dedupe(jd.nice_to_have_skills)
    matched = [s for s in must if has_skill(s, candidate, resume_text)]
    gaps = [s for s in must if s not in matched]
    nice_hit = [s for s in nice if has_skill(s, candidate, resume_text)]
    nice_miss = [s for s in nice if s not in nice_hit]

    claims: list[ProbeClaim] = []
    for skill in profile.skills:
        if skill.level in (SkillLevel.advanced, SkillLevel.intermediate) and not skill.evidence.strip():
            claims.append(ProbeClaim(text=skill.name, reason="Claimed without any project or job evidence"))
    for project in profile.projects:
        outcome = project.claimed_outcome.strip()
        if outcome and _NUMBER_RE.search(outcome):
            claims.append(ProbeClaim(text=f"{project.title}: {outcome}", reason="Specific result claimed; check ownership and how it was measured"))
        elif project.title and not project.tech_stack:
            claims.append(ProbeClaim(text=project.title, reason="Project listed without technologies or detail"))

    # Strengths to warm up with: matched skills that the resume backs with evidence.
    evidence = {normalize(s.name): s.evidence.strip() for s in profile.skills}
    strengths = [s for s in matched if evidence.get(normalize(s))] or matched[:3]

    return GapAnalysis(
        matched_skills=matched,
        gaps=gaps,
        nice_to_have_matched=nice_hit,
        nice_to_have_missing=nice_miss,
        claims_to_probe=claims[:8],
        strengths=strengths[:5],
        match_percent=round(100 * len(matched) / len(must)) if must else None,
    )
