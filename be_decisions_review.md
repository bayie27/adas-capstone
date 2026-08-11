# ADAS Backend Decision Review

> **Started:** July 12, 2026  
> **Repository baseline:** `main` at `35ca41d`  
> **Status:** In progress  
> **Purpose:** Consolidated, decision-by-decision verification and replacement of `be_decisions.md`. This is the only decision-locking document; separate files will not be created for individual decisions.

## Decision Process

Each decision is checked against:

- `final_paper_text.txt`
- `be_masterplan_text.txt`
- `be_decisions.md`
- `backend_assessment.md`
- the live backend, AI engine, scripts, and tests

Decision statuses:

- **Locked** — approved and ready to drive implementation planning.
- **Open** — requires discussion or user confirmation.
- **Superseded** — an earlier decision that must no longer guide implementation.

If a paper requirement belongs to another teammate or deployment owner, it must still have an explicit interface, owner, and acceptance-evidence requirement. It may not be silently omitted.

## Decision Matrix

| ID | Area | Status | Replaces or verifies |
|---|---|---|---|
| D-001 | Scope and ownership | **Locked** | Supersedes `be_decisions.md` §1 scope boundary and §9 AI/deployment exclusions |
| D-002 | Canonical incident lifecycle and concurrency | **Locked** | Refines the paper's HITL lifecycle and supersedes non-atomic current route behavior |
| D-003 | Camera and AI control model | **Locked** | Supersedes hardcoded camera polling and separates desired backend state from observed AI state |
| D-004 | Alarm settings and shared snooze | **Locked** | Refines `be_decisions.md` §2.1–2.2 and replaces ephemeral revisioned timers with a persisted deadline |
| D-005 | Database evolution and SQLite integrity | **Locked** | Replaces production `create_all()` upgrades with a clean initial migration after schema lock |
| D-006 | Authentication and revocable sessions | **Locked** | Replaces username-only, non-revocable JWTs and unauthenticated WebSockets with a proportional LAN deployment model |
| D-007 | Append-only activity audit | **Locked** | Refines `be_decisions.md` §2.3 with transactional writes, database immutability, and sanitized failure records |
| D-008 | WebSocket delivery and recovery | **Locked** | Refines `be_decisions.md` §3 with versioned events, per-client backpressure, and REST state recovery |
| D-009 | System health, hardware profiles, and camera KPIs | **Locked** | Refines `be_decisions.md` §2.4 and distinguishes demo validation from production-target readiness |
| D-010 | Reports, PDF/CSV, and retraining exports | **Locked** | Refines `be_decisions.md` §2.5 with shared filter contracts and bounded local export jobs |
| D-011 | Backup, restore, restart, and archival | **Locked** | Refines `be_decisions.md` §2.6 with verified online backup and rollback-safe offline restore |
| D-012 | AI detection-event pipeline and owner handoff | **Locked** | Hardens frame scheduling, pause behavior, snapshots, event delivery, and environment-specific inference while reserving measured AI tuning for the AI owner |

## Locked Decisions

### D-001 — Scope and Ownership

**Status:** Locked on July 12, 2026.

**Decision:** The completion effort owns the backend and every backend–AI runtime integration required for the system promised in the paper. It is not limited to changing the heartbeat payload.

#### In Scope

- FastAPI backend behavior, database models, database constraints, and versioned migrations.
- REST API and WebSocket contracts.
- AI-engine runtime integration required by the paper:
  - dynamic camera discovery and reconciliation;
  - desired versus observed camera state;
  - pause, resume, enable, disable, and cooldown handling;
  - connection and AI status reporting;
  - FPS and inference-latency telemetry;
  - retry and failure recovery;
  - worker lifecycle and failure isolation.
- Alarm settings, snooze, activity auditing, system health, report exports, backup/restore, and session handling.
- Application-owned deployment artifacts, including systemd service definitions, restart and restore scripts, configuration templates, and operational documentation.
- Backend unit tests plus backend–AI integration, load, resilience, backup/restore, and recovery tests.
- Traceability and acceptance evidence for all 82 unique paper test cases.

#### Out of Scope

- YOLO model training or accuracy tuning.
- Dataset collection, labeling, and augmentation.
- Physical VLAN, NAS, Dahua DSS, and server administration.
- Frontend UI implementation.
- Hardware procurement and physical installation.

#### Boundary Rule

Out-of-scope ownership does not remove a paper requirement. The implementation plan must still define the interface, responsible owner, prerequisites, and acceptance evidence for each externally owned requirement.

#### Consequences

- The old decision that AI changes are limited to the heartbeat is **superseded**.
- The AI engine may be modified wherever required to make backend-controlled camera state and incident handling reliable.
- Deployment scripts and service definitions are application deliverables even though physical infrastructure administration remains external.
- AI accuracy requirements remain evidence obligations, but model retraining is not part of this effort.

### D-002 — Canonical Incident Lifecycle and Concurrency

**Status:** Locked on July 12, 2026.

**Decision:** Incident status transitions, their actor/timestamp meanings, camera consequences, and multi-operator behavior are governed by one canonical state machine.

#### Canonical Statuses

- `Unverified` — a new AI detection awaiting human action.
- `Ongoing` — an operator-confirmed accident that has not cleared.
- `Dismissed` — a terminal false positive or correction of a mistaken confirmation.
- `Resolved` — a terminal confirmed accident whose emergency has cleared.
- `Closed` is not a stored status. Where the paper uses “Closed,” it describes a terminal `Resolved` or `Dismissed` incident.

#### Allowed Transitions

```text
AI detection -> Unverified
Unverified  -> Ongoing    (Confirm)
Unverified  -> Dismissed  (Immediate false positive)
Ongoing     -> Resolved   (Emergency cleared)
Ongoing     -> Dismissed  (Correction of mistaken confirmation)
```

All other transitions are rejected.

#### Actor and Timestamp Semantics

- Initial Confirm populates `verified_by_id` and `verified_at`.
- Initial Dismiss also populates `verified_by_id` and `verified_at`; `closed_by_id` and `closed_at` remain empty.
- Resolve retains the original verification fields and populates `closed_by_id` and `closed_at`.
- Correction from `Ongoing` to `Dismissed` retains the original verifier and records the correcting operator in `closed_by_id` and `closed_at`.
- Add server-managed `created_at` and `updated_at` fields to the incident record.
- Store and exchange all timestamps in UTC; frontend clients perform display-time localization.

#### Camera and Snooze Consequences

- Creating an `Unverified` incident immediately sets the camera's desired AI state to paused.
- The RTSP connection stays alive and continues draining current frames while inference is paused, preventing stale buffered footage on resume.
- Confirm leaves inference paused.
- Immediate Dismiss starts a 60-second camera-specific cooldown and leaves inference paused until it expires.
- Resolve and correction resume inference immediately.
- Confirm, Dismiss, and any terminal transition cancel active snooze timers for the incident.

#### Atomic Multi-Operator Handling

- A transition updates the incident only when its stored status still equals the expected starting status.
- Competing actions cannot overwrite one another; exactly one valid transition succeeds.
- A stale competing request returns `409 Conflict` with the incident's current status, action, handler, and handling time.
- The normal synchronization path is real-time: after commit, the backend broadcasts `ALERT_STATUS_UPDATE` to every connected dashboard.
- When another operator's modal receives that event, it stops that incident's alarm/snooze state, disables its action controls, explains who handled it and how, and replaces Confirm/Dismiss with a single **Okay** button.
- **Okay** closes only that client's modal and does not mutate backend state.
- If an operator acts before the WebSocket update arrives, the `409` response drives the frontend into the same already-handled modal state.

#### Duplicate Prevention and Event Identity

- Enforce at most one open (`Unverified` or `Ongoing`) incident per camera using a SQLite partial unique index.
- Historical `Dismissed` and `Resolved` incidents do not participate in that uniqueness rule.
- The AI engine generates a UUID `source_event_id` once for each genuine detection event and reuses it for every retry of that event.
- The backend stores `source_event_id` under a unique constraint.
- `log_id` remains the backend-generated, human-facing accident record identifier.
- A retry with an existing `source_event_id` returns the already-created incident and its existing `log_id`; it does not create a duplicate.
- A genuinely new accident receives both a new AI-generated `source_event_id` and a new database-generated `log_id`.

#### Transaction and Broadcast Boundary

- The incident transition, camera desired-state change, and corresponding audit record are written in one database transaction.
- If any write fails, the entire transaction rolls back.
- WebSocket broadcasts occur only after the transaction commits successfully, so clients are never told about uncommitted state.
- Incident records have no general-purpose edit or delete API.

#### Audit Mapping

- `Unverified -> Ongoing`: `ALERT_CONFIRM`
- `Unverified -> Dismissed`: `ALERT_DISMISS`
- `Ongoing -> Resolved`: `ALERT_RESOLVE`
- `Ongoing -> Dismissed`: `ALERT_CORRECTION`

#### Consequences

- Existing route implementations that read a status and later perform an unconditional write must be replaced with atomic expected-state transitions.
- Existing immediate-dismiss handling must move its initial actor from closure fields to verification fields.
- Frontend integration requires both real-time `ALERT_STATUS_UPDATE` handling and `409` fallback handling.
- The AI webhook contract must add `source_event_id`.

### D-003 — Camera and AI Control Model

**Status:** Locked on July 12, 2026.

**Decision:** The backend is authoritative for camera configuration and desired operational state. A supervised AI engine reconciles its runtime to that state and reports observed state exclusively through an internal heartbeat; it never accesses SQLite directly.

#### Backend-Owned Desired State

Each camera stores:

- `is_active` — soft-deletion state.
- `is_enabled` — operator-controlled enable/disable state.
- `desired_ai_state` — `Active`, `Paused`, or `Inactive`.
- `desired_state_reason` — `incident`, `cooldown`, `disabled`, or null.
- `cooldown_until` — persisted UTC deadline or null.
- `config_version` — monotonically incremented whenever AI-relevant configuration or desired state changes.

Incident transitions update desired camera state in the same transaction defined by D-002.

#### AI-Owned Observed State

For each local camera runtime, the AI engine reports:

- `connection_status` — `Connected`, `Disconnected`, `Reconnecting`, or `Unresponsive`.
- `ai_status` — `Active`, `Paused`, `Inactive`, or `Unresponsive`.
- latest measured FPS and inference latency;
- the applied camera `config_version`;
- a sanitized error code and message when applicable.

The backend records `last_heartbeat_at` and treats stale reports as unavailable. Observed state never overrides backend desired state.

#### Bidirectional Heartbeat

- One AI supervisor calls the versioned internal heartbeat endpoint every three seconds using the protected internal-service credential.
- The request contains engine identity, send timestamp, and a complete report of locally known camera runtimes.
- The response contains server time and a complete authoritative snapshot of all active camera configurations and their desired state.
- A complete snapshot, rather than change-only commands, enables deterministic recovery after either process restarts or misses earlier heartbeats.
- The AI engine does not read or write the backend database.
- The existing hardcoded camera list and `GET /api/internal/cameras` polling contract are superseded after a coordinated backend/AI cutover.

#### Reconciliation Rules

After every successful heartbeat, the supervisor:

- starts a missing ingestion unit for each enabled active camera;
- applies configuration changes when the backend `config_version` is newer;
- pauses, resumes, or deactivates inference according to desired state;
- stops and releases any local camera absent from the authoritative snapshot or marked disabled/deleted;
- reports its applied version and resulting observed state on the next heartbeat.

Normal operator changes take effect within approximately one heartbeat interval, with a maximum expected control delay of about three seconds.

#### Worker Architecture

- Run one supervised AI-engine controller process.
- Use isolated, bounded per-camera ingestion units with per-camera exception boundaries and latest-frame buffers.
- Run one inference worker process per configured GPU, loading one model instance per GPU rather than one model per camera.
- Batch frames from multiple cameras assigned to each GPU.
- A malformed frame or stream exception is contained to that camera's ingestion path.
- The supervisor automatically restarts a failed GPU inference worker and restores its camera assignments.
- GPU count and assignment policy are configuration-driven so vertical hardware scaling does not require application code changes.

This replaces the non-scalable alternatives of one duplicated YOLO model process per camera and one unsupervised shared inference loop for every camera.

#### Camera Creation and Configuration Flow

- The backend validates and stores a new or changed camera configuration and increments its `config_version`.
- A new or reconfigured camera initially appears as `Reconnecting` while the AI engine applies it asynchronously.
- The AI engine performs the RTSP handshake and reports `Connected`/`Active` on success or `Unresponsive` with a sanitized error on failure.
- The backend broadcasts observed status changes to dashboards after persisting them.
- Camera create/update API requests do not block while waiting for an RTSP connection attempt.

#### Failure and Cleanup Rules

- A disconnected stream retries every 10 seconds, matching NFR-14 and TC-R-301.
- After three failed attempts, observed state becomes `Unresponsive`, but retries continue every 10 seconds.
- If the backend receives no AI heartbeat for 10 seconds, it exposes the affected runtime state as `Unresponsive` until fresh reports arrive.
- Disabled, deleted, or superseded camera runtimes release their RTSP socket, buffers, and assigned processing resources.
- Paused inference continues draining the stream through a bounded latest-frame buffer so resume cannot process stale queued footage.
- AI and backend restarts recover from the authoritative snapshot without relying on prior in-memory commands.

#### Consequences

- Existing `connection_status` and `ai_status` become explicitly observed fields rather than a mixture of user intent and runtime reports.
- Backend routes must change desired state; only heartbeat processing updates observed state.
- The AI engine requires a supervisor, dynamic camera registry, GPU worker pool, bounded ingestion buffers, metrics collection, and reconciliation logic.
- Status broadcasts occur on meaningful observed-state changes rather than every unchanged heartbeat.

### D-004 — Alarm Settings and Shared Incident Snooze

**Status:** Locked on July 12, 2026.

**Decision:** Alarm sound and volume preferences are per-user, while snoozing is shared incident state synchronized across every dashboard. The persisted UTC snooze deadline is authoritative; no `snooze_revision` field is used.

#### Per-User Alarm Settings

Each user has exactly one alarm-settings record containing:

- `user_id` — unique foreign key to the user.
- `alarm_sound` — a validated frontend/backend sound key.
- `volume` — integer from 0 through 100.
- `snooze_duration` — integer from 15 through 60 seconds.
- `created_at` and `updated_at` — UTC timestamps.

Defaults are:

- `alarm_sound = default`
- `volume = 80`
- `snooze_duration = 30`

Settings are created with new accounts and backfilled for existing accounts through a migration. `GET /api/settings/alarm` is side-effect-free; `PUT /api/settings/alarm` replaces the authenticated user's complete settings representation and is idempotent.

The frontend plays and previews audio locally using the stored key and volume. The backend stores and validates the key but does not stream or play sound. The final allowed sound enum must match real frontend audio assets; Claude's proposed list is not accepted without corresponding files and a frontend contract.

#### Shared Snooze Semantics

- Only an `Unverified` incident may be snoozed.
- `POST /api/alerts/{log_id}/snooze` reads the authenticated actor's saved duration; clients cannot submit an arbitrary duration.
- The incident persists `snoozed_at`, `snoozed_until`, and `snoozed_by_id`.
- The backend broadcasts `SNOOZE_ACTIVATED` only after the snooze transaction commits.
- Every dashboard mutes that incident until the shared deadline; unrelated incidents remain independently audible.
- Each snooze is written to the activity audit trail.

#### Re-Snooze Without a Revision Field

- Unlimited re-snoozes are allowed as required by the paper.
- The latest valid snooze overwrites `snoozed_at`, `snoozed_until`, and `snoozed_by_id` using the latest actor's saved duration.
- A scheduled job uses the stable identity `snooze:{log_id}` and is replaced when that incident is re-snoozed.
- `snoozed_until` in SQLite remains authoritative even if replacing or cancelling an in-memory job races with execution.
- Any job that wakes reloads the incident and does nothing when the current deadline is still in the future, has been cleared, or the incident is no longer `Unverified`.

#### Expiration and Atomic Safety

- Expiration atomically clears snooze fields only when the incident is still `Unverified` and its currently stored `snoozed_until` is due.
- Only the process that successfully clears the due snooze may broadcast `RE_ALARM`.
- An obsolete job, duplicate scheduler execution, or concurrent process updates zero rows and cannot emit a duplicate re-alarm.
- Confirm or Dismiss clears persisted snooze state in the same transaction as the D-002 incident transition; cancelling an in-memory job is then only resource cleanup, not the correctness mechanism.

#### Restart and Missed-Job Recovery

- On backend startup, unexpired snoozes are rescheduled for their remaining duration.
- Expired `Unverified` snoozes are atomically cleared and become alarm-active again.
- A lightweight periodic safety sweep processes any due snooze whose in-memory job was lost or delayed.
- Dashboard initial load and reconnection return the persisted snooze fields with active incidents, so clients reconstruct the correct state without relying on a previous WebSocket message.

#### Real-Time and Conflict Behavior

- `SNOOZE_ACTIVATED` includes the incident, camera, actor, and authoritative `snoozed_until` timestamp.
- `RE_ALARM` is broadcast when the current persisted deadline expires while the incident remains `Unverified`.
- A snooze request racing with another operator's Confirm or Dismiss uses the D-002 atomic expected-state rule.
- If the incident was already handled, the snooze request returns `409 Conflict`, and the client displays the same already-handled modal state defined in D-002.

#### Consequences

- Snoozing one incident consistently silences it across the command center while preserving per-user sound and volume choices.
- The latest snoozing operator's configured duration becomes the shared deadline.
- Correctness survives task cancellation races, process restarts, and duplicate expiry attempts without an extra revision column.
- Claude's in-memory-only snooze decision is superseded.

### D-005 — Database Evolution and SQLite Integrity

**Status:** Locked on July 12, 2026.

**Decision:** Current development databases are disposable and may be reset while the schema is evolving. Alembic becomes mandatory after the schema is decision-complete and before the first production deployment; the first migration represents the clean production schema rather than preserving every intermediate development shape.

#### Pre-Production Development Policy

- Continue using disposable local SQLite databases while schema decisions and implementation are in progress.
- Breaking development schema changes use the existing reset-and-reseed workflow.
- Do not create migrations for every intermediate design change.
- Do not build production-style backfills for current demo/test incidents.
- Preserve a development database only when a teammate explicitly identifies non-disposable local data before a reset.

#### Initial Production Migration

After all schema-affecting decisions are locked and their models are implemented:

1. Reset the development database and validate the complete schema.
2. Introduce Alembic configuration and versioned migration scripts.
3. Generate and manually review one initial production migration representing the full intended schema.
4. Test applying that migration to a new empty SQLite file.
5. Verify constraints, indexes, seed/bootstrap behavior, and schema revision.
6. Use that migration for the first production deployment.

`SQLModel.metadata.create_all()` may remain in fast isolated unit-test fixtures, but it is not a production schema-upgrade mechanism. Migration-specific tests must exercise real SQLite files through Alembic.

#### Post-Deployment Evolution

- Every schema change after the first production deployment requires a new reviewed migration.
- Production deployment checks the current database revision and refuses to run code against an older or unexpectedly newer schema.
- Ordinary application startup never silently changes the production schema.
- Before later production migrations, create and verify a WAL-safe backup; after migration, run integrity and schema-revision checks.
- After new-version data has been written, operational rollback restores the verified pre-migration backup instead of relying on a potentially destructive schema downgrade.

#### SQLite Connection Policy

Every production connection enables:

```text
foreign_keys = ON
journal_mode = WAL
synchronous = FULL
busy_timeout = 5000 milliseconds
```

- Transactions remain short.
- PDF generation, network calls, RTSP work, and WebSocket sends never occur while a database transaction is held.
- Background jobs use their own short-lived sessions.
- Run one Uvicorn application worker because WebSocket connections, scheduling, and live AI metrics are process-local in the selected architecture.
- A lock timeout returns a structured temporary-service error and is operationally logged rather than hanging indefinitely.

#### Database-Enforced Integrity

SQLite, not only Python validation, enforces:

- active-only uniqueness for camera names and channel IDs;
- unique AI `source_event_id` values;
- at most one open incident per camera;
- exactly one alarm-settings row per user;
- foreign-key protection for referenced users and cameras;
- allowed roles and lifecycle/status values;
- confidence, alarm volume, snooze duration, positive channel ID, and health-metric ranges.

Use restrictive foreign-key behavior for operational records because users and cameras are soft-deleted rather than physically removed.

#### Index and Query Policy

- Add focused indexes for incident status/time, camera/time, verifier/closer filters, audit filters/time, health timestamps, and active-camera status queries.
- Avoid speculative indexes that do not support an actual route or paper test.
- Confirm index use with SQLite query plans and the paper's 100,000-incident performance test.

#### UTC Storage

- Use one UTC-normalizing SQLAlchemy type or conversion layer because SQLite does not preserve timezone semantics merely from `DateTime(timezone=True)`.
- Normalize values on write and return UTC-aware values on read.
- API timestamps remain ISO 8601 UTC values, and frontend clients localize only for display.

#### Consequences

- Migration work is deferred until it will describe a stable production schema, avoiding throwaway migration chains.
- The current untracked/development database can be reset without legacy-data conversion work.
- The first real deployment is migration-managed from day one, allowing later upgrades without deleting production incidents.
- Existing database setup must add foreign-key enforcement and production-safe connection settings before release.

### D-006 — Authentication and Revocable Sessions

**Status:** Locked on July 12, 2026.

**Decision:** Use one database-backed, revocable eight-hour session represented by a signed JWT in a secure HTTP-only cookie. The same session authenticates REST and WebSocket traffic. Do not add short-lived access/refresh token rotation or one-time WebSocket tickets for this single-server, same-origin LAN application.

#### Session Record

Successful login creates an `auth_session` row containing:

- `session_id` — server-generated UUID used as the JWT `sid`.
- `user_id` — foreign key to the authenticated user.
- `created_at` and `expires_at` — UTC timestamps.
- `revoked_at` and `revocation_reason` — nullable revocation metadata.
- optional sanitized client metadata needed for security review, such as user agent and source IP.

The database session is authoritative. A correctly signed JWT is rejected when its session is missing, expired, or revoked.

#### JWT and Cookie

- Default absolute session lifetime is eight hours and remains configuration-driven.
- JWT identity uses immutable `user_id` in `sub`, never mutable username.
- Required claims include `sub`, `sid`, `role`, issued-at time, expiration, issuer, and audience.
- The database user's current role and active state remain authoritative; the role claim supports frontend initialization only.
- In production, the JWT cookie is `HttpOnly`, `Secure`, `SameSite=Strict`, host-only, and scoped to `/`.
- Plain HTTP cookies are permitted only for explicit localhost development configuration.
- Authentication responses use `Cache-Control: no-store`.
- The frontend does not place authentication credentials in `localStorage` or `sessionStorage`.

Because the cookie is HTTP-only, the login response or authenticated profile endpoint supplies the current user and role needed to render the UI; frontend JavaScript does not decode the session JWT directly.

#### Request Authentication

For every protected request, the backend:

1. verifies JWT signature, issuer, audience, and expiration;
2. loads the `auth_session` identified by `sid` and requires it to be active;
3. loads the user identified by `sub` and requires the account to be active;
4. authorizes using the current database role.

Cookie-authenticated unsafe HTTP methods validate the allowed `Origin`/same-origin context in addition to `SameSite=Strict`. State-changing behavior never uses `GET`.

#### Persistent Standby and Browser Recovery

- The persistent eight-hour cookie permits page reload and browser-crash recovery during an operator shift.
- No short idle timeout is imposed because the dashboard must remain able to receive alerts during extended standby.
- At absolute expiry, the user must authenticate again; there is no refresh-token endpoint.
- TC-S-203's four-hour standby scenario must pass within the configured session lifetime.

#### Logout and Security Revocation

`POST /api/auth/logout`:

1. revokes the current `auth_session`;
2. closes all WebSockets associated with that session;
3. clears the session cookie;
4. directs the frontend to clear private in-memory state and cached user data.

Self password change, administrator password reset, role change, and account deactivation/soft deletion revoke every session for the affected user and close their WebSockets. The user must log in again. Username/profile-only changes do not invalidate sessions because identity is based on `user_id`.

#### WebSocket Authentication

- The browser sends the same session cookie during the WebSocket handshake; no reusable token appears in the URL.
- The backend validates the handshake `Origin`, JWT, database session, user activity, and current authorization before accepting the connection.
- The connection manager maps each socket to both `user_id` and `session_id`.
- Logout or revocation closes matching sockets immediately.
- Periodic connection liveness/session checks close sockets whose session has expired or become invalid.
- Production WebSockets use WSS.

#### Password Handling

- Use Argon2id for passwords when the development database is next reset for the production schema.
- No bcrypt-to-Argon2 migration is required for disposable development accounts.
- Passwords are never stored, logged, audited, or transmitted in plaintext beyond the TLS-protected login/change request needed to verify them.
- Password validation remains server-side even when the frontend also provides immediate validation feedback.

#### Login Protection and Auditing

- Apply configurable login rate limiting using both source IP and normalized username dimensions.
- Wrong password, unknown username, and inactive account return the same generic authentication failure to reduce account enumeration.
- Successful and failed attempts are audited without passwords, JWTs, raw cookies, or other reusable credentials.
- Production REST and WebSocket traffic requires HTTPS/WSS even on the internal LAN.

#### Explicitly Rejected Complexity

For the selected single-server, same-origin deployment, do not add:

- 15-minute access tokens;
- refresh tokens or token rotation;
- `/api/auth/refresh`;
- separate refresh cookies;
- one-time WebSocket tickets;
- frontend multi-tab refresh coordination.

These may be reconsidered only if the deployment becomes internet-facing, cross-origin, or distributed across multiple backend instances.

#### Consequences

- Logout becomes real server-side revocation rather than client-side token deletion.
- Browser recovery and four-hour standby work without exposing a credential to JavaScript storage.
- Password, role, and account-security changes immediately terminate existing access.
- Current JWT creation, authentication dependencies, WebSocket handshake, and connection-manager data structures must be replaced.

### D-007 — Append-Only Activity Audit

**Status:** Locked on July 12, 2026.

**Decision:** Implement one local append-only activity-audit table for security- and operations-relevant human actions. Couple successful audit entries transactionally to their primary actions, record denied/failed attempts separately, and enforce immutability in both the API and SQLite. Do not add a cryptographic hash chain or separate audit service.

#### Audit Record

Each `audit_log` row contains:

- `audit_id` — integer primary key.
- `actor_type` — `user` or `system`.
- `user_id` — nullable user foreign key.
- `username` and `role` — nullable actor snapshots retained for historical readability.
- `action` — constrained action identifier.
- `target_type` — nullable entity category.
- `target_ref` — nullable text identifier.
- `result` — `success`, `denied`, or `failure`.
- `detail` — nullable sanitized JSON object.
- `request_id` — correlation identifier shared with operational logs.
- `source_ip` — nullable normalized client address where applicable.
- `created_at` — indexed UTC timestamp.

`target_ref` is text rather than integer so the same field can represent numeric database IDs, backup filenames, and session UUIDs.

#### Action Catalog

Authentication and session actions:

- `LOGIN_SUCCESS`
- `LOGIN_FAILURE`
- `LOGOUT`

Incident actions:

- `ALERT_CONFIRM`
- `ALERT_DISMISS`
- `ALERT_RESOLVE`
- `ALERT_CORRECTION`
- `ALERT_SNOOZE`

Camera actions:

- `CAMERA_CREATE`
- `CAMERA_UPDATE`
- `CAMERA_ENABLE`
- `CAMERA_DISABLE`
- `CAMERA_DELETE`

Reporting actions:

- `REPORT_EXPORT`, with the incident/dashboard/performance report type in `detail`.
- `AUDIT_EXPORT`

User and self-service actions:

- `USER_CREATE`
- `USER_UPDATE`
- `USER_ENABLE`
- `USER_DISABLE`
- `USER_ROLE_CHANGE`
- `USER_PASSWORD_RESET`
- `USER_PROFILE_UPDATE`
- `USER_PASSWORD_CHANGE`

Settings and recovery actions:

- `ALARM_SETTINGS_UPDATE`
- `BACKUP_TRIGGER`
- `RESTORE_TRIGGER`

AI detections, heartbeats, FPS/latency samples, and routine camera telemetry are excluded from the human activity audit. Incident records and structured operational logs cover those machine events.

When one request performs multiple distinct audited changes, create one row per semantic action. For example, renaming and disabling a camera creates both `CAMERA_UPDATE` and `CAMERA_DISABLE` rows in the same transaction.

#### Result and Transaction Semantics

- `success` means the primary action committed successfully.
- `denied` means authentication, authorization, validation, or current-state rules rejected the requested action.
- `failure` means execution began but an internal or infrastructure error prevented completion.
- A successful critical action and every required audit row commit in one database transaction.
- If a required success audit insert fails, the primary action rolls back.
- After the primary transaction has rolled back, a denied/failed attempt is recorded using a separate short transaction.
- If that separate audit write fails, the original action remains denied/failed and a critical structured operational error is emitted.

#### Detail and Redaction Policy

Audit `detail` may contain:

- safe changed field names and before/after values;
- incident status transitions;
- export format, filters, and generated row count;
- non-sensitive failure category;
- relevant cooldown or snooze deadlines.

Audit records never contain:

- plaintext passwords or password hashes;
- JWTs, cookies, session secrets, or reusable WebSocket credentials;
- internal API keys;
- DSS/VMS/RTSP credentials or credential-bearing URLs;
- raw exception stack traces;
- complete request headers or bodies when they may contain secrets.

#### Append-Only Integrity and Retention

- No application update or delete operation exists for audit records.
- SQLite triggers reject `UPDATE` and `DELETE` on `audit_log`.
- Schema migrations may replace those triggers only within the controlled migration process.
- Administrators have read/export access; Operators have no audit-viewer access.
- No automatic pruning is performed.
- Audit rows remain for the deployment lifetime and are included in database backups.
- A cryptographic chain/WORM service is not required because NFR-21 requires immutability against application users, not resistance to a root administrator replacing the physical database.

#### Viewer and Export

- `GET /api/audit-logs` provides stable newest-first pagination with action, user, result, target type/reference, date-range, and search filters.
- `GET /api/audit-logs/export?format=csv|pdf` uses the identical filter implementation.
- Audit exports record `AUDIT_EXPORT` with filters, format, and row count.
- The newly created export audit row is not included in the dataset snapshot currently being exported.
- Viewing ordinary audit pages is not itself audited to avoid recursive noise; exporting them is audited.

#### Consequences

- Existing route handlers must use shared transaction-aware audit helpers rather than ad hoc commits.
- Actor username/role snapshots preserve historical meaning after later profile or role changes.
- Failed logins can be recorded without a user foreign key while retaining the attempted normalized username and result.
- Tests must cover every action type, multi-action requests, rollback coupling, failure recording, trigger-enforced immutability, redaction, RBAC, filtering, and export behavior.

### D-008 — WebSocket Delivery and Recovery

**Status:** Locked on July 12, 2026.

**Decision:** Use the authenticated WebSocket as a low-latency notification channel while SQLite and REST remain authoritative. Provide isolated per-client delivery, bounded resource usage, connection liveness, and deterministic REST recovery without adding a broker or durable event stream to the selected single-worker deployment.

#### Versioned Event Envelope

Every server event uses:

```json
{
  "version": 1,
  "event_id": "event-uuid",
  "type": "ALERT_STATUS_UPDATE",
  "occurred_at": "2026-07-12T10:30:05Z",
  "data": {}
}
```

- `version` identifies the event contract version.
- `event_id` is a server-generated UUID used for client-side duplicate suppression.
- `type` selects the typed payload schema in `data`.
- `occurred_at` is the committed event's UTC timestamp.
- Domain-specific payloads use explicit response models and OpenAPI-adjacent documentation rather than arbitrary dictionaries.

#### Event Catalog

- `CONNECTION_READY`
- `NEW_DETECTION`
- `ALERT_STATUS_UPDATE`
- `CAMERA_STATUS_UPDATE`
- `SNOOZE_ACTIVATED`
- `RE_ALARM`

Operational events are delivered to authenticated active Operators and Administrators. Domain mutations continue to use audited REST endpoints; clients do not Confirm, Dismiss, Snooze, Resolve, or edit configuration through WebSocket messages.

#### Connection Ownership and Limits

- Authenticate the handshake using D-006's secure session cookie and allowed `Origin`.
- Track every connection by both `user_id` and `session_id`.
- Logout or security revocation closes the matching session/user connections.
- Per-user, per-session, and total connection limits are configuration-driven with deployment-safe defaults; Claude's fixed ten-connection ceiling is not retained.
- Reject excess connections using a documented policy close code without displacing established operational dashboards.

#### Isolated Outgoing Queues

- Each accepted connection owns a bounded `asyncio.Queue` and one sender task.
- Broadcasting places the committed event independently into each eligible queue and does not await sequential network sends.
- Sender operations use bounded timeouts.
- A repeatedly failing sender or full queue closes only that slow connection and triggers client reconnection/recovery.
- One frozen workstation cannot delay alerts to other operators.

#### Ordering and Delivery Semantics

- Enqueue events only after the related database transaction commits.
- Preserve FIFO ordering within each connection's queue.
- Delivery while connected is best-effort and at-most-once; the client uses `event_id` to ignore duplicates if a reconnect race presents one.
- Do not claim durable replay or exactly-once delivery.
- A commit followed by backend failure disconnects clients; reconnect recovery reads the committed database state.

#### Initial Load and Reconnect Recovery

After every accepted initial connection or reconnection:

1. server sends `CONNECTION_READY` with connection and server-time metadata;
2. frontend fetches all `Unverified` and `Ongoing` incidents;
3. frontend fetches current desired/observed camera states;
4. frontend reconstructs active alarm and snooze behavior from persisted incident deadlines;
5. frontend merges concurrently received events using incident `updated_at` and camera `config_version`, preventing an older snapshot from replacing newer event state.

The frontend also performs a lightweight periodic active-state reconciliation as a safety net. WebSocket remains the primary path for the paper's sub-two-second alert requirement.

#### Liveness and Reconnection

- Configure protocol ping/pong intervals and timeouts.
- Periodically confirm that the underlying D-006 database session remains valid.
- Close connections when the session expires, is revoked, or the user becomes inactive.
- Frontend reconnects with bounded exponential backoff and jitter.
- Authentication/session failures stop automatic reconnection and return the user to login.
- Network/transient closures reconnect and then execute the complete recovery sequence.

#### Explicitly Rejected Complexity

For the locked single-worker architecture, do not add:

- Redis Pub/Sub;
- Kafka, RabbitMQ, or another message broker;
- client acknowledgement/retry protocols;
- a durable WebSocket event/replay table;
- cross-instance fan-out.

Reconsider those components only if the backend becomes a multi-instance deployment where process-local queues can no longer reach every client.

#### Consequences

- Replace the current flat list and sequential broadcast loop with session-aware connection records and per-connection sender queues.
- All event types require typed payload contracts and frontend reducer behavior.
- Recovery tests must cover missed events, server restart, browser crash, stale snapshots, duplicate event IDs, slow clients, queue overflow, logout, and session expiry.
- Performance testing must demonstrate that a slow client does not prevent another client from receiving a new alert within two seconds.

### D-009 — System Health, Hardware Profiles, and Camera KPIs

**Status:** Locked on July 12, 2026.

**Decision:** Separate live in-memory sampling from compact historical persistence, support unavailable and multi-GPU sensors honestly, add CPU-temperature and GPU-memory history, and expose camera inventory/status counts in number-only Camera Management KPI modals. Validate the demo laptop honestly while keeping the implementation configuration-ready for the paper's enterprise target.

#### Hardware Profiles and Evidence Boundary

Demo/development profile:

- Intel Core i5-12500H laptop.
- NVIDIA RTX 3050 Ti Laptop GPU with 4 GB GDDR6.
- One configured GPU inference worker.
- Conservative model batch size and stream count established through measurement.
- Cross-platform hardware collection suitable for the actual Windows demo environment.

Production-target profile:

- Linux edge server.
- Configuration-driven multi-GPU inventory and one inference process per configured GPU, as locked in D-003.
- Dynamic camera assignment and larger batch/stream capacity without code changes.

The laptop demonstration validates only the measured laptop workload. Enterprise camera capacity, eight-GPU behavior, thermal stability, and restart timing remain **Needs Evidence** until tested on representative production hardware. Documentation and the paper must distinguish “demo-validated” from “production-target/configuration-ready.”

Portable `.pt` weights remain the source model. TensorRT `.engine` artifacts are compiled and selected per compatible CUDA/TensorRT/GPU environment; a laptop-generated engine is not assumed compatible with future L4 hardware.

#### Sampling Layers

- A background collector refreshes one in-memory live hardware sample every five seconds by default; the interval is configurable.
- The frontend polls `GET /api/system/health/live` every 10–15 seconds, satisfying NFR-05 without requiring WebSocket telemetry.
- Every five minutes, a historical subset of the latest valid sample is written to SQLite.
- Raw five-minute rows are retained for 48 hours.
- Raw rows are aggregated at the start of each UTC hour and hourly rows are retained for 30 days.
- Live samples are overwritten in memory and are not individually persisted.

This prevents every workstation from independently querying OS/GPU drivers and avoids high-frequency database growth.

#### System Health Endpoints

- `GET /api/system/health/live`
- `GET /api/system/health/history?range=48h`
- `GET /api/system/health/history?range=30d`

Both authenticated roles may access them. History is returned oldest-to-newest using one consistent response point shape for raw and hourly ranges.

#### Live Metrics

The typed live response contains:

- host/OS uptime;
- backend-process uptime;
- CPU usage and nullable CPU temperature;
- RAM usage;
- configured data-volume disk total, used, available, and percentage;
- per-GPU index/name, usage, temperature, memory used/total, and memory percentage;
- aggregate GPU utilization, maximum GPU temperature, and highest per-GPU memory percentage;
- average inference latency and FPS from fresh D-003 heartbeats;
- `sample_camera_count`, identifying how many fresh actively reporting cameras contributed to AI averages;
- collection timestamp, freshness/availability flags, warnings, and overall `healthy`, `degraded`, or `critical` state.

System Health does not duplicate Camera Management KPI cards. `sample_camera_count` is contextual text beside FPS/latency, not another camera KPI.

#### Missing Sensor Semantics

- Unavailable CPU temperature is `null` with an explicit availability flag.
- No available GPU produces an empty per-GPU list and null GPU aggregates.
- Sensor/provider failure does not make the complete endpoint fail when other metrics remain available.
- Missing measurements are never represented as zero.
- Historical charts render missing values as gaps.
- A stale retained sample is marked stale with its original collection timestamp; it is not presented as fresh.

#### CPU Temperature and GPU Memory UI

- CPU temperature is included in live System Health and historical charts when available.
- GPU Memory is added as a live System Health KPI because VRAM is a primary limit on the 4 GB demo GPU.
- The KPI shows the highest-utilized GPU's percentage and used/total memory.
- Clicking GPU Memory opens a number-only/current-detail modal listing utilization, temperature, and memory for each GPU; one row appears on the laptop and multiple rows on future hardware.
- CPU-temperature unavailability is shown as “Unavailable,” not an error or zero-degree reading.

#### Historical Raw and Hourly Metrics

Each raw five-minute row stores:

- CPU usage;
- RAM usage;
- average available-GPU utilization, nullable;
- maximum available-GPU temperature, nullable;
- CPU temperature, nullable;
- highest per-GPU memory usage percentage, nullable.

Each hourly row stores:

- average CPU, RAM, and available-GPU utilization;
- average and peak CPU temperature;
- peak GPU temperature;
- average and peak of the five-minute highest-GPU memory percentages;
- `sample_count` used in the rollup.

Disk, uptime, inference latency, and FPS remain live-only. Live per-GPU used/total MB remains available, while compact historical VRAM charts store the worst-device percentage needed to identify memory pressure.

#### Multi-GPU Aggregation

- Live responses expose each GPU independently.
- Aggregate GPU utilization is the mean of available GPU utilization values.
- Aggregate GPU temperature is the maximum device temperature.
- Aggregate GPU-memory pressure is the maximum device memory percentage, not an average that could hide one nearly exhausted GPU.
- Historical aggregate semantics are identical across the one-GPU demo and future multi-GPU deployment.

#### Scheduler Policy

Within the single worker locked in D-005:

- live collection runs every five seconds;
- raw persistence runs every five minutes;
- hourly rollup runs at each UTC hour boundary;
- raw pruning runs hourly;
- hourly pruning runs daily.

Jobs use UTC, `max_instances=1`, coalescing, bounded misfire grace, idempotent hourly keys, and short-lived database sessions. Missed periods do not fabricate samples; `sample_count` makes incomplete hours visible.

#### Configurable Warning Defaults

- GPU temperature critical: 85°C.
- RAM critical: 95%.
- Disk warning: 80%; disk critical: 90%.
- AI heartbeat stale: more than 10 seconds.
- CPU/GPU usage, CPU temperature, and VRAM warning/critical thresholds remain profile-configurable and are finalized using measured hardware behavior.

The backend returns warning code, severity, measurement, and threshold. The frontend controls visual presentation.

#### Camera Management KPI Population

All camera KPI counts exclude soft-deleted rows and use all remaining camera configurations as the common population:

```text
Total Cameras = all cameras where is_active = true
Enabled + Disabled = Total Cameras
Connected + Disconnected + Reconnecting + Unresponsive = Total Cameras
Active + Paused + Inactive + Unresponsive = Total Cameras
```

Configuration, connection, and AI state are independent dimensions. Disabled cameras normally settle to `Disconnected` and `Inactive`, but those statuses are not used to infer whether a camera is disabled. A temporarily reconciling camera may briefly have desired and observed states that differ.

Top KPI cards are:

- Total Cameras
- Enabled Cameras
- Network Connected
- Active Detection

`Total Cameras` needs no modal. Clicking the other KPI cards opens number-only summaries:

- Enabled Cameras: Enabled and Disabled.
- Network Connected: Connected, Disconnected, Reconnecting, and connection-Unresponsive.
- Active Detection: Active, Paused, Inactive, and AI-Unresponsive.

No camera records or pagination appear in these KPI modals. Existing page filters remain the mechanism for finding individual matching cameras. Connection-Unresponsive and AI-Unresponsive remain distinct statuses even when one camera has both.

#### Camera KPI API Shape

The Camera Management response exposes global counts separately from the paginated/filtered table:

```json
{
  "kpis": {
    "total": 10,
    "enabled": 8,
    "network_connected": 7,
    "active_detection": 6
  },
  "breakdowns": {
    "connection": {
      "connected": 7,
      "disconnected": 2,
      "reconnecting": 1,
      "unresponsive": 0
    },
    "ai": {
      "active": 6,
      "paused": 1,
      "inactive": 3,
      "unresponsive": 0
    }
  }
}
```

Disabled is derived as `total - enabled`; a separate camera list is not returned for any breakdown.

#### Operational Probes

- `GET /healthz/live` proves only that the backend process responds.
- `GET /healthz/ready` verifies database access and required initialization.
- Probes expose no detailed telemetry or sensitive configuration and remain separate from authenticated dashboard health data.

#### Verification

- Unit and scheduler tests mock OS, time, NVML, missing sensors, and heartbeat providers.
- Laptop integration tests record actual stream count, resolution, batch size, FPS, latency, VRAM/RAM, temperatures, alert latency, and test duration.
- Multi-GPU assignment and telemetry are tested with simulated providers until representative hardware exists.
- Twenty-four-hour laptop endurance results do not constitute proof of enterprise-scale capacity.
- The final paper/presentation must identify which results are measured, simulated, or pending production-hardware acceptance.

### D-010 — Reports, PDF/CSV, and Retraining Exports

**Status:** Locked on July 12, 2026.

**Decision:** Generate normal filtered CSV/PDF reports synchronously using shared query contracts and `fpdf2`. Use a persisted, bounded local export job only for oversized requests and snapshot-heavy retraining packages. All artifacts remain on the edge server and all export attempts are audited.

#### PDF Implementation

- Use `fpdf2` for programmatic table-based PDF generation on both the Windows demo laptop and future Linux server.
- Do not use WeasyPrint because its HTML/CSS rendering and native graphical dependencies are unnecessary for the required reports.
- Keep PDF layout in shared backend report components for headers, filter summaries, tables, footers, pagination, and value formatting.

#### Normal Export Endpoints

- `GET /api/alerts/export?format=csv|pdf`
- `GET /api/analytics/export/dashboard?format=csv|pdf`
- `GET /api/analytics/export/performance?format=csv|pdf`
- `GET /api/audit-logs/export?format=csv|pdf`

`format` defaults to `csv`. These endpoints are synchronous for requests within configured format-specific limits.

#### Shared Filtering and Sorting

- List/view and export routes use the same reusable filter and allowlisted sorting builders.
- An export must match the screen's active date, camera, status, user, search, and sort criteria exactly.
- `sort_by` accepts only documented fields and `sort_order` accepts only `asc` or `desc`; clients never provide raw SQL expressions.
- Count and export queries use the same status definitions locked in D-002.

#### PDF Contract

Every PDF contains:

- ADAS/report title and approved branding asset;
- generated UTC timestamp plus configured local-display timestamp;
- requesting user's display identity;
- applied filters and sorting;
- KPI/summary section where relevant;
- repeated table headings, wrapped values, and stable `N/A` rendering;
- current page and total page count;
- a report-specific filename.

PDFs never contain credentials, private filesystem paths, raw exceptions, or internal service configuration.

Report contents are:

- Incident report — filtered incident records and HITL lifecycle fields.
- Dashboard report — filtered KPIs, location frequency, and peak-time results.
- Performance report — global and per-camera AI-performance metrics.
- Audit report — filtered append-only activity records.

#### CSV Contract

- Encode deterministic UTF-8 CSV with documented, stable columns.
- Prefer raw machine-readable values over presentation-only strings where practical.
- Stream database rows for large synchronous CSV responses rather than materializing the entire dataset.
- Neutralize values beginning with `=`, `+`, `-`, or `@` to prevent spreadsheet formula injection.
- Performance CSV includes both global and per-camera metrics.
- Empty datasets still produce valid headers and report metadata where applicable.

#### Retraining Package

`POST /api/exports/retraining` creates a local ZIP containing:

```text
manifest.csv
snapshots/
```

Only human-labeled incidents are included:

- `Ongoing` and `Resolved` map to `true_positive`.
- `Dismissed` maps to `false_positive`.
- `Unverified` is excluded.

The manifest contains `log_id`, `source_event_id`, camera identity, detection timestamp, model confidence, final human label, snapshot filename/checksum/availability, and verification/closure metadata. Missing snapshots are explicitly represented in the manifest and job result rather than silently omitted.

#### Synchronous Limits and Performance

Initial configurable limits are:

- PDF: 10,000 rows.
- CSV: 50,000 rows.

The paper's filtered 10,000-row, 30-day report must be benchmarked on the demo laptop to initiate download within five seconds. Limits may be lowered only if measured evidence and the final requirements are updated; they are not assumed satisfied from unit tests.

#### Persisted Local Export Jobs

Large or retraining exports use:

- `POST /api/exports/jobs`
- `GET /api/exports/jobs/{job_id}`
- `GET /api/exports/jobs/{job_id}/download`

An `export_job` row stores job ID, requester, report type/format, sanitized filters/sorting, status, progress counts, protected artifact path, timestamps, and safe failure category.

- Job creation returns promptly with `queued` status.
- One bounded local worker processes heavy exports on the demo profile; concurrency remains configurable for future hardware.
- No Celery, Redis, message broker, cloud queue, or cloud storage is introduced.
- Pending/interrupted jobs are safely restarted from the beginning when supported or explicitly marked failed after backend restart; they never remain indefinitely `processing`.
- Job artifacts live outside public static directories and downloads require authorization.
- Generated artifacts expire after a configurable period and are deleted by cleanup; source incidents and snapshots are never deleted by export cleanup.
- The durable audit record remains after artifact expiration.

#### Audit Semantics

- Every export records report type, format, filters/sorting, row/item count, synchronous/job mode, job ID if applicable, result, and safe failure category.
- `AUDIT_EXPORT` is selected from a stable dataset snapshot before its own new audit entry is committed, preventing recursive inclusion.
- A successful asynchronous audit entry means the artifact was generated and made available, not that a browser completed downloading every byte.

#### Verification

- Verify exact screen/export parity for every filter and sorting combination.
- Test CSV escaping, spreadsheet-formula neutralization, streaming, and stable columns.
- Parse generated PDFs to verify metadata, headings, tables, pagination, and empty states.
- Test row limits, job authorization, progress/failure states, restart handling, artifact expiration, and cleanup.
- Verify retraining labels, checksums, missing-snapshot reporting, safe ZIP paths, and local-only storage.
- Measure the five-second requirement on the actual demo profile and clearly label results that remain pending production-hardware validation.

### D-011 — Backup, Restore, Restart, and Archival

**Status:** Locked on July 12, 2026.

**Plain-language companion:** See `backup_restore_explained.md` for the detailed learning-oriented explanation approved with this decision.

**Decision:** Create verified WAL-safe backups while the application remains online, but restore a database only while backend and AI services are stopped. Every restore keeps an emergency rollback copy. Use cross-platform Python maintenance logic with PowerShell/manual demo operation and restricted systemd production orchestration.

#### Local Online Backup

- Use Python's SQLite `Connection.backup()` API; do not copy a live `adas.db` directly and do not require the external `sqlite3` CLI.
- `POST /api/system/backups` creates a manual backup and `GET /api/system/backups` lists verified restore points; both are Admin-only.
- Write a new backup to a temporary path, close it, validate it, then atomically rename it to its final protected filename.
- Prevent overlapping backup operations; a concurrent request receives a conflict response.
- Check available disk space before beginning and never remove an older valid backup because a new backup failed.

#### Backup Metadata and Validation

Each backup has a sidecar manifest containing:

- random backup ID and safe filename;
- UTC creation timestamp;
- manual/scheduled/pre-restore origin;
- application version and Alembic schema revision;
- file size and SHA-256 checksum;
- validation results.

Daily/manual backup validation runs `PRAGMA quick_check`, `PRAGMA foreign_key_check`, and checksum verification against the completed backup file. Restore candidates and weekly archives additionally run full `PRAGMA integrity_check`. A file is not listed as a valid restore point unless required checks pass.

#### Retention

Initial configurable defaults are:

- 30 scheduled daily backups;
- 10 manual backups;
- emergency pre-restore backup retained until restore success is verified.

Pruning occurs only after a new valid backup exists. Selected restore candidates and active emergency rollback files cannot be pruned.

#### Restore Authorization and Request

- `POST /api/system/restores` initiates restore and `GET /api/system/restores/latest` reports the latest outcome.
- Only an active Administrator may restore.
- Require current administrator password and explicit confirmation containing the selected backup ID.
- Validate that the ID maps to a manifest-listed file inside the configured backup directory; never accept a client filesystem path.
- The API revalidates metadata, writes a protected restore-request file via atomic rename, audits `RESTORE_TRIGGER`, broadcasts planned maintenance, and returns `202 Accepted`.
- FastAPI does not replace its own active database and does not receive unrestricted root/sudo command execution.

#### Offline Restore and Rollback

A restricted external maintenance process:

1. stops the AI supervisor;
2. stops FastAPI and waits for database connections to close;
3. creates and verifies an emergency backup of the current database;
4. verifies the selected backup's checksum, SQLite integrity, foreign keys, and compatible schema revision;
5. restores to a temporary database path and validates it again;
6. removes obsolete WAL/SHM sidecars only while services are offline;
7. atomically replaces the primary database;
8. starts FastAPI and waits for `/healthz/ready`;
9. starts the AI supervisor and waits for a fresh heartbeat;
10. records and exposes the final restore result.

If backend readiness or required startup validation fails, the process stops services, restores the emergency pre-restore database, restarts the original system, and records a rollback outcome. A failed restore may not leave the system silently half-restored.

#### Scheduled Backup and Daily Restart

- Default maintenance time is configurable, initially 3:00 AM in deployment-local time.
- Complete and verify the online daily backup before beginning restart downtime.
- Broadcast planned maintenance, gracefully stop AI ingestion, restart backend/AI services, wait for backend readiness and AI heartbeat, and record measured durations.
- Backup duration is measured separately from service restart downtime.
- The paper's under-ten-second restart remains a benchmark target, not a presumed result. Report the laptop's actual model-load, service-ready, and camera-recovery timings.

#### Demo and Production Orchestration

- Implement backup, validation, restore, and rollback as cross-platform Python maintenance commands.
- Windows/demo uses explicit PowerShell/manual wrappers and does not pretend to have systemd.
- Linux/production uses restricted systemd service/timer units that can perform only the approved ADAS maintenance workflow.
- Core file validation and replacement logic is shared across profiles.

#### Weekly Air-Gapped Archive

Provide an archival command that builds from a verified database backup and includes:

- database backup and manifest;
- incident snapshots referenced by that backup;
- portable `.pt` model weights;
- checksums and a missing-file report.

Never include `.env`, session/JWT secrets, VMS/RTSP credentials, or credential-bearing configuration. Copy the result to a configured mounted destination; physical NAS administration and security remain the CDRRMO owner's responsibility. The demo may target a controlled local/removable directory.

#### Audit and Verification

- Audit manual backup and restore requests/results without filesystem secrets.
- Test concurrent writes during backup, insufficient space, interrupted backup, corrupt checksum, SQLite/FK failure, unsafe IDs/path traversal, interrupted restore, readiness failure, automatic rollback, offline WAL/SHM cleanup, retention, and archive completeness.
- Measure the paper's 60-second restore target on the demo profile and retain the biannual production restore-drill procedure.
- Clearly distinguish simulated/demo recovery evidence from eventual production-hardware acceptance.

#### Consequences

- Claude's direct shell-oriented restore flow is replaced by reusable Python maintenance logic and a restricted external orchestrator.
- Backup files become verified restore points rather than unvalidated copies.
- A destructive restore cannot be started by one accidental click and always has a tested rollback path.
- The application supplies archive tooling while physical air-gapped storage ownership remains external under D-001.

### D-012 - AI Detection-Event Pipeline and AI-Owner Handoff

**Status:** Locked on July 12, 2026, with the AI-owned tuning gate below.

**Companion handoff:** See `ai_engine_detection_pipeline_handoff.md` for the current-code comparison, rationale, alternatives, paper/test conflicts, hardware tradeoffs, and AI-owner review checklist.

**Decision:** Lock the cross-component reliability contract for frame scheduling, pause behavior, snapshot storage, idempotent event delivery, and demo/production configuration. The AI owner has final technical approval over confidence and temporal-qualification values, model artifacts, batch sizing, and measured camera capacity.

#### Authority Boundary

The following are locked system and backend-integration invariants:

- bounded latest-frame buffering rather than unbounded per-camera frame queues;
- configurable 10-15 FPS inference scheduling and measured profile limits;
- pausing YOLO inference and alert generation while continuing to drain the RTSP stream into the latest-frame buffer;
- safe relative snapshot keys, validated atomic image writes, and authenticated evidence retrieval;
- one durable `source_event_id` per qualified event, persistent local delivery, and idempotent backend retries;
- configuration-driven model, device, batch, preview, endpoint, secret, snapshot, and outbox behavior;
- separate demo-validated and production-target evidence.

The AI owner must approve or amend, using representative validation evidence:

- the effective confidence threshold: the paper-test baseline is `0.75`, while the current prototype uses `0.90`;
- whether temporal qualification is enabled and its exact rule; `3` qualifying detections in the latest `5` processed frames is the proposed starting point, not an unmeasured model claim;
- the exact model artifact, image size, batch size, target FPS, and supported stream count for each hardware profile.

An evidence-backed change to those AI-owned parameters does not reopen the locked safety, idempotency, storage, or state-control invariants. It must be recorded in this decision and reconciled with the paper and tests before implementation is called complete.

#### Frame Ingestion and Inference Scheduling

- Each camera keeps at most one consumable latest frame; a newer frame replaces an older unprocessed frame.
- The demo profile initially targets 10 inference frames per second per active camera. Production may target up to 15 only after hardware measurement.
- Target FPS, batch size, GPU device, model artifact, and preview mode are configuration-driven.
- The scheduler samples the newest available frame per camera; it does not build latency-producing frame queues while waiting for a GPU batch.
- A pause stops inference, temporal qualification, and event generation for that camera, but capture continues reading and replacing/discarding frames so resume begins with current footage.
- Entering or leaving pause, reconnecting, or applying a relevant configuration change clears any pre-existing qualification window.
- Disabling or deleting a camera is different from pausing it: the runtime and RTSP connection are stopped and resources are released.

The drain-on-pause behavior intentionally clarifies and revises paper test TC-I-202, whose current wording says the worker ceases frame ingestion. Its acceptance wording must instead verify that YOLO inference/event generation ceases while bounded RTSP draining continues. This avoids stale footage while still removing paused-camera GPU inference load.

#### Detection Qualification

- Confidence filtering remains mandatory and configuration-driven.
- `0.75` is the paper-test baseline, but it is not treated as calibrated merely because it appears in a test table.
- The proposed temporal rule is at least three qualifying detections among the latest five processed frames.
- If that rule is approved, retain only qualification metadata and the best annotated candidate frame rather than five full frame copies per camera.
- On qualification, use the highest-confidence annotated candidate, generate one UUID `source_event_id`, pause that camera's inference immediately, save the evidence, and enqueue the event for delivery.
- A camera cannot generate another event while the qualified event is pending or the backend's desired state remains Paused.

Single-frame, consecutive-frame, and M-of-N qualification must be compared using event-level precision, recall, false-alert rate, time-to-qualify, and total detection-to-dashboard latency. Model mAP and IoU do not by themselves select an alert confidence threshold.

#### Snapshot Contract

- Configure one absolute snapshot root on the edge host, but never send or store that private root in an incident payload.
- Store a normalized relative `snapshot_key`, for example `2026/07/12/camera_5/<source_event_id>.jpg`.
- Reject absolute paths, traversal segments, and paths that resolve outside the configured root.
- Encode/write to a temporary file, verify success, then atomically rename it into place.
- Replace the public static snapshot mount with authenticated retrieval through `GET /api/alerts/{log_id}/snapshot`.
- The frontend receives an authorized URL based on `log_id`; it never receives an operating-system path.

#### Durable Webhook Delivery

The AI event request contains at least:

```json
{
  "source_event_id": "uuid",
  "camera_id": 5,
  "detected_at": "2026-07-12T10:30:00Z",
  "snapshot_key": "2026/07/12/camera_5/event-uuid.jpg",
  "confidence_score": 0.87
}
```

- Persist the event in a local AI-owned outbox before relying on network delivery.
- Send immediately when healthy, then use bounded exponential backoff with jitter for retryable failures.
- Reuse the same payload and `source_event_id` for every attempt and resume pending delivery after AI-process restart.
- Use a bounded delivery worker rather than creating an unbounded daemon thread for every event.
- Keep inference paused while delivery is pending; continue draining the RTSP stream.
- Remove an outbox entry only after an acknowledged or explicitly terminal outcome; quarantined artifacts remain available for diagnosis and bounded cleanup.

Backend response semantics are:

- `201 Created` - new incident committed; acknowledge the outbox event.
- `200 OK` - idempotent retry; return the incident previously created for that `source_event_id` and acknowledge it.
- `409 Conflict` - another open incident owns the camera; return its current state, keep desired pause, and stop blind retries of the conflicting event.
- `404 Not Found` - camera is removed, inactive, or disabled; reconcile and stop that camera runtime.
- `401/403` - configuration/security fault; stop rapid retry flooding and raise a critical operational error.
- `422 Unprocessable Entity` - non-retryable payload defect; quarantine it for diagnosis.
- network errors and `5xx` - retry from the persistent outbox.

#### Demo and Production Profiles

Demo laptop:

- portable `.pt` weights or a TensorRT engine compiled for the RTX 3050 Ti environment;
- one GPU worker;
- initial 10 FPS target and conservative batch/stream capacity established by measurement within 4 GB VRAM;
- optional OpenCV windows only when demo preview is enabled.

Production target:

- headless operation;
- TensorRT engines compiled for the actual production CUDA, TensorRT, and GPU combination;
- one model instance per configured GPU with dynamic camera assignment and bounded batching under D-003;
- measured capacity rather than an assumed 418-camera/eight-L4 claim.

Portable `.pt` weights remain the source artifact. An `.engine` built for the laptop is never assumed portable to L4 or another runtime.

#### Verification and Evidence Gate

Engineering tests cover latest-frame replacement, controlled FPS, pause/resume freshness, qualification-state reset, safe paths, failed/partial image writes, persistent retry, restart recovery, idempotent delivery, response classification, camera disable/delete during retry, and no duplicate event while paused.

Hardware/integration evidence records model identity, threshold, qualification rule, stream resolution/count, batch size, actual per-camera FPS, inference latency, VRAM/RAM, temperature, and detection-to-dashboard latency on the demo laptop.

Model accuracy, mAP/IoU, nighttime/rain/glare behavior, and final threshold/qualification calibration remain AI-owner evidence. The implementation may not claim those passed based only on unit mocks.

#### Consequences

- The current one-shot, absolute-path, hardcoded prototype is replaced by a recoverable and portable event pipeline.
- Paused cameras retain some network and CPU decoding cost, but free GPU inference capacity and resume from live footage.
- Paper tests TC-I-202 and TC-U-205 require contract wording updates for drain-on-pause and AI-generated `source_event_id` respectively.
- The backend team owns storage authorization and idempotent incident creation; the AI owner owns model behavior and measured inference parameters; both teams jointly verify the end-to-end contract.

## Open Decisions

D-012's cross-component contract is locked. Before implementation of its model-behavior layer, the AI owner must return the selected confidence threshold, temporal-qualification rule, demo model artifact, batch/FPS profile, and supporting evidence or an explicit test plan. Those values will be recorded as an amendment to D-012 rather than silently assumed.
