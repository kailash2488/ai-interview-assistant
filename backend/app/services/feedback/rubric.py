"""Guards that keep small-model scoring honest. Models are generous judges, so the code adds hard rules:
evidence must exist in the answer, short answers cannot score high on depth, off-topic answers cannot be relevant."""
import re

from app.schemas.report import DIMENSION_WEIGHTS, DIMENSIONS, AnswerEvaluation, DimensionResult
from app.services.interview.text import word_count

SHORT_ANSWER_WORDS = 6     # below this the answer is not sent to the model at all
THIN_ANSWER_WORDS = 15     # below this, depth and evidence are capped
UNVERIFIED_CAP = 3         # a score above this needs a quote that really appears in the answer
THIN_CAP = 2
_TOKEN = re.compile(r"[a-z0-9+#.]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def quote_in_answer(quote: str, answer: str) -> bool:
    """Verbatim, or close to it (models sometimes drop a word). Needs at least 3 words to count as evidence."""
    q = _tokens(quote)
    if len(q) < 3:
        return False
    a = _tokens(answer)
    joined_a, joined_q = " ".join(a), " ".join(q)
    if joined_q in joined_a:
        return True
    present = sum(1 for t in q if t in set(a))
    return present / len(q) >= 0.85


def apply_guards(ev: AnswerEvaluation, answer: str, off_topic: bool = False) -> tuple[dict[str, DimensionResult], list[str]]:
    """Returns the final per-dimension results and human-readable notes about every rule that changed a score."""
    notes: list[str] = []
    words = word_count(answer)
    out: dict[str, DimensionResult] = {}
    for dim in DIMENSIONS:
        given = getattr(ev, dim)
        score, quote = given.score, given.quote.strip()
        verified = quote_in_answer(quote, answer)
        if not verified and score > UNVERIFIED_CAP:
            notes.append(f"{dim}: score {score} lowered to {UNVERIFIED_CAP} because its evidence quote is not in your answer")
            score = UNVERIFIED_CAP
        if words < THIN_ANSWER_WORDS and dim in ("depth", "evidence") and score > THIN_CAP:
            notes.append(f"{dim}: capped at {THIN_CAP} because the answer was very short")
            score = THIN_CAP
        if off_topic and dim == "relevance" and score > THIN_CAP:
            notes.append(f"relevance: capped at {THIN_CAP} because the answer was off topic")
            score = THIN_CAP
        out[dim] = DimensionResult(score=score, quote=quote if verified else "", verified=verified)
    return out, notes


def too_short_result() -> dict[str, DimensionResult]:
    return {d: DimensionResult(score=1, quote="", verified=False) for d in DIMENSIONS}


def score_percent(dims: dict[str, DimensionResult]) -> int:
    """Weighted mean of the 1-5 dimension scores, mapped to 0-100."""
    total = sum(DIMENSION_WEIGHTS[d] * dims[d].score for d in DIMENSIONS)
    return round((total / sum(DIMENSION_WEIGHTS.values()) - 1) / 4 * 100)
