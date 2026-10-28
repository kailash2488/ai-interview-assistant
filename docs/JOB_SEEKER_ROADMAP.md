# Job Seeker Platform — Implementation Roadmap

**Companion to:** [AI Interview Assistant Project Outline & SOP](SOP.pdf)

**Status:** Phase 8 complete; Phases 9–18 have not started

**Roadmap version:** 1.0 — 28 October 2026
**Starts after:** Phase 7 (Practice Lab)

## 1. Purpose

This document turns the AI Interview Assistant into a broader, practical workspace for people searching for jobs. It defines the order, boundaries, security controls, migrations, tests, rollout gates, and definition of done for every proposed feature.

The roadmap is intentionally incremental. Every phase must be useful by itself, preserve existing interviews and accounts, and be safe to deploy before the next phase begins.

## 2. Product outcomes

The expanded product should help a user:

1. organise job applications and follow-ups;
2. understand how well a resume matches a job;
3. maintain tailored resume versions without changing the original;
4. prepare reusable behavioural examples using the STAR method;
5. organise company research and interview questions;
6. follow a realistic preparation calendar;
7. practise coding, debugging, and SQL safely;
8. understand overall interview readiness;
9. measure application and preparation outcomes; and
10. draft professional follow-ups while keeping the user in control.

## 3. Non-negotiable delivery rules

These rules apply to every phase.

### 3.1 Compatibility and deployment safety

- Use additive database migrations first: new tables, nullable columns, and indexes. Destructive changes require a separate, tested migration phase.
- Run migrations automatically only after creating a consistent backup. Retain the existing backup policy and document restoration steps.
- Never change the meaning of an existing API response without introducing a compatible field or a versioned endpoint.
- Put incomplete features behind server-side feature flags. Hidden UI alone is not a security boundary.
- A failed optional feature must not block login, existing interviews, reports, or data export/deletion.
- Background jobs must be idempotent and safe to retry. Store job status, attempt count, last error, and timestamps.
- Do not depend on in-memory state for durable workflows. The application must survive restart or redeployment.
- SQLite remains supported for a single-server installation. Before introducing multi-process background workers, add and validate a PostgreSQL production path.

### 3.2 Account isolation and authorization

- Every new record must have a non-null `user_id` or inherit ownership through a parent with an enforced foreign key.
- Every read, update, delete, export, and download must verify ownership on the server. Do not trust IDs supplied by the browser.
- Return `404` for another user's object to avoid confirming that it exists.
- Add cross-account isolation tests for every resource and nested route.
- Use unpredictable IDs and never expose filesystem paths, provider credentials, internal errors, or sequential database IDs.

### 3.3 Privacy and data lifecycle

- Classify stored data as account data, job-search data, documents, generated content, or operational metadata.
- Clearly show when resume, job, company, or answer content will be sent to an AI provider.
- Send the minimum content needed for each AI task. Do not include unrelated resumes, applications, notes, or credentials.
- Preserve existing encrypted provider-key storage. Keys must never appear in API responses, logs, analytics, prompts, or exports.
- Extend “Delete all my data” and account deletion to every new table, file, background job, and generated artefact.
- Add per-resource deletion and a machine-readable user export before storing substantial new job-search history.
- Do not train models on user content or retain prompts externally beyond the selected provider's documented behaviour.
- Logs and metrics must use resource IDs and outcome codes, not resumes, company notes, answers, email bodies, or generated drafts.

### 3.4 Input and AI safety

- Validate type, length, allowed values, and encoding for every input at both API-schema and service boundaries.
- Treat resumes, job descriptions, company research, web excerpts, imported emails, and user notes as untrusted data, never as instructions.
- Place untrusted text inside explicit prompt delimiters and tell the model to ignore instructions found inside it.
- Validate every structured AI response with strict Pydantic schemas. Reject extra fields and cap list sizes and text lengths.
- Generated match scores, readiness scores, and recommendations are preparation aids, not hiring predictions. Display this limitation near the result.
- Do not infer protected traits or recommend decisions based on age, race, caste, religion, disability, sex, gender, health, family status, nationality, or other sensitive characteristics.
- Do not invent experience or credentials. Tailored content may rephrase supported facts but must identify unsupported suggestions for user review.
- No automatic job application, recruiter message, email send, calendar booking, or external profile update. The user must review and explicitly confirm any future external action.

### 3.5 File, URL, and execution safety

- Continue signature-based file validation, safe generated filenames, upload-size limits, and storage outside the web root.
- Store original and generated resumes separately and preserve immutable provenance to the source document/version.
- Initially store job and company URLs as text only. If URL fetching is later added, use a dedicated SSRF-resistant fetcher with HTTPS-only policy, DNS/IP revalidation, redirect limits, private-network blocking, response-size limits, content-type allowlists, and timeouts.
- Do not scrape job boards without permission. Prefer user-provided content and official APIs whose terms allow the intended use.
- All Python execution remains in the fail-closed gVisor runner. SQL practice must use an ephemeral database with no application connection, extensions, file access, or network access.

### 3.6 Quality, accessibility, and operations

- Meet WCAG 2.2 AA for keyboard navigation, focus, labels, contrast, status announcements, error messages, and charts that do not rely on colour alone.
- Support mobile, tablet, and wide desktop layouts.
- Every phase requires unit, API, ownership, validation, failure-path, accessibility, and frontend interaction tests.
- Production build, Compose validation, migration upgrade/rollback rehearsal, dependency audit, and backup/restore smoke test are release gates.
- Add structured metrics for counts, latency, error categories, retries, and provider usage without user content.
- Define per-user rate limits and cost/token ceilings for every AI-generating endpoint.

## 4. Shared architecture to build first

Phase 8 establishes reusable foundations so later features do not create separate, inconsistent systems.

### 4.1 Common entities

- `JobOpportunity`: role, company, location, work mode, employment type, source URL, salary range, currency, job description, status, priority, owner, and timestamps.
- `ApplicationEvent`: stage changes, notes, interviews, follow-ups, and outcome history. Events are append-only; corrections create a new event.
- `Contact`: recruiter or referrer name, role, company, email/phone as optional private fields, notes, and consent/source notes.
- `Task`: due date, reminder state, related resource type/ID, completion state, and recurrence metadata.
- `Artifact`: generated resume, match report, cover letter, email draft, company brief, or study plan with source references, generator/provider metadata, and version.
- `BackgroundJob`: task type, resource, state, attempt count, safe error code, timestamps, and idempotency key.

All tables require foreign keys, ownership indexes, timestamps, bounded text fields, and explicit cascade behaviour. Large generated objects should use JSON only when their schema is versioned and validated; searchable or relational fields belong in columns.

### 4.2 Shared services

- Ownership-aware repository helpers.
- Audit/event service for significant user actions without storing sensitive content.
- Background-job abstraction that can run in-process initially and move to a queue later.
- Versioned artefact service with provenance and safe download names.
- Notification/reminder abstraction that begins as in-app reminders.
- AI task policy wrapper for prompt isolation, schemas, token caps, provider disclosure, retries, and rate limits.
- Export/deletion registry so every feature declares how its data is exported and erased.

### 4.3 Shared UI

- A “Job search” top-level area with Overview, Applications, Tasks, Documents, Stories, and Insights.
- Consistent empty, loading, retry, unavailable, and permission-denied states.
- Reusable status timeline, filters, search, date picker, tags, confirmation dialog, provenance panel, and AI disclosure component.
- Autosave only where data loss would be harmful; show saved/saving/error states and prevent silent overwrites.

## 5. Phased implementation plan

### Phase 8 — Platform foundation and safe data evolution

**Goal:** Prepare the application for all job-search modules without changing existing user workflows.

**Deliverables**

- Add the shared entities and services in Section 4 with only internal/admin test surfaces.
- Introduce feature flags, schema-version metadata, background-job records, audit events, and the export/deletion registry.
- Add migration backup verification and a documented restore drill.
- Add PostgreSQL CI coverage while preserving SQLite development support.
- Establish AI endpoint rate-limit and token-budget helpers.
- Add a test factory for two-user ownership checks across all future resources.

**Security gate**

- Threat-model review covering IDOR, mass assignment, prompt injection, SSRF, stored XSS, file access, credential leakage, denial of service, and deletion completeness.
- Migration rehearsal using a copy of a populated pre-Phase-8 database.
- Confirm no new page or endpoint is accessible when its feature flag is off.

**Definition of done**

- Existing interviews, MCQs, reports, Practice Lab, Settings, and account deletion pass regression tests.
- Upgrade and restore are documented and repeatable.
- No user-visible behaviour changes except an optional hidden navigation placeholder in development.

### Phase 9 — Job application tracker and follow-up tasks

**Goal:** Give users one reliable place to manage applications.

**Core scope**

- Create, edit, archive, restore, and delete opportunities.
- Stages: interested, preparing, applied, screening, interview, offer, accepted, rejected, withdrawn, and archived.
- Timeline of stage changes, interview dates, notes, contacts, and follow-up tasks.
- Filters by stage, company, role, priority, date, and tags; search only within the signed-in user's data.
- Dashboard showing overdue tasks, upcoming interviews, and applications needing attention.
- Store source URLs without fetching them.

**Suggested API**

- `/jobs`, `/jobs/{id}`, `/jobs/{id}/events`, `/jobs/{id}/contacts`, and `/tasks` with pagination and ownership enforcement.
- Use optimistic concurrency (`updated_at` or version) to prevent one browser tab silently overwriting another.

**Tests and acceptance**

- Another user cannot enumerate or modify a job, contact, event, or task.
- Stage history remains accurate after edits and application restarts.
- Date/time display follows the user's timezone while storage remains UTC.
- The page remains usable with 1,000 applications through server-side pagination and indexed filters.

### Phase 10 — Resume-to-job match report

**Goal:** Explain how a selected resume aligns with a selected opportunity without pretending to predict ATS or hiring outcomes.

**Core scope**

- Select an existing resume and job opportunity; reuse current parsing where possible.
- Produce required/preferred skill matches, missing evidence, keyword coverage, experience alignment, formatting warnings, and suggested next actions.
- Every positive claim must cite a resume passage; every job requirement must cite job-description text.
- Use a transparent rubric with component scores. Label the result “Resume alignment”, not “ATS approval probability”.
- Cache by resume version, job version, rubric version, and model configuration; invalidate when any source changes.

**Safety requirements**

- Exclude protected traits and contact details from scoring.
- Never recommend keyword stuffing, hidden text, false credentials, or fabricated experience.
- Separate deterministic checks from model observations in the UI.
- Show provider disclosure before generation and allow regeneration only within rate limits.

**Tests and acceptance**

- Citation validation rejects claims not supported by source text.
- The same deterministic inputs produce the same deterministic sub-scores.
- Empty or adversarial job descriptions fail safely.
- Reports remain attached to immutable source versions.

### Phase 11 — Tailored resume versions and document studio

**Goal:** Help users adapt presentation while preserving truth and the original document.

**Core scope**

- Create immutable resume versions from a selected source resume and job.
- Suggest summary, skill ordering, and bullet rewrites with side-by-side original/draft comparison.
- Require explicit user acceptance for every change; support undo and version history.
- Mark suggestions that need evidence and block them from export until edited or confirmed with supporting source content.
- Export to PDF and DOCX using controlled templates; no user-supplied HTML/CSS execution.
- Optionally draft a role-specific cover letter as a versioned artefact.

**Safety requirements**

- Never overwrite uploaded originals.
- Sanitize exported text, cap document size, and prevent formulas/macros/external links in generated office files.
- Embed provenance: source resume, target job, creation time, and accepted changes.

**Tests and acceptance**

- Original files remain byte-for-byte unchanged.
- Exported documents open correctly and contain no active content.
- Unsupported claims are visibly flagged and never silently introduced.

### Phase 12 — STAR story library

**Goal:** Build reusable, evidence-based behavioural interview examples.

**Core scope**

- Create stories with situation, task, action, result, skills, companies/projects, and confidentiality notes.
- Guided quality checks for specificity, ownership, measurable impact, length, and likely follow-up questions.
- Link stories to job competencies and reuse them in behavioural mock interviews.
- Practise short, medium, and detailed versions without changing the canonical story.

**Safety requirements**

- Warn users not to store employer secrets, client personal data, credentials, or restricted metrics.
- Suggestions may improve structure but may not invent numbers, outcomes, or ownership.
- Private stories are excluded from exports unless individually selected.

**Tests and acceptance**

- Linked interview questions retrieve only the current user's selected stories.
- Version history and deletion propagate correctly to derived practice artefacts.

### Phase 13 — Preparation calendar and daily study plan

**Goal:** Convert opportunities, interview dates, weak areas, and available time into an achievable plan.

**Core scope**

- User sets availability, rest days, timezone, interview date, and priority.
- Generate daily tasks across resume review, company research, STAR stories, MCQs, coding, system design, and mock interviews.
- Drag, reschedule, complete, skip, and regenerate remaining tasks without rewriting completed history.
- In-app reminders first; calendar export as an `.ics` file.

**Safety requirements**

- No external calendar writes in the initial version.
- Prevent excessive workload; enforce daily caps, rest periods, and accessible language.
- Calendar exports contain only user-selected details and no resume text or API credentials.

**Tests and acceptance**

- Timezone and daylight-saving transitions do not shift interview times incorrectly.
- Regeneration is idempotent and preserves completed tasks.
- Plans remain useful if AI generation is unavailable by falling back to deterministic templates.

### Phase 14 — Company research workspace

**Goal:** Organise trustworthy company and role research for interview preparation.

**Core scope**

- User-entered company overview, products, values, role notes, interview process, sources, risks, questions to ask, and open questions.
- Convert selected notes into a concise interview brief and targeted question bank.
- Source fields include title, URL, publisher, publication date, date accessed, and user notes.
- Initially require users to paste notes; do not automatically crawl websites.

**Future controlled retrieval**

- Add only after an SSRF threat model and terms-of-service review.
- Allowlist supported sources or use compliant official APIs.
- Clearly separate sourced facts, user notes, and AI inferences.

**Tests and acceptance**

- Prompt injection inside research notes cannot alter the requested output schema or expose other data.
- Generated briefs cite selected sources and mark uncertain/inferred statements.

### Phase 15 — Coding, debugging, and SQL assessments

**Goal:** Expand Practice Lab into realistic technical screening preparation.

**Core scope**

- Question catalogue by language, topic, difficulty, company pattern, and expected time.
- Public sample tests plus hidden tests; deterministic scoring with runtime and memory results.
- Debugging exercises with controlled starter repositories/snippets.
- SQL exercises against a fresh ephemeral database and fixed datasets.
- Explanations, complexity review, retry history, and progress by topic.

**Security requirements**

- Python remains gVisor-only and fail-closed; JavaScript remains in the constrained browser worker unless moved to an equally isolated runner.
- SQL uses an isolated engine with no application database credentials, network, extensions, filesystem reads/writes, or persistent user objects.
- Hidden tests never reach the browser. Limit source, stdin, result, runtime, memory, output, processes, and concurrent jobs.
- Apply per-user quotas and queue backpressure. Never fall back to executing code in FastAPI or the frontend server.

**Tests and acceptance**

- Escape, fork-bomb, infinite-loop, output-flood, filesystem, socket, metadata, and cross-user test suites fail safely.
- Runner unavailability leaves all non-execution features usable and explains the next step plainly.

### Phase 16 — Interview readiness score

**Goal:** Provide an explainable preparation summary, not a hiring prediction.

**Inputs**

- Resume alignment, practice recency, interview rubric dimensions, MCQ/coding topic coverage, STAR story readiness, company research, and planned-task completion.

**Design**

- Versioned, documented weighted rubric calculated deterministically from available inputs.
- Show component scores, missing evidence, confidence/completeness, last updated time, and concrete actions.
- Never reduce readiness because sensitive information is absent.
- Allow users to inspect and challenge source data.

**Tests and acceptance**

- Score is clamped to 0–100 and cannot display impossible values.
- Missing modules reduce completeness, not unfairly set performance to zero.
- Historical scores retain their rubric version when the formula changes.

### Phase 17 — Application and preparation analytics

**Goal:** Help users learn from their own process without comparing them unfairly with other users.

**Core scope**

- Applications, response rate, interview conversion, offer rate, time in stage, follow-up completion, preparation time, practice outcomes, and trends.
- Filters for date, role family, company, source, and stage.
- Explain denominators and small sample sizes; show counts alongside percentages.
- Export selected analytics as CSV without internal IDs or hidden metadata.

**Privacy and correctness**

- No cross-user benchmarking by default.
- Avoid causal claims such as “this resume caused rejection”. Present correlations as observations.
- Aggregate from event history rather than mutable current status wherever possible.

**Tests and acceptance**

- Metrics reconcile against seeded event histories, including withdrawn and duplicate applications.
- Empty and small datasets show guidance rather than misleading charts.

### Phase 18 — Follow-up and professional communication tools

**Goal:** Help users draft accurate messages while keeping all external communication under their control.

**Core scope**

- Templates for recruiter follow-up, interview thank-you, referral request, scheduling reply, offer clarification, and respectful withdrawal.
- Use selected job/contact/interview context and allow tone and length choices.
- Save drafts as versioned artefacts; copy/download only in the first release.
- Detect placeholders, unsupported claims, accidental secrets, and missing recipient/context before marking a draft ready.

**Safety requirements**

- Never send messages automatically.
- Do not expose one contact's information in another job's draft.
- Do not generate deceptive urgency, harassment, discriminatory language, or fabricated competing offers.
- Future email integrations require separate OAuth scopes, explicit preview and confirmation, audit history, revocation, and provider-specific security review.

**Tests and acceptance**

- Every draft identifies its source job/contact and contains no unresolved hidden template variables.
- Deleting a contact removes or redacts it according to the documented artefact-retention rule.

## 6. Release process for every phase

Each phase follows the same sequence:

1. **Design review:** user journeys, wireframes, schema, API contract, threat model, and acceptance criteria.
2. **Migration rehearsal:** upgrade a populated database copy, validate counts and ownership, then test restoration.
3. **Backend slice:** models, service layer, endpoints, authorization, validation, rate limits, and unit/API tests.
4. **Frontend slice:** accessible responsive UI, clear disclosure, empty/error/loading states, and interaction tests.
5. **Adversarial testing:** cross-user IDs, malformed inputs, oversized content, prompt injection, repeated requests, provider outage, restart, and deletion.
6. **Regression:** existing interview and account workflows, full frontend suite, backend suite, build, lint, Compose, dependency audit, and backup smoke test.
7. **Staged rollout:** feature flag off by default, enable for the owner/test account, observe metrics, then enable generally.
8. **Documentation:** README, configuration, privacy/data map, backup/restore, troubleshooting, and screenshots.

No phase moves to “complete” with failing tests, undocumented migration risk, incomplete deletion, missing ownership checks, or a security control that exists only in the browser.

## 7. Roadmap dependencies

```text
Phase 8 Foundation
 ├─ Phase 9 Job tracker ─┬─ Phase 13 Calendar
 │                       ├─ Phase 14 Company research
 │                       ├─ Phase 17 Analytics
 │                       └─ Phase 18 Communication tools
 ├─ Phase 10 Match report ─ Phase 11 Tailored resumes
 ├─ Phase 12 STAR stories
 └─ Phase 15 Coding & SQL

Phases 9–15 ─────────────── Phase 16 Readiness score
Phases 9, 13, 16 ────────── Phase 17 Analytics
```

Phase 16 must wait until enough source modules exist to make its score meaningful. Phase 17 must use event history introduced in Phase 9. Phase 18 depends on jobs and contacts and must not introduce sending integrations in its first release.

## 8. Recommended execution order

Follow the numbered phase order unless a security or migration prerequisite forces a pause. The highest-value first release is Phases 8–10: safe foundations, application tracking, and resume alignment. After that, Phases 11–14 deepen preparation, Phase 15 expands technical practice, and Phases 16–18 add synthesis and productivity.

Do not implement multiple schema-heavy phases simultaneously. Complete, migrate, test, document, and deploy one phase before beginning the next.

## 9. Global definition of done

The roadmap is complete only when:

- all ten product outcomes in Section 2 are available and documented;
- every resource is ownership-tested, exportable, and deletable;
- all AI outputs disclose provider processing and validate structured results;
- no automatic external action occurs without explicit user confirmation;
- existing interviews and reports work after every upgrade;
- backup restoration and migration from the pre-roadmap database are demonstrated;
- production dependency and container scans have no unresolved critical/high findings;
- accessibility and responsive-layout checks pass;
- operational runbooks cover provider outage, runner outage, failed jobs, rollback, backup, and account deletion; and
- the README and SOP companion accurately describe the deployed product rather than planned behaviour.

## 10. Progress register

Update this table only after the phase definition of done is satisfied.

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 8 | Platform foundation | Complete | [Design, threat model and operations](phases/phase-8/DESIGN.md) |
| 9 | Application tracker | Not started | — |
| 10 | Resume alignment | Not started | — |
| 11 | Tailored resume studio | Not started | — |
| 12 | STAR story library | Not started | — |
| 13 | Preparation calendar | Not started | — |
| 14 | Company research | Not started | — |
| 15 | Coding, debugging, and SQL | Not started | — |
| 16 | Readiness score | Not started | — |
| 17 | Analytics | Not started | — |
| 18 | Communication tools | Not started | — |

When implementation begins, add a short phase-specific design document under `docs/phases/phase-N/` before changing application code. That document should contain the final schema, endpoint contract, wireframes, threat model, migration/rollback steps, and test matrix for that phase.

## 11. Decisions required before Phase 8 starts

Record these choices in the Phase 8 design document so they do not change silently during implementation:

1. **Production database:** confirm whether the first hosted deployment remains single-instance SQLite or moves to PostgreSQL before job-search data is added.
2. **Feature rollout:** identify the owner/test account used for feature-flagged releases.
3. **Retention:** choose whether archived applications and generated artefacts are retained indefinitely or automatically removed after a defined period.
4. **Notifications:** confirm that the initial calendar uses in-app reminders and `.ics` export only, with no email/SMS sending.
5. **Document templates:** select the supported resume and cover-letter templates and fonts before building exports.
6. **Coding languages:** choose the language order after Python and JavaScript; SQL should remain a separately isolated exercise type.
7. **Analytics policy:** confirm that analytics remain private per user and that no cross-user benchmarks will be introduced without explicit consent and a privacy review.
8. **Provider policy:** decide which cloud providers are enabled on the production server and establish per-user request/token limits.

Until these decisions are recorded, Phase 8 may perform research and design work but should not introduce irreversible schema or operational choices.
