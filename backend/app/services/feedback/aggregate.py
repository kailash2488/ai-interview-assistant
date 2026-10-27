"""All numbers in the report are computed here, deterministically. The model only writes prose."""
from collections import defaultdict

from app.schemas.report import DIMENSIONS, AreaScore, Insight, PlanStep, QuestionReport

VERDICTS = [  # (minimum overall score, verdict)
    (80, "Strong - ready for this role"),
    (65, "Good - close to ready"),
    (50, "Borderline - needs focused practice"),
    (0, "Not ready yet - build the fundamentals first"),
]
MIN_ANSWERS_FOR_VERDICT = 3
STRENGTH_MIN_SCORE = 60  # an area or dimension must score at least this to be called a strength


def overall_score(questions: list[QuestionReport]) -> int:
    return round(sum(q.score_percent for q in questions) / len(questions)) if questions else 0


def verdict(overall: int, evaluated: int, planned_scored: int) -> tuple[str, str]:
    label = next(text for floor, text in VERDICTS if overall >= floor)
    basis = f"Based on {evaluated} evaluated answers"
    if evaluated < MIN_ANSWERS_FOR_VERDICT or evaluated < planned_scored / 2:
        basis += f"; the interview ended early, so treat this as a partial result"
    return label, basis + "."


def dimension_scores(questions: list[QuestionReport]) -> dict[str, int]:
    out = {}
    for dim in DIMENSIONS:
        scores = [q.dimensions[dim].score for q in questions]
        out[dim] = round((sum(scores) / len(scores) - 1) / 4 * 100) if scores else 0
    return out


def area_scores(questions: list[QuestionReport]) -> list[AreaScore]:
    """One area per planned topic (a skill, a project, a behavioural theme). Follow-ups count toward their topic."""
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for q in questions:
        groups[(q.topic, q.category)].append(q.score_percent)
    names = [name for name, _ in groups]
    label = {"core": "core skill", "gap": "gap area", "project": "project", "behavioural": "behavioural"}
    return [
        AreaScore(
            # The same skill can be both a core topic and a gap topic: keep the two rows apart.
            name=f"{name} ({label.get(cat, cat)})" if names.count(name) > 1 else name,
            category=cat, score_percent=round(sum(v) / len(v)), answers=len(v),
        )
        for (name, cat), v in groups.items()
    ]


def fallback_narrative(areas: list[AreaScore], dims: dict[str, int], questions: list[QuestionReport]) -> tuple[list[Insight], list[Insight], list[PlanStep]]:
    """Used when the model cannot write the summary: still specific, built from the computed data."""
    ranked = sorted(areas, key=lambda a: a.score_percent, reverse=True)
    strengths = [Insight(title=a.name, detail=f"You scored {a.score_percent}/100 on this topic.")
                 for a in ranked[:3] if a.score_percent >= STRENGTH_MIN_SCORE]
    weakest = list(reversed(ranked))[:3]
    missing = {q.topic: q.missing_points for q in questions if q.missing_points}
    improvements = [
        Insight(title=a.name, detail=f"You scored {a.score_percent}/100. " + (f"Work on: {', '.join(missing[a.name][:3])}." if a.name in missing else "Add depth and a concrete example."))
        for a in weakest
    ]
    plan = [
        PlanStep(timeframe="Week 1", focus=weakest[0].name if weakest else "Fundamentals",
                 actions=[f"Review {a.name} and write a two-minute spoken answer with one real example." for a in weakest[:3]]),
        PlanStep(timeframe="Week 2", focus="Mock practice",
                 actions=["Redo this interview and compare scores.", "Practise answers in the order: point, example, result.", "Record yourself and cut filler words."]),
    ]
    return strengths, improvements, plan


def strength_candidates(areas: list[AreaScore], dims: dict[str, int]) -> list[str]:
    """The only things the write-up may call strengths: areas and rubric dimensions that really scored well."""
    good_areas = [f"{a.name}: area score {a.score_percent}" for a in sorted(areas, key=lambda a: -a.score_percent) if a.score_percent >= STRENGTH_MIN_SCORE]
    good_dims = [f"{k}: dimension score {v}" for k, v in sorted(dims.items(), key=lambda kv: -kv[1]) if v >= STRENGTH_MIN_SCORE]
    return good_areas[:3] + good_dims[:2]
