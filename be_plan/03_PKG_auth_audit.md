# P2 — Authentication, Sessions, RBAC, and the Audit Trail

> **Blocked by:** P1.
> **Branch:** `feat/be-p2-auth-audit`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md), `be_decisions_review.md` D-006 and D-007.
> **Size:** XL. Eleven steps.
>
> ⚠️ **This package breaks the frontend.** Hand [`11_FRONTEND_MIGRATION.md`](11_FRONTEND_MIGRATION.md)
> to the frontend owner *before* merging. It is a five-file change on their side.

## Why this package exists

Today: a stateless username-keyed JWT that cannot be revoked, no logout, an 8-hour window in which a
deactivated user's or demoted admin's token keeps working, no rate limiting on `/api/auth/login`, and
no audit trail at all — while FR-21 and NFR-21 require an append-only record of every operator and
admin action, and TC-S-501…505 test it directly.

D-007's audit helper is the piece every later package depends on, so its ergonomics matter more than
its feature count. Build it before wiring it into routes.

---

## Step 1 — Argon2id

**Files:** `backend/app/core/security.py`, `pyproject.toml`

```python
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
```

- Add `passlib[argon2]` and `argon2-cffi`. **Remove** `bcrypt==4.0.1` and `passlib[bcrypt]`.
- The `bcrypt==4.0.1` pin exists only because passlib 1.7.4 crashes on bcrypt ≥ 4.1. Dropping bcrypt
  removes that landmine.
- **No hash migration is needed.** D-006: the dev database is disposable and gets reset. Reseed after
  this step; existing dev accounts stop working, which is expected.
- Run `uv lock` and commit `uv.lock`.

---

## Step 2 — Session model and service

**Files:** `backend/app/models/user.py` (`AuthSession` from P1), new `backend/app/services/sessions.py`

```python
def create_session(session, user, *, user_agent, source_ip) -> AuthSession
def get_active_session(session, session_id) -> AuthSession | None    # not revoked, not expired
def revoke_session(session, session_id, reason) -> None
def revoke_all_for_user(session, user_id, reason) -> list[str]       # returns revoked session_ids
```

`revoke_all_for_user` returns the ids so the caller can close the matching WebSockets — P3 wires that
up; here it is just a return value.

The **database session record is authoritative**. A correctly signed JWT whose `auth_session` row is
missing, expired, or revoked is rejected.

---

## Step 3 — JWT and cookie

**File:** `backend/app/core/security.py`

Claims (D-006):

```python
{
  "sub": str(user.user_id),      # immutable id, NEVER the mutable username
  "sid": session.session_id,
  "role": user.role,             # for frontend init only — authorization reads the DB
  "iat": ..., "exp": ...,
  "iss": settings.JWT_ISSUER,
  "aud": settings.JWT_AUDIENCE,
}
```

Verification must pass `issuer=` and `audience=` to `jwt.decode` — omitting them means the claims are
written but never checked.

Cookie:

| Attribute | Value |
|---|---|
| name | `settings.SESSION_COOKIE_NAME` (`adas_session`) |
| `HttpOnly` | always `True` |
| `Secure` | `settings.SESSION_COOKIE_SECURE` — `True` in production, `False` for localhost dev |
| `SameSite` | `Strict` |
| `Path` | `/` |
| `Domain` | omitted (host-only) |
| `Max-Age` | `SESSION_LIFETIME_MINUTES * 60` |

`SameSite=Strict` works in dev even though the SPA is on `:5173` and the API on `:8000` — SameSite is
evaluated per *site*, and the port is not part of a site. In production the backend serves the SPA, so
they are same-origin anyway.

Auth responses carry `Cache-Control: no-store`.

---

## Step 4 — Request authentication

**File:** `backend/app/api/dependencies.py`

`get_current_user` performs all four checks, in order (D-006):

1. verify JWT signature, `iss`, `aud`, `exp` → `401 AUTH_EXPIRED` on expiry, `401 AUTH_REQUIRED` otherwise
2. load `auth_session` by `sid`; require active → `401 AUTH_REVOKED`
3. load `User` by `sub`; require `is_active` → `401 AUTH_REVOKED`
4. authorize using the **current database role**, never the `role` claim

The token is read from the cookie only. Remove `OAuth2PasswordBearer` from the dependency graph.

> Keep `OAuth2PasswordRequestForm` on the *login* route — it is only a form parser, and Swagger's
> "Authorize" button stops working anyway once auth moves to a cookie. That is acceptable; note it in
> the module docstring.

`get_current_admin` keeps wrapping `get_current_user` and returns `403 FORBIDDEN`.

---

## Step 5 — Origin validation

**File:** `backend/app/main.py` middleware

For every **unsafe** method (`POST`, `PUT`, `PATCH`, `DELETE`) authenticated by cookie, require the
`Origin` header to be in `CORS_ORIGINS` (or absent for same-origin non-browser callers, which is what
`TestClient` and `curl` do). Reject with `403 ORIGIN_REJECTED`.

`SameSite=Strict` already blocks the cross-site case; this is defense in depth for the case where a
browser or proxy does not honor it. State-changing behavior never uses `GET` — audit this while you
are in here.

**Exempt `/api/internal/*`** — those authenticate with `x-api-key` from a non-browser client and have
no `Origin`.

---

## Step 6 — Login rate limiting

**File:** new `backend/app/core/rate_limit.py`

A small in-process sliding-window limiter. Two independent key dimensions per D-006: **source IP** and
**normalized (lowercased, stripped) username**. Either exceeding the limit rejects.

```python
class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None: ...
    def check(self, key: str) -> tuple[bool, int]:   # (allowed, retry_after_seconds)
    def record_failure(self, key: str) -> None
    def reset(self, key: str) -> None                # on successful login
```

Only **failed** attempts count toward the limit, and a success resets both keys. Rejection returns
`429 AUTH_RATE_LIMITED` with a `Retry-After` header **and writes a `LOGIN_FAILURE` audit row with
`result='denied'`**.

`slowapi` is deliberately not used: D-005 locks a single Uvicorn worker (so process-local state is
correct), D-006 needs two key dimensions, and every rejection has to reach the audit trail. That is
about forty lines of code and a lot less indirection.

Expose a way for tests to clear the limiter between cases (an app-state instance, not a module global).

---

## Step 7 — Login and logout

**File:** `backend/app/api/routes/auth.py`

### `POST /api/auth/login` — CHANGED

1. Rate-limit check on IP and normalized username.
2. Look up the user; verify the password.
3. **Return the identical `401 AUTH_INVALID_CREDENTIALS` for unknown username, wrong password, and
   inactive account.** The current code returns a distinguishable `400` for an inactive account, which
   is an account-enumeration oracle.
4. On success: create the `auth_session`, stamp `last_login`, reset the limiter, set the cookie, write
   `LOGIN_SUCCESS`.
5. Respond `200 {"user": UserRead}` with `Cache-Control: no-store`. **No token in the body.**

Ensure timing does not leak user existence — verify a dummy hash when the user is not found.

### `POST /api/auth/logout` — NEW

Revoke the session → collect its id for WebSocket closure (P3) → delete the cookie → write `LOGOUT` →
`204`. Idempotent: logging out with an already-revoked session still returns `204`.

---

## Step 8 — Revocation cascade

Wire `revoke_all_for_user` into every event D-006 lists. Each of these already exists as a route; add
the revocation inside the same transaction:

| Route | Reason |
|---|---|
| `PATCH /api/users/me/password` | `password_change` |
| `POST /api/users/{id}/reset-password` | `password_reset` |
| `PATCH /api/users/{id}` when `role` changes | `role_change` |
| `PATCH /api/users/{id}` when `is_active` → false | `account_disabled` |
| `DELETE /api/users/{id}` | `account_disabled` |

`PATCH /api/users/me` (profile/username only) must **not** revoke — identity is `user_id`, so a rename
does not invalidate anything. Test this explicitly; it is easy to over-revoke here.

---

## Step 9 — The audit service

**File:** new `backend/app/services/audit.py`. This is the most-reused code in the whole effort.

```python
def record(
    session: Session,
    *,
    action: AuditAction,
    result: AuditResult = AuditResult.SUCCESS,
    actor: User | None = None,          # None => actor_type="system"
    target_type: str | None = None,
    target_ref: str | None = None,
    detail: dict | None = None,
    source_ip: str | None = None,
) -> AuditLog
```

- Snapshots `username` and `role` from `actor` so the row stays readable after a later rename or role
  change.
- Pulls `request_id` from the P1 `ContextVar` automatically.
- Runs `detail` through a **redaction filter** before serializing (§1.6 of the contracts doc), and
  unit-tests confirm passwords, tokens, API keys, RTSP URLs, and absolute paths never survive it.
- Adds to the caller's session and does **not** commit. Coupling is the caller's job.

Plus a helper for the denied/failure path, which by definition cannot share the rolled-back transaction:

```python
def record_out_of_band(engine, *, ...) -> None
```

It opens its own short-lived session and commits. If *that* write fails, it logs a critical structured
error and swallows — the original action stays denied/failed either way (D-007).

**Transaction rules to enforce in review:**

- A successful action and its audit row(s) commit together. If the audit insert fails, the action
  rolls back.
- One row per **semantic** action. `PATCH /api/cameras/{id}` that renames *and* disables writes both
  `CAMERA_UPDATE` and `CAMERA_DISABLE` in the same transaction.
- `detail` carries safe changed-field names with before/after values.

---

## Step 10 — Wire audit into existing routes

Add audit calls to every route that already exists. P4–P8 add theirs as they build.

| Route | Actions |
|---|---|
| `POST /api/auth/login` | `LOGIN_SUCCESS` / `LOGIN_FAILURE` (denied) |
| `POST /api/auth/logout` | `LOGOUT` |
| `POST /api/users/` | `USER_CREATE` |
| `PATCH /api/users/{id}` | `USER_UPDATE`, plus `USER_ROLE_CHANGE` / `USER_ENABLE` / `USER_DISABLE` as applicable |
| `POST /api/users/{id}/reset-password` | `USER_PASSWORD_RESET` |
| `DELETE /api/users/{id}` | `USER_DISABLE` |
| `PATCH /api/users/me` | `USER_PROFILE_UPDATE` |
| `PATCH /api/users/me/password` | `USER_PASSWORD_CHANGE` |
| `POST /api/cameras/` | `CAMERA_CREATE` |
| `PATCH /api/cameras/{id}` | `CAMERA_UPDATE` and/or `CAMERA_ENABLE` / `CAMERA_DISABLE` |
| `DELETE /api/cameras/{id}` | `CAMERA_DELETE` |

Also record `result='denied'` for the guard rejections that already exist: last-admin demote,
last-admin deactivate, last-admin delete, self-delete, and every `403` from `get_current_admin`.
TC-S-505 tests exactly this.

**RBAC decision to record in the module docstring:** `POST`/`PATCH`/`DELETE /api/cameras/*` remain
accessible to Operators. FR-02 grants Operators "camera status/config management"; only User Account
Management is Admin-exclusive. This is deliberate, not an oversight — write it down so the next
reader does not "fix" it.

---

## Step 11 — Audit viewer

**File:** new `backend/app/api/routes/audit.py`

```
GET /api/audit-logs        Admin only
```

Filters: `action[]`, `user_id[]`, `result[]`, `target_type`, `target_ref`, `start_date`, `end_date`,
`search` (across `username`, `target_ref`, `detail`). Newest-first, stable pagination — order by
`(created_at DESC, audit_id DESC)` so equal timestamps cannot shuffle between pages.

Operators get `403`, not an empty list. Viewing is not audited (it would be recursive noise);
exporting is, and the export endpoint lands in P6.

---

## Verification

```bash
uv run pytest
```

Then manually:

1. `curl -i -c jar.txt -X POST localhost:8000/api/auth/login -d 'username=admin&password=…'` →
   `200`, `Set-Cookie: adas_session=…; HttpOnly; SameSite=Strict`, **no token in the body**.
2. `curl -b jar.txt localhost:8000/api/users/me` → `200`.
3. `curl -b jar.txt -X POST localhost:8000/api/auth/logout` → `204`. Repeat step 2 → `401 AUTH_REVOKED`.
4. Log in, then have an admin deactivate that user in another session. The first session's next
   request → `401 AUTH_REVOKED` immediately, not after 8 hours.
5. Eleven failed logins in five minutes → `429` with `Retry-After`, and eleven `LOGIN_FAILURE` rows.
6. `UPDATE audit_log …` via sqlite3 → aborts.
7. **Legacy AI contract still works** — `/api/internal/*` is unaffected by the cookie change because
   it authenticates with `x-api-key`. Verify with the engine actually running.
8. `pnpm check`.

E2E: `e2e/login.spec.ts` should keep passing without modification — Playwright manages cookies
natively. If it fails, the cookie attributes are wrong for `http://127.0.0.1`, most likely `Secure`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Login | success sets cookie; unknown user / wrong password / inactive account all return the **same** body and status; `last_login` stamped; `LOGIN_SUCCESS` row |
| JWT | wrong `iss` rejected; wrong `aud` rejected; expired → `AUTH_EXPIRED`; tampered signature → `AUTH_REQUIRED` |
| Session authority | valid JWT + deleted session row → 401; + revoked → 401; + expired row but unexpired JWT → 401 |
| Logout | revokes; idempotent; cookie cleared |
| Revocation cascade | password change, admin reset, role change, deactivation, deletion each kill **all** that user's sessions; **profile rename does not** |
| Rate limit | Nth+1 failure → 429 with `Retry-After`; success resets; IP and username dimensions are independent |
| Origin | cookie-auth POST with a foreign `Origin` → 403; absent `Origin` allowed; `/api/internal/*` exempt |
| RBAC | Operator → 403 on every admin user route and on `/api/audit-logs`; denied attempts audited |
| Audit coupling | forcing the audit insert to fail rolls back the primary action; a denied action still produces a row after rollback |
| Audit redaction | password, token, API key, `rtsp://user:pass@host`, and absolute paths never appear in a stored `detail` |
| Audit immutability | API has no update/delete path; DB triggers abort both |
| Multi-action | rename + disable in one PATCH → exactly two rows, same transaction |
| Viewer | newest-first stable pagination; every filter; Operator 403 |

## Paper test cases covered

TC-U-201 (salted hash + verify), TC-U-202 (JWT carries user id and role, strict expiry),
TC-U-203 (expired token → 401), TC-U-204 (Operator → 403 before payload processing),
TC-S-201 / TC-S-202 (server-side RBAC), TC-S-203 (four-hour idle standby within the 8-hour session —
verify with a `time-machine`-frozen clock), TC-S-501…TC-S-505 (audit coverage for incident, camera,
report, login, and admin account actions).

TC-I-404 (logout closes the user's WebSocket connections) is **started** here — `revoke_session`
returns the ids — and **completed in P3**, which owns the connection registry.

## Deliberately not in this package

WebSocket authentication (P3 — but the session model it needs is done here), incident lifecycle
changes, audit export (P6), any frontend change.
