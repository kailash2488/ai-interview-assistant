"""Communication notes computed in plain code from the answers (no model involved)."""
import re
from collections import Counter

from app.core.config import settings

from app.schemas.report import CommunicationNotes, VoiceNotes

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


IDEAL_WPM = (120, 160)
PAUSE_HEAVY = 2.0  # average long pauses per spoken answer


def voice_notes(voices: list[dict]) -> tuple[VoiceNotes | None, list[str]]:
    """Speaking pace and pauses from the measurements taken on recordings. Fillers are not reported: speech
    recognition tends to leave out 'um' and 'uh', so counting them from a transcript would be misleading."""
    voices = [v for v in voices if v]
    if not voices:
        return None, []
    wpms = [v["wpm"] for v in voices if v.get("wpm")]
    avg_wpm = round(sum(wpms) / len(wpms)) if wpms else None
    pauses = [int(v.get("pauses", 0)) for v in voices]
    notes = VoiceNotes(answers=len(voices), avg_wpm=avg_wpm, total_pauses=sum(pauses), avg_pauses=round(sum(pauses) / len(pauses), 1),
                       longest_pause=max((float(v.get("longest_pause", 0)) for v in voices), default=0.0))
    obs: list[str] = []
    if avg_wpm is not None:
        low, high = IDEAL_WPM
        if avg_wpm < low - 10:
            obs.append(f"You spoke slowly: about {avg_wpm} words per minute. Interviewers find {low} to {high} easiest to follow.")
        elif avg_wpm > high + 15:
            obs.append(f"You spoke fast: about {avg_wpm} words per minute. Slow down to {low} to {high} and pause between points.")
        else:
            obs.append(f"Your speaking pace was good: about {avg_wpm} words per minute.")
    if notes.avg_pauses >= PAUSE_HEAVY:
        obs.append(f"You paused for more than {settings.voice_pause_seconds:g} seconds about {notes.avg_pauses:g} times per answer (longest {notes.longest_pause:g}s). Outline your answer first so you do not stall mid-sentence.")
    return notes, obs


def analyse(answers: list[tuple[str, int | None]], voices: list[dict] | None = None) -> CommunicationNotes:
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
    voice, voice_obs = voice_notes(voices or [])
    if not obs:
        obs.append("Your answer length and wording were in a good range.")
    obs.extend(voice_obs)
    return CommunicationNotes(
        answers=len(counts), avg_words=avg, shortest_words=min(counts), longest_words=max(counts), one_line_answers=one_line,
        rambling_answers=rambling, filler_words=fillers, vague_phrases=vague,
        avg_seconds=round(sum(durations) / len(durations)) if durations else None, observations=obs, voice=voice,
    )
