# 11 — From Five Tables to Ten

> **One-liner:** ADAS kept its five core operational and telemetry entities and added five durable stores for sessions, alarm preferences, audit evidence, asynchronous exports, and searchable help.
> **Panel risk:** high — the panel may read a larger schema as evidence that the first design failed, or challenge the performance and necessity of the additions.

## 1. What it is

A database table keeps one kind of information in a durable, structured form.

At the 28 April 2026 defense, the backend model had five table-backed entities:
users, cameras, detected incidents, raw system-health readings, and hourly
system-health summaries.

Today the schema has ten persistent relational entities. The original five still
cover those same core jobs; the additional five hold five different kinds of
state: active login sessions, per-user alarm preferences, cross-system audit
events, asynchronous export jobs, and help articles.

That is requirement-driven growth. The new entities correspond to capabilities
specified in the paper’s functional and non-functional requirements. The team
should not say that a table count of ten was itself a requirement: the
requirements call for the stored behavior, and the separate tables are the
chosen way to persist it.

The useful answer to “was the first schema wrong?” is that the five original
entities remain in the current data model. The schema gained distinct records
as the software implementation filled out the user, audit, reporting, and help
workflows already described in the requirements.

## 2. Where it lives

### In the paper

- Chapter III, “Requirements Analysis,” Table 2 contains the functional
  requirements cited for the new entities.
- Chapter III, “Requirements Analysis,” Table 3 contains NFR-06, which governs
  report generation and export scalability.
- Chapter III, “Requirements Analysis,” Table 7 contains NFR-19 for session
  security and NFR-21 for audit-trail integrity.
- Chapter III, “System Architecture and Design,” Figure 7 is the database ERD.
- Chapter III, “Data Dictionary,” Tables 9–18 describe the ten current
  relational entities.
- The ERD text groups those entities into four domains: core detection;
  security and identity; governance and async jobs; documentation and
  telemetry. It also explains the user-to-session, user-to-settings,
  user-to-audit, and user-to-export relationships.
- The Help Article discussion describes `help_article_fts` as a full-text
  search index synchronized with the help table. It is a virtual index, not an
  eleventh domain entity in the paper’s count.
- Chapter III, “Project Development Model,” describes the software track as
  iterative refinement of the dashboard, backend, database operations,
  incident logging, reports, and alert workflow against the established
  requirements.

### In the code

- Historical defense-era model snapshot: `backend/app/models.py` at commit
  `f964741` (2026-04-26) declares the five original classes at lines 46, 160,
  236, 292, and 314.
- The first database-model commit is `f6c6b12` (2026-04-24), titled “add
  initial FastAPI backend db models and schemas, sqlite init, and admin
  seeding.” It already contains all five original model classes.
- Current core models: `backend/app/models/user.py:30`,
  `backend/app/models/camera.py:28`, `backend/app/models/detection.py:21`, and
  `backend/app/models/health.py:20` and `backend/app/models/health.py:61`.
- Current added models: `backend/app/models/user.py:81` and
  `backend/app/models/user.py:108`; `backend/app/models/audit.py:49`;
  `backend/app/models/export.py:9`; and `backend/app/models/help.py:12`.
- The session lifecycle is in `backend/app/services/sessions.py:14`,
  `backend/app/services/sessions.py:38`, `backend/app/services/sessions.py:52`,
  and `backend/app/services/sessions.py:63`.
- Alarm settings are read and updated by
  `backend/app/api/routes/settings.py:31` and
  `backend/app/api/routes/settings.py:52`; new accounts receive a settings
  row in `backend/app/api/routes/users.py:277`.
- Audit rows are constructed by `backend/app/services/audit.py:76`; the model
  defines append-only triggers in `backend/app/models/audit.py:92` and
  `backend/app/models/audit.py:99`, then attaches them at
  `backend/app/models/audit.py:117`.
- Export-job creation is in `backend/app/services/reports/jobs.py:588` and
  `backend/app/services/reports/jobs.py:598`; job routes begin at
  `backend/app/api/routes/exports.py:54`.
- Help article search is in `backend/app/services/help.py:214` and
  `backend/app/services/help.py:283`; the FTS5 virtual table is created in
  `backend/app/models/help.py:43`.
- The history command requested for this guide,
  `git log --since="2026-04-28" -- backend/app/models/`, shows the five new
  model tables first appearing together in `5a95eaf` on 2026-08-09.

## 3. How it works

### The five at the April defense

| April model entity   | What it held                                                     | Current paper table            |
| -------------------- | ---------------------------------------------------------------- | ------------------------------ |
| `User`               | User identity, credentials, role, and account state              | Table 9: User                  |
| `Camera`             | Camera configuration and operating state                         | Table 10: Camera               |
| `DetectionLog`       | Detected incident, evidence snapshot, confidence, and HITL state | Table 11: Detection Log        |
| `SystemHealthRaw`    | Individual persisted system-health readings                      | Table 12: System Health Raw    |
| `SystemHealthHourly` | Hourly system-health summaries                                   | Table 13: System Health Hourly |

The defense-era monolith’s table classes are visible in `f964741` at
`backend/app/models.py:46`, `backend/app/models.py:160`,
`backend/app/models.py:236`, `backend/app/models.py:292`, and
`backend/app/models.py:314`.

Those original entities map to existing requirements: user access and account
management (FR-01 to FR-03), camera and incident operations (FR-04 to FR-14),
and system health and telemetry (FR-15 and NFR-05). They are still part of the
current ERD and data dictionary.

### The ten today

| Paper data-dictionary table    | Domain in the ERD                | First-five or addition |
| ------------------------------ | -------------------------------- | ---------------------- |
| Table 9 — `user`               | Security and identity            | Original               |
| Table 10 — `camera`            | Core detection operations        | Original               |
| Table 11 — `detection_log`     | Core detection operations        | Original               |
| Table 12 — `sys_health_raw`    | Independent telemetry            | Original               |
| Table 13 — `sys_health_hourly` | Independent telemetry            | Original               |
| Table 14 — `audit_log`         | System governance and async jobs | Added                  |
| Table 15 — `auth_session`      | Security and identity            | Added                  |
| Table 16 — `alarm_settings`    | Security and identity            | Added                  |
| Table 17 — `export_job`        | System governance and async jobs | Added                  |
| Table 18 — `help_article`      | Independent documentation        | Added                  |

This count follows the paper’s ten persistent relational entities in
Chapter III’s ERD discussion and Tables 9–18. The `help_article_fts` SQLite
virtual table is counted as a search index, not another application entity.

### Addition 1 — `auth_session`

**What it stores:** one durable row for each login session, linked to a user.
The row records its identifier, creation and expiry times, revocation time and
reason, and available browser and network metadata.

**Requirement that drives it:** FR-01 requires authenticated access, FR-03
includes account management, and NFR-19 limits a session to 8 hours and
requires it to be ended immediately on logout, password change, or an
Administrator’s revocation of access. See Chapter III, Table 2 (FR-01 and
FR-03) and Table 7 (NFR-19).

**What fails without durable session state:** the backend could not check
whether a particular session had expired or been revoked. Immediate logout,
password-change invalidation, and administrator revocation would not have a
server-side record to enforce them against.

**Mechanism:** `AuthSession` is declared in `backend/app/models/user.py:81`;
session creation, active-session lookup, and revocation are handled in
`backend/app/services/sessions.py:14`, `backend/app/services/sessions.py:38`,
and `backend/app/services/sessions.py:52`.

**Relationship:** the paper models a user with many session rows. That matters
because session state is per login, while identity and role are per account.
See Chapter III, Figure 7 and the `Auth Session` entry in Table 15.

### Addition 2 — `alarm_settings`

**What it stores:** one row per user for the chosen alarm sound, playback
volume, and snooze duration.

**Requirement that drives it:** FR-08 requires selectable alert tones,
volume control, and a configurable snooze duration. FR-07 supplies the
operator’s mute and snooze behavior. See Chapter III, Table 2 (FR-07 and
FR-08) and the `Alarm Settings` entry in Table 16.

**What fails without durable preferences:** a user’s chosen sound, volume, and
snooze duration could not be retained and applied to later alerts. The system
would be limited to transient settings or defaults, which would not satisfy
the paper’s per-user configuration behavior.

**Mechanism:** `AlarmSettings` is declared in
`backend/app/models/user.py:108`. The `/alarm` read and update routes use it in
`backend/app/api/routes/settings.py:31` and
`backend/app/api/routes/settings.py:52`; account creation seeds a row at
`backend/app/api/routes/users.py:277`.

**Relationship:** the paper specifies a strict one-to-one relationship to a
user. Code enforces one settings row per user with a unique `user_id` in
`backend/app/models/user.py:111`.

### Addition 3 — `audit_log`

**What it stores:** an append-only record of an event’s actor, role, action,
target, result, details, request context, and UTC write time. It can also store
system events and events where there is no matching user row.

**Requirement that drives it:** FR-20 requires an activity trail for critical
incident, camera, report, and account actions. NFR-21 requires changes and
failed or unauthorized attempts to be recorded, with sensitive values
redacted, and prohibits users from editing or deleting the records. See
Chapter III, Table 2 (FR-20) and Table 7 (NFR-21).

**What fails without a durable audit ledger:** `detection_log` can show an
incident’s current HITL state, but it cannot establish a complete history of
user, camera, report, security, and system actions. Without an append-only
record, the system cannot meet the paper’s cross-system record and immutability
requirements.

**Mechanism:** `AuditLog` is declared in `backend/app/models/audit.py:49`;
`backend/app/services/audit.py:76` builds entries, and the model attaches
update- and delete-rejecting triggers at `backend/app/models/audit.py:117`.

**Relationship:** the paper allows the actor relationship to be absent for
system work and attempts involving a nonexistent user. That makes the audit
ledger broader than a foreign-key history attached only to `User` or
`DetectionLog`. See Chapter III, Figure 7 and Table 14.

### Addition 4 — `export_job`

**What it stores:** the requesting user, report type and format, filters and
sort order, job status and progress, generated artifact metadata, failure
category, and lifecycle timestamps including expiry.

**Requirement that drives it:** FR-18 requires report and data exports.
NFR-06 requires standard reports to start within the stated target and larger
exports to run in the background, expose progress, retain the finished file,
and resume if interrupted. See Chapter III, Table 2 (FR-18), Table 3 (NFR-06),
and Table 17.

**What fails without durable job state:** a background request would have no
stored job identifier, progress, filter set, status, or artifact record for
the dashboard to retrieve. After a process interruption, the system would
also lack the persisted state needed to resume and report the job lifecycle
required by NFR-06.

**Mechanism:** `ExportJob` is declared in `backend/app/models/export.py:9`.
Job creation is in `backend/app/services/reports/jobs.py:588`; API creation,
listing, status, and download routes begin in
`backend/app/api/routes/exports.py:54`, `backend/app/api/routes/exports.py:111`,
`backend/app/api/routes/exports.py:182`, and
`backend/app/api/routes/exports.py:193`.

**Relationship:** the paper models one user’s export requests as a one-to-many
collection. The record is about the export job lifecycle, not another copy of
the report’s incident data. See Chapter III, Figure 7 and Table 17.

### Addition 5 — `help_article`

**What it stores:** searchable, categorized documentation: article title,
slug, role visibility, summary, Markdown body, sort order, FAQ flag, and
content metadata.

**Requirement that drives it:** FR-19 requires a centralized searchable Help
Center with role-appropriate SOPs, navigation guidance, and frequently asked
questions. See Chapter III, Table 2 (FR-19) and Table 18.

**What fails without stored articles:** the dashboard would not have a single
queryable content source for role-filtered help and FAQ results. Hard-wired
labels alone would not provide the paper’s documented article and search
behavior.

**Mechanism:** `HelpArticle` is declared in `backend/app/models/help.py:12`.
`backend/app/services/help.py:214` uses FTS search when available, and
`backend/app/services/help.py:283` performs article search. The FTS5 virtual
index is created at `backend/app/models/help.py:43` and synchronized with the
base table.

**Relationship:** the article store is independent of the user graph; role
visibility belongs to the article and filters what each role can read. The
paper describes the FTS5 table as the search index for `help_article`, not a
separate help-content entity.

## 4. Why it was built this way

### What the evidence supports

The five additions each have a distinct durable lifecycle: a login session
expires or is revoked; an alarm preference follows a user; an audit event is
append-only; an export job progresses and eventually expires; a help article
is searched and displayed according to role.

The current paper explicitly maps these records to separate areas of the
system. Its ERD discussion says that `auth_session`, `alarm_settings`,
`audit_log`, and `export_job` are specialized user-related tables, while
`help_article` and health telemetry are independent of the user graph.

Those relationships match the requirements. A session is not the same thing as
an account, an export request is not an incident, and a help article is not an
operator profile. Giving each record type its own lifecycle also lets the
system express the retention, ownership, and integrity rules in the paper.

This is additive evolution of a working core. The current ERD still includes
`user`, `camera`, `detection_log`, `sys_health_raw`, and `sys_health_hourly`.
The added tables represent capabilities that require their own persistent
records, rather than replacements for those five core entities.

### Why the five original tables are still there

`User` holds account identity and role. The new session and preference rows
refer to that identity without replacing it.

`Camera` remains the source of camera configuration and state. The new tables
do not turn camera management into a different domain.

`DetectionLog` remains the source for each collision record, snapshot, and
HITL state. The audit ledger complements that incident record by capturing
actions across other areas too.

The raw and hourly health entities remain responsible for telemetry. The
paper’s NFR-05 still calls for live refresh, retained detailed readings, and
hourly summaries (Chapter III, Table 3).

### What “requirement-driven” means here

The paper’s requirements specify the necessary user-visible behavior and data
retention, not a mandated table count.

FR-19 requires searchable help; it does not say “create table number ten.”
FR-19 is the reason the system needs durable help articles. The same
distinction applies to sessions, settings, audit events, and export jobs.

The schema is the implementation chosen to keep those records structured and
separate. The direct evidence for that choice is the paper’s ERD and data
dictionary, the FR/NFR mapping above, and the 9 August schema commit that
introduces the five named tables together.

The paper’s Chapter III methodology supports this interpretation: requirements
were established through stakeholder consultation, then the software track
iterated the backend, database, incident logging, exports, and alert workflow
to implement and stabilize them. It characterizes those iterations as
technical refinement against the planned scope, not as changing client
requirements.

Do not claim that no alternative schema was possible. A team could represent
some data in another physical form, but the study does not present a measured
comparison of those alternatives. The defensible claim is that the five
capabilities could not simply be dropped while retaining the cited FRs and
NFRs.

## 5. What changed since the 28 April defense

### Timeline from the model history

| Date       | Evidence from Git                                                    | What it establishes                                                                                    |
| ---------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 2026-04-24 | `f6c6b12` — initial FastAPI backend models and SQLite initialization | The five original model classes were already present together.                                         |
| 2026-04-26 | `2e30471` — user-management routes and additional models             | User-management behavior advanced; the defense-era model still had five table classes.                 |
| 2026-04-26 | `25a9ec9` — AI-engine/backend camera-status synchronization          | HITL and camera-sync behavior advanced without increasing the entity count.                            |
| 2026-04-28 | Defense date; the last pre-defense model snapshot is `f964741`       | The schema baseline remains five entities.                                                             |
| 2026-08-09 | `1831e3d` — split models, schemas, and services into packages        | The model file was organized into packages.                                                            |
| 2026-08-09 | `5a95eaf` — “land the complete target database schema”               | `auth_session`, `alarm_settings`, `audit_log`, `export_job`, and `help_article` first appear together. |

The `git log --since="2026-04-28" -- backend/app/models/` history shows the
additions as one schema rollout, not five separate emergency patches. The
commit describes them as the new tables in a complete target schema.

That same schema commit also reshaped some existing entities and constraints.
For example, it added session and alarm-settings models beside `User`, and
extended `detection_log` and camera state. Those changes affect columns,
constraints, and relationships; they do not explain the increase from five
tables to ten.

After the schema commit, later work adds behavior around the entities: an audit
viewer route (`f2b1306`, 2026-08-09), help-content update handling
(`c0d0e54`, 2026-08-09), and system-health endpoints (`b4d968c`, 2026-08-10).
These are follow-on uses of the data model, not additional table additions.

### Requirement mapping at a glance

| Added table      | Requirement link in the paper | Paper location                                        |
| ---------------- | ----------------------------- | ----------------------------------------------------- |
| `auth_session`   | FR-01, FR-03, NFR-19          | Chapter III, Tables 2 and 7; Data Dictionary Table 15 |
| `alarm_settings` | FR-07, FR-08                  | Chapter III, Table 2; Data Dictionary Table 16        |
| `audit_log`      | FR-20, NFR-21                 | Chapter III, Tables 2 and 7; Data Dictionary Table 14 |
| `export_job`     | FR-18, NFR-06                 | Chapter III, Tables 2 and 3; Data Dictionary Table 17 |
| `help_article`   | FR-19                         | Chapter III, Table 2; Data Dictionary Table 18        |

The sequence is therefore: keep the initial incident, camera, account, and
telemetry model; implement the remaining required workflows; give their
long-lived state a place to persist.

## 6. Limits and honest caveats

- The five-to-ten count refers to the ten application data entities in the
  paper’s ERD and data dictionary. `help_article_fts` is a SQLite virtual
  search index, not an eleventh relational domain entity.
- This guide compares the five defense-era model classes to the current ten
  paper entities. Table spellings changed during the later schema work; the
  comparison is about the same five core responsibilities plus five new ones.
- Git history identifies the first appearance of the five additions together
  in one 9 August schema commit. It does not establish five separate dates or
  prove which developer designed each one.
- A required behavior does not logically force one exact SQL layout. The
  paper does not document a formal “tables avoided” study or a benchmark
  comparing a merged-table alternative with the chosen schema.
- The tracker does not contain a five-table-versus-ten-table before/after
  benchmark. Do not claim that adding tables had zero cost or that it improved
  database performance by itself.
- For the current system, `docs/ADAS Test Execution.xlsx`, Performance & Load
  Testing, TC-PERF-011 records NFR-08 as Pass:
  the combined date, camera, and status filter took 1.28–1.41 seconds across
  three trials, within the paper’s 3-second screen-loading target. The tracker
  describes a 100,000-row detection table and a later 600,006-row dataset;
  this is current-system evidence, not a causal comparison with the April
  schema.
- The same tracker’s Performance & Load Testing sheet records NFR-06 /
  TC-PERF-006 as Pass for an asynchronous
  600,006-row CSV export. Use the test’s recorded scope and workflow when
  discussing this result; it does not prove every export size, database, or
  production deployment will perform identically.
- The paper’s workload and database claims apply to the documented edge/test
  setup. Do not turn the table count into a claim of production-scale
  readiness.
- The paper and tracker do not claim that creating more tables automatically
  makes a database faster. The defensible answer is that the current tested
  implementation met its documented acceptance criteria.

## 7. Likely panel questions

### “Why did your schema double — was the original design wrong?”

The original five still exist as the core account, camera, incident, and
telemetry entities. The other five persist separate behaviors required by the
paper: revocable sessions, individual alarm settings, complete auditing,
resumable exports, and searchable help. The current ERD shows those additions
as separate functional domains and child records, and Git shows them landing
together in the target-schema rollout.

### “Which of these could you have avoided?”

We could not drop any of the five capabilities and still satisfy the cited
requirements. The exact physical schema could have been designed differently,
but the paper does not provide a benchmark of merged or alternative schemas.
Our defensible claim is that these workflows needed durable state, not that
ten was the only possible table count.

### “Did adding tables hurt performance?”

The tracker does not compare the April schema to the current one, so it cannot
isolate the cost of the added tables. Its Performance & Load Testing sheet,
TC-PERF-011, records the current NFR-08 test as a Pass: the combined filter ran
in 1.28–1.41 seconds across three trials against the paper’s 3-second target.
That supports the tested current design; it does not prove the additions were
free.

### “Which one was the most important addition?”

For integrity, `audit_log` is the most consequential: FR-20 calls for recording
critical actions, and NFR-21 requires the record to be written with the change
and protected from editing or deletion. Without that ledger, the system could
not show a cross-domain history of who did what and whether the action
succeeded.

### “Why not put login sessions in the user table?”

An account and a login session have different lifecycles: one account can have
separate sessions, each with its own expiry and revocation state. NFR-19
requires immediate session termination on logout, password change, or
Administrator revocation. A session row lets the backend check and revoke the
specific server-side session.

### “Why is audit history a new table if incidents already record who verified them?”

Incident fields explain the incident’s HITL state. FR-20 and NFR-21 cover
critical actions across accounts, cameras, reports, security, and system
operations as well, including failed and unauthorized attempts. A separate
append-only ledger can represent all of those events, even when there is no
incident or user row to update.

### “Why make report export a database job?”

FR-18 asks for exports, and NFR-06 requires large jobs to run in the
background, show progress, retain a finished artifact, and resume if
interrupted. `export_job` keeps the request and progress state available to
the dashboard while generation runs. Without that durable job record, those
requirements cannot be met by a one-shot synchronous response.

### “What evidence says this was refinement, not scope drift?”

Chapter III says the software track refined the backend, database, incident
logging, reporting, and alert workflow against the established requirements.
The current ERD maps the new records to those workflows, and the 9 August Git
commit adds the five tables as one target-schema step. That is evidence of
implementation growth for specified behavior, rather than evidence that the
original five-table core was replaced.

## 8. Cram summary

- **April 28:** five model entities — `User`, `Camera`, `DetectionLog`,
  `SystemHealthRaw`, and `SystemHealthHourly`.
- **Today:** ten paper entities; the original five remain, plus
  `auth_session`, `alarm_settings`, `audit_log`, `export_job`, and
  `help_article`.
- **Why:** FR-01/03/NFR-19 need revocable sessions; FR-07/08 need persistent
  alarm preferences; FR-20/NFR-21 need immutable audit events; FR-18/NFR-06
  need durable export jobs; FR-19 needs searchable help content.
- **Timeline:** the five additions first appear together in
  `5a95eaf`, “land the complete target database schema,” on 2026-08-09.
- **Evidence against “the first design was wrong”:** the current ERD retains
  the original five; the added tables map to separate required workflows and
  their own lifecycles.
- **Performance answer:** no before/after schema benchmark exists. The tracker
  records current NFR-08 / TC-PERF-011 as Pass at 1.28–1.41 seconds against
  the 3-second target, under the recorded test conditions.
- **Count carefully:** `help_article_fts` is a virtual search index; it is not
  an eleventh relational entity in the paper’s ten-table count.
