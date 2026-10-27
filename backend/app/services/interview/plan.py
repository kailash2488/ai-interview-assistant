"""Build the interview plan in plain code from the analysis. The plan is data: inspectable and testable.
The LLM only writes the words of each question later; it never decides the structure."""
import re

from app.schemas.analysis import CandidateProfile, GapAnalysis, JDRequirements
from app.schemas.interview import Category, InterviewPlan, PlanItem

# Share of the middle questions per category (PDF section 8.3: core 40%, projects 30%, gaps 15%, behavioural 15%)
WEIGHTS = {
    "mixed": {Category.core: 0.40, Category.project: 0.30, Category.gap: 0.15, Category.behavioural: 0.15},
    "technical": {Category.core: 0.45, Category.project: 0.30, Category.gap: 0.25, Category.behavioural: 0.0},
    "behavioural": {Category.core: 0.15, Category.project: 0.25, Category.gap: 0.0, Category.behavioural: 0.60},
}
MAX_FOLLOWUPS = {Category.intro: 0, Category.core: 2, Category.project: 2, Category.gap: 1, Category.behavioural: 1, Category.closing: 0}
LEVELS = ["easy", "medium", "hard"]

BEHAVIOURAL_TOPICS = [
    ("Teamwork and conflict", "Assess how the candidate handles disagreement or friction in a team.", "Tell me about a time you disagreed with a teammate. What happened and how did you resolve it?"),
    ("Ownership under pressure", "Assess ownership and prioritisation when a deadline was at risk.", "Describe a time you had to deliver under a tight deadline. What did you do and what was the outcome?"),
    ("Learning from failure", "Assess honesty about mistakes and what the candidate learned.", "Tell me about a mistake you made at work. What did you learn from it?"),
    ("Learning something new fast", "Assess how the candidate picks up unfamiliar technology.", "Tell me about a time you had to learn a new technology quickly. How did you approach it?"),
    ("Handling a disagreement with a decision", "Assess how the candidate pushes back constructively.", "Tell me about a time you disagreed with a technical decision. How did you handle it?"),
    ("Communication and mentoring", "Assess how the candidate explains and shares knowledge.", "Describe a time you explained something complex to a less experienced colleague. How did you go about it?"),
]


def _allocate(total: int, weights: dict[Category, float], available: dict[Category, int]) -> dict[Category, int]:
    """Largest-remainder allocation. Categories with no source material give their slots to 'core'."""
    usable = {c: w for c, w in weights.items() if w > 0 and (available.get(c, 0) > 0 or c is Category.core)}
    norm = sum(usable.values())
    raw = {c: total * w / norm for c, w in usable.items()}
    alloc = {c: int(v) for c, v in raw.items()}
    if total >= 4:  # every non-empty category gets at least one question
        for c in alloc:
            alloc[c] = max(1, alloc[c])
    while sum(alloc.values()) > total:
        biggest = max(alloc, key=lambda c: alloc[c])
        alloc[biggest] -= 1
    for c in sorted(usable, key=lambda c: raw[c] - int(raw[c]), reverse=True):
        if sum(alloc.values()) >= total:
            break
        alloc[c] += 1
    while sum(alloc.values()) < total:
        alloc[Category.core] += 1
    for c in list(alloc):  # cap by available material (core is the overflow bucket and is never capped)
        if c is not Category.core and alloc[c] > available.get(c, 0):
            alloc[Category.core] += alloc[c] - available[c]
            alloc[c] = available[c]
    return alloc


_AREA_SUFFIX = re.compile(r"\s*\((core skill|gap area|project|behavioural)\)$", re.IGNORECASE)


def clean_topic(name: str) -> str:
    """Report area names carry a suffix when a skill is both a core topic and a gap; compare without it."""
    return _AREA_SUFFIX.sub("", name).strip().lower()


def _step(difficulty: str, delta: int) -> str:
    return LEVELS[max(0, min(2, LEVELS.index(difficulty) + delta))]


def build_plan(
    *, question_count: int, interview_type: str, difficulty: str, role: str,
    profile: CandidateProfile, requirements: JDRequirements, gap: GapAnalysis,
    focus_topics: list[str] | None = None,
) -> InterviewPlan:
    """`focus_topics` (for example the weak spots of an earlier attempt) are asked first within their category, and
    their categories get a bigger share of the questions."""
    middle = max(1, question_count - 2)  # intro and closing are fixed

    core_skills = list(dict.fromkeys(
        [s for s in gap.strengths if s in requirements.must_have_skills]
        + gap.matched_skills + requirements.must_have_skills + requirements.nice_to_have_skills
    ))
    if not core_skills:
        core_skills = [s.name for s in profile.skills] or requirements.responsibilities or [role]
    project_topics = [(p.title, p) for p in profile.projects if p.title] or [
        (f"{e.role or 'Experience'} at {e.company}", None) for e in profile.employers if e.company
    ]
    gap_skills = list(gap.gaps)
    behavioural = BEHAVIOURAL_TOPICS

    available = {
        Category.core: len(core_skills), Category.project: len(project_topics),
        Category.gap: len(gap_skills), Category.behavioural: len(behavioural),
    }
    order = [clean_topic(t) for t in (focus_topics or [])]  # given weakest first
    focus = set(order)
    weights = dict(WEIGHTS[interview_type])
    if focus:
        def first(items, name):  # focus topics move to the front (weakest first); the rest keep their order
            rank = lambda x: order.index(clean_topic(name(x))) if clean_topic(name(x)) in focus else len(order)  # noqa: E731
            return sorted(items, key=rank)

        core_skills, project_topics = first(core_skills, str), first(project_topics, lambda t: t[0])
        gap_skills, behavioural = first(gap_skills, str), first(behavioural, lambda b: b[0])
        hits = {
            Category.core: any(clean_topic(s) in focus for s in core_skills), Category.project: any(clean_topic(t[0]) in focus for t in project_topics),
            Category.gap: any(clean_topic(s) in focus for s in gap_skills), Category.behavioural: any(clean_topic(b[0]) in focus for b in behavioural),
        }
        weights = {c: w * 1.6 if hits.get(c) else w for c, w in weights.items()}
    alloc = _allocate(middle, weights, available)

    items: list[PlanItem] = []

    def add(cat: Category, topic: str, goal: str, diff: str, fallback: str) -> None:
        items.append(PlanItem(index=len(items), category=cat, topic=topic, goal=goal, difficulty=diff,
                              max_followups=MAX_FOLLOWUPS[cat], fallback_question=fallback))

    add(Category.intro, "Introduction and motivation", "Warm up and learn why the candidate wants this role.", "easy",
        f"Please introduce yourself and tell me what draws you to the {role} role.")
    for i in range(alloc.get(Category.core, 0)):
        skill = core_skills[i % len(core_skills)]
        add(Category.core, skill, f"Assess practical depth in {skill}, including trade-offs and real experience.", difficulty,
            f"Can you walk me through how you have used {skill} in your work, and what trade-offs you considered?")
    for i in range(alloc.get(Category.project, 0)):
        title, _ = project_topics[i]
        add(Category.project, title, f"Understand the candidate's own role, design decisions and results in '{title}'.", difficulty,
            f"Tell me about {title}. What was your specific role and what were the key technical decisions?")
    for i in range(alloc.get(Category.gap, 0)):
        skill = gap_skills[i]
        add(Category.gap, skill, f"Gauge familiarity with {skill}, which the job needs but the resume does not show.", _step(difficulty, -1),
            f"{skill} is part of this role. How familiar are you with it, and how would you approach getting up to speed?")
    for i in range(alloc.get(Category.behavioural, 0)):
        topic, goal, question = behavioural[i]
        add(Category.behavioural, topic, goal, "medium", question)
    add(Category.closing, "Candidate's questions", "Give the candidate a chance to ask questions.", "easy",
        "That covers my questions. Do you have any questions for me about the role or the team?")

    return InterviewPlan(items=items, followup_budget=max(1, question_count // 3))
