"""Communication notes computed in plain code from the answers (no model involved)."""
import re
from collections import Counter

from app.schemas.report import CommunicationNotes

FILLERS = ["um", "uh", "like", "you know", "basically", "actually", "kind of", "sort of", "i guess", "literally"]
VAGUE = ["stuff", "things", "etc", "something like that", "and so on", "whatever", "a lot of"]
ONE_LINE_WORDS = 12
RAMBLING_WORDS = 250


def _count(phrases: list[str], text: str) -> dict[str, int]:
    found = {}
    for phrase in phrases:
        n = len(re.findall(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text))
        if n:
            found[phrase] = n
    return found


def analyse(answers: list[tuple[str, int | None]]) -> CommunicationNotes:
    if not answers:
        return CommunicationNotes(answers=0, avg_words=0, shortest_words=0, longest_words=0, one_line_answers=0,
                                  rambling_answers=0, filler_words={}, vague_phrases={}, avg_seconds=None, observations=[])
    counts = [len(text.split()) for text, _ in answers]
    lowered = " ".join(text.lower() for text, _ in answers)
    fillers, vague = _count(FILLERS, lowered), _count(VAGUE, lowered)
    durations = [d for _, d in answers if d]
    one_line = sum(1 for c in counts if c < ONE_LINE_WORDS)
    rambling = sum(1 for c in counts if c > RAMBLING_WORDS)
    avg = round(sum(counts) / len(counts))

    obs: list[str] = []
    if one_line:
        obs.append(f"{one_line} of {len(counts)} answers were one line (under {ONE_LINE_WORDS} words). Add an example or a reason to each.")
    if rambling:
        obs.append(f"{rambling} answers ran over {RAMBLING_WORDS} words. Lead with the point, then give one example.")
    if avg < 40:
        obs.append(f"Your answers averaged {avg} words, which is short for an interview. Aim for 60 to 150 words.")
    elif avg > 180:
        obs.append(f"Your answers averaged {avg} words. Tighten them to the key points.")
    filler_total = sum(fillers.values())
    if filler_total >= 3:
        top = ", ".join(f'"{k}" ({v})' for k, v in sorted(fillers.items(), key=lambda kv: -kv[1])[:3])
        obs.append(f"Filler words appeared {filler_total} times, mostly {top}.")
    if sum(vague.values()) >= 2:
        top = ", ".join(f'"{k}"' for k in vague)
        obs.append(f"Vague wording ({top}) hides detail. Name the specific tool, number or step instead.")
    if not obs:
        obs.append("Your answer length and wording were in a good range.")
    return CommunicationNotes(
        answers=len(counts), avg_words=avg, shortest_words=min(counts), longest_words=max(counts), one_line_answers=one_line,
        rambling_answers=rambling, filler_words=fillers, vague_phrases=vague,
        avg_seconds=round(sum(durations) / len(durations)) if durations else None, observations=obs,
    )
