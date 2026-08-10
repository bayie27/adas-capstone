# Frontend Migration Guide

> **Audience:** the frontend owner.
> **Hand over:** before backend package **P2** merges — that is the breaking one.
> **Estimated size:** five files for auth, then incremental work as P3/P4 land.

The backend is being rebuilt against `be_decisions_review.md` (D-001…D-012). Most changes are
additive, but three are breaking. This document lists every contract change, in the order the backend
will merge them, with the exact files affected.

---

## Breaking change 1 — Auth moves to an HttpOnly cookie (backend P2)

### Why

The dashboard needs an authenticated WebSocket (D-008). **A browser cannot set an `Authorization`
header on a WebSocket handshake** — there is no API for it — and D-006 explicitly rejects putting a
token in the query string, because it lands in server logs and browser history. A cookie is sent
automatically on the handshake, which is why D-006 selected it.

The token also stops being readable by JavaScript, which is the other half of D-006: no credential in
`localStorage` or `sessionStorage`.

### What changes

| Before | After |
|---|---|
| `POST /api/auth/login` → `{access_token, token_type}` | `POST /api/auth/login` → `{"user": {...}}` **+ `Set-Cookie: adas_session=…; HttpOnly; SameSite=Strict`** |
| `Authorization: Bearer <token>` on every request | the cookie, sent automatically |
| token in `localStorage` under `adas-auth-session` | nothing stored — the cookie is invisible to JS |
| logout = clear localStorage | `POST /api/auth/logout` → real server-side revocation |
| session survives password change / role change / deactivation for up to 8h | those events revoke **immediately** |

Session lifetime is unchanged: **8 hours absolute**, no idle timeout, no refresh endpoint. TC-S-203's
four-hour standby still passes.

### Files to change

**`frontend/src/services/api.ts`**

```diff
 const api = axios.create({
   baseURL: API_BASE_URL,
+  withCredentials: true,          // send + receive the session cookie
   paramsSerializer: { indexes: null },
   headers: { "Content-Type": "application/json" },
 })
```

Delete `attachAuthorizationHeader` and its `api.interceptors.request.use(...)` registration. Keep the
**response** interceptor exactly as it is — the 401 → `clearSession()` → redirect flow, and the
`sessionStorage` `auth-message` handoff, both still work and are still correct.

Optionally branch on the new error `code` for a better message: `AUTH_EXPIRED` → "Your session
expired", `AUTH_REVOKED` → "You were signed out", `AUTH_RATE_LIMITED` → "Too many attempts, try again
in N seconds" (read `Retry-After`).

**`frontend/src/services/auth.ts`**

- `authApi` also needs `withCredentials: true`.
- `loginUser` returns `{ user }` instead of `{ access_token }`. The user object is everything you need
  for `setSession`, so `getCurrentUser` is no longer required immediately after login.
- `getCurrentUser(accessToken)` loses its parameter and its manual `Authorization` header — it becomes
  `getCurrentUser()` calling `api.get("/users/me")`.
- Add `logoutUser()` → `api.post("/auth/logout")`.

**`frontend/src/store/useAuthStore.ts`**

- Remove `token` from the state, from `StoredAuthSession`, and from `setSession`'s signature.
- Delete `isTokenExpired` and the `atob` JWT decode — there is no token to decode, and the server is
  now authoritative about expiry anyway.
- `role`, `username`, and `userId` may still be persisted for instant UI rendering on reload, **but
  treat them as a display cache, not as proof of authentication.** On app boot, call
  `GET /api/users/me`; a 401 clears the cache and redirects.
- `clearSession()` should also call `logoutUser()` when the user initiated it (best-effort — ignore
  failures, the cookie may already be gone).
- The `ApiUserRole` (`"Admin"`) → `AppUserRole` (`"Administrator"`) mapping in `types/auth.ts` is
  unchanged. Keep it.

**`frontend/src/pages/Login.tsx`** — mostly unchanged. It no longer receives a token; it calls
`setSession(role, username, userId)`. The `auth-message` expiry banner keeps working.

**`frontend/src/hooks/useAdasWebSocket.ts`** — **no change required.** The browser attaches the cookie
to the handshake automatically. It will simply start succeeding against an authenticated endpoint
instead of an open one.

> Seb's `fix(auth): harden session management` work is **not** wasted. The stored-shape validation, the
> `auth-message` expiry banner, and the 401 redirect all survive. Only the JWT-decode expiry check goes
> away, because the server now enforces it and can revoke early.

### Dev-environment note

In dev the SPA is on `:5173` and the API on `:8000`. That is cross-**origin**, so `withCredentials`
and CORS `allow_credentials` are both required (the backend already has the latter). It is *not*
cross-**site** — SameSite is evaluated per site and the port is not part of a site — so
`SameSite=Strict` works fine. `Secure` is off in development and on in production.

Playwright manages cookies natively, so `e2e/login.spec.ts` should pass unchanged.

### New close codes on the WebSocket

Handle these rather than blindly reconnecting:

| Code | Meaning | Client action |
|---|---|---|
| `4001` | authentication failed | stop reconnecting, go to login |
| `4003` | origin rejected | stop, this is a config bug |
| `4008` | too many connections for this user | back off hard, or surface a message |
| `4009` | session revoked or expired | stop reconnecting, go to login |
| `1011` | send failure / your queue overflowed | reconnect **and re-run the full recovery sequence** |

D-008: authentication and session failures stop automatic reconnection; transient failures reconnect
with bounded exponential backoff **and jitter**.

---

## Breaking change 2 — WebSocket events get an envelope (backend P3)

Every message is now wrapped:

```json
{
  "version": 1,
  "event_id": "8c2a…-uuid",
  "type": "ALERT_STATUS_UPDATE",
  "occurred_at": "2026-07-12T10:30:05+00:00",
  "data": { }
}
```

Read `msg.type` and `msg.data` instead of the current flat shape. Two things to build:

- **Duplicate suppression** using `event_id` — a reconnect race can deliver the same event twice.
  `useAlertStore` already persists handled ids to `sessionStorage`; this is the same idea one level
  lower.
- **Merge ordering.** Use incident `updated_at` and camera `config_version` as merge keys so a REST
  snapshot fetched during reconnection cannot overwrite a newer event that arrived first.

Two new event types:

| Type | `data` | UI behavior |
|---|---|---|
| `SNOOZE_ACTIVATED` | `{log_id, camera_id, snoozed_by, snoozed_until}` | mute **that incident** on every dashboard until the deadline |
| `RE_ALARM` | `{log_id, camera_id}` | the shared deadline expired and the incident is still `Unverified` — sound the alarm again |

`CONNECTION_READY` arrives first on every connection and carries `server_time`, which is useful for
measuring clock skew before comparing `occurred_at`.

### The recovery sequence (NFR-17 / TC-R-304)

On every initial load **and** every reconnection:

1. wait for `CONNECTION_READY`
2. `GET /api/alerts/?status=Unverified&status=Ongoing`
3. `GET /api/cameras/`
4. rebuild alarm and snooze state from the persisted `snoozed_until` on each incident — **not** from a
   previously received WebSocket message
5. merge any events that arrived during steps 2–3 using the merge keys above

---

## Breaking change 3 — Snapshots require authentication (backend P4)

The public `/snapshots/*` static mount is removed. Every accident image is currently readable by
anyone who can reach the server, and the CSV export even embedded absolute links to them.

- `DetectionLogRead` gains **`snapshot_url`**, e.g. `"/api/alerts/42/snapshot"`.
- Use that value directly. Never construct an image URL from `snapshot_key` or any path.
- `<img src>` on a same-origin path sends the cookie automatically, so no fetch wrapper is needed.

---

## Additive change — Camera list response shape (backend P4)

```json
{
  "kpis":       { "total": 10, "enabled": 8, "network_connected": 7, "active_detection": 6 },
  "breakdowns": {
    "connection": { "connected": 7, "disconnected": 2, "reconnecting": 1, "unresponsive": 0 },
    "ai":         { "active": 6, "paused": 1, "inactive": 3, "unresponsive": 0 }
  },
  "total_filtered": 4,
  "cameras": []
}
```

`total_cameras`, `network_connected`, and `active_detection` move from the top level into `kpis`.
`cameras` and `total_filtered` are unchanged.

This gives you the KPI modals D-009 specifies. They are **number-only** — no camera rows, no
pagination inside a modal. Clicking `Total Cameras` opens nothing; the other three open count
summaries. Existing page filters remain how you find individual cameras.

`Disabled` is derived as `total - enabled` and is not returned.

Each camera object also gains `desired_ai_state`, `desired_state_reason`, `cooldown_until`, and
`config_version`. `desired_state_reason` is what lets you show *why* a camera is paused
(`incident` / `cooldown` / `disabled`) instead of just "Paused", and `cooldown_until` drives a
countdown after a false-positive dismissal.

> A camera can be **disabled and still report `Connected`** during the seconds before the AI engine
> reconciles. Configuration, connection, and AI state are independent dimensions — never infer
> "disabled" from a connection or AI status.

---

## Additive — new endpoints

| Endpoint | What it unlocks |
|---|---|
| `POST /api/alerts/{log_id}/snooze` | FR-07 mute/snooze. **Send no body** — duration comes from the user's saved settings |
| `GET` / `PUT /api/settings/alarm` | FR-08 alarm settings panel: sound key, volume 0–100, snooze 15–60s |
| `GET /api/system/health/live` | System Health page. Poll every **10–15 seconds** (NFR-05) — not over WebSocket |
| `GET /api/system/health/history?range=48h\|30d` | System Health charts |
| `GET /api/audit-logs` | Activity audit viewer, **Admin only** |
| `GET /api/help/articles`, `/{slug}` | Help Center, role-filtered, with search |
| `GET /api/system/backups`, `POST /api/system/restores` | Admin backup/restore UI |
| `?format=csv\|pdf` on all four export endpoints | PDF export (FR-19) |

Notes:

- **`alarm_sound` currently accepts exactly one value: `"default"`.** Only
  `frontend/public/detection_sound.mp3` exists. Add audio assets and tell the backend to extend
  `ALARM_SOUND_KEYS` — D-004 forbids a sound enum without corresponding files.
- **System Health `cpu_temp` is `null` on Windows** with `cpu_temp_available: false`. Render
  "Unavailable" — never `0°C`. Same for GPU aggregates when no GPU is present: empty list and nulls,
  and missing points in charts must be **gaps, not zeros**.
- Snooze is **shared incident state**, not per-user. Operator A snoozing mutes it for everyone.
  Sound and volume stay per-user.

---

## Behavior changes worth knowing about

### `409 CONFLICT_STATE` — the already-handled modal (D-002)

Any confirm / dismiss / resolve / snooze can now lose a race to another operator and return:

```json
{
  "detail": "This incident was already handled by another operator.",
  "code": "CONFLICT_STATE",
  "current_status": "Ongoing",
  "handled_action": "ALERT_CONFIRM",
  "handled_by": "D. Sahagun",
  "handled_at": "2026-07-12T10:30:05+00:00"
}
```

D-002 specifies the UX precisely: the modal stops that incident's alarm and snooze state, disables its
action controls, explains **who** handled it and **how**, and replaces Confirm/Dismiss with a single
**Okay** button. Okay closes only that client's modal and mutates nothing.

The same state is reached via the `ALERT_STATUS_UPDATE` event when it arrives first. Both paths feed
one component.

### Immediate dismiss now records the *verifier*, not the closer

Dismissing an `Unverified` incident populates `verified_by` / `verified_at` and leaves `closed_by` /
`closed_at` empty (D-002). Detail views showing "Closed by" for a dismissed alert will now show
nothing there — that is correct.

### Missing incident returns 404

`GET`/`POST /api/alerts/{log_id}` on a nonexistent log returned `400`. It now returns `404`.

### Timestamps

Every timestamp is ISO 8601 **with an explicit UTC offset** (`+00:00`). Some currently come back
without one, which JavaScript parses as local time — an eight-hour error in Philippine time. Localize
at display time.

---

## Suggested order on your side

1. **With P2:** the five auth files. Everything else keeps working.
2. **With P3:** the WebSocket envelope, `event_id` deduplication, close-code handling, the recovery
   sequence.
3. **With P4:** `snapshot_url`, the camera response reshape, the `409` already-handled modal, snooze
   and alarm settings.
4. **After that, incrementally:** System Health, audit viewer, Help Center, PDF export, backup/restore
   admin UI.

## Questions for the backend owner

If any response shape here does not match what you actually receive, the backend has drifted from the
contract — say so rather than adapting around it. `be_plan/01_CONTRACTS.md` is the authority, and it
is meant to be corrected, not worked around.
