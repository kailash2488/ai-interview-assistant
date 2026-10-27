"""Local speech-to-text (faster-whisper) and text-to-speech (Piper). Both are optional extras: when a library or model
is missing, `status()` says so and the app falls back to the browser's own speech features."""
import hashlib
import io
import logging
import tempfile
import threading
import wave
from collections import OrderedDict
from pathlib import Path

from app.core.config import settings
from app.services.voice.metrics import Segment, voice_metrics

log = logging.getLogger(__name__)


class VoiceUnavailable(Exception):
    """A voice feature is not installed or its model is missing. The message says what to do."""


class AudioTooLong(Exception):
    pass


_lock = threading.Lock()          # models are loaded once
_stt_gate = threading.Semaphore(1)  # one transcription at a time: they are CPU heavy
_tts_gate = threading.Semaphore(1)
_whisper = None
_piper = None
_speech_cache: "OrderedDict[str, bytes]" = OrderedDict()
CACHE_SIZE = 40


def _piper_files() -> tuple[Path, Path]:
    base = settings.voice_dir / "piper"
    return base / f"{settings.piper_voice}.onnx", base / f"{settings.piper_voice}.onnx.json"


def _lib(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def status() -> dict:
    model, _ = _piper_files()
    stt_ok = _lib("faster_whisper")
    tts_lib = _lib("piper")
    return {
        "stt": {"available": stt_ok, "model": settings.whisper_model, "loaded": _whisper is not None,
                "hint": None if stt_ok else 'Install the voice extras: pip install ".[voice]"'},
        "tts": {"available": tts_lib and model.exists(), "voice": settings.piper_voice,
                "hint": None if tts_lib and model.exists() else ("Install the voice extras: pip install \".[voice]\"" if not tts_lib else "Download the voice: python scripts/download_voice.py")},
    }


def _load_whisper():
    global _whisper
    with _lock:
        if _whisper is None:
            if not _lib("faster_whisper"):
                raise VoiceUnavailable('Speech-to-text is not installed. Run: pip install ".[voice]"')
            from faster_whisper import WhisperModel

            log.info("Loading the %s speech model", settings.whisper_model)
            _whisper = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8", download_root=str(settings.voice_dir / "whisper"))
        return _whisper


def transcribe(audio: bytes, suffix: str = ".webm", vocabulary: str | None = None) -> tuple[str, dict]:
    """Returns (text, metrics). `vocabulary` (technical terms from the interview) biases recognition toward those words.
    Raises AudioTooLong for recordings over the configured limit."""
    model = _load_whisper()
    with _stt_gate, tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(audio)
        f.flush()
        try:
            segments_iter, info = model.transcribe(f.name, language="en", beam_size=1, vad_filter=True, condition_on_previous_text=False,
                                                   initial_prompt=(f"A technical job interview. Terms used: {vocabulary}." if vocabulary else None))
        except Exception as exc:  # undecodable or empty audio
            raise ValueError("The recording could not be read. Try recording again.") from exc
        if info.duration > settings.voice_max_seconds:
            raise AudioTooLong(f"Recordings are limited to {settings.voice_max_seconds // 60} minutes")
        segments = [Segment(s.start, s.end, s.text.strip()) for s in segments_iter]
    text = " ".join(s.text for s in segments if s.text).strip()
    return text, voice_metrics(text, segments, info.duration)


def _load_piper():
    global _piper
    with _lock:
        if _piper is None:
            model, config = _piper_files()
            if not _lib("piper"):
                raise VoiceUnavailable('Text-to-speech is not installed. Run: pip install ".[voice]"')
            if not model.exists():
                raise VoiceUnavailable("The speech voice is not downloaded. Run: python scripts/download_voice.py")
            from piper import PiperVoice

            _piper = PiperVoice.load(model, config_path=config)
        return _piper


def speak(text: str) -> bytes:
    """WAV audio for `text`. Repeated sentences are served from a small in-memory cache."""
    key = hashlib.sha256(f"{settings.piper_voice}|{text}".encode()).hexdigest()
    if key in _speech_cache:
        _speech_cache.move_to_end(key)
        return _speech_cache[key]
    voice = _load_piper()
    with _tts_gate:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            voice.synthesize_wav(text, wav)
    audio = buffer.getvalue()
    _speech_cache[key] = audio
    while len(_speech_cache) > CACHE_SIZE:
        _speech_cache.popitem(last=False)
    return audio
