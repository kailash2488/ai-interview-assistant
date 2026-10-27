"""Smoke-test the configured LLM provider (Ollama or Gemini) with one tiny structured call.

Usage (from backend/):  python scripts/check_llm.py
Prints the provider, model, latency and the parsed result. Never prints the API key.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.llm import runtime  # noqa: E402
from app.services.llm.client import LLMError, get_llm  # noqa: E402


class Check(BaseModel):
    skills: list[str]
    seniority: str


def main() -> int:
    runtime.apply()  # honour the choice saved on the Settings page
    print(f"provider={settings.llm_provider}")
    try:
        llm = get_llm()
        print(f"model={getattr(llm, 'model_name', '?')}")
        t = time.time()
        out = llm.chat_json(
            system="Extract data. Reply with JSON only.",
            user="Job: Senior engineer needing Python and Docker.",
            schema=Check, temperature=0.0, max_tokens=100,
        )
        print(f"structured call OK in {time.time() - t:.1f}s: {out.model_dump()}")
        t = time.time()
        text = "".join(llm.stream_text(system="Reply in one short sentence.", user="Say hello to an interview candidate.", max_tokens=40))
        print(f"streaming call OK in {time.time() - t:.1f}s: {text.strip()!r}")
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
