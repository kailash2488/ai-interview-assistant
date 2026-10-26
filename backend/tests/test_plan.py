import pytest

from app.schemas.analysis import CandidateProfile, GapAnalysis, JDRequirements, Project
from app.schemas.interview import Category
from app.services.interview.plan import build_plan
from tests.fakes import fake_profile, fake_requirements
from app.services.analysis.gap import analyse_gap


def make(n=10, kind="mixed", difficulty="medium", profile=None, reqs=None, gap=None):
    profile = profile or fake_profile()
    reqs = reqs or fake_requirements()
    gap = gap or analyse_gap(profile, reqs)
    return build_plan(question_count=n, interview_type=kind, difficulty=difficulty, role="Python Developer",
                      profile=profile, requirements=reqs, gap=gap)


def cats(plan):
    return [i.category for i in plan.items]


def test_structure_intro_first_closing_last_and_count():
    for n in (3, 5, 8, 10, 12, 20):
        plan = make(n)
        assert len(plan.items) == n
        assert cats(plan)[0] is Category.intro and cats(plan)[-1] is Category.closing
        assert [i.index for i in plan.items] == list(range(n))


def test_mixed_ten_follows_the_documented_split():
    counts = {c: cats(make(10)).count(c) for c in Category}
    assert counts[Category.intro] == counts[Category.closing] == 1
    assert counts[Category.core] >= 2 and counts[Category.project] >= 1 and counts[Category.gap] >= 1
    assert counts[Category.core] >= counts[Category.project]


def test_technical_has_no_behavioural_and_behavioural_type_is_mostly_behavioural():
    assert Category.behavioural not in cats(make(10, "technical"))
    b = cats(make(12, "behavioural"))
    assert b.count(Category.behavioural) > b.count(Category.core)


def test_no_gaps_gives_slots_to_core():
    profile = fake_profile()
    reqs = JDRequirements(must_have_skills=["Python", "FastAPI"], nice_to_have_skills=["Qdrant"])
    plan = make(10, profile=profile, reqs=reqs)
    assert Category.gap not in cats(plan)
    assert len(plan.items) == 10


def test_core_topics_unique_when_enough_skills_and_matched_first():
    plan = make(10)
    core = [i.topic for i in plan.items if i.category is Category.core]
    assert len(core) == len(set(core))
    assert core[0] == "Python"  # matched and evidenced = warm-up strength


def test_gap_items_are_easier_and_have_fewer_followups():
    plan = make(10, difficulty="hard")
    gap_items = [i for i in plan.items if i.category is Category.gap]
    assert gap_items and all(i.difficulty == "medium" and i.max_followups == 1 for i in gap_items)
    assert all(i.max_followups == 0 for i in plan.items if i.category in (Category.intro, Category.closing))


def test_every_item_has_fallback_question_and_followup_budget():
    plan = make(10)
    assert all(i.fallback_question.strip().endswith(("?", ".")) and i.goal for i in plan.items)
    assert plan.followup_budget == 3


def test_sparse_profile_still_builds():
    plan = make(8, profile=CandidateProfile(), reqs=JDRequirements(), gap=GapAnalysis())
    assert len(plan.items) == 8
    assert any(i.category is Category.core for i in plan.items)


def test_project_topics_come_from_resume():
    profile = fake_profile()
    profile.projects.append(Project(title="Data Pipeline", tech_stack=["Airflow"]))
    plan = make(12, profile=profile)
    assert {"Interview Bot", "Data Pipeline"} <= {i.topic for i in plan.items if i.category is Category.project}
