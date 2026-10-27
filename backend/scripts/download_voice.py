"""Download the local speech models (about 200 MB, once): Whisper for speech-to-text and a Piper voice for text-to-speech.

Usage (from backend/):  python scripts/download_voice.py
Needs the voice extras:  pip install ".[voice]"
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402


def main() -> int:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print('Install the voice extras first: pip install ".[voice]"')
        return 1
    print(f"Downloading the speech-to-text model {settings.whisper_model} ...")
    WhisperModel(settings.whisper_model, device="cpu", compute_type="int8", download_root=str(settings.voice_dir / "whisper"))
    piper_dir = settings.voice_dir / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading the voice {settings.piper_voice} ...")
    done = subprocess.run([sys.executable, "-m", "piper.download_voices", settings.piper_voice], cwd=piper_dir)
    print("Done." if done.returncode == 0 else "The voice download failed. Check your internet connection and try again.")
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
