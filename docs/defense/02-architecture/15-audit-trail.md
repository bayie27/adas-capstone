# 15 — Activity Audit Trail

> **One-liner:** The audit trail records who did what, to which record, when,
> and with what result, while tying successful state changes to their evidence.
> **Panel risk:** high — the design depends on transaction boundaries,
> database-level immutability, and careful explanation of which refusals are
> actually written as audit rows.

## 1. What it is

The activity audit trail is the system's durable account of important actions.
It covers incident decisions, camera configuration, user and account changes,
authentication, reporting, and maintenance.

An incident record answers, “What happened to this detection?” The audit row
answers, “Which person or system action changed it, and what was the result?”
The two records complement each other; the audit row is not a copy of the
entire incident record or a transcript of the operator's screen.

The paper requires an audit record for critical user actions and says that each
record includes the user ID, role, action, affected record, timestamp, and
result. It also requires state changes and their records to be written at the
same time, failed or unauthorized attempts to be recorded with sensitive
values hidden, and records to be unavailable for editing or deletion by users,
including Administrators.

The implementation expresses each type of action with a named value. It stores
the actor and target, a result category, request context, a timestamp, and
optional structured detail. The application can search and export these rows;
the database rejects updates and deletes to the audit table.

The central rule is simple: a successful audited change and its evidence are
one database transaction. If the audit insert cannot commit, the state change
does not commit either. An audited action therefore cannot survive without its
audit row.

There is a distinct path for attempts that are denied or fail. The main work is
rolled back or never proceeds; a short, separate transaction then tries to
write the denial or failure row. If that secondary write fails, the system
preserves the original denial or failure response and records a critical
server-side error.

## 2. Where it lives

### In the paper

- **Chapter 3, Requirements Analysis, Functional Requirements Specification,
  Table 2, FR-20 — Activity Audit Trail, p. 63.** This is the functional
  requirement for the action coverage and the core actor, action, target, time,
  and result fields.
- **Chapter 3, Requirements Analysis, Non-Functional Requirements
  Specification, Table 7, NFR-21 — Audit Trail Integrity, p. 70.** This is the
  requirement for same-time recording, logging failed or unauthorized attempts
  with sensitive values hidden, and preventing users from editing or deleting
  records.
- **Chapter 3, Table 14 — Audit Log.** The data dictionary describes the audit
  row: actor type, user ID, username and role snapshots, action, target,
  result, detail, request ID, source IP, and UTC creation time. It marks the
  user foreign key as nullable so a row can exist without a matching account.
- **Chapter 3, Use Cases, “Review and Export the Activity Audit Log.”** This
  describes the Administrator's read-only review and export workflow, filters,
  detail inspection, and the export watermark that keeps an export from
  including its own audit event.
- **Chapter 3, Figure 26 — Audit Log Page.** The paper shows the audit viewer
  and describes its actor, action, target, result, time, and detail columns,
  plus search, filters, and export.

### In the code

- `backend/app/models/audit.py:9` defines the action catalogue. The SQL
  `CHECK` expression is generated from that tuple at
  `backend/app/models/audit.py:40` and applied at
  `backend/app/models/audit.py:58`. The query-validation enum is generated
  from the same tuple at `backend/app/models/audit.py:46`.
- `backend/app/models/audit.py:49` defines the stored audit row and its
  fields. `backend/app/models/audit.py:88` defines the append-only SQLite
  triggers that reject `UPDATE` and `DELETE` statements.
- `backend/app/services/audit.py:51` builds an audit row in the caller's
  session without committing it. `backend/app/services/audit.py:99` handles
  denied or failed outcomes in a separate short-lived session.
- `backend/app/core/redaction.py:5` defines the credential-bearing URL
  pattern. `backend/app/core/redaction.py:36` redacts text values before the
  audit service stores detail.
- `backend/app/api/routes/alerts.py:517` contains the operator dismissal
  route. Its audit row is added at `backend/app/api/routes/alerts.py:554`
  and committed with the state change at
  `backend/app/api/routes/alerts.py:567`.
- `backend/app/api/routes/auth.py:75` handles failed sign-in attempts;
  successful sign-ins are recorded at
  `backend/app/api/routes/auth.py:116`.
- `backend/app/api/dependencies.py:118` defines an Administrator guard that
  writes a denied audit row for catalogued protected actions before returning
  the 403 response.
- `backend/app/api/routes/audit.py:143` validates action filters against the
  enum. The Administrator-only viewer does not audit a read of the viewer;
  exporting audit records is handled by
  `backend/app/api/routes/audit.py:275`.
- `backend/tests/test_audit.py:53` verifies rollback when the audit insert
  fails. `backend/tests/test_audit.py:111` exercises detail redaction.
  `backend/tests/test_schema.py:320` checks database rejection of updates,
  deletes, and invalid values.
- `backend/tests/test_audit.py:760` exercises immutability after replaying
  the Alembic migration chain, not only against a schema built directly from
  the current models.

## 3. How it works

### The action catalogue

The action value is a controlled vocabulary. A caller chooses a known semantic
action such as `ALERT_DISMISS`; it does not invent a new action string from a
request body or an exception message.

The catalogue is grouped here by the work it describes:

| Area              | Stored action values                                                                                                                                  |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Authentication    | `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`                                                                                                            |
| Incident handling | `ALERT_CONFIRM`, `ALERT_DISMISS`, `ALERT_CLEAR`, `ALERT_CORRECTION`, `ALERT_SNOOZE`                                                                   |
| Camera management | `CAMERA_CREATE`, `CAMERA_UPDATE`, `CAMERA_ENABLE`, `CAMERA_DISABLE`, `CAMERA_DELETE`, `CAMERA_RESTORE`                                                |
| Exports           | `REPORT_EXPORT`, `AUDIT_EXPORT`                                                                                                                       |
| User management   | `USER_CREATE`, `USER_UPDATE`, `USER_ENABLE`, `USER_DISABLE`, `USER_ROLE_CHANGE`, `USER_PASSWORD_RESET`, `USER_PROFILE_UPDATE`, `USER_PASSWORD_CHANGE` |
| Preferences       | `ALARM_SETTINGS_UPDATE`                                                                                                                               |
| Maintenance       | `BACKUP_TRIGGER`, `RESTORE_TRIGGER`                                                                                                                   |

FR-20 gives the panel the user-facing categories and examples. The catalogue
gives the implementation a distinct value for each recorded action. Where a
single request makes more than one semantic change, each change can receive
its own action value in the same database transaction instead of being hidden
under one generic “update” row.

The same `AUDIT_ACTIONS` tuple produces two protections:

1. The model joins the tuple into the SQL expression for the
   `ck_audit_action_valid` database `CHECK` constraint. An insert with an
   unknown action is rejected even if it bypasses the normal Python caller.
2. The model creates the `AuditAction` enum from the tuple. The audit viewer's
   `action` query parameter is typed as that enum, so an unknown filter is
   rejected during request validation instead of becoming a valid-looking
   search that silently returns no matches.

The result column is also constrained. Its accepted values are `success`,
`denied`, and `failure`. A policy refusal such as a role check is recorded as
`denied`; the code keeps that category distinct from `failure`.

This shared definition prevents the database's accepted actions and the
viewer’s accepted filters from drifting into two separate lists. A new action
must be deliberately added to the catalogue and carried through the schema
migration before it can be stored.

### What a row contains

An audit row contains these kinds of information:

- **Actor type:** `user` or `system`.
- **Actor identity:** user ID when available, plus a username snapshot and
  role snapshot. A snapshot keeps the name and role as they were at action
  time, even if the account is later renamed or deactivated.
- **Action:** a catalogue value identifying what happened.
- **Target:** a target type and reference, such as an incident ID or camera
  ID, when there is a specific affected record.
- **Result:** `success`, `denied`, or `failure`.
- **Detail:** optional JSON context, such as the camera associated with an
  incident decision or a normalized reason for refusal.
- **Request context:** a request ID and source IP when the action came from an
  HTTP request.
- **Time:** a UTC timestamp. The transaction makes the row durable only if
  the commit succeeds.

The database allows `user_id` to be empty. A system-owned action can have no
user actor, and a failed login for an unknown username cannot link to a user
row that does not exist. In that login case the attempted normalized username
is still snapshotted in the row; it is not replaced with a guessed account.

### A successful state change

The flow for a successful audited operation is:

1. The route validates the request and checks the caller's role and action
   preconditions.
2. The route or service changes the domain record using its database session.
3. The audit helper builds the corresponding row and adds it to that same
   session. It deliberately does not commit on its own.
4. The request commits once. The state update and audit insert are part of
   the same database transaction.
5. If the commit succeeds, the route can return success and, where needed,
   broadcast the resulting state to connected clients.

The ordering in step three is why the audit row cannot get detached from the
change. If the row violates its `CHECK`, the insert fails, the transaction
does not commit, and the primary state change is rolled back with it. If the
state update itself fails, its audit row is rolled back as well.

For an incident dismissal, the route changes the incident state and any
associated camera state, adds the audit entry, and commits them in the same
session. This transaction boundary is visible in
`backend/app/api/routes/alerts.py:535`,
`backend/app/api/routes/alerts.py:554`, and
`backend/app/api/routes/alerts.py:567`.

### Example: an operator dismisses an alert

The row records a successful action with the operator as actor and the
incident as target. `target_type` is `incident`; `target_ref` is the incident
log ID. The route supplies camera ID and camera name in the structured detail
and records the source IP. The audit helper also captures the request ID and
UTC timestamp when available.

The action code distinguishes a dismissal of an unverified alert
(`ALERT_DISMISS`) from a correction that dismisses an already ongoing incident
(`ALERT_CORRECTION`). The code for those legal transitions is in
`backend/app/services/incidents.py:37`; the route records the selected action
at `backend/app/api/routes/alerts.py:554`.

The audit detail is structured context, not the whole request. It does not
store a prose explanation typed by the operator in this route. The incident
record itself remains the source for the current lifecycle state and its
timestamps; the audit row supplies actor, action, target, result, and context.

### A denied or failed operation

A denial cannot be recorded inside a transaction that is being rolled back:
rollback would erase the evidence along with any attempted work. The denial
path therefore follows a separate sequence:

1. The primary operation is refused or rolled back before a state change can
   persist.
2. `record_out_of_band` opens a new, short-lived session against the same
   database engine.
3. It creates the audit row and commits that separate transaction.
4. Control returns to the original path, which produces its original 403,
   401, conflict, or other failure response.

For example, the Administrator guard can record a `denied` row for a
catalogued admin-only action before raising its 403. The login route records
failed sign-in attempts out of band before returning the generic 401 response.

The out-of-band writer catches an audit-write exception, logs a critical
server-side error with the action and result, and returns without re-raising.
That is why losing a denial row must never turn a 403 into a 500: the audit
attempt is secondary to the access-control decision. A failed denial audit is
still a lost audit row, but it does not grant access or change the response.

### Detail redaction

Redaction happens before detail is JSON-encoded and stored. It applies
recursively to nested dictionaries and lists.

The audit helper fully masks values under credential-like keys, including
password, password-hash, token, cookie, API-key, secret, and authorization
fields. Key matching is case-insensitive.

Every string value is also passed through the shared text redactor. That
redactor masks credentials embedded in a URL, replaces configured secret
values such as the application secret and internal API key, and replaces
configured absolute snapshot, backup, export, and archive paths with stable
placeholders.

The system stores normalized reasons for failures rather than the submitted
secret. Examples include `wrong_password`, `unknown_user`, or
`confirmation_mismatch`. The password or confirmation text itself is not
needed to explain why the attempt was denied.

Redaction is deliberate and scoped. A source IP and request ID remain
available for traceability. The text redactor is not a classifier that can
recognize every arbitrary sensitive phrase inside free text; do not promise
that it catches an unknown secret merely because the string looks token-like.
The protected keys, configured secret values, credential URLs, and configured
paths are the behavior that the code and tests support.

### Append-only database enforcement

The database installs a `BEFORE UPDATE` trigger and a `BEFORE DELETE` trigger
on `audit_log`. Each trigger aborts the statement with the message
`audit_log is append-only`.

This control sits below the application routes. It does not rely on the
Administrator viewer merely hiding edit buttons: an SQL update or delete
against the table is rejected while the triggers are installed. The
application also exposes no audit-log edit or delete route.

The action `CHECK` and immutability triggers serve separate purposes. The
`CHECK` rejects unrecognized action or result values on insert. The triggers
reject attempts to change or erase rows after insertion. Together they make
the log append-only through supported database operations.

The Administrator can filter and inspect the log but cannot edit or delete
records. Reading the viewer itself is not audited, avoiding recursive noise.
An audit export is an action and is recorded. Its query uses a watermark taken
before the export row is written, so the export cannot include its own row.

## 4. Why it was built this way

**One vocabulary avoids drift.** If the database constraint and the API
filter used independent lists, one could accept a value that the other
rejected. Generating both from `AUDIT_ACTIONS` keeps stored actions and
validated filters aligned.

**Database triggers enforce the rule at the storage boundary.** A user
interface-only restriction would not stop a future route or a direct SQL
statement from changing a stored audit row. The triggers make update and
delete attempts fail at the database operation itself.

**Atomic writes close the evidence gap.** Writing the domain update first and
the audit row later would leave a window where the application could stop or
the second insert could fail after the state change had already committed.
Sharing one transaction means either both are durable or neither is.

**A refusal needs a different transaction.** A denied operation should not
commit its requested state change, so its primary transaction is rolled back
or never advances. A separate short transaction lets the system preserve
evidence of the refusal without undoing the denial.

**The original response must survive a secondary logging failure.** Returning
403 is the security decision; an audit insert error cannot convert that
decision into an internal server error. The helper reports the logging loss
to the server log while keeping the user-facing denial intact.

**Redaction happens before persistence.** Hiding a password in the viewer
would still leave it in the database. Sanitizing detail before JSON storage
keeps protected values out of the durable audit row in the first place.

## 5. What changed since the 28 April defense

The repository history after the April defense records a dedicated audit
service, audit viewer, export support, and additional coverage for atomicity,
redaction, and immutable rows. The current paper now gives the capability a
clear requirement statement in FR-20 and NFR-21, describes the stored fields
in Table 14, and shows the review screen in Figure 26.

The defense explanation should focus on the enforcement points that make the
requirement concrete: one catalog for storage and query validation,
transaction-coupled success rows, separate refusal/failure rows, redaction
before storage, and database triggers for immutability. These mechanisms
address the combined integrity requirement in NFR-21.

When contrasting with the earlier defense, describe the current evidence and
implementation rather than guessing what the panel saw in a particular build.
The paper and tracker are the sources for the current claim and its tested
scope.

## 6. Limits and honest caveats

### What the controls demonstrate

The tests demonstrate that a bad audit insert rolls back the associated
primary state change, that direct database updates and deletes are rejected,
that the triggers remain after migrations, and that tested credential values
are removed from stored detail. These are application and database controls
within the running system.

The Security Testing sheet records positive evidence for several paths:

- **TC-SEC-001 — Pass.** Wrong-password, unknown-user, and deactivated-account
  attempts return the same generic 401 response. The tracker notes that all
  three are recorded as `LOGIN_FAILURE` with result `denied`.
- **TC-SEC-005 — Pass.** Direct calls to Administrator-only APIs return 403
  without restricted data; the tracker says the denied attempts were
  recorded.
- **TC-SEC-006 — Pass.** Role escalation through self-profile input is
  ignored, direct protected updates are refused, and the tracker notes audit
  evidence for the denied attempt.
- **TC-SEC-008 — Pass.** An Operator's audit-log request is denied with 403.
- **TC-SEC-009 — Pass.** Deactivating an account preserves its audit and
  incident history; restoration keeps that history.
- **TC-SEC-010 — Pass.** The Administrator's forced password reset is
  recorded as `USER_PASSWORD_RESET`, with the acting Administrator.
- **TC-SEC-027 — Pass.** The recorded refusal examples retain actor or
  attempted username, source address, and target where applicable while
  storing normalized reasons instead of the password or confirmation text.

For update/delete protection, `test_schema.py` exercises SQL statements
against the triggers, and `test_audit.py` exercises the same protection after
replaying database migrations. The Security Testing sheet's TC-SEC-026 is a
separate API-surface check; it is not the proof of trigger behavior.

### Where the tracker narrows the claim

Do not say that every HTTP 403 or every rejected request necessarily creates
an audit row.

**TC-SEC-024 — marked Pass, with an important actual-result note.** The
cross-origin confirmation request is rejected with 403 at the Origin check,
before it reaches the audited service layer. The tracker explicitly says no
audit row was written for that refusal, even though the expected-result column
asks for one. This case does not support a claim that middleware-level
Origin denials are present in the audit table.

**TC-SEC-026 — marked Pass, with an important actual-result note.** The
tracker says there is no edit or delete route: PATCH and DELETE requests
return 404, and the audit contents remain unchanged. The expected-result
column asks for attempted mutations to be recorded, but the actual note does
not show a row for those 404 requests. Use the database-trigger tests for the
immutability claim; do not claim these nonexistent-route attempts were logged.

**TC-SEC-027 distinguishes the implementation's result categories.** Its
expected-result text calls for result `failure`, while its actual examples
show credential and restore refusals recorded as `denied`. In the code,
`denied` and `failure` are separate allowed values. When describing those
specific security-test examples, say `denied`.

The tested login paths include wrong passwords, unknown usernames, and
deactivated accounts. Do not expand that result to malformed requests that
may be rejected by request validation before the login route records an
attempt.

### Evidence boundary

The paper describes the audit table as an immutable, append-only security
ledger for non-repudiation. The implementation supports traceability with
actor snapshots, target, action, result, timestamp, request context, source IP,
redaction, and database triggers.

This is operational evidence from the application and its SQLite database.
The project does not establish legal admissibility in a court, an external
third-party witness, or a cryptographic hash chain that independently proves
the database file was never replaced. A person with control of the host and
database file is outside the protection boundary described by the SQL
triggers. Do not claim protection against that threat as if it were tested.

An out-of-band audit insert is best-effort when the database cannot accept the
write. The helper logs a critical error and preserves the original response;
in that exceptional case the refusal row is missing. Successful state changes
behave differently: if their audit insert cannot commit, the change rolls
back.

## 7. Likely panel questions

### “Can an Administrator delete an audit entry?”

No. The application has no edit or delete endpoint, and SQLite triggers abort
`UPDATE` and `DELETE` statements against the audit table. The tracker also
records 404 responses for attempted API mutations; the database-trigger tests
cover the lower-level enforcement.

### “What happens if the audit write fails?”

For a successful state change, the audit row shares the transaction, so a
failed insert prevents both from committing. For a denied or failed attempt,
the separate audit write is best-effort; if it fails, the system logs a
critical error but keeps the original 403 or other response.

### “Would this stand up as evidence?”

The paper presents it as an append-only operational audit ledger, and each
row ties an actor, action, target, result, time, and request context together.
We can defend that traceability design; we did not test courtroom admissibility
or independent proof against someone controlling the database file.

### “What exactly gets recorded when an operator dismisses an alert?”

The row records the actor, successful action, incident target, camera ID and
name in detail, source IP, request ID when present, and UTC time. The action
code distinguishes `ALERT_DISMISS` from `ALERT_CORRECTION`; the incident row
keeps the lifecycle state and timestamps.

### “Do you log failed logins?”

Yes. Wrong-password, unknown-user, and deactivated-account attempts are
recorded as `LOGIN_FAILURE` with result `denied`; an unknown account keeps the
attempted username but has no user ID. TC-SEC-001 confirms those tested cases
share the same generic 401 response.

### “Does every 403 get written to the audit table?”

No. Catalogued role and service refusals use the separate denied-row path,
but TC-SEC-024 says an Origin rejection occurs before the audited service
and leaves no row. Be exact about that boundary instead of claiming every
early request rejection is audited.

### “Why not keep the database rule and query filter as separate lists?”

Separate lists could drift: the database might accept an action the viewer
cannot filter, or the viewer might accept a value that cannot be stored. Both
are generated from `AUDIT_ACTIONS`, so the catalogue is the shared source.

### “Are passwords or tokens stored in the detail field?”

Credential-like detail keys are masked recursively, known configured secret
values are removed from strings, credential URLs are scrubbed, and configured
storage paths are replaced. The tested refusal rows store normalized reasons,
not the submitted password or confirmation string.

### “Is opening the audit page itself logged?”

No. Reading the viewer is treated as a read and is not logged, which avoids
recursive noise. Exporting audit records is a distinct action and is logged;
the export watermark excludes its own event from the file.

### “What if the process stops between the state update and the audit insert?”

The application does not commit those writes separately. They share one
database transaction, so a process interruption before commit leaves neither
durable; a completed commit leaves both durable.

## 8. Cram summary

- FR-20 defines the critical action coverage and core audit fields; NFR-21
  requires same-time recording, redaction, and no user edit/delete.
- One `AUDIT_ACTIONS` tuple generates the database action `CHECK` and the
  `AuditAction` enum used to validate viewer filters.
- A successful audited state change and its audit row share one commit. If
  the audit insert fails, the state change rolls back too.
- Denied and failed outcomes use a separate short transaction after primary
  work has rolled back or stopped. Losing that write must not change a 403
  into a 500; the helper logs a critical error and preserves the response.
- Detail redaction masks credential fields, known secrets, credential URLs,
  and configured absolute storage paths before JSON is saved.
- SQLite triggers reject audit-row updates and deletes; the API exposes no
  edit or delete route.
- A dismissal row identifies the operator, `ALERT_DISMISS` or
  `ALERT_CORRECTION`, incident target, camera context, and request metadata.
- Answer the tracker precisely: TC-SEC-024's early Origin denial and
  TC-SEC-026's nonexistent-route 404 attempts are not shown as audit rows.
- Describe this as operational traceability and append-only protection
  within the application/database boundary, not independent legal proof
  against someone controlling the database file.
