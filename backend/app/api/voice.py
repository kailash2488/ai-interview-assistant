import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.core.config import settings
from app.models import InterviewSession, User
from app.services.voice import engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"], dependencies=[Depends(current_user)])

_SUFFIX = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav"}


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


class TranscriptOut(BaseModel):
    text: str
    seconds: int
    words: int
    wpm: int | None
    pauses: int
    longest_pause: float
    fillers: int


MAX_VOCAB_CHARS = 350


def vocabulary_for(db: Session, user: User, session_id: str | None) -> str | None:
    """Technical terms from the user's own analysis (skills, job requirements, plan topics), so 'asyncio' and
    'PostgreSQL' are not heard as ordinary words. Only the caller's own interview is ever used."""
    if not session_id:
        return None
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != user.id or session.analysis is None or session.analysis.status != "ready":
        return None
    terms: list[str] = []
    profile, reqs = session.analysis.profile_json or {}, session.analysis.requirements_json or {}
    terms += [s.get("name", "") for s in profile.get("skills", [])]
    terms += [t for p in profile.get("projects", []) for t in p.get("tech_stack", [])]
    terms += reqs.get("must_have_skills", []) + reqs.get("nice_to_have_skills", [])
    out, size = [], 0
    for term in dict.fromkeys(t.strip() for t in terms if t and t.strip()):
        if size + len(term) + 2 > MAX_VOCAB_CHARS:
            break
        out.append(term)
        size += len(term) + 2
    return ", ".join(out) or None


@router.get("/status")
def voice_status():
    """What this server can do locally; the browser falls back to its own speech features for anything missing."""
    return engine.status()


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(file: UploadFile = File(...), session_id: str | None = Form(None), db: Session = Depends(get_db), user: User = Depends(current_user)):
    limit = settings.voice_max_audio_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Recording exceeds {settings.voice_max_audio_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The recording is empty")
    base = (file.content_type or "").split(";")[0].strip().lower()
    if not base.startswith("audio/") and base != "video/webm":  # browsers label audio-only webm as either
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Send an audio recording")
    try:
        text, metrics = await run_in_threadpool(engine.transcribe, data, _SUFFIX.get(base, ".webm"), vocabulary_for(db, user, session_id))
    except engine.VoiceUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except engine.AudioTooLong as exc:
        raise HTTPException(413, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No speech was heard. Check your microphone and try again.")
    return TranscriptOut(text=text, **{k: metrics[k] for k in ("seconds", "words", "wpm", "pauses", "longest_pause", "fillers")})


@router.post("/speak")
async def speak(payload: SpeakIn):
    try:
        audio = await run_in_threadpool(engine.speak, payload.text.strip())
    except engine.VoiceUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})
