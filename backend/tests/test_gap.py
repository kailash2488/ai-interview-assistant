from app.schemas.analysis import CandidateProfile, JDRequirements, Project, SkillItem
from app.services.analysis.gap import analyse_gap, normalize
from tests.fakes import fake_profile, fake_requirements


def test_normalize_aliases_and_noise():
    assert normalize("K8s") == "kubernetes"
    assert normalize("Postgres (3 yrs)") == "postgresql"
    assert normalize("  Node.JS ") == "node.js"
    assert normalize("C++") == "c++"


def test_gap_matches_aliases_and_finds_gaps():
    gap = analyse_gap(fake_profile(), fake_requirements())
    assert gap.matched_skills == ["Python", "K8s"]
    assert gap.gaps == ["PostgreSQL", "Docker"]
    assert gap.nice_to_have_matched == ["Qdrant"]  # via project tech stack
    assert gap.nice_to_have_missing == ["LangChain"]
    assert gap.match_percent == 50


def test_resume_text_fallback_rescues_missed_skill_but_not_substrings():
    profile = CandidateProfile(skills=[SkillItem(name="Python")])
    jd = JDRequirements(must_have_skills=["Docker", "Go", "Java"])
    gap = analyse_gap(profile, jd, "Deployed with Docker. Loves going places. Knows JavaScript.")
    assert gap.matched_skills == ["Docker"]
    assert gap.gaps == ["Go", "Java"]  # 'going' and 'JavaScript' must not match


def test_claims_to_probe_and_strengths():
    gap = analyse_gap(fake_profile(), fake_requirements())
    texts = [c.text for c in gap.claims_to_probe]
    assert "Kubernetes" in texts  # intermediate claim with no evidence
    assert any("40%" in t for t in texts)  # numeric outcome
    assert gap.strengths == ["Python"]  # matched AND evidenced


def test_empty_jd_has_no_percent():
    assert analyse_gap(fake_profile(), JDRequirements()).match_percent is None


def test_duplicate_jd_skills_collapsed():
    gap = analyse_gap(fake_profile(), JDRequirements(must_have_skills=["python", "Python", "PYTHON"]))
    assert gap.matched_skills == ["python"] and gap.match_percent == 100
