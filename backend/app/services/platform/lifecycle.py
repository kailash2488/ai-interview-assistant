"""Central export/deletion registry for all Phase 8 data domains."""
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ApplicationEvent, Artifact, AuditEvent, BackgroundJob, Contact, JobOpportunity, Task


@dataclass(frozen=True)
class DataDomain:
    name: str
    model: type
    export_fields: tuple[str, ...]


DOMAINS = (
    DataDomain("job_opportunities", JobOpportunity, ("id", "role", "company", "location", "work_mode", "employment_type", "source_url", "salary_min", "salary_max", "currency", "description", "status", "priority", "tags_json", "archived", "created_at", "updated_at")),
    DataDomain("contacts", Contact, ("id", "job_id", "name", "role", "company", "email", "phone", "notes", "source_note", "created_at", "updated_at")),
    DataDomain("tasks", Task, ("id", "job_id", "title", "notes", "due_at", "completed_at", "reminder_state", "recurrence_json", "created_at", "updated_at")),
    DataDomain("artifacts", Artifact, ("id", "job_id", "kind", "title", "version", "schema_version", "content_json", "source_refs_json", "provider", "model", "created_at")),
)


def export_foundation_data(db: Session, user_id: str) -> dict[str, list[dict]]:
    exported: dict[str, list[dict]] = {}
    for domain in DOMAINS:
        rows = db.scalars(select(domain.model).where(domain.model.user_id == user_id)).all()
        exported[domain.name] = [
            {field: getattr(row, field).isoformat() if hasattr(getattr(row, field), "isoformat") else getattr(row, field)
             for field in domain.export_fields}
            for row in rows
        ]
    job_ids = select(JobOpportunity.id).where(JobOpportunity.user_id == user_id)
    events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.job_id.in_(job_ids))).all()
    exported["application_events"] = [{
        field: getattr(row, field).isoformat() if hasattr(getattr(row, field), "isoformat") else getattr(row, field)
        for field in ("id", "job_id", "event_type", "from_status", "to_status", "note", "event_at", "created_at")
    } for row in events]
    return exported


def delete_foundation_data(db: Session, user_id: str) -> None:
    job_ids = select(JobOpportunity.id).where(JobOpportunity.user_id == user_id)
    db.execute(delete(ApplicationEvent).where(ApplicationEvent.job_id.in_(job_ids)))
    for model in (Artifact, Task, Contact, BackgroundJob, AuditEvent, JobOpportunity):
        db.execute(delete(model).where(model.user_id == user_id))
