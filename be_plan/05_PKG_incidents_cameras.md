# P4 — Incident Lifecycle, Camera Control, and Snooze

> **Blocked by:** P3.
> **Branch:** `feat/be-p4-incidents-cameras`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §§5.3, 6, 7, 10, 11 and
> `be_decisions_review.md` D-002, D-003, D-004, D-012.
> **Size:** XL — the largest package. Eleven steps. Expect to split it across sessions.

## Why this package exists

This is the heart of the paper: FR-06, FR-07, FR-08, FR-09, FR-11, FR-12, FR-13, FR-15. The current
implementation has five defects that matter:

1. **Transitions are read-then-write.** `confirm_alert` reads the status, checks it, then writes
   unconditionally. Two operators hitting `/confirm` and `/dismiss` concurrently both read
   `Unverified` and both pass their guard.
2. **The 60-second cooldown is `asyncio.create_task(...)` with the handle discarded.** It can be
   garbage-collected mid-flight, and a server restart inside the window leaves the camera **stuck in
   `Paused` forever** — nothing reconciles it, and the `409` guard in `internal.py` no longer applies
   because the incident is already `Dismissed`.
3. **Immediate dismiss stamps the closure fields.** D-002 says the initial actor belongs in the
   *verification* fields on both Confirm and Dismiss.
4. **`connection_status` and `ai_status` mix operator intent with AI runtime reports.** D-003 splits
   them into backend-owned *desired* state and AI-owned *observed* state.
5. **No snooze at all**, so FR-07, FR-08, UC-11, TC-I-306, TC-I-307, and TC-I-308 are unimplemented.

Plus: `/snapshots/*` is a public static mount, so every accident image is readable by anyone on the LAN.

---

## Step 1 — The incident service

**File:** new `backend/app/services/incidents.py`

One transition function, used by every route. No route re-implements a guard.

```python
ALLOWED: dict[tuple[DetectionStatus, DetectionStatus], AuditAction] = {
    (UNVERIFIED, ONGOING):   AuditAction.ALERT_CONFIRM,
    (UNVERIFIED, DISMISSED): AuditAction.ALERT_DISMISS,
    (ONGOING,    RESOLVED):  AuditAction.ALERT_RESOLVE,
    (ONGOING,    DISMISSED): AuditAction.ALERT_CORRECTION,
}

def transition(
    session: Session, *, log_id: int, expected: DetectionStatus,
    new: DetectionStatus, actor: User,
) -> TransitionResult
```

**Atomic, never read-then-write** (`01_CONTRACTS.md` §10.3):

```sql
UPDATE detection_log
   SET detection_status = :new,
       verified_by_id   = COALESCE(verified_by_id, :actor),   -- see the actor table below
       ...
       snoozed_at = NULL, snoozed_until = NULL, snoozed_by_id = NULL,
       updated_at = :now
 WHERE log_id = :log_id AND detection_status = :expected
```

`rowcount == 0` → re-read the row → raise a `ConflictState` carrying current status, the action that
handled it, the handler's display name, and the handling time. The route turns that into the exact
`409` body in `01_CONTRACTS.md` §5.3. A missing row is a plain `404` — note the current code returns
`400` for a missing log and existing tests assert that; update them.

Actor semantics (D-002), which the current code gets wrong for dismiss:

| Transition | verification fields | closure fields |
|---|---|---|
| Confirm | set to actor | untouched |
| **Immediate dismiss** | **set to actor** | **stay empty** |
| Resolve | retained | set to actor |
| Correction | retained (original verifier) | set to actor |

Terminal transitions clear snooze fields **in the same UPDATE**. That is what makes the in-memory
snooze job an optimization rather than the correctness mechanism (D-004).

One transaction contains: the incident UPDATE, the camera desired-state change (Step 2), and the audit
row (P2's `audit.record`). Broadcasts are enqueued by the **route**, after commit.

---

## Step 2 — The camera control service

**File:** new `backend/app/services/cameras.py`

```python
def recompute_desired_state(session, camera, *, now) -> bool   # True if it changed
def set_desired(session, camera, state, reason, *, cooldown_until=None) -> None
def bump_config_version(session, camera) -> None
def apply_observed(session, camera, report) -> bool            # heartbeat only
```

`recompute_desired_state` is the single source of truth, precedence top to bottom:

1. `not is_active` or `not is_enabled` → `Inactive`, reason `disabled`
2. an open (`Unverified`/`Ongoing`) incident exists → `Paused`, reason `incident`
3. `cooldown_until` in the future → `Paused`, reason `cooldown`
4. otherwise → `Active`, reason `None`, `cooldown_until` cleared

Use it everywhere — routes, transitions, cooldown expiry, and the P1 lifespan reconciliation. Having
one function means "why is this camera paused?" always has one answer.

`bump_config_version` fires when an **AI-relevant** field changes: `channel_id`, `is_enabled`,
`is_active`, `desired_ai_state`, `desired_state_reason`, `cooldown_until`. Renaming a camera does not
bump it — the engine does not care about names.

`apply_observed` is the **only** writer of `connection_status`, `ai_status`, `measured_fps`,
`inference_latency_ms`, `applied_config_version`, `last_error_*`, `last_heartbeat_at`. Observed state
never overrides desired state (D-003). It returns whether anything meaningfully changed, so the
heartbeat only broadcasts on real changes rather than every three seconds.

**Staleness:** a camera whose `last_heartbeat_at` is older than `HEARTBEAT_STALE_SECONDS` (10s) is
*presented* as `Unresponsive` for both dimensions. Compute this at read time in the serializer — do
not write `Unresponsive` into the row, or a stale value becomes indistinguishable from a reported one.
This is how the `Unresponsive` status finally gets used; the AI engine never emits it.

---

## Step 3 — Alert routes

**File:** `backend/app/api/routes/alerts.py` (482 lines, heavily rewritten)

Each of `confirm` / `dismiss` / `resolve` becomes: call `transition(...)` → commit → recompute camera
desired state → enqueue broadcasts. Delete `_resume_camera_after_cooldown` and the
`asyncio.create_task` call entirely; Step 4 replaces them.

Broadcast ordering (the existing tests assert exact ordering — preserve the intent):

| Route | Events, in order |
|---|---|
| confirm | `ALERT_STATUS_UPDATE` |
| dismiss from `Unverified` | `ALERT_STATUS_UPDATE`, then `CAMERA_STATUS_UPDATE` (cooldown began) |
| dismiss from `Ongoing` | `CAMERA_STATUS_UPDATE`, then `ALERT_STATUS_UPDATE` |
| resolve | `CAMERA_STATUS_UPDATE`, then `ALERT_STATUS_UPDATE` |

> Immediate dismiss now emits a `CAMERA_STATUS_UPDATE` it did not emit before, because
> `desired_state_reason` moves from `incident` to `cooldown` and `cooldown_until` becomes visible.
> The frontend needs it to render the cooldown countdown.

`GET /api/alerts/{log_id}` returns `404` for a missing log (was `400`).

---

## Step 4 — Durable cooldown

**Files:** `backend/app/services/cameras.py`, `backend/app/core/scheduler.py`

- Immediate dismiss sets `cooldown_until = now + DISMISS_COOLDOWN_SECONDS` and schedules a one-shot
  job with the stable id `cooldown:{camera_id}` (replace-existing).
- The job re-reads the camera, calls `recompute_desired_state`, commits, and broadcasts
  `CAMERA_STATUS_UPDATE` **only if the state actually changed**.
- **`cooldown_until` in SQLite is authoritative.** The job is an optimization. A job that fires while
  the deadline is still in the future, or after the camera was disabled, or after a new incident
  opened, does nothing — `recompute_desired_state` already returns the right answer.
- A periodic sweep (every 30s) catches deadlines whose job was lost to a restart. The P1 lifespan
  reconciliation covers the restart case; the sweep covers scheduler-level loss.

FR-11 requires the cooldown to be per-camera and exactly 60 seconds. It is enforced **entirely by the
backend** — the AI engine has no timer and receives no timestamp. TC-I-203's wording describes a
design the engine does not implement; D-012 records this. The backend simply does not flip
`desired_ai_state` to `Active` until the deadline passes, and the `409` guard on the legacy status
PATCH already prevents the engine from forcing it.

---

## Step 5 — Alarm settings

**File:** new `backend/app/api/routes/settings.py`

```
GET /api/settings/alarm     side-effect free
PUT /api/settings/alarm     full replacement, idempotent
```

Fields and bounds are in `01_CONTRACTS.md` §3.5. `alarm_sound` is validated against
`settings.ALARM_SOUND_KEYS`, which currently contains exactly `["default"]` because
`frontend/public/detection_sound.mp3` is the only audio asset that exists. D-004 forbids inventing a
sound enum without corresponding files — extend the config list when the frontend adds assets.

Rows are created with new accounts (P2's `POST /api/users/`) and backfilled for existing accounts by
the P1 seeder. `GET` must still work if the row is somehow missing: return the defaults rather than a
404, and create the row lazily on the next `PUT`.

Per UC-11: saving without changing anything returns success and **does not write a redundant audit
row**. Compare before/after and only emit `ALARM_SETTINGS_UPDATE` on an actual change.

---

## Step 6 — Snooze

**Files:** `backend/app/services/snooze.py`, `routes/alerts.py`, `core/scheduler.py`

```
POST /api/alerts/{log_id}/snooze
```

Rules (`01_CONTRACTS.md` §11 — read it before implementing, the race handling is the whole point):

- Only `Unverified`. Anything else → `400 PRECONDITION_FAILED`; already handled by another operator →
  `409 CONFLICT_STATE`, same body as a lost transition race, so the frontend reuses one code path.
- Duration comes from the **actor's** saved `snooze_duration`. A body is not accepted; sending one is
  a `422`.
- Shared state: every dashboard mutes that incident until the shared deadline. Sound and volume stay
  per-user.
- Unlimited re-snooze; the latest actor's duration wins and overwrites all three snooze columns.
- Scheduled job id `snooze:{log_id}`, replace-existing.
- Writes `ALERT_SNOOZE` to the audit trail; broadcasts `SNOOZE_ACTIVATED` after commit.

**Expiry is the part that is easy to get wrong.** It is an atomic conditional UPDATE:

```sql
UPDATE detection_log
   SET snoozed_at = NULL, snoozed_until = NULL, snoozed_by_id = NULL, updated_at = :now
 WHERE log_id = :log_id
   AND detection_status = 'Unverified'
   AND snoozed_until IS NOT NULL
   AND snoozed_until <= :now
```

**Only the process whose UPDATE affected a row broadcasts `RE_ALARM`.** A duplicate job, a delayed
job, or a job racing a Confirm updates zero rows and stays silent. That is why D-004 does not need a
`snooze_revision` column.

Startup and safety (implemented here, the hook was stubbed in P1 Step 9):

- reschedule unexpired snoozes for their remaining duration
- atomically clear expired `Unverified` snoozes, making those incidents alarm-active again
- a periodic sweep (every 30s) processes any due snooze whose job was lost

---

## Step 7 — Internal heartbeat (contract v2)

**File:** `backend/app/api/routes/internal.py`

```
POST /api/internal/heartbeat
```

Request and response shapes are pinned in `01_CONTRACTS.md` §6.2. Implementation notes:

- The response is a **complete authoritative snapshot** of all `is_active` cameras, not a change list.
  That is what makes recovery deterministic after either process restarts or misses heartbeats (D-003).
- Build `rtsp_url` from `RTSP_URL_TEMPLATE` (§7.2). **It is credential-bearing.** Add it to the P1
  redaction filter's patterns and assert in a test that it never appears in a log record.
- Process the report through `apply_observed` for each camera; broadcast `CAMERA_STATUS_UPDATE` **only
  for cameras whose observed state meaningfully changed**. At 3-second intervals across dozens of
  cameras, broadcasting unconditionally would flood every dashboard.
- Unknown `camera_id` in the report: ignore it, do not error. The engine will drop it once it applies
  the snapshot.
- One transaction for all camera updates; broadcasts after commit.

---

## Step 8 — Idempotent ingestion, with legacy compatibility

**File:** `backend/app/api/routes/internal.py`

`POST /api/internal/alert` accepts **both** payload shapes:

| | v1 (legacy, what `ai_engine/` sends today) | v2 |
|---|---|---|
| id | none — backend generates a UUID | `source_event_id` (client-generated) |
| snapshot | `snapshot_path`, a bare filename | `snapshot_key`, a relative nested key |
| `detected_at` | naive local time | UTC with offset |

Discriminate on the presence of `source_event_id`. Use a `Union` request model with a validator, not
`dict` sniffing.

**v1 `detected_at` is naive local time** (`datetime.datetime.now().isoformat()` in
`ai_engine/accident.py`). Interpret it as **server-local** and convert to UTC — not as UTC, which
would shift every legacy detection by eight hours in Philippine time. Log a one-time warning that a
legacy payload was received, so the cutover is visible. Document this in the route docstring; it is
the single most likely thing for a later reader to "simplify" incorrectly.

Response semantics (`01_CONTRACTS.md` §6.3) — the AI outbox branches on these, so they are a contract:

- `201` new incident committed
- `200` idempotent retry: look up by `source_event_id`, return the existing incident unchanged
- `409 CONFLICT_STATE` another open incident owns this camera. The `ux_detection_open_camera` partial
  unique index enforces this at the database level; catch `IntegrityError` and translate it. Do **not**
  pre-check with a SELECT and skip the constraint — the constraint is what makes it race-proof.
- `404` camera missing, inactive, or disabled
- `422` malformed payload

On success, in one transaction: insert the incident, set the camera to `Paused`/`incident`, bump
`config_version`. After commit, broadcast `NEW_DETECTION` then `CAMERA_STATUS_UPDATE` — preserve that
order, the existing tests assert it and the frontend relies on it.

The legacy endpoints keep working unchanged:

- `GET /api/internal/cameras` — but its `ai_status` field now reports **`desired_ai_state`**, because
  the engine uses that value to decide whether to pause or resume, which is desired-state semantics.
  Document this clearly; it is a silent semantic change to an existing field.
- `PATCH /api/internal/cameras/{id}/status` — writes observed state only, keeps its `409` guard.

---

## Step 9 — Snapshots

**Files:** new `backend/app/services/snapshots.py`, `routes/alerts.py`, `main.py`

```python
def resolve(snapshot_key: str) -> Path | None
```

- Normalize, then reject absolute paths, any `..` segment, drive letters, and UNC prefixes.
- Resolve against `SNAPSHOT_ROOT`; if the key has no path separator, fall back to
  `LEGACY_SNAPSHOT_DIR`.
- **After resolving, assert the result is inside one of the two configured roots.** Checking the input
  string is not enough — symlinks and `Path.resolve()` normalization can escape it.
- Unit-test with hostile inputs: `../../../.env`, `/etc/passwd`, `C:\Windows\win.ini`,
  `..%2f..%2fadas.db`, `\\\\server\\share\\x`, and a symlink pointing outside the root.

```
GET /api/alerts/{log_id}/snapshot      session-authenticated
```

Returns a `FileResponse` with the correct content type, `Cache-Control: private, max-age=…`, and a
`404` when the file is missing (the row can outlive the file). **Remove the `/snapshots` static mount
and the import-time `os.makedirs`** from `backend/app/main.py`.

`DetectionLogRead` gains `snapshot_url = "/api/alerts/{log_id}/snapshot"`. It never exposes
`snapshot_key` or any filesystem path.

The alerts CSV export currently embeds absolute snapshot URLs built from `request.base_url`. P6
changes it to the authorized API path — note it there.

---

## Step 10 — Camera routes and KPIs

**File:** `backend/app/api/routes/cameras.py`

- Response reshaped to the `kpis` + `breakdowns` object in `01_CONTRACTS.md` §5.9. All counts share
  one population (`is_active = 1`) and satisfy the four invariants — assert them in a test, they are
  easy to break with a stray filter.
- The three separate unfiltered `COUNT` queries become one grouped query per dimension.
- `POST` catches `IntegrityError` → `409 CONFLICT_DUPLICATE`. Today it has no handler at all, so
  creating a camera whose name matches a **soft-deleted** camera raises an unhandled `IntegrityError`
  → 500. The P1 partial unique index fixes the underlying rule; this fixes the response.
- `PATCH` bumps `config_version` for AI-relevant changes and emits `CAMERA_ENABLE` / `CAMERA_DISABLE`
  audit rows in addition to `CAMERA_UPDATE`.
- `DELETE` (soft) sets `desired_ai_state = Inactive`, reason `disabled`, bumps `config_version`, and
  **refuses with `400 PRECONDITION_FAILED` if the camera has an open incident** — otherwise the
  incident becomes unreachable and the `ux_detection_open_camera` index blocks any future incident on
  a camera nobody can see.
- New/reconfigured cameras start as observed `Disconnected` and are presented as `Reconnecting` until
  the first heartbeat — camera create must **not** block on an RTSP handshake (D-003).

---

## Step 11 — Test suite updates

`backend/tests/test_alerts.py` (836 lines) and `test_internal.py` (406 lines) are thorough and mostly
still correct. Update rather than rewrite:

- immediate dismiss now asserts **verification** fields, not closure fields
- missing log on `confirm` is now `404`, not `400`
- cooldown assertions move from "`asyncio.create_task` was called with a coro named
  `_resume_camera_after_cooldown`" to "`cooldown_until` is set and a job with id `cooldown:{id}` is
  registered" — a much more meaningful assertion
- `_resume_camera_after_cooldown` direct tests become scheduler-job tests using `time-machine`
- broadcast assertions move from raw dicts to envelopes; keep the ordering assertions
- add concurrency tests: two `transition` calls on one incident from two sessions → exactly one wins,
  the other raises `ConflictState`

---

## Verification

```bash
uv run pytest
```

Manually, with `mediamtx mediamtx.yml` and the real AI engine running:

1. **Legacy contract intact.** The unmodified `ai_engine/main.py` polls, streams, detects, and posts
   successfully. An incident appears with a backend-generated `source_event_id` and the camera pauses.
2. **Idempotency.** POST the same v2 payload twice → `201` then `200`, one row.
3. **One open incident per camera.** POST two different `source_event_id`s for one camera → `201`
   then `409`.
4. **Durable cooldown.** Dismiss an `Unverified` incident, **kill the backend within 60 seconds**,
   restart it. The camera must return to `desired_ai_state=Active` at the original deadline. This is
   the defect the package exists to fix — verify it explicitly.
5. **Snooze.** Snooze an `Unverified` incident from browser A → browser B mutes it too. Wait for
   expiry → both receive exactly one `RE_ALARM`. Re-snooze mid-window → the deadline extends and only
   one re-alarm ever fires.
6. **Snooze vs confirm race.** Snooze, then confirm before expiry → no `RE_ALARM` at all.
7. **Snapshot auth.** `GET /api/alerts/1/snapshot` with no cookie → `401`. `/snapshots/whatever.jpg`
   → `404` (mount removed).
8. **Heartbeat.** POST a v2 heartbeat with curl and confirm the response snapshot is complete and the
   `rtsp_url` never appears in the log output.
9. `pnpm check`.

---

## Paper test cases covered

FR-06, FR-07, FR-08, FR-09, FR-11, FR-12, FR-13, FR-15.

TC-U-401, TC-U-403 (`detected_at` preserved across transitions), TC-I-202 (Confirm pauses the worker —
note D-012 revises the wording to "inference and event generation cease while bounded RTSP draining
continues"), TC-I-203 (60-second cooldown, backend-owned), TC-I-303 (camera POST leads to ingestion
starting — via heartbeat reconciliation rather than a synchronous thread spawn), TC-I-304 (disable
stops that camera's runtime), TC-I-306 (alarm config round-trip), TC-I-307 / TC-I-308 (snooze mutes
one camera, backend timer fires the re-alarm, other cameras unaffected), TC-I-401 (actor recorded in
`verified_by`), TC-S-402 (independent per-camera alert state), TC-R-304 (`Unverified` alerts
repopulate after a browser restart).

## Deliberately not in this package

System health telemetry (P5), report exports (P6), backup (P7). Do not modify `ai_engine/` — the
v2 contract is written down in `12_AI_ENGINE_CONTRACT.md` for its owner.
