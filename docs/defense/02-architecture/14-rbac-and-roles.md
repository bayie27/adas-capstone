# 14 — RBAC and roles

> **One-liner:** ADAS gives Operators the complete operational workflow and gives Administrators that same workflow plus account, audit, AI-performance, and backup/restore authority.
> **Panel risk:** high — the boundary is easy to test directly, and the panel can ask what happens after a role change, a forged request, or a stale session.

## 1. What it is

Role-based access control (RBAC) is the server-side decision about which authenticated user may call an endpoint or perform an operation.

ADAS defines exactly two application roles: **Operator** and **Administrator**. The paper describes an Operator as the command-center user who monitors feeds, verifies alerts, manages the incident lifecycle, manages camera configurations, reviews history, and uses the operational dashboard. An Administrator inherits those capabilities and additionally manages accounts, audit records, AI-performance reporting, and backup and restoration.

An Operator therefore has the working surface needed to handle an alert from detection through clearance. An Administrator has that same surface plus governance and maintenance controls.

The important boundary is the backend. React uses the role to choose a route tree and hide navigation, but a caller can still type a URL or construct an HTTP request. FastAPI dependencies and route checks must reject that request before protected data or a protected mutation is reached.

The authorization question is separate from authentication:

1. Is the cookie a valid, active session for an active user?
2. What role does that user have **now**, in the database?
3. Does that current role permit this endpoint and this resource?

A menu, a URL, or the role value copied into a token cannot answer the second question safely.

## 2. Where it lives

### In the paper

The primary statement is **FR-02 Role-Based Access Control** in Chapter 3, Requirements Analysis, Functional Requirements Specification, **Table 2**. It gives Operators the analytics dashboard, active camera lists and configurations, detection logs, and system-health metrics; Administrators inherit those privileges and have exclusive access to AI-performance monitoring, AI-performance exports, and User Account Management.

**FR-03 User Account Management** in Table 2 says Administrators create, edit, deactivate, restore, assign roles, change passwords, and search the user list. Operators may update only their own account details and their own password.

**FR-14 Camera Configuration Management**, **FR-15 System Health and Hardware Telemetry**, **FR-16 AI Performance**, **FR-17 Accident Analytics and Visualization**, and **FR-18 Report Generation and Data Export** define the operational and report surfaces that the matrix below maps to actual routes.

**FR-19 Help Center** requires guidance tailored to the user’s access level. **FR-20 Activity Audit Trail** requires critical incident, camera, report, account, and login activity to retain the actor, role, action, target, time, and result.

The paper’s Chapter 1 Scope and Delimitations, User Scope paragraph, and Chapter 3 Use Case Diagram narrative (Figure 4) states the same inheritance rule: both roles operate the system; Administrators additionally manage users, audit records, and backup/restoration. The Chapter 3 Use Cases for Manage User Accounts, Trigger and Manage Database Backups, Restore the System from a Backup, and Review and Export the Activity Audit Log identify Administrator as the actor.

The Chapter 3 System Architecture and Design, Backend Layer, and Secure Access and Session Management narrative describe per-route RBAC through FastAPI dependency injection, an HttpOnly cookie, and a server-side session row. The Chapter 3 Testing and Validation, Security Testing subsection names session security, RBAC, audit integrity, non-repudiation, transport security, and data localization as tested security areas.

The test evidence is in docs/ADAS Test Execution.xlsx, worksheet **Security Testing**. The most relevant rows are TC-SEC-003 through TC-SEC-010 and TC-SEC-027; their recorded results are summarized in Section 6 below.

### In the code

The role values are Admin and Operator in backend/app/models/enums.py:4-7. The user.role column has a database CHECK constraint in backend/app/models/user.py:30-41.

Authentication and current-role resolution are in backend/app/api/dependencies.py:48-115:

- authenticate_session_token verifies the token, loads the active auth_session, loads the active User, and returns the database row.
- get_current_user reads the HttpOnly cookie and calls that function.
- The role claim in the token is not used to authorize a route.

The reusable Administrator dependency is require_admin in backend/app/api/dependencies.py:118-152. Its action-named variants are created in:

- backend/app/api/routes/users.py:34-40
- backend/app/api/routes/maintenance.py:73-76

The route modules containing the matrix are:

- incidents: backend/app/api/routes/alerts.py:54-58
- cameras: backend/app/api/routes/cameras.py:47-51
- analytics: backend/app/api/routes/analytics.py:50-54
- audit: backend/app/api/routes/audit.py:27-31
- users: backend/app/api/routes/users.py:29-40
- exports: backend/app/api/routes/exports.py:28-29
- help: backend/app/api/routes/help.py:11-15
- alarm settings: backend/app/api/routes/settings.py:18-22
- system health: backend/app/api/routes/system_health.py:29-33
- maintenance: backend/app/api/routes/maintenance.py:73-76

The frontend route split is convenience only: frontend/src/App.tsx:73-112 mounts the Administrator tree under /admin and the Operator tree under /user; frontend/src/components/ProtectedRoute.tsx:12-27 redirects a stale or mismatched client role. The API remains authoritative.

## 3. How it works

### Request authentication, then authorization

1. The browser sends the session cookie. The browser JavaScript does not hold the token.
2. get_current_user reads the cookie in backend/app/api/dependencies.py:104-115.
3. authenticate_session_token verifies the configured JWT signature, issuer, audience, and expiry in backend/app/api/dependencies.py:63-76.
4. It reads sid and sub, loads the active server-side session, checks that the session belongs to that user, and loads the user row in backend/app/api/dependencies.py:78-101.
5. An inactive user or revoked session receives 401. A valid active Operator reaching an Administrator gate is authenticated but forbidden, so that request receives 403.
6. The returned User.role is the current database value. The code never authorizes from payload["role"].
7. The route dependency runs before the endpoint body. An invalid role cannot get as far as a query, form mutation, backup trigger, or report generation.

The token does contain a role claim in backend/app/core/security.py:36-50, but that function documents it as frontend initialization context. The authoritative role lookup is the session.get(User, sub_user_id) in backend/app/api/dependencies.py:97-101.

### Endpoint-by-endpoint matrix

Allowed means that the role passes the role check; normal input, ownership, resource-state, and validation rules still apply. 403 means the role check itself rejects the request. A 404, 409, 422, or 401 after an allowed role check is a different failure.

#### Authentication, profile, and operational incident work

| Endpoint                          | Operator | Administrator | Route evidence and meaning                                                                                                                                                     |
| --------------------------------- | -------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| POST /api/auth/login              | Allowed  | Allowed       | Public credential entry in backend/app/api/routes/auth.py:39-46; the resulting user role is returned after authentication.                                                     |
| POST /api/auth/logout             | Allowed  | Allowed       | Idempotent session revocation in backend/app/api/routes/auth.py:137-188; the role does not change the ability to log out.                                                      |
| GET /api/users/me                 | Allowed  | Allowed       | Own profile read, backend/app/api/routes/users.py:83-88.                                                                                                                       |
| PATCH /api/users/me               | Allowed  | Allowed       | Own username, first name, and last name only, backend/app/api/routes/users.py:91-133; UserOperatorUpdate has no role or active-state field, backend/app/schemas/user.py:34-50. |
| PATCH /api/users/me/password      | Allowed  | Allowed       | Own password after old-password verification, backend/app/api/routes/users.py:136-171; the user’s sessions are revoked after the change.                                       |
| GET /api/alerts/                  | Allowed  | Allowed       | Incident list and filters, backend/app/api/routes/alerts.py:222-296.                                                                                                           |
| GET /api/alerts/export            | Allowed  | Allowed       | Incident CSV/PDF export, backend/app/api/routes/alerts.py:299-418; REPORT_EXPORT is recorded by the export service.                                                            |
| GET /api/alerts/{log_id}          | Allowed  | Allowed       | Detailed incident record, backend/app/api/routes/alerts.py:421-435.                                                                                                            |
| GET /api/alerts/{log_id}/snapshot | Allowed  | Allowed       | Session-authenticated evidence retrieval, backend/app/api/routes/alerts.py:438-456.                                                                                            |
| POST /api/alerts/{log_id}/confirm | Allowed  | Allowed       | HITL Unverified → Ongoing, backend/app/api/routes/alerts.py:464-514; the state change and audit row commit together.                                                           |
| POST /api/alerts/{log_id}/dismiss | Allowed  | Allowed       | False-positive or correction path, backend/app/api/routes/alerts.py:517-599; it also applies the camera cooldown/resume rule.                                                  |
| POST /api/alerts/{log_id}/clear   | Allowed  | Allowed       | Ongoing → Cleared, backend/app/api/routes/alerts.py:602-662; it resumes the camera after the audited commit.                                                                   |
| POST /api/alerts/{log_id}/snooze  | Allowed  | Allowed       | Shared incident snooze, backend/app/api/routes/alerts.py:665-710; it is tied to the caller’s saved alarm setting.                                                              |

This is the first answer to “what can an Operator do?” The Operator can complete the operational incident workflow. The Administrator can do the same work because Administrator is an inherited, higher access level.

#### Cameras, dashboard analytics, health, settings, and help

| Endpoint                              | Operator               | Administrator                               | Route evidence and meaning                                                                                                               |
| ------------------------------------- | ---------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| GET /api/cameras/                     | Allowed                | Allowed                                     | Camera list, status filters, and KPIs, backend/app/api/routes/cameras.py:151-223.                                                        |
| GET /api/cameras/{camera_id}          | Allowed                | Allowed                                     | Diagnostic detail, backend/app/api/routes/cameras.py:226-255; rtsp_url_redacted is populated only for an Administrator at lines 242-254. |
| POST /api/cameras/                    | Allowed                | Allowed                                     | Add camera, backend/app/api/routes/cameras.py:258-301; audited as CAMERA_CREATE.                                                         |
| PATCH /api/cameras/{camera_id}        | Allowed                | Allowed                                     | Edit, enable/disable, and restore camera, backend/app/api/routes/cameras.py:304-441; audited by semantic action.                         |
| DELETE /api/cameras/{camera_id}       | Allowed                | Allowed                                     | Soft-remove camera, backend/app/api/routes/cameras.py:444-483; an open incident is a domain precondition.                                |
| GET /api/analytics/dashboard          | Allowed                | Allowed                                     | Operational dashboard data, backend/app/api/routes/analytics.py:266-305.                                                                 |
| GET /api/analytics/export/dashboard   | Allowed                | Allowed                                     | Dashboard summary CSV/PDF, backend/app/api/routes/analytics.py:341-504.                                                                  |
| GET /api/analytics/performance        | 403                    | Allowed                                     | Administrator-only AI-performance view, backend/app/api/routes/analytics.py:673-740, with get_current_admin at line 696.                 |
| GET /api/analytics/export/performance | 403                    | Allowed                                     | Administrator-only performance export, backend/app/api/routes/analytics.py:743-800, with get_current_admin at line 752.                  |
| GET /api/system/health/live           | Allowed                | Allowed                                     | Authenticated live telemetry, backend/app/api/routes/system_health.py:208-210.                                                           |
| GET /api/system/health/history        | Allowed                | Allowed                                     | Authenticated historical telemetry, backend/app/api/routes/system_health.py:246-252.                                                     |
| GET /api/settings/alarm               | Allowed                | Allowed                                     | Caller’s own alarm preferences, backend/app/api/routes/settings.py:31-49.                                                                |
| PUT /api/settings/alarm               | Allowed                | Allowed                                     | Caller’s own alarm preferences, backend/app/api/routes/settings.py:52-80; it cannot edit another user’s settings.                        |
| GET /api/help/articles                | Allowed, role-filtered | Allowed, includes Operator-visible articles | backend/app/api/routes/help.py:18-45 passes the current role to the help service.                                                        |
| GET /api/help/articles/{slug}         | Allowed if visible     | Allowed if visible                          | backend/app/api/routes/help.py:47-57 returns 404 when the article is not visible to that role, avoiding existence disclosure.            |

The paper’s FR-14, FR-15, and FR-17 therefore remain operational for both roles. FR-16 is the deliberate Administrator-only exception. A camera detail response is a useful small example of field-level authorization: both roles may diagnose the camera, but only the Administrator receives the redacted RTSP value.

#### Account management, audit, maintenance, and asynchronous exports

| Endpoint                                                       | Operator                | Administrator                           | Route evidence and meaning                                                                                                                                               |
| -------------------------------------------------------------- | ----------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GET /api/users/                                                | 403                     | Allowed                                 | Administrator user directory, backend/app/api/routes/users.py:202-246, gated by get_current_admin.                                                                       |
| POST /api/users/                                               | 403                     | Allowed                                 | Create account, backend/app/api/routes/users.py:249-296, gated by require_admin("USER_CREATE").                                                                          |
| PATCH /api/users/{user_id}                                     | 403                     | Allowed                                 | Edit profile, role, or active state and restore a deactivated account, backend/app/api/routes/users.py:299-460, gated by require_admin("USER_UPDATE").                   |
| POST /api/users/{user_id}/reset-password                       | 403                     | Allowed                                 | Force-reset another user’s password, backend/app/api/routes/users.py:463-496, gated by require_admin("USER_PASSWORD_RESET").                                             |
| DELETE /api/users/{user_id}                                    | 403                     | Allowed                                 | Soft-disable another account, backend/app/api/routes/users.py:498-564, gated by require_admin("USER_DISABLE"); self-delete and last-Administrator deletion are rejected. |
| GET /api/audit-logs/                                           | 403                     | Allowed                                 | Append-only audit viewer, backend/app/api/routes/audit.py:143-213, router-gated by get_current_admin. An Operator gets 403, not an empty list.                           |
| GET /api/audit-logs/export                                     | 403                     | Allowed                                 | Audit CSV/PDF export, backend/app/api/routes/audit.py:274-440, gated by get_current_admin; the export itself writes AUDIT_EXPORT.                                        |
| POST /api/exports/jobs with report_type=incidents or dashboard | Allowed                 | Allowed                                 | Async operational export creation, backend/app/api/routes/exports.py:54-92.                                                                                              |
| POST /api/exports/jobs with report_type=audit or performance   | 403                     | Allowed                                 | The explicit report-type check at backend/app/api/routes/exports.py:66-79 prevents an Operator from using async jobs as a side door.                                     |
| GET /api/exports/jobs                                          | Own visible jobs        | Own jobs; all users with all_users=true | backend/app/api/routes/exports.py:111-154; an Operator cannot pass all_users=true, and performance jobs are excluded from the Operator’s list.                           |
| GET /api/exports/jobs/{job_id}                                 | Own non-performance job | Own or any permitted job                | Ownership and report-type checks are in backend/app/api/routes/exports.py:157-190; an Administrator can inspect the job of another user.                                 |
| GET /api/exports/jobs/{job_id}/download                        | Own non-performance job | Own or any permitted job                | The same owner/report-type guard runs before artifact download, backend/app/api/routes/exports.py:193-225.                                                               |
| POST /api/exports/retraining                                   | 403                     | Allowed                                 | Administrator-only retraining package, backend/app/api/routes/exports.py:228-253, gated by get_current_admin.                                                            |
| GET /api/system/backups                                        | 403                     | Allowed                                 | Backup inventory, backend/app/api/routes/maintenance.py:158-184, gated by get_current_admin.                                                                             |
| POST /api/system/backups                                       | 403                     | Allowed                                 | Manual backup trigger, backend/app/api/routes/maintenance.py:187-230, gated by require_admin("BACKUP_TRIGGER").                                                          |
| POST /api/system/restores                                      | 403                     | Allowed                                 | Restore request, backend/app/api/routes/maintenance.py:233-538, gated by require_admin("RESTORE_TRIGGER") plus password, confirmation, and backup validation.            |
| GET /api/system/restores/latest                                | 403                     | Allowed                                 | Latest restore state, backend/app/api/routes/maintenance.py:573-580, gated by get_current_admin.                                                                         |
| GET /api/system/maintenance/status                             | 403                     | Allowed                                 | Backup/restart maintenance status, backend/app/api/routes/maintenance.py:684-720, gated by get_current_admin.                                                            |

This table is the complete Administrator-only application surface represented by the current route definitions. FR-03 maps to the five user routes; FR-16 and the performance branch of FR-18 map to the performance routes; the paper’s administrative use cases map to audit and maintenance routes.

#### Service, probe, schema, and development routes

| Endpoint                                | Operator                          | Administrator                     | Role meaning                                                                                                                                                |
| --------------------------------------- | --------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET /                                   | Unauthenticated                   | Unauthenticated                   | Process health response in backend/app/main.py:615-616; no user data.                                                                                       |
| GET /healthz/live                       | Unauthenticated                   | Unauthenticated                   | Liveness probe, backend/app/api/routes/system.py:14-18.                                                                                                     |
| GET /healthz/ready                      | Unauthenticated                   | Unauthenticated                   | Readiness probe, backend/app/api/routes/system.py:20-31.                                                                                                    |
| GET /api/events/schema                  | Public documentation route        | Public documentation route        | Event-envelope schema only, backend/app/api/routes/events.py:14-41.                                                                                         |
| POST /api/internal/alert                | Internal API key                  | Internal API key                  | AI-engine seam, backend/app/api/routes/internal.py:30-34,93-137; it is not browser-user RBAC.                                                               |
| POST /api/internal/heartbeat            | Internal API key                  | Internal API key                  | AI-engine heartbeat seam, backend/app/api/routes/internal.py:139-183; it uses X-API-Key.                                                                    |
| GET /ws/alerts                          | Authenticated                     | Authenticated                     | Handshake in backend/app/main.py:442-505 authenticates the cookie and records the current role on the connection.                                           |
| GET /api/dev/status                     | Public when dev router is enabled | Public when dev router is enabled | Safe capability probe, backend/app/api/routes/dev.py:106-120; when disabled, the router is not registered and the route is absent.                          |
| POST /api/dev/reseed                    | 403                               | Allowed                           | Development-only reseed, backend/app/api/routes/dev.py:123-187, gated by get_current_admin.                                                                 |
| POST /api/dev/login-as                  | Allowed if already authenticated  | Allowed                           | Development-only account switcher, backend/app/api/routes/dev.py:190-224, gated by get_current_user; it is intentionally not an unauthenticated login path. |
| POST /api/dev/detections                | 403                               | Allowed                           | Development detection injection, backend/app/api/routes/dev.py:227-274, gated by get_current_admin.                                                         |
| POST /api/dev/cameras/{camera_id}/state | 403                               | Allowed                           | Development camera-state control, backend/app/api/routes/dev.py:307-362, gated by get_current_admin.                                                        |
| POST /api/dev/health-history            | 403                               | Allowed                           | Development telemetry seeding, backend/app/api/routes/dev.py:365-375, gated by get_current_admin.                                                           |
| POST /api/dev/uat/reset                 | 403                               | Allowed                           | Development UAT reset, backend/app/api/routes/dev.py:378-397, gated by get_current_admin.                                                                   |

The development rows matter when reading code, but they are not the paper’s production role claim. create_app includes the dev router only when DEV_TOOLS_ENABLED is true, backend/app/main.py:602-606; the setting defaults from the environment in backend/app/core/config.py:144-157. A defense demonstration must state whether that test-only router is enabled.

### Exactly what an Operator cannot do

An Operator cannot:

- list the user directory or inspect another account;
- create an account, edit another account, assign a role, restore or disable an account, or reset another user’s password;
- read or export the audit trail;
- open AI-performance analytics or export AI-performance data;
- create audit or performance asynchronous export jobs;
- widen asynchronous export listing to all_users=true, inspect another user’s job, or download another user’s job;
- request a retraining package; or
- view or trigger backup and restore administration.

The Operator can still add, edit, enable/disable, restore, and remove cameras because the current camera routes depend on get_current_user, not get_current_admin. That is an intentional operational capability under FR-14 and the paper’s Operator scope.

### Where the 403 is produced

For a reusable Administrator dependency, require_admin compares the current database role at backend/app/api/dependencies.py:128-147. When the role is not Admin, it raises AppHTTPException(status.HTTP_403_FORBIDDEN, ..., code="FORBIDDEN").

FastAPI resolves that dependency before the endpoint handler. The common HTTP exception handler in backend/app/main.py:359-368 turns the exception into the API error envelope. That is why a malformed Administrator request body cannot make an Operator reach the handler: the role check runs first.

Some resource-level gates are explicit handler checks rather than require_admin: async export creation and listing at backend/app/api/routes/exports.py:71-79 and 127-141, and owner/report checks at exports.py:164-179. They also raise 403, but they are checking report type or ownership after the caller is authenticated.

An Origin rejection can also be a 403, but it is a transport/CSRF defense in backend/app/main.py:330-356, not an RBAC decision. Keep those two reasons separate when explaining a failed request.

### Why a denial writes its own audit row

A denied Administrator action is security evidence even though the requested mutation never happened. For action-named guards, require_admin calls record_out_of_band before raising 403 (backend/app/api/dependencies.py:133-146). The action codes used by the current guards are USER_CREATE, USER_UPDATE, USER_PASSWORD_RESET, USER_DISABLE, BACKUP_TRIGGER, and RESTORE_TRIGGER.

record_out_of_band opens a short-lived session and commits the denied row independently in backend/app/services/audit.py:99-130. It cannot share a transaction that contains a successful mutation because the denied handler has no successful mutation to commit, and the request may already be rolling back. The audit service captures the actor and role and redacts sensitive detail values in backend/app/services/audit.py:13-31,72-96.

Routine read gates created with get_current_admin = require_admin(None) intentionally have no catalog action and are not themselves audited; this is stated in backend/app/api/dependencies.py:118-126 and backend/app/api/routes/audit.py:175-179. The audit viewer cannot audit every read of itself without creating recursive noise. The tracker’s RBAC rows still provide the recorded evidence for the tested denied requests; the code distinction is whether the guard was given a catalog action.

For a successful state change, the route records the success row in the same transaction as the state mutation. That is the FR-20 rule: a critical state change must not persist without its evidence. A denied or failed attempt is a separate out-of-band denied or failure row.

### What happens if the role changes mid-session

When an Administrator changes a user’s role, update_user computes role_changed before mutation, changes the row, revokes all of that user’s sessions, commits the user and audit rows, and then closes the user’s live sockets (backend/app/api/routes/users.py:364-387,392-458). The active user cannot keep the old session merely because its natural expiry has not arrived.

On the next HTTP request, the revoked auth_session produces 401. If a race leaves a request with an active session, authenticate_session_token still loads the current User row and authorization uses its current role. A stale Admin claim therefore cannot grant Administrator access.

The last-active-Administrator invariant is checked before demotion or deactivation in backend/app/api/routes/users.py:321-362 and before delete in users.py:531-546. The system refuses the lockout state and records the denied administrative action.

The WebSocket handshake follows the same cookie/session authentication in backend/app/main.py:459-494. Direct role-change and account-disable paths close existing sockets through RealtimeManager.close_user; the scheduled revalidation catch-all also closes sockets whose session was revoked or whose user is inactive (backend/app/services/realtime_revalidation.py:25-43).

## 4. Why it was built this way

### Backend enforcement is mandatory

A frontend-only role switch protects navigation but does not protect an API. A caller can send a request with curl, browser developer tools, or another client. Server-side dependencies put the decision before protected data access and before mutations.

### The database role beats the token role

A token is a snapshot issued at login. Account administrators can change a role or deactivate an account later. Loading the active session and User row on every protected request lets the server revoke access and apply the current role without trusting client-visible state.

### Authentication and authorization stay distinct

401 means the caller has no valid active session: the cookie is missing, invalid, expired, revoked, or attached to an inactive account. 403 means the session is valid, but the role or resource authorization is insufficient. That distinction gives the frontend a useful response and gives the panel a precise security explanation.

### Administrator inherits the operational surface

The paper defines Administrator as the higher access level. The routes therefore protect only the exclusive surfaces instead of duplicating every operational route with a second implementation. The same incident transition, camera state, and dashboard code serves both roles.

### Denied attempts are evidence

The audit trail is not only a history of successful work. A denied account, backup, restore, or role-management attempt is an event that a security reviewer may need to investigate. Writing it out-of-band preserves the denied result without claiming that a state change occurred.

### Last-admin protection preserves recoverability

A user-management feature that could remove the final active Administrator would be able to lock the team out of its own recovery controls. The route checks the count before demotion, deactivation, or deletion and rejects the operation if it would leave no active Administrator.

## 5. What changed since the 28 April defense

The current tree shows a materially fuller RBAC and session boundary than the April baseline. The relevant post-28-April history includes:

- cfc0aa7 added cookie-only request authentication with the active-session check.
- 3fe8d19 added session revocation for password, role, and account-status changes.
- 597d1c9 and 4c72c77 added the shared audit service and wired auth/user actions to it.
- 5cee396 added asynchronous export jobs and the retraining package; ccac2b5 closed the async audit-report boundary to Administrators.
- 432311b made AI-performance routes Administrator-only, including the synchronous boundary.
- b0810ff added the Administrator audit viewer/export surface; 413071e added the Administrator backup list and trigger.
- 1d7f735 added restoration of deactivated user rows through the Administrator update route.

The current paper claim is the one to defend: Operators use the operational system; Administrators inherit those capabilities and additionally control user accounts, audit records, AI-performance reports, and backup/restoration. The route matrix above is the implementation evidence for that claim.

## 6. Limits and honest caveats

- RBAC proves who may invoke an operation. It does not decide whether an Operator’s incident judgment is correct; that remains the HITL workflow.
- The matrix describes authorization before ordinary domain checks. An allowed user can still receive 404, 409, or 422 for a missing record, a state conflict, or invalid input.
- The role cache in the frontend is a navigation convenience. It is not a security credential; the HttpOnly cookie and backend session check remain authoritative.
- The camera detail endpoint intentionally returns a reduced field set to an Operator. This is field-level masking inside an operationally shared route.
- Help visibility is role-filtered and uses 404 for an inaccessible article slug, so a restricted article is not confirmed to exist.
- Internal AI routes and host health probes have separate purposes and credentials. Their existence does not give a browser Operator administrative capability.
- Development tools are conditional. When enabled, POST /api/dev/login-as is available to any already authenticated user as a test account switcher. It can switch to a seeded active account, so it must be treated as a demonstration/test control, not as the production RBAC story.
- The paper’s role scope is the Lipa CDRRMO command-center Operator and Administrator model. It does not claim a multi-tenant permission hierarchy or arbitrary per-user capabilities.

### Security Testing sheet evidence

| Tracker item | Requirement link    | Recorded result and what it demonstrates                                                                                                                                                               |
| ------------ | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TC-SEC-003   | FR-02               | Pass. An Operator’s user-management request returns 403 before protected administration data is returned. The tracker records the full backend fast suite as 939 passed, 2 skipped, and 12 deselected. |
| TC-SEC-004   | FR-02, FR-16, FR-18 | Pass. The Administrator-only AI-performance boundary holds for synchronous analytics and asynchronous job operations; the tracker records the targeted P29 backend suite as 227 passed.                |
| TC-SEC-005   | FR-02               | Pass. Direct Operator calls to /api/users/, /api/audit-logs/, and /api/system/backups return 403 with no restricted body; client-side interception is recorded under TC-SYS-001.                       |
| TC-SEC-006   | FR-02, FR-03        | Pass. A self-profile role field is ignored, a direct protected role update returns 403, the stored role remains Operator, and the denied attempt leaves audit evidence.                                |
| TC-SEC-007   | FR-02, NFR-19       | Pass. No-cookie and revoked-cookie WebSocket handshakes are refused before a message; a valid Operator receives CONNECTION_READY.                                                                      |
| TC-SEC-008   | FR-02, NFR-21       | Pass. An Operator’s audit-log request returns 403.                                                                                                                                                     |
| TC-SEC-009   | FR-03               | Pass. User deletion is a soft deactivation; history remains attributable and the account can be restored.                                                                                              |
| TC-SEC-010   | FR-03, NFR-19       | Pass. An Administrator password reset revokes the target’s session immediately; the next request is refused and the live alert connection is closed.                                                   |
| TC-SEC-027   | NFR-21              | Pass. Failed and unauthorized attempts retain actor, source address, and target context while hiding passwords, tokens, and confirmation strings.                                                      |

The tracker qualifies these as recorded checks in the Security Testing activity. Quote the item ID and its recorded result, rather than presenting the test row as a claim about unmeasured production deployment.

## 7. Likely panel questions

### “Show me exactly what an Operator cannot do.”

They cannot manage another account or role, reset another password, read or export the audit trail, view or export AI-performance data, request retraining, widen export jobs to all users, or run backup/restore administration. The backend rejects those requests with 403 after authenticating the caller.

### “Could an Operator escalate to Administrator?”

Not through the production account routes. Self-service accepts only name fields, and direct role changes require the current caller to be an Administrator. If development tools are deliberately enabled, login-as is a test switcher for an already authenticated user, so that route must not be presented as production authorization.

### “What if someone’s role changes mid-session?”

The Administrator role-change path revokes every session for that user and closes their live connections. The next request is 401; independently, authorization reloads the current database role, so a stale token claim cannot preserve Administrator access.

### “Where is that enforced — the frontend or the backend?”

The backend. React redirects and hides Administrator destinations for usability, but FastAPI dependencies and explicit route checks enforce the actual boundary. A direct request cannot bypass the backend by skipping the UI.

### “Why is this 403 and not 401?”

401 means the caller has no valid active session. 403 means the session is valid, but the current role or resource authorization is insufficient.

### “Why not trust the role claim in the JWT?”

The claim is a snapshot from login and can become stale. The server verifies the session, reloads the User row, and authorizes from the current database role instead.

### “Do denied actions leave evidence?”

Action-named Administrator guards write a separate denied audit row before returning 403. The row keeps the actor, role, action, target, time, and source address where available, with sensitive values redacted.

### “Can an Administrator do everything an Operator can?”

Yes. Administrator inherits the incident, camera, dashboard, health, settings, help, and export capabilities available to an Operator. The extra routes are account, audit, AI-performance, retraining, and maintenance controls.

### “Why can an Operator change cameras if cameras are security-sensitive?”

The paper defines camera configuration as part of the Operator’s operational work, and the current camera router uses get_current_user for list, add, edit, restore, and remove. Every mutation is still validated and audited; role separation is reserved for governance and maintenance surfaces.

### “Can an Operator see an empty audit page?”

No. The audit viewer is Administrator-only and returns 403 rather than an empty list. That makes a permission boundary visible instead of making an unauthorized user look like there is simply no history.

### “What prevents deleting the last Administrator?”

The user route counts active Administrators before demotion, deactivation, or deletion. If the target is the last active Administrator, the operation is rejected and the attempted administrative action is recorded.

### “Is the WebSocket a role bypass?”

No. The handshake reads the same session cookie and active User row as HTTP. Both roles receive operational alert events, while revoked sessions and inactive users are disconnected.

### “Can the AI engine impersonate an Administrator?”

No. The AI engine uses the internal API key on /api/internal/alert and /api/internal/heartbeat. Those service-to-service routes do not create a browser user session or grant Administrator permissions.

### “What does your security testing actually prove?”

The Security Testing sheet records the executed RBAC, session, and audit checks. TC-SEC-003 through TC-SEC-010 and TC-SEC-027 cover account boundaries, AI-performance boundaries, direct API calls, role escalation, WebSocket authentication, revocation, and redacted denial evidence in the recorded test environment.

## 8. Cram summary

- ADAS has two roles: Operator and Administrator.
- Administrator inherits the complete Operator operational surface.
- Operators handle alerts, cameras, incident history, dashboard analytics, health, personal settings, and help.
- Administrators additionally manage users and roles, view/export audits, view/export AI performance, request retraining packages, and administer backup/restore.
- get_current_user verifies the cookie and active server-side session, then reloads the active User row.
- Authorization uses the current database role, never the JWT role claim.
- require_admin runs before protected handlers and returns 403 FORBIDDEN for a valid Operator.
- Action-named Administrator guards write a separate denied audit row; routine read gates intentionally have no catalog action.
- Role changes revoke sessions and close live sockets; the last active Administrator cannot be removed.
- Frontend route hiding improves usability; backend checks are the security boundary.
- Quote FR-02, FR-03, FR-14, FR-16, FR-18, FR-19, and FR-20, plus Security Testing items TC-SEC-003 through TC-SEC-010 and TC-SEC-027.
