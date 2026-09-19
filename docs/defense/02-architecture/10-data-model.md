# 10 — Data Model

> **One-liner:** The data model keeps incidents, cameras, people, audit activity, exports, help content, and system health in ten relational tables, with a separate FTS5 search index for help articles.
> **Panel risk:** High — data integrity, time-zone handling, and concurrency meet at the database boundary, so the panel can probe whether the schema itself protects operational rules.

## 1. What it is

The data model is the durable record of what ADAS knows and what happened.

It gives the system a stable way to connect a camera to an incident, an incident to the operator who handled it, and an action to the audit record that explains it.

The paper groups the persistent entities into four functional domains:

- **Core Detection Operations:** `camera` and `detection_log`.
- **Security and Identity Management:** `user`, `auth_session`, and `alarm_settings`.
- **System Governance and Async Jobs:** `audit_log` and `export_job`.
- **Independent Documentation and Telemetry:** `help_article`, `sys_health_raw`, and `sys_health_hourly`.

The ten relational tables are the business and operational records.

`help_article_fts` is an additional SQLite FTS5 virtual table for searching help content.

It is a search index over `help_article`, not another independent source of help data.

The relationships and table purposes follow the defense paper's ERD and data dictionary.

Database constraints described below are the enforcement mechanisms in the current model code.

## 2. Where it lives

### In the paper

Chapter 3, Methodology, under **System Architecture and Design**, introduces the data model.

The ERD discussion describes the ten entities and their relationships.

**Figure 7**, “Entity-Relationship Diagram of the Database Architecture,” shows the table graph on p. 117.

The **Data Dictionary, Tables 9–18**, begins on p. 120 and describes the ten relational tables.

The database-engine rationale is in Chapter 3, **Database Technologies**, with the comparison in **Table 19**, p. 172.

The paper's discussion of normalization and the hourly health summary follows Figure 7.

### In the code

The SQLModel definitions live in `backend/app/models/`:

- `camera.py:28` defines `camera` and its active-camera indexes.
- `detection.py:21` defines `detection_log` and its incident constraints.
- `user.py:30` defines `user`.
- `user.py:81` defines `auth_session`.
- `user.py:108` defines `alarm_settings`.
- `audit.py:49` defines `audit_log` and its immutability triggers.
- `export.py:9` defines `export_job`.
- `health.py:20` and `health.py:61` define the raw and hourly telemetry tables.
- `help.py:12` defines `help_article` and creates the FTS5 virtual table.

Shared persistence behavior is in `backend/app/core/`:

- `types.py:7` defines the custom `UtcDateTime` SQLAlchemy type.
- `enums.py:1` defines the Python `StrEnum` values used by the models.
- `db.py:18` installs SQLite connection pragmas, including foreign-key enforcement and WAL mode.

Help-search execution is in `backend/app/services/help.py:214`.

## 3. How it works

### The ERD as a relationship map

Read Figure 7 as a graph of persistent records, not as a list of screens.

The camera is the source record for incident rows.

The operator table is linked to incident handling, sessions, preferences, audit activity, and export jobs.

Help content and telemetry remain outside the user-centered operational graph.

The paper describes these links as follows:

- A camera has many detection-log rows.
- A detection-log row must refer to a camera.
- The verification, closure, and snooze actor links from an incident to a user are optional.
- A user can have many session rows.
- A user has one alarm-settings row in the intended account workflow.
- A user may be linked to many audit rows; a system-generated audit row may have no user.
- A user can request many export jobs.
- The two system-health tables are independent of the user and camera relations.
- Help articles are a separate content store, with the FTS5 virtual table synchronized from them.

The current foreign keys and relationships are visible in `backend/app/models/detection.py:12` and `:55`, `backend/app/models/user.py:62`, `:81`, and `:108`, `backend/app/models/audit.py:69`, and `backend/app/models/export.py:28`.

### The ten relational tables

#### `user` — accounts and roles

**Stores:** account identity, credential hash, role, active flag, and security timestamps.

The paper describes this as the account record for operators and administrators.

**Key columns:** `user_id` is the primary key; `username` identifies the login; `password_hash` stores the hash; `role` stores the access role.

`first_name`, `last_name`, `is_active`, `created_at`, and `updated_at` support account administration.

`password_changed_at` and `last_login` are optional security timestamps.

**Constraints:** `username` is unique and required; `role` is restricted to `Admin` or `Operator` by a database `CHECK`.

The primary key identifies an account; the model also trims and validates account-name input before persistence.

The `is_active` flag supports soft deletion, retaining the account row instead of removing its history.

Paper: Data Dictionary Table 9. Code: `backend/app/models/user.py:16`, `:30`, `:33`, and `:43`.

The explicit `String` column and role check are at `backend/app/models/user.py:36` and `:41`.

#### `camera` — configured streams and reported state

**Stores:** camera identity, channel assignment, administrative enablement, desired AI state, reported runtime state, and heartbeat metrics.

The backend owns the desired-state fields; the AI engine reports observed status and runtime measurements.

**Key columns:** `camera_id`, `camera_name`, and `channel_id` identify the row and stream.

`is_active` marks a soft-deleted record; `is_enabled` is the operator's enablement control.

Desired state is carried by `desired_ai_state`, `desired_state_reason`, `cooldown_until`, and `config_version`.

Reported state is carried by `connection_status`, `ai_status`, `applied_config_version`, `last_heartbeat_at`, `measured_fps`, and `inference_latency_ms`.

`last_error_code`, `last_error_message`, `created_at`, and `updated_at` complete the operational record.

**Constraints:** `channel_id` must be positive.

Database checks restrict desired AI state, desired-state reason, connection status, and AI status to their allowed values.

Active names and channels are unique through partial unique indexes; the name index compares the lowercase name.

The active-state index supports filtering cameras by active, enabled, connection, and AI status.

Paper: Data Dictionary Table 10 and the ERD discussion. Code: `backend/app/models/camera.py:28`, `:33`, `:52`, and `:64`.

#### `detection_log` — incident evidence and handling history

**Stores:** each AI-raised incident, its camera and evidence reference, confidence score, lifecycle status, and human handling timestamps.

**Key columns:** `log_id` is the primary key; `source_event_id` uniquely identifies an incoming event; `camera_id` links the incident to its source.

`detected_at`, `confidence_score`, and `snapshot_key` describe the detection and its evidence.

`detection_status` records whether the incident is `Unverified`, `Ongoing`, `Dismissed`, or `Cleared`.

`verified_by_id` / `verified_at` and `closed_by_id` / `closed_at` attribute verification and closure.

`snoozed_by_id`, `snoozed_at`, and `snoozed_until` record a snooze; `created_at` and `updated_at` record the row timestamps.

**Constraints:** the camera foreign key is required and uses `ON DELETE RESTRICT`.

The verification, closure, and snooze user foreign keys are optional and also restrict deletion of a referenced user.

The database checks the confidence-score range and the allowed status values.

`source_event_id` is unique, so retrying the same event cannot create a second incident row.

A partial unique index on `camera_id` applies only while status is `Unverified` or `Ongoing`.

Paper: Data Dictionary Table 11. Code: `backend/app/models/detection.py:12`, `:21`, `:23`, `:32`, and `:33`.

#### `sys_health_raw` — recent hardware samples

**Stores:** the raw hardware telemetry used to inspect recent system health.

Paper Table 12 describes a timestamped sample with CPU, GPU, RAM, and GPU-temperature measurements.

**Key columns:** `sys_health_id` is the row identifier; `created_at` marks the sample time; the remaining columns carry the measurements.

The paper specifies collection at five-minute intervals and a forty-eight-hour rolling retention window.

**Constraints:** the primary key identifies each sample; utilization measurements have database range checks.

The time column is indexed for time-window queries.

Paper: Data Dictionary Table 12. Code: `backend/app/models/health.py:20`, `:24`, and `:25`.

#### `sys_health_hourly` — summarized health trends

**Stores:** hourly health summaries for longer-term trends and dashboard queries.

**Key columns:** an integer row identifier, a unique UTC-hour key, `sample_count`, average CPU/GPU/RAM measures, and peak-temperature measures.

Paper Table 13 specifies a rolling thirty-day retention window.

The unique hour key prevents two summary rows for the same hour.

**Constraints:** primary key; unique and indexed hour key; database range checks on utilization percentages.

Paper: Data Dictionary Table 13 and the normalization discussion after Figure 7. Code: `backend/app/models/health.py:61`, `:65`, and `:67`.

#### `audit_log` — actor and action record

**Stores:** a timestamped record of administrative, operational, authentication, and system actions.

**Key columns:** `audit_id` identifies the row; `actor_type`, optional `user_id`, `username`, and `role` identify the actor.

`action`, `target_type`, `target_ref`, and `result` describe what was attempted and what it affected.

`detail`, `request_id`, `source_ip`, and `created_at` provide context for review.

**Constraints:** `actor_type`, `action`, and `result` are each restricted by a database `CHECK` to defined values.

`user_id` is optional so system-originated records can exist without an account reference.

Indexes support time, action, actor, and target lookups.

Database triggers reject updates and deletes, making the audit table append-only through normal database operations.

Paper: Data Dictionary Table 14 and the ERD discussion. Code: `backend/app/models/audit.py:49`, `:53`, `:63`, `:92`, and `:99`.

#### `auth_session` — revocable login sessions

**Stores:** server-side session state associated with the user's signed session token.

**Key columns:** `session_id` is the primary key; `user_id` links the session to its account.

`created_at`, `expires_at`, and optional `revoked_at` define the session lifecycle.

`revocation_reason`, `user_agent`, and `source_ip` record how the session was revoked and its client context.

**Constraints:** `user_id` is required and references `user` with `ON DELETE RESTRICT`.

`revocation_reason` is null or one of the database's allowed reason strings.

Indexes support account/revocation lookup and expiry cleanup.

Paper: Data Dictionary Table 15 and the ERD discussion. Code: `backend/app/models/user.py:81`, `:86`, and `:96`.

#### `alarm_settings` — per-user alert preferences

**Stores:** the alarm sound, playback volume, snooze duration, and preference timestamps for an account.

**Key columns:** `alarm_settings_id` is the primary key; `user_id` is a unique foreign key to `user`.

`alarm_sound`, `volume`, and `snooze_duration` hold the preference values.

**Constraints:** unique `user_id` permits at most one settings row per account; deleting a user cascades to this child row.

The volume is checked within zero to one hundred; snooze duration is checked from fifteen to sixty seconds.

The paper describes the intended relationship as one-to-one and says settings are initialized at account registration.

Paper: Data Dictionary Table 16 and the ERD discussion. Code: `backend/app/models/user.py:108`, `:112`, `:120`, and `:121`.

#### `export_job` — asynchronous report jobs

**Stores:** the request parameters, progress, outcome, and artifact metadata for background exports.

**Key columns:** `job_id` is the primary key; `requested_by_id` links the job to its requesting user.

`report_type`, `format`, `filters_json`, and `sort_json` describe the requested export.

`status`, `progress_current`, and optional `progress_total` track processing.

`artifact_path`, `artifact_bytes`, and `failure_category` describe the result; lifecycle timestamps record when the job was created, started, completed, and expired.

**Constraints:** the requester foreign key is required and restricts deletion of the account.

Database checks restrict report type, file format, and job status to their defined value sets.

Paper: Data Dictionary Table 17 and the ERD discussion. Code: `backend/app/models/export.py:9`, `:13`, and `:15`.

#### `help_article` — operator guidance content

**Stores:** categorized standard operating procedures and system help written in Markdown.

**Key columns:** `article_id` is the primary key; `slug` is unique; `title`, `category`, and `body_markdown` identify and contain the article.

`roles` stores the visibility list; `summary`, `sort_order`, `is_faq`, and `content_hash` support display and synchronization.

`created_at` and `updated_at` provide content timestamps.

**Constraints:** article identity is unique by primary key and slug.

The paper's data dictionary describes `roles` as required content and `summary` as optional.

Paper: Data Dictionary Table 18. Code: `backend/app/models/help.py:12`, `:16`, and `:18`.

### The help search virtual table

`help_article_fts` is an external-content FTS5 virtual table over `help_article`.

Its indexed text columns are `title`, `summary`, and `body_markdown`.

Its `content_rowid` points to `help_article.article_id`, so the base article remains the source record.

An insert trigger indexes a new article.

An update trigger removes the old text from the index and adds the replacement text.

A delete trigger removes the deleted article's indexed text.

The help service joins FTS row IDs back to `help_article`, runs a `MATCH` query, and returns ranked base rows.

If FTS5 is unavailable, search falls back to a `LIKE` query over article text.

Paper: Data Dictionary Table 18 and the ERD discussion on p. 116. Code: `backend/app/models/help.py:42`, `:49`, `:58`, `:67`, `backend/app/services/help.py:214`, and `:235`.

### Partial unique indexes: the rules the database makes impossible

A partial unique index applies uniqueness only to rows matching its `WHERE` condition.

The rule is therefore scoped to the records that matter operationally, while historical rows remain stored.

For incidents, `ux_detection_open_camera` is unique on `camera_id` only when the status is `Unverified` or `Ongoing`.

That makes it impossible for a camera to have two open incidents at once, including when requests race or another write path bypasses request-level validation.

After an incident is `Dismissed` or `Cleared`, it no longer occupies the open-incident index.

The paper calls out this guarantee in the Detection Log description and Table 11.

Code: `backend/app/models/detection.py:33`.

For cameras, `ux_camera_name_active` is unique on lowercase `camera_name` for active rows.

`ux_camera_channel_active` is unique on `channel_id` for active rows.

These indexes make it impossible to create two active cameras with names that differ only by case or with the same channel.

When `is_active` becomes false, the row is excluded from both indexes, so its name and channel may be reused without deleting the old camera record.

`is_enabled` is a separate operational switch; disabling a camera does not free its name or channel.

The paper describes active-only uniqueness and soft deletion in Table 10.

Code: `backend/app/models/camera.py:52` and `:58`.

These indexes complement service validation; they are not replaced by it.

Python checks can return clearer errors before a write.

The database index is the final arbiter when independent requests attempt the same unique state.

### UTC timestamps and the `UtcDateTime` type

SQLite's ordinary datetime storage does not preserve Python `tzinfo` reliably.

`UtcDateTime` normalizes timestamps in Python on the way into and out of the database.

On a database bind, `None` remains `None`.

A timezone-aware datetime is converted to UTC, then stored without `tzinfo` because SQLite cannot preserve it.

A naive datetime raises `ValueError` at the SQLAlchemy bind boundary.

On a database read, the type attaches UTC to the returned value so application code receives an aware datetime.

This is why the write path rejects naive values instead of guessing whether they mean local time or UTC.

It prevents a silently misinterpreted timestamp from entering incident, audit, session, or health history.

Model timestamp fields use this type; current-time defaults use `datetime.now(UTC)`.

Code: `backend/app/core/types.py:7`, `:17`, and `:24`; model example: `backend/app/models/detection.py:16`.

There is a separate input contract for query parameters.

An explicit offset is converted to UTC by `parse_utc_query_datetime`.

A naive query datetime is treated as UTC by that parser, while a naive value bound for storage is rejected.

Code: `backend/app/core/types.py:28`.

### Strings with `CHECK` constraints instead of database enum types

Application code names finite values with Python `StrEnum` definitions.

The stored database columns are string values, and `CHECK` constraints restrict those strings to the allowed set.

Examples include the user role, camera desired and observed states, incident status, audit actor/action/result, session revocation reason, and export type/format/status.

For `user.role`, the model explicitly selects `String` as the SQL column type and checks for `Admin` or `Operator`.

The model comment records a specific reason: SQLAlchemy's inferred Enum column would store the member name, such as `ADMIN`, while the desired database value is `Admin`.

The database check protects the persisted spelling even if a write does not pass through the usual Python enum field.

The Python enum improves naming and typing in application code; the database constraint protects the record.

Code: `backend/app/models/enums.py:1`, `backend/app/models/user.py:33` and `:36`, `backend/app/models/camera.py:35`, and `backend/app/models/detection.py:28`.

## 4. Why it was built this way

### SQLite fits the edge deployment described in the paper

The paper selects SQLite because it is embedded and serverless: reads and writes go to a local database file through an in-process library.

That avoids a separate database daemon competing with the edge server's CPU and memory, while keeping database access local.

The paper says PostgreSQL and MySQL would require separate server processes; it also says a document database would need application code to reproduce relational constraints.

The workload described in the paper is a relational record set with indexes on incident status, camera, and timestamp.

The paper ties that design to the requirement to query up to 100,000 historical incident logs within 3 seconds; this is a requirement and design rationale, not a new benchmark claim in this guide.

Paper: Chapter 3, Database Technologies, Table 19, p. 172.

SQLite's write journal is configured for WAL mode.

WAL lets readers continue while a write is active, which fits simultaneous AI writes and dashboard reads.

The engine also enables foreign-key checks, sets `synchronous=FULL`, and applies a busy timeout on each new SQLite connection.

Code: `backend/app/core/db.py:18` and `:31`.

### Data invariants belong at the persistence boundary

Application validation is useful for messages and early rejection.

It cannot guarantee a database invariant across every service, background task, seed script, or concurrent request.

Unique constraints, `CHECK` constraints, foreign keys, and partial unique indexes are evaluated where writes commit.

For example, a Python check that counts open incidents can be stale by the time a second request writes.

The unique partial index evaluates the final database state and rejects the conflicting row.

The same principle applies to allowed enum strings, unique account names, camera identity, and unique hourly summaries.

### UTC avoids machine-local interpretation

The timestamps represent a shared instant, not the local clock on whichever process handled the request.

Normalizing to UTC gives incident ordering, audit review, expiry, and health aggregation a consistent basis.

SQLite does not preserve timezone metadata for this type, so the custom bind and result processing carries the convention across storage.

Rejecting naive database values makes missing timezone context visible at the boundary rather than silently assigning meaning.

### The model is relational, with one deliberate summary table

The paper describes the operational schema as normalized to reduce duplicated facts and update anomalies.

The hourly health table is a controlled denormalization: it stores summaries so dashboard reads do not repeatedly aggregate raw samples.

Raw health supports recent inspection; the hourly table supports longer-term trends.

The separation keeps frequent telemetry independent from user-account relationships.

Paper: ERD discussion and the normalization explanation following Figure 7; Data Dictionary Tables 12 and 13.

### The FTS table accelerates help search without duplicating the source record

The `help_article` table remains the authoritative content row.

FTS5 maintains a tokenized search index over article text and points results back to the base article by row ID.

Triggers keep the index synchronized with article inserts, edits, and deletes.

This gives the help center full-text search while retaining a normal relational table for article editing and display.

Paper: Data Dictionary Table 18. Code: `backend/app/models/help.py:42` and `:49`.

## 5. What changed since the 28 April defense

The April baseline at repository snapshot `f964741` had five relational models: user, camera, detection log, raw system health, and hourly system health.

The current paper's Figure 7 and Data Dictionary describe ten relational tables, plus the `help_article_fts` virtual search table.

The added records make server-side sessions, per-user alarm preferences, audit activity, export jobs, and searchable help content first-class data.

The current code organizes each domain in separate model modules under `backend/app/models/`.

The full table-by-table growth timeline is the scope of Guide 11; this guide focuses on the current schema and its constraints.

History reference: `backend/app/models.py` at Git snapshot `f964741`; current paper: Chapter 3, Figure 7 and Data Dictionary Tables 9–18.

## 6. Limits and honest caveats

SQLite's WAL mode supports concurrent readers with a writer; it does not make the database a multi-host, multi-writer service.

The paper's engine choice is grounded in a local edge workload and the database requirement cited above.

Foreign-key declarations only work as intended when SQLite foreign-key enforcement is enabled.

The application enables it for every new SQLite connection with `PRAGMA foreign_keys=ON`.

Code: `backend/app/core/db.py:26` and `:31`.

The partial unique indexes enforce uniqueness only inside their predicates.

The camera indexes intentionally apply only while `is_active` is true; they do not constrain soft-deleted rows.

The open-incident index includes only `Unverified` and `Ongoing` rows; it does not encode every allowed lifecycle transition.

The service layer owns the transition rules; the data model enforces the subset that can be expressed as relational constraints.

The alarm-settings `user_id` unique constraint prevents duplicate settings rows.

Uniqueness alone does not force every user to have a settings row; the paper's one-to-one relationship also depends on account setup creating the preference row.

The UTC guard is in SQLAlchemy's type boundary.

SQLite itself does not attach timezone metadata to a stored datetime, so a direct SQL writer outside this type must follow the UTC storage convention.

The `help_article_fts` virtual table depends on an SQLite build with FTS5 support.

When that module is unavailable, the help service uses a simpler `LIKE` search path.

Code: `backend/app/models/help.py:76` and `backend/app/services/help.py:244`.

No test-tracker performance or uptime result is claimed in this guide.

The numbers here are the paper's schema, requirement, and retention values; any measured test result belongs to the tracker-based results guide.

## 7. Likely panel questions

**“Why enforce that in the database instead of in Python?”**

Python validation gives early, readable errors, but it cannot protect every write path or resolve a race between requests.

The database checks uniqueness, allowed values, and relationships when a row is written, so the invalid state cannot commit.

**“Why SQLite for a system that runs 24/7?”**

The paper's choice is based on a local edge workload: SQLite avoids a separate database service, and WAL lets dashboard readers work while records are written.

The paper also ties the indexed design to its historical-log responsiveness requirement; it does not make a general claim that SQLite suits every scale.

**“What stops two incidents opening on the same camera?”**

The database has a unique partial index on `camera_id` while the incident status is `Unverified` or `Ongoing`.

A conflicting write fails even if two requests reach the insert path at nearly the same time.

**“How do you handle time zones?”**

Stored timestamps are normalized to UTC; an aware value is converted before it is stored, then returned as an aware UTC value.

A naive datetime bound for storage raises an error instead of being guessed as local time.

**“Why store status enums as strings instead of database enum types?”**

The application uses `StrEnum` values, while SQLite stores plain strings guarded by `CHECK` constraints.

That keeps the saved spelling explicit: SQLAlchemy's inferred enum would save a member name such as `ADMIN` rather than the value `Admin`.

**“If a camera is deleted, can you reuse its name or channel?”**

Yes: a soft-deleted row is excluded from the active-only unique indexes, so its name or channel can be assigned to a new active record.

An operator-disabled camera is still active, so disabling it does not release either value.

**“Is `help_article_fts` another business table?”**

No. It is a virtual search index whose row IDs map back to `help_article`; triggers synchronize its text when articles change.

If FTS5 is unavailable, the service falls back to `LIKE` search over the base content.

**“Are your foreign keys really enforced in SQLite?”**

SQLite requires foreign-key enforcement to be enabled on each connection, and the application runs `PRAGMA foreign_keys=ON` when it opens one.

The model declares the relationships, and the connection setup makes SQLite enforce them.

## 8. Cram summary

- The paper's ERD has ten relational tables in four domains; `help_article_fts` is the additional virtual search index.
- `camera` owns stream identity; `detection_log` is a required child of a camera and stores evidence plus handling attribution.
- `user` links to sessions, alarm settings, audit records, and export jobs; health tables are independent; help text has its own FTS index.
- Partial unique indexes prevent multiple open incidents on one camera and duplicate names or channels among active cameras.
- `is_active` controls soft-delete uniqueness; `is_enabled` controls operational enablement.
- `UtcDateTime` converts aware timestamps to UTC, strips timezone metadata for SQLite storage, restores UTC on read, and rejects naive database writes.
- Finite values persist as strings protected by `CHECK` constraints; Python `StrEnum` definitions provide named values to the application.
- SQLite was selected for the embedded edge workload; WAL supports readers during writes, and the paper ties the indexed design to its historical-query requirement.
- The health-hour summary is deliberate controlled denormalization; the audit table is append-only through database triggers.
