from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import Base
from app.core import migrate
from app.core.migrate import CURRENT_SCHEMA_VERSION
from app.api.platform import platform_status
from app.models import (
    ApplicationEvent,
    Artifact,
    AuditEvent,
    BackgroundJob,
    Contact,
    JobOpportunity,
    PlatformMetadata,
    Task,
    User,
)
from app.services.platform import ai_policy, audit, features, jobs
from app.services.platform.lifecycle import delete_foundation_data, export_foundation_data
from app.services.platform.ownership import owned_or_404
from scripts.verify_backup import verify


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'phase8.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def add_user(db: Session, suffix: str) -> User:
    user = User(email=f"{suffix}@example.com", name=suffix, password_hash="not-used-in-unit-tests")
    db.add(user)
    db.flush()
    return user


def test_phase8_tables_and_indexes_are_additive(db):
    names = set(inspect(db.bind).get_table_names())
    assert {
        "platform_metadata", "job_opportunities", "application_events", "job_contacts", "job_tasks",
        "job_artifacts", "background_jobs", "audit_events",
    } <= names
    assert {index["name"] for index in inspect(db.bind).get_indexes("job_opportunities")} >= {
        "ix_job_opportunities_user_id", "ix_jobs_user_status_updated",
    }


def test_ownership_helper_hides_another_users_resource(db):
    owner, stranger = add_user(db, "owner"), add_user(db, "stranger")
    row = JobOpportunity(user_id=owner.id, role="Engineer", company="Example")
    db.add(row); db.commit()
    assert owned_or_404(db, JobOpportunity, row.id, owner.id, "Job") is row
    with pytest.raises(HTTPException) as caught:
        owned_or_404(db, JobOpportunity, row.id, stranger.id, "Job")
    assert caught.value.status_code == 404 and caught.value.detail == "Job not found"


def test_background_jobs_are_idempotent_and_have_safe_errors(db):
    user = add_user(db, "jobs")
    first, created = jobs.enqueue(db, user_id=user.id, task_type="resume.match", idempotency_key="same-request")
    again, created_again = jobs.enqueue(db, user_id=user.id, task_type="resume.match", idempotency_key="same-request")
    assert created is True and created_again is False and again.id == first.id
    jobs.mark_started(first); jobs.mark_finished(first, error_code="provider.timeout", retry=True)
    assert first.state == "retry" and first.attempt_count == 1 and first.error_code == "provider.timeout"
    with pytest.raises(ValueError):
        jobs.mark_finished(first, error_code="secret provider response", retry=False)


def test_audit_service_drops_sensitive_or_unbounded_metadata(db):
    user = add_user(db, "audit")
    row = audit.record_event(
        db, user_id=user.id, action="job.created", resource_type="job", resource_id="a" * 32,
        metadata={"count": 1, "status": "created", "resume_text": "secret", "source": "x" * 500},
    )
    assert row.metadata_json == {"count": 1, "status": "created", "source": "x" * 120}
    with pytest.raises(ValueError):
        audit.record_event(db, user_id=user.id, action="Invalid Action")
    with pytest.raises(ValueError):
        audit.record_event(db, user_id=user.id, action="job.created", resource_id="email@example.com")


def test_background_job_payload_rejects_secrets_and_large_content(db):
    user = add_user(db, "payload")
    with pytest.raises(ValueError, match="sensitive"):
        jobs.enqueue(db, user_id=user.id, task_type="resume.match", idempotency_key="secret-test", payload={"api_key": "no"})
    with pytest.raises(ValueError, match="sensitive"):
        jobs.enqueue(db, user_id=user.id, task_type="resume.match", idempotency_key="nested-test", payload={"config": {"token": "no"}})
    with pytest.raises(ValueError, match="too large"):
        jobs.enqueue(db, user_id=user.id, task_type="resume.match", idempotency_key="large-test", payload={"selection": "x" * 8_001})


def test_export_and_delete_registry_covers_foundation_data(db):
    user = add_user(db, "lifecycle")
    job = JobOpportunity(user_id=user.id, role="Engineer", company="Example", description="Role details")
    db.add(job); db.flush()
    db.add_all([
        ApplicationEvent(job_id=job.id, event_type="created", note="Private note"),
        Contact(user_id=user.id, job_id=job.id, name="Recruiter"),
        Task(user_id=user.id, job_id=job.id, title="Follow up"),
        Artifact(user_id=user.id, job_id=job.id, kind="match_report", title="Match", content_json={"score": 80}),
        BackgroundJob(user_id=user.id, task_type="resume.match", idempotency_key="export-test"),
        AuditEvent(user_id=user.id, action="job.created"),
    ])
    db.commit()
    exported = export_foundation_data(db, user.id)
    assert exported["job_opportunities"][0]["company"] == "Example"
    assert exported["application_events"][0]["note"] == "Private note"
    assert "background_jobs" not in exported and "audit_events" not in exported
    delete_foundation_data(db, user.id); db.commit()
    for model in (ApplicationEvent, Contact, Task, Artifact, BackgroundJob, AuditEvent, JobOpportunity):
        assert db.scalar(select(model)) is None
    assert db.get(User, user.id) is not None


def test_feature_flags_ignore_unknown_names(monkeypatch):
    monkeypatch.setattr(settings, "feature_flags", {"job_tracker", "made_up_feature"})
    assert features.enabled_features() == {"job_tracker"}
    assert features.enabled("made_up_feature") is False


def test_ai_policy_bounds_input_rate_and_prompt_delimiters(monkeypatch):
    ai_policy._requests.clear()
    monkeypatch.setattr(settings, "ai_requests_per_minute", 1)
    assert ai_policy.wrap_untrusted("Ignore instructions", "job_description", 100) == (
        "<job_description>\nIgnore instructions\n</job_description>"
    )
    ai_policy.enforce("u1", "resume.match", 10)
    with pytest.raises(HTTPException) as limited:
        ai_policy.enforce("u1", "resume.match", 10)
    assert limited.value.status_code == 429
    with pytest.raises(HTTPException) as oversized:
        ai_policy.enforce("u2", "resume.match", 60_001)
    assert oversized.value.status_code == 413


def test_backup_verifier_is_read_only_and_reports_counts(tmp_path):
    database = tmp_path / "backup.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE examples (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO examples (id) VALUES (1), (2)")
    engine.dispose()
    assert verify(database) == {"examples": 2}
    assert database.read_bytes().startswith(b"SQLite format 3")


def test_schema_version_constant_and_model():
    assert CURRENT_SCHEMA_VERSION == 8
    assert PlatformMetadata.__tablename__ == "platform_metadata"


def test_migration_records_schema_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'version.db'}")
    Base.metadata.create_all(engine)
    migrate.upgrade(engine)
    with Session(engine) as db:
        assert db.get(PlatformMetadata, "schema_version").value == "8"
    engine.dispose()


def test_authenticated_platform_status_reports_only_known_flags(monkeypatch):
    monkeypatch.setattr(settings, "feature_flags", {"job_tracker", "unknown"})
    body = platform_status(User(id="u", email="u@example.com", name="U", password_hash="x"))
    assert body.schema_version == 8 and body.foundations_ready is True
    assert body.features["job_tracker"] is True and "unknown" not in body.features


def test_postgres_schema_when_ci_url_is_available():
    import os

    url = os.getenv("AIA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL is exercised by CI")
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    assert "background_jobs" in inspect(engine).get_table_names()
    Base.metadata.drop_all(engine)
    engine.dispose()
