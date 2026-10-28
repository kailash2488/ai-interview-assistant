# Phase 8 — Platform foundation

Status: implemented and locally validated. CI repeats SQLite, PostgreSQL, backend, frontend, and production-build gates. This phase intentionally exposes no job-tracker UI or CRUD API.

## Scope and architecture

Phase 8 adds additive tables for job opportunities, append-oriented application events, contacts, tasks, versioned artefacts, durable background jobs, content-free audit events, and platform schema metadata. It also adds reusable ownership, feature flag, lifecycle, audit, AI policy, and job-state services.

All roadmap feature flags default off. `/platform/status` is authenticated and reports only known flags plus the schema version. Future phases must add their own schemas, APIs, UI, and threat-model updates before enabling a flag.

## Data and ownership

Every top-level record has a non-null `user_id` with an indexed foreign key and `ON DELETE CASCADE`. Application events inherit ownership through their job. IDs are random 128-bit hexadecimal values. Foreign-key actions are explicit. Another user's resource must be returned as `404` through `owned_or_404`.

Operational audit and background-job rows are deliberately excluded from user exports because they contain only operational identifiers and safe codes. All user-authored job, contact, task, artefact, and event content is included. Account/data deletion removes both user content and operational rows.

## Threat model

| Risk | Phase 8 control | Required future control |
|---|---|---|
| IDOR / cross-account access | Non-null ownership, shared `owned_or_404`, two-user tests | Every route must use ownership-filtered reads |
| Mass assignment | No generic CRUD API; future Pydantic allowlists | Separate create/update schemas |
| Prompt injection | Delimited untrusted document helper and bounded AI policy | Task-specific system prompts and strict output schemas |
| Sensitive logs | Audit metadata key allowlist and length caps | No content in worker/HTTP metrics |
| Duplicate/retried work | Per-user idempotency constraint and durable state | Transactional worker claim/lease |
| Resource exhaustion | Shared per-user request/input policy | Provider token budget, queue backpressure and quotas |
| SSRF | URLs are inert text; no fetcher exists | Dedicated HTTPS-only SSRF-resistant fetcher if approved |
| Stored XSS | No Phase 8 UI; React escaping remains default | Never render user HTML; sanitize exports |
| Data remnants | Central deletion registry and cascades | Register every future model/file/vector before release |
| Migration data loss | Consistent pre-schema SQLite snapshot | PostgreSQL backup/restore runbook before hosted migration |

## Migration and rollback

Startup imports all models, calls `backup_before_new_tables`, creates missing tables, performs additive column upgrades, and records schema version `8`. For an existing SQLite database, a consistent snapshot is written to `data/schema-backups` before the first new table is created.

Before deployment:

1. Stop writes or enter a maintenance window.
2. Copy both data and upload volumes to independent storage.
3. Start the new backend once and retain the logged backup path.
4. Run `python -m scripts.verify_backup PATH_TO_BACKUP.db`.
5. Compare key row counts and exercise login, dashboard, interview history, Settings, and deletion.

Rollback is application-first because Phase 8 is additive: stop the new application and deploy the previous image. Old code ignores the new tables. Do not delete Phase 8 tables during emergency rollback. If an existing table was unexpectedly altered or corrupted, stop the service, preserve the failed database, restore the verified snapshot, and then deploy the previous image.

## Test matrix

- SQLite table/index creation and schema-version record.
- PostgreSQL create/drop in CI using the same SQLAlchemy metadata.
- Cross-user resource concealment.
- Background-job idempotency and state transitions.
- Audit metadata redaction and bounded values.
- Full foundation export and deletion.
- Unknown feature flag rejection.
- AI request size/rate controls and untrusted-document delimiters.
- Backup integrity verification.
- Existing frontend, backend, build, Compose, lint, and dependency regression gates.

## Operational notes

- `AIA_FEATURE_FLAGS` accepts a JSON array, for example `[]`. Keep it empty in production until a later phase is complete.
- `AIA_AI_REQUESTS_PER_MINUTE` defaults to `10` and is a ceiling applied by the shared policy helper.
- In-process rate limiting is a first deployment guard, not a distributed quota. Before multiple backend replicas, move quota state to a shared transactional store.
- Background jobs are records only in Phase 8. No worker executes them yet.
