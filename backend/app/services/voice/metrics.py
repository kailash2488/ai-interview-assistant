"""Speaking metrics measured from a recording's transcript timing (no model involved)."""
import re
from dataclasses import dataclass

from app.core.config import settings

_FILLERS = ["um", "uh", "er", "erm", "like", "you know", "basically", "actually", "kind of", "sort of", "i guess", "literally"]
MIN_SPEECH_SECONDS = 2.0  # below this a words-per-minute figure is noise


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def count_fillers(text: str) -> int:
    lowered = text.lower()
    return sum(len(re.findall(rf"(?<![a-z]){re.escape(f)}(?![a-z])", lowered)) for f in _FILLERS)


def voice_metrics(text: str, segments: list[Segment], duration: float) -> dict:
    """seconds: length of the recording. wpm: words per minute of actual speech (leading and trailing silence
    excluded). pauses: silences longer than the configured threshold between phrases."""
    words = len(text.split())
    if segments:
        spoken = max(segments[-1].end - segments[0].start, 0.0)
        gaps = [b.start - a.end for a, b in zip(segments, segments[1:])]
    else:
        spoken, gaps = 0.0, []
    long_gaps = [g for g in gaps if g >= settings.voice_pause_seconds]
    wpm = round(words / (spoken / 60)) if spoken >= MIN_SPEECH_SECONDS and words else None
    return {
        "seconds": round(duration),
        "words": words,
        "wpm": wpm,
        "pauses": len(long_gaps),
        "longest_pause": round(max(long_gaps), 1) if long_gaps else 0.0,
        "fillers": count_fillers(text),
    }
