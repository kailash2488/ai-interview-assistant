import io
import wave

import pytest

from app.api.interview import clean_voice
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Answer
from app.schemas.interview import AnswerAnalysis
from app.services.feedback import communication
from app.services.interview.engine import InterviewEngine
from app.services.voice import engine as voice
from app.services.voice.metrics import Segment, count_fillers, voice_metrics
from tests.fakes import FakeLLM
from tests.test_analysis_api import _ready_session
from tests.test_api import _create_session
from tests.test_engine import LONG, run
from tests.test_report_api import generate, use_llm  # noqa: F401


# ---------- measurements ----------

def test_wpm_excludes_leading_and_trailing_silence():
    segs = [Segment(3.0, 9.0, "a"), Segment(9.2, 33.0, "b")]
    m = voice_metrics("word " * 60, segs, duration=40.0)  # 60 words over 30 s of speech (3.0 to 33.0)
    assert m["wpm"] == 120 and m["seconds"] == 40 and m["words"] == 60


def test_pauses_are_silences_between_phrases_above_the_threshold():
    segs = [Segment(0, 5, "a"), Segment(5.5, 10, "b"), Segment(12.5, 18, "c"), Segment(18.2, 20, "d")]
    m = voice_metrics("x " * 40, segs, 20)
    assert m["pauses"] == 1 and m["longest_pause"] == 2.5  # only the 2.5 s gap is long enough (default threshold 1.5 s)


def test_very_short_or_empty_speech_has_no_pace():
    assert voice_metrics("hello", [Segment(0, 1.0, "hello")], 1.2)["wpm"] is None
    empty = voice_metrics("", [], 3)
    assert empty["wpm"] is None and empty["pauses"] == 0 and empty["words"] == 0


def test_filler_counting():
    assert count_fillers("Um, I like, you know, basically did it. Umbrella and likeable do not count.") == 4


def test_browser_supplied_measurements_are_sanitised():
    assert clean_voice({"seconds": 42, "wpm": 131.6, "pauses": 2, "longest_pause": 2.46, "words": 90, "fillers": 1}) == {
        "seconds": 42, "wpm": 131, "pauses": 2, "longest_pause": 2.5, "words": 90, "fillers": 1}
    assert clean_voice({"wpm": 9999, "pauses": -1, "seconds": "12", "words": True, "evil": "<script>", "longest_pause": 601}) is None
    assert clean_voice({"wpm": 120, "x": 1}) == {"wpm": 120}
    for junk in (None, "text", 5, [1], {}):
        assert clean_voice(junk) is None


# ---------- speaking notes in the report ----------

def v(wpm, pauses=0, longest=0.0):
    return {"wpm": wpm, "pauses": pauses, "longest_pause": longest}


def test_voice_notes_judge_pace_and_pauses():
    notes, obs = communication.voice_notes([v(95), v(100)])
    assert notes.avg_wpm == 98 and notes.answers == 2 and "spoke slowly" in obs[0]
    assert "spoke fast" in communication.voice_notes([v(190), v(200)])[1][0]
    assert "pace was good" in communication.voice_notes([v(140), v(150)])[1][0]
    notes, obs = communication.voice_notes([v(140, 3, 4.0), v(140, 2, 2.5)])
    assert notes.total_pauses == 5 and notes.avg_pauses == 2.5 and notes.longest_pause == 4.0
    assert any("paused for more than" in o for o in obs)


def test_voice_notes_are_absent_without_recordings():
    assert communication.voice_notes([]) == (None, [])
    assert communication.voice_notes([{}, {}]) == (None, [])
    assert communication.analyse([("A fine answer " * 10, 30)]).voice is None


def test_missing_pace_is_handled():
    notes, obs = communication.voice_notes([{"wpm": None, "pauses": 0, "longest_pause": 0}])
    assert notes.avg_wpm is None and obs == []


# ---------- API with a fake speech engine ----------

@pytest.fixture()
def fake_voice(monkeypatch):
    calls = {"transcribe": [], "speak": []}

    def transcribe(audio, suffix=".webm", vocabulary=None):
        calls["transcribe"].append((audio, suffix, vocabulary))
        return "I used asyncio for IO bound services", {"seconds": 6, "words": 7, "wpm": 140, "pauses": 1, "longest_pause": 1.8, "fillers": 0}

    def speak(text):
        calls["speak"].append(text)
        return b"RIFF....WAVEfake"

    monkeypatch.setattr(voice, "transcribe", transcribe)
    monkeypatch.setattr(voice, "speak", speak)
    return calls


def send(client, data=b"audio-bytes", ctype="audio/webm", **extra):
    return client.post("/voice/transcribe", files={"file": ("answer.webm", data, ctype)}, data=extra)


def test_voice_routes_require_sign_in(anon_client):
    assert anon_client.get("/voice/status").status_code == 401
    assert anon_client.post("/voice/transcribe", files={"file": ("a.webm", b"x", "audio/webm")}).status_code == 401
    assert anon_client.post("/voice/speak", json={"text": "hi"}).status_code == 401


def test_status_reports_what_is_installed(client, monkeypatch):
    s = client.get("/voice/status").json()
    assert set(s) == {"stt", "tts"} and {"available", "model", "loaded", "hint"} <= set(s["stt"]) and {"available", "voice", "hint"} <= set(s["tts"])
    monkeypatch.setattr(voice, "_lib", lambda name: False)
    s = client.get("/voice/status").json()
    assert s["stt"]["available"] is False and "voice extras" in s["stt"]["hint"] and s["tts"]["available"] is False


def test_transcribe_returns_text_and_measurements(client, fake_voice):
    r = send(client, b"abc", "audio/webm;codecs=opus")
    assert r.status_code == 200
    body = r.json()
    assert body["text"].startswith("I used asyncio") and body["wpm"] == 140 and body["pauses"] == 1 and body["seconds"] == 6
    assert fake_voice["transcribe"][0][:2] == (b"abc", ".webm")
    send(client, b"abc", "audio/wav")
    assert fake_voice["transcribe"][1][1] == ".wav"


def test_transcribe_rejects_bad_uploads(client, fake_voice, monkeypatch):
    assert send(client, b"").status_code == 400
    assert send(client, b"x", "text/plain").status_code == 415
    assert send(client, b"x", "video/webm").status_code == 200  # audio-only webm is sometimes labelled video/webm
    monkeypatch.setattr(settings, "voice_max_audio_mb", 0)
    assert send(client, b"x").status_code == 413


def test_transcribe_error_mapping(client, monkeypatch):
    def fail(exc):
        def _t(*a, **k):
            raise exc
        return _t

    monkeypatch.setattr(voice, "transcribe", fail(voice.VoiceUnavailable("Speech-to-text is not installed.")))
    r = send(client)
    assert r.status_code == 503 and "not installed" in r.json()["detail"]
    monkeypatch.setattr(voice, "transcribe", fail(voice.AudioTooLong("Recordings are limited to 5 minutes")))
    assert send(client).status_code == 413
    monkeypatch.setattr(voice, "transcribe", fail(ValueError("The recording could not be read.")))
    assert send(client).status_code == 422
    monkeypatch.setattr(voice, "transcribe", lambda *a, **k: ("", {"seconds": 3, "words": 0, "wpm": None, "pauses": 0, "longest_pause": 0.0, "fillers": 0}))
    r = send(client)
    assert r.status_code == 422 and "No speech" in r.json()["detail"]


def test_vocabulary_comes_only_from_the_callers_own_interview(client, other_client, fake_voice, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    send(client, session_id=sid)
    vocab = fake_voice["transcribe"][-1][2]
    assert vocab and "Python" in vocab and "FastAPI" in vocab and len(vocab) <= 350
    send(other_client, session_id=sid)  # someone else's interview: no vocabulary, no error, no leak
    assert fake_voice["transcribe"][-1][2] is None
    send(client, session_id="not-a-session")
    assert fake_voice["transcribe"][-1][2] is None
    send(client)
    assert fake_voice["transcribe"][-1][2] is None


def test_speak(client, fake_voice, monkeypatch):
    r = client.post("/voice/speak", json={"text": "  Tell me about yourself.  "})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == b"RIFF....WAVEfake"
    assert fake_voice["speak"] == ["Tell me about yourself."]
    assert client.post("/voice/speak", json={"text": ""}).status_code == 422
    assert client.post("/voice/speak", json={"text": "x" * 1501}).status_code == 422

    def unavailable(text):
        raise voice.VoiceUnavailable("The speech voice is not downloaded. Run: python scripts/download_voice.py")

    monkeypatch.setattr(voice, "speak", unavailable)
    r = client.post("/voice/speak", json={"text": "hello"})
    assert r.status_code == 503 and "download_voice" in r.json()["detail"]


# ---------- spoken answers through the interview and into the report ----------

def spoken_interview(client, monkeypatch):
    monkeypatch.setattr("app.services.analysis.service.get_llm", lambda *a, **k: FakeLLM())
    sid = _ready_session(client)
    client.post(f"/sessions/{sid}/analyze")
    client.post(f"/sessions/{sid}/plan")
    eng = InterviewEngine(sid, FakeLLM(analyses=[AnswerAnalysis(answer_quality="strong")] * 30))
    events = run(eng.start())
    while events and events[-1]["type"] != "complete":
        events = run(eng.answer(LONG, 40, {"seconds": 40, "wpm": 95, "pauses": 3, "longest_pause": 3.2, "words": 70}))
    return sid


def test_voice_measurements_are_saved_with_the_answer(client, monkeypatch):
    sid = spoken_interview(client, monkeypatch)
    with SessionLocal() as db:
        saved = [a.voice_json for a in db.query(Answer).all()]
    assert len(saved) == 10 and all(s == {"seconds": 40, "wpm": 95, "pauses": 3, "longest_pause": 3.2, "words": 70} for s in saved)
    assert client.get(f"/sessions/{sid}/interview").json()["status"] == "completed"
    assert "voice" not in str(client.get(f"/sessions/{sid}/interview").json())  # not exposed in the transcript


def test_report_has_speaking_notes_for_spoken_interviews_only(client, monkeypatch):
    sid = spoken_interview(client, monkeypatch)
    use_llm(monkeypatch, FakeLLM())
    comm = generate(client, sid)["report"]["communication"]
    assert comm["voice"]["answers"] == 8 and comm["voice"]["avg_wpm"] == 95 and comm["voice"]["total_pauses"] == 24
    assert any("spoke slowly" in o for o in comm["observations"]) and any("paused for more than" in o for o in comm["observations"])
    pdf = client.get(f"/sessions/{sid}/report/pdf")
    import pymupdf
    text = "".join(p.get_text() for p in pymupdf.open(stream=pdf.content, filetype="pdf"))
    assert "Spoken answers: 8" in text and "95 words per minute" in text


def test_typed_interviews_have_no_speaking_section(client, monkeypatch):
    from tests.test_phase5 import finished_report

    sid = finished_report(client, monkeypatch, 4)
    assert client.get(f"/sessions/{sid}/report").json()["report"]["communication"]["voice"] is None


# ---------- the real local models (skipped where they are not installed) ----------

models_present = (settings.voice_dir / "piper" / f"{settings.piper_voice}.onnx").exists() and (settings.voice_dir / "whisper").exists() and voice._lib("faster_whisper") and voice._lib("piper")
real = pytest.mark.skipif(not models_present, reason="needs `pip install .[voice]` and python scripts/download_voice.py")


@real
def test_real_round_trip_speak_then_transcribe():
    wav = voice.speak("The trade-off is that one blocking call stalls the event loop.")
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getnframes() / w.getframerate() > 2 and w.getnchannels() == 1
    text, m = voice.transcribe(wav, ".wav", "event loop, asyncio")
    assert "blocking call" in text.lower() and "event loop" in text.lower()
    assert m["words"] >= 9 and m["wpm"] and 80 <= m["wpm"] <= 260 and m["seconds"] >= 3


@real
def test_real_speech_is_cached_and_bad_audio_is_reported():
    first = voice.speak("Cache me please.")
    assert voice.speak("Cache me please.") is first
    with pytest.raises(ValueError, match="could not be read"):
        voice.transcribe(b"this is definitely not audio", ".webm")


@real
def test_real_long_recordings_are_refused(monkeypatch):
    wav = voice.speak("This sentence is long enough to be refused when the limit is one second.")
    monkeypatch.setattr(settings, "voice_max_seconds", 1)
    with pytest.raises(voice.AudioTooLong):
        voice.transcribe(wav, ".wav")


@real
def test_real_endpoint_end_to_end(client):
    wav = client.post("/voice/speak", json={"text": "I would add a composite index and check the query plan."}).content
    assert wav[:4] == b"RIFF"
    r = client.post("/voice/transcribe", files={"file": ("a.wav", wav, "audio/wav")})
    assert r.status_code == 200 and "composite index" in r.json()["text"].lower()
