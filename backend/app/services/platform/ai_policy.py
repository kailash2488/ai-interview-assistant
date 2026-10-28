"""Bounded AI task policies shared by future roadmap features."""
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class AITaskPolicy:
    max_input_chars: int
    max_output_tokens: int
    requests_per_minute: int


DEFAULT_POLICY = AITaskPolicy(max_input_chars=60_000, max_output_tokens=4_000, requests_per_minute=10)
_requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def enforce(user_id: str, task_type: str, input_chars: int, policy: AITaskPolicy = DEFAULT_POLICY) -> None:
    if input_chars < 0 or input_chars > policy.max_input_chars:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "This AI request contains too much text")
    now = time.monotonic()
    bucket = _requests[(user_id, task_type)]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    limit = min(policy.requests_per_minute, settings.ai_requests_per_minute)
    if len(bucket) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "AI request limit reached. Wait a minute and try again.")
    bucket.append(now)


def wrap_untrusted(text: str, label: str, max_chars: int) -> str:
    if not label.replace("_", "").isalnum() or not text.strip() or len(text) > max_chars or "\x00" in text:
        raise ValueError("Invalid untrusted document")
    return f"<{label}>\n{text}\n</{label}>"
