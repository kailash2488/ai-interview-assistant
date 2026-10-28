"""Content-free audit events. Never pass document text, prompts, keys, email bodies or notes."""
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_RESOURCE_ID = re.compile(r"^[a-f0-9]{32}$")
_SAFE_METADATA = frozenset({"count", "format", "source", "stage", "status", "version"})


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, str | int | float | bool | None]:
    result: dict[str, str | int | float | bool | None] = {}
    for key, value in (metadata or {}).items():
        if key not in _SAFE_METADATA or not isinstance(value, (str, int, float, bool, type(None), date, datetime)):
            continue
        rendered = value.isoformat() if isinstance(value, (date, datetime)) else value
        result[key] = rendered[:120] if isinstance(rendered, str) else rendered
    return result


def record_event(
    db: Session,
    *,
    user_id: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    if not _NAME.fullmatch(action) or (resource_type is not None and not _NAME.fullmatch(resource_type)):
        raise ValueError("Invalid audit event name")
    if resource_id is not None and not _RESOURCE_ID.fullmatch(resource_id):
        raise ValueError("Invalid audit resource ID")
    if outcome not in {"success", "failure", "denied"}:
        raise ValueError("Invalid audit outcome")
    row = AuditEvent(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata_json=_safe_metadata(metadata),
    )
    db.add(row)
    return row
