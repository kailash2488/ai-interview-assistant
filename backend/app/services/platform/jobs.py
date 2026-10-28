"""Durable and idempotent background-job records; execution workers come in later phases."""
import re
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BackgroundJob

_TASK = re.compile(r"^[a-z][a-z0-9_.-]{0,59}$")
_RESOURCE_ID = re.compile(r"^[a-f0-9]{32}$")
_SECRET_PARTS = ("api_key", "password", "secret", "token", "credential", "document_text", "resume_text")


def _safe_payload(payload: dict | None) -> dict:
    value = payload or {}
    def contains_secret_key(item) -> bool:
        if isinstance(item, dict):
            return any(
                any(part in str(key).lower() for part in _SECRET_PARTS) or contains_secret_key(child)
                for key, child in item.items()
            )
        if isinstance(item, list):
            return any(contains_secret_key(child) for child in item)
        return False

    if contains_secret_key(value):
        raise ValueError("Background-job payload contains a forbidden sensitive field")
    try:
        encoded = json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Background-job payload must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 8_000:
        raise ValueError("Background-job payload is too large")
    return value


def enqueue(
    db: Session,
    *,
    user_id: str,
    task_type: str,
    idempotency_key: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict | None = None,
) -> tuple[BackgroundJob, bool]:
    if not _TASK.fullmatch(task_type) or not 8 <= len(idempotency_key) <= 80:
        raise ValueError("Invalid background-job identity")
    if resource_type is not None and not _TASK.fullmatch(resource_type):
        raise ValueError("Invalid background-job resource type")
    if resource_id is not None and not _RESOURCE_ID.fullmatch(resource_id):
        raise ValueError("Invalid background-job resource ID")
    safe_payload = _safe_payload(payload)
    existing = db.scalar(select(BackgroundJob).where(
        BackgroundJob.user_id == user_id,
        BackgroundJob.idempotency_key == idempotency_key,
    ))
    if existing is not None:
        return existing, False
    row = BackgroundJob(
        user_id=user_id,
        task_type=task_type,
        idempotency_key=idempotency_key,
        resource_type=resource_type,
        resource_id=resource_id,
        payload_json=safe_payload,
    )
    db.add(row)
    db.flush()
    return row, True


def mark_started(row: BackgroundJob) -> None:
    if row.state not in {"queued", "retry"}:
        raise ValueError("Only queued jobs can start")
    row.state = "running"
    row.attempt_count += 1
    row.started_at = datetime.now(timezone.utc)
    row.finished_at = None
    row.error_code = None


def mark_finished(row: BackgroundJob, *, error_code: str | None = None, retry: bool = False) -> None:
    if row.state != "running":
        raise ValueError("Only running jobs can finish")
    if error_code is not None and not _TASK.fullmatch(error_code):
        raise ValueError("Invalid safe error code")
    if retry and error_code is None:
        raise ValueError("A retry requires a safe error code")
    row.state = "retry" if retry else ("failed" if error_code else "completed")
    row.error_code = error_code
    row.finished_at = datetime.now(timezone.utc)
