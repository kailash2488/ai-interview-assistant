import re

_WORD = re.compile(r"[a-z0-9+#.]+")
_STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "you", "your", "me", "is", "are", "was", "how", "what", "do", "did", "with", "about", "that", "this", "it", "can", "tell", "us", "have", "has", "had", "did", "does", "would", "could", "should", "please"}


def _stem(word: str) -> str:
    """Crude suffix stripping so 'use', 'used' and 'using' compare equal."""
    for suffix in ("ing", "ed", "es", "s", "e"):
        if len(word) > (2 if suffix == "e" else 3) and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def words(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOP}


def similarity(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def is_duplicate(candidate: str, asked: list[str], threshold: float = 0.7) -> bool:
    return any(similarity(candidate, q) >= threshold for q in asked)


def clean_question(raw: str) -> str:
    """Models sometimes add preambles, quotes or several questions. Keep one clean question."""
    text = raw.strip().strip('"').strip()
    text = re.sub(r"^(question\s*\d*\s*[:.\-]\s*|\d+[.)]\s*)", "", text, flags=re.IGNORECASE)
    first_para = text.split("\n\n")[0].replace("\n", " ").strip()
    questions = re.findall(r"[^?]*\?", first_para)
    if len(questions) > 1:
        # keep the first question, plus its leading context sentence if the model split them
        first_para = questions[0].strip()
    return first_para.strip()


def word_count(text: str) -> int:
    return len(text.split())
