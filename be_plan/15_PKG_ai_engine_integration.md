# P10 — AI Engine Backend Integration

> **Blocked by:** P4 (the v2 contract it targets). P4 is implemented on
> `feat/be-p4-incidents-cameras` and merged into the current line — verify before starting.
> **Branch:** `feat/ai-p10-backend-integration`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §§6, 7 · [`12_AI_ENGINE_CONTRACT.md`](12_AI_ENGINE_CONTRACT.md)
> · `be_decisions_review.md` D-003 and D-012.
> **Size:** L. Eight steps.
>
> **This is the one package that modifies `ai_engine/`.** Every other package doc forbids it. That
> prohibition is lifted here and only here.

## Why this package exists

`ai_engine/` has not changed since the DX work. The backend's v2 contract is fully built and fully
unused, and three things are **currently broken in ways only the engine can fix**:

1. **Every camera shows `Reconnecting` forever on the dashboard.** `presented_statuses()` in
   `backend/app/services/cameras.py` returns `Reconnecting` when `last_heartbeat_at IS NULL`. Only
   `POST /api/internal/heartbeat` writes that column, and the engine never calls it. This was
   confirmed live during P4's verification against the real engine, real GPU, and real RTSP.
2. **`Unresponsive` (FR-15) can never appear.** The backend derives it from heartbeat staleness. No
   heartbeats means no staleness signal, so a hung engine is indistinguishable from a healthy one.
3. **P7's restart and restore drills cannot confirm AI recovery.** `backend/app/maintenance/cli.py`
   carries an explicit comment about this: `heartbeat_confirmed` is permanently `false`, so NFR-16's
   camera-recovery timing has no evidence. The gate had to be downgraded to ready-only because
   waiting on a heartbeat that can never arrive would make every restore roll itself back.

And one that is broken but silent: **a failed webhook loses the accident entirely.**
`accident.py:85-90` catches the exception, prints, and calls `camera.resume()`. A backend restart or
a network stall during a real collision means no incident record and no operator notification. The
backend's idempotency machinery — the `ux_detection_source_event` unique index, the `200`-on-retry
path, the `409` constraint backstop — exists specifically to make retries safe, and nothing retries.

Looking forward: **P5 (system health) has not started.** Its live `avg_fps`,
`avg_inference_latency_ms`, and `sample_camera_count` all come from fresh heartbeats. Without this
package, P5 ships with those permanently null.

---

## Scope

### In — everything the backend needs and cannot supply itself

| # | Change | Closes |
|---|---|---|
| 1 | Env-configurable backend URLs | `WEBHOOK_URL`/`SYNC_URL` are hardcoded to `127.0.0.1:8000` |
| 2 | Per-camera FPS and inference-latency measurement | P5's live metrics |
| 3 | `Unresponsive` after repeated connect failures | FR-15 |
| 4 | Heartbeat client replacing the poll **and** the status PATCH | The three broken things above |
| 5 | `rtsp_url` consumed from the heartbeat snapshot | Backend-owned RTSP (§7.2); MediaMTX→DSS becomes a backend `.env` change |
| 6 | UTC timestamps, `source_event_id`, nested `snapshot_key`, atomic image writes | The v2 payload |
| 7 | Persistent outbox with backoff and response-code branching | Silent accident loss |

### Out — AI-owner territory, explicitly untouched

Do **not** change any of these. D-012 reserves them for the AI owner pending measured evidence, and
touching them here would make this package unreviewable:

- `CONFIDENCE_THRESHOLD` (stays `0.90`; the paper's test table says `0.75` — that is an open gate)
- temporal qualification / M-of-N logic (does not exist; do not add it)
- `ACCIDENT_CLASS_ID`, model artifact selection, `imgsz`, batch size
- FPS **capping** or inference scheduling (measure FPS, do not throttle it)
- the supervisor / per-GPU worker-pool architecture (D-003's production design)
- `device=0` in `main.py`

---

## The testability constraint — read this before writing code

`ai_engine/` has **zero tests** today, and there are two structural reasons it is hard to test:

1. **It is not a package.** No `__init__.py`; modules use flat `from config import …` imports that
   rely on `ai_engine/` being the running script's own directory. `CLAUDE.md` documents this.
2. **CI installs without the AI extra.** `.github/workflows/ci.yml` runs plain `uv sync`;
   `opencv-python`, `torch`, and `ultralytics` live in the `ai` optional extra. **Any test that
   imports `camera.py` (which imports `cv2`) or `main.py` (which imports `ultralytics`) will fail in
   CI**, even though both import fine on your machine.

**Therefore: all new logic goes in modules that import neither `cv2` nor `ultralytics`.**

```
ai_engine/
  config.py           # extended
  events.py           # NEW — pure: snapshot keys, payload building, UTC       ← tested
  outbox.py           # NEW — pure: durable queue, backoff, terminal outcomes  ← tested
  backend_client.py   # NEW — pure: HTTP + response classification            ← tested
  supervisor.py       # NEW — replaces sync.py; imports camera.py (cv2)
  camera.py           # modified
  accident.py         # modified
  main.py             # modified
  tests/
    __init__.py
    conftest.py       # puts ai_engine/ on sys.path
    test_events.py  test_outbox.py  test_backend_client.py
```

The three pure modules are where the logic that can actually be wrong lives — retry classification,
idempotency, path safety, backoff. They get real tests that run in CI. `camera.py`, `supervisor.py`,
and `main.py` stay thin enough to verify by running the system.

Also update `pyproject.toml`:

```toml
testpaths = ["backend/tests", "ai_engine/tests"]
```

If any test genuinely needs `cv2`, guard it with `pytest.importorskip("cv2")` — never let CI fail on
a missing optional dependency.

---

## Step 1 — Configuration

**File:** `ai_engine/config.py`

Make the backend reachable somewhere other than `127.0.0.1:8000`, and add the new settings. Keep the
existing fail-fast `INTERNAL_API_KEY` check exactly as it is.

```python
BACKEND_BASE_URL = os.environ.get("AI_BACKEND_BASE_URL", "http://127.0.0.1:8000")
HEARTBEAT_URL = f"{BACKEND_BASE_URL}/api/internal/heartbeat"
WEBHOOK_URL   = f"{BACKEND_BASE_URL}/api/internal/alert"
SYNC_URL      = f"{BACKEND_BASE_URL}/api/internal/cameras"   # legacy, kept for rollback

ENGINE_ID            = os.environ.get("AI_ENGINE_ID", "adas-ai-1")
SNAPSHOT_ROOT        = Path(os.environ.get("AI_SNAPSHOT_ROOT", Path(__file__).resolve().parent / "snapshots"))
OUTBOX_DIR           = SNAPSHOT_ROOT.parent / "outbox"
HEARTBEAT_INTERVAL_SECONDS = 3      # a default; the backend's response overrides it
RECONNECT_INTERVAL_SECONDS = 10     # NFR-14 / TC-R-301 (was a hardcoded 5)
UNRESPONSIVE_AFTER_FAILURES = 3     # D-003
```

Two things that matter:

- **`SNAPSHOT_ROOT` must match the backend's `SNAPSHOT_ROOT`.** Both default to
  `ai_engine/snapshots`, so they agree out of the box. Say so in a comment — a divergence here means
  every incident detail page shows a broken image and nothing else fails loudly.
- **Keep `RTSP_BASE_URL` for now**, unused by the new path. Step 4 stops reading it; Step 8 deletes
  it. This keeps the legacy rollback intact until the cutover is verified.

---

## Step 2 — Camera metrics and the failure counter

**File:** `ai_engine/camera.py`

Add to `CameraStream`:

- **`rtsp_url` as a constructor argument.** Stop building the URL from `RTSP_BASE_URL`. The backend
  supplies it (§7.2). Keep `channel_id` — it is still used in every log line.
- **A decoded-frame counter** and a rolling FPS figure over a short window (5s is fine). Measure
  what actually gets decoded and handed to inference, not what the socket delivers.
- **`inference_latency_ms`**, written by `main.py` after each batch (Step 6).
- **`consecutive_failures`**, incremented on each failed `cv2.VideoCapture` open or dropped read and
  reset on a successful connect. At `>= UNRESPONSIVE_AFTER_FAILURES`, `connection_status` becomes
  `"Unresponsive"` — but **retries continue** at the same interval (D-003). Unresponsive is a report,
  not a stop condition.
- **`observed_state()`** returning a plain dict matching `HeartbeatCameraReport`.

**Remove `_update_status()` entirely**, along with the fire-and-forget PATCH thread it spawns. All
state reporting now flows through the heartbeat. This deletes an unbounded thread-per-status-change
and a `contextlib.suppress(Exception)` that swallowed every failure including the backend's `409`.

Change the reconnect sleep from the hardcoded `5` to `RECONNECT_INTERVAL_SECONDS`. Keep `pause()` and
`resume()` as local state setters — they no longer call the backend.

**Do not change the pause-drain behavior.** `cap.grab()` without `retrieve()` while paused is
correct and locked by D-012 — it keeps the socket alive and the buffer empty so resume starts from
live footage. It is one of the few things the current engine gets exactly right.

---

## Step 3 — `backend_client.py`

**File:** new `ai_engine/backend_client.py`. No `cv2`, no `ultralytics`.

Two functions plus one classifier.

```python
def send_heartbeat(engine_id, camera_reports, *, timeout=5) -> dict | None
def post_event(payload: dict, *, timeout=5) -> "DeliveryOutcome"
```

`DeliveryOutcome` is an enum the outbox branches on. This mapping is a hard contract
(`01_CONTRACTS.md` §6.3) — get it exactly right, it is the whole point of the module:

| HTTP | Outcome | Meaning |
|---|---|---|
| `201` | `ACKNOWLEDGED` | new incident committed |
| `200` | `ACKNOWLEDGED` | idempotent retry; backend returned the incident it already has |
| `409` | `CONFLICT` | another open incident owns this camera — stop retrying **this** event |
| `404` | `CAMERA_GONE` | camera removed, inactive, or disabled — stop that runtime |
| `401`, `403` | `AUTH_FAILURE` | config/security fault — stop rapid retry, log critically |
| `422` | `QUARANTINE` | non-retryable payload defect |
| `5xx`, timeout, connection error | `RETRY` | transient |

Note `200` and `201` are **both** success. The backend returns `201` for a new v2 incident and `200`
for an idempotent retry — that difference is informational, not a branch.

Never log the response body at info level: the heartbeat response contains `rtsp_url`, which is
credential-bearing in production. Redact or omit it.

---

## Step 4 — `supervisor.py` (replaces `sync.py`)

**File:** new `ai_engine/supervisor.py`. Delete `ai_engine/sync.py` in Step 8.

A daemon thread that every `HEARTBEAT_INTERVAL_SECONDS`:

1. builds a report from every local `CameraStream.observed_state()`
2. POSTs it to `/api/internal/heartbeat`
3. reconciles local runtimes against the returned snapshot
4. uses the response's `heartbeat_interval_seconds` for the next sleep

**Reconciliation rules** (D-003 §2.2) — the snapshot is authoritative and complete:

| Snapshot says | Local action |
|---|---|
| camera absent from the snapshot | `stop()` the runtime, release the socket, drop it from the dict |
| `is_enabled: false` **or** `desired_ai_state: "Inactive"` | stop the runtime and release resources — this is **not** the same as pausing |
| `desired_ai_state: "Paused"` and not locally paused | `pause()` — socket stays open, frames drain |
| `desired_ai_state: "Active"` and locally paused | `resume()` |
| `config_version` newer than the applied one | apply the config; if `rtsp_url` or `channel_id` changed, restart that stream. Report the new `applied_config_version` on the next heartbeat |
| camera present and `Active` but no local runtime | start one using the snapshot's `rtsp_url` |

> **A behavioral difference from the legacy poll that will bite you if you miss it:** v1
> `GET /api/internal/cameras` returned only `is_enabled AND is_active` cameras. The v2 heartbeat
> returns **all `is_active` cameras, including disabled ones**, with `is_enabled: false`. The engine
> must filter. Blindly starting everything in the snapshot would start streams for every disabled
> camera. Verified against `backend/app/api/routes/internal.py` — the snapshot query filters on
> `is_active` only.

On any exception: log, keep the existing local runtimes, sleep, retry. A backend outage must not tear
down running cameras — the engine keeps inferring and reconnects on its own, which is what `sync.py`
already does correctly.

---

## Step 5 — `events.py`

**File:** new `ai_engine/events.py`. No `cv2`.

```python
def new_source_event_id() -> str                      # uuid4
def build_snapshot_key(camera_id: int, source_event_id: str, *, now: datetime) -> str
def build_event_payload(camera_id, source_event_id, snapshot_key, confidence, *, now) -> dict
```

Snapshot key format, matching `01_CONTRACTS.md` §7.1:

```
2026/07/12/camera_5/5f1c8b2e-....jpg
```

- **Date segments are UTC**, consistent with `detected_at`. Using local dates here and UTC there
  produces files that land in yesterday's folder for eight hours a day.
- `<source_event_id>.jpg` as the filename **fixes a real bug**: the current
  `cam{id}_{YYYYMMDD_HHMMSS}.jpg` has one-second granularity, so two detections on the same camera in
  the same second silently overwrite each other. A UUID cannot collide.
- Forward slashes only, even on Windows. The backend's `resolve()` rejects backslash-leading keys and
  drive letters.

Payload — matches `DetectionLogCreateV2` exactly. That schema is `extra="forbid"`, so **an extra or
misspelled field makes the whole thing fall back to the v1 model and then fail validation**. The five
keys are exactly:

```python
{
  "source_event_id": "...",
  "camera_id": 5,
  "detected_at": "2026-07-12T10:30:00.123456+00:00",   # UTC, WITH offset
  "snapshot_key": "2026/07/12/camera_5/....jpg",
  "confidence_score": 0.8734,
}
```

`detected_at` **must** carry an offset. The backend runs a v2 payload through
`parse_utc_query_datetime`, which treats a naive value as UTC — so sending naive local time silently
shifts every incident by eight hours in Philippine time. Use `datetime.now(UTC).isoformat()`.

---

## Step 6 — `outbox.py` and durable delivery

**File:** new `ai_engine/outbox.py`. No `cv2`.

A directory-backed queue. One JSON file per pending event under `OUTBOX_DIR`, plus a `quarantine/`
subdirectory. No SQLite, no broker — the engine must stay simple and inspectable, and D-003 forbids
it touching the backend's database.

```python
def enqueue(payload: dict) -> Path          # atomic: write .tmp, then os.replace
def pending() -> list[Path]
def acknowledge(path: Path) -> None         # delete
def quarantine(path: Path, reason: str) -> None
def mark_attempt(path: Path) -> None        # bump attempt count + next_attempt_at
```

Write atomically — temp file then `os.replace` — so a crash mid-write never leaves a half-parsed
event that poisons the queue on restart.

**A single bounded delivery worker thread** (not a thread per event, and not the current
`ThreadPoolExecutor(max_workers=5)` fire-and-forget). It walks pending events oldest-first and acts
on each outcome:

| Outcome | Action |
|---|---|
| `ACKNOWLEDGED` | delete the entry |
| `CONFLICT` | stop retrying this event; log it and remove it. The backend already has an open incident for that camera — this event is genuinely redundant |
| `CAMERA_GONE` | remove the entry and signal the supervisor to stop that camera's runtime |
| `AUTH_FAILURE` | stop rapid retry (long backoff), log at critical. This is a misconfigured `INTERNAL_API_KEY`, not a transient fault |
| `QUARANTINE` | move to `quarantine/` with the reason. Never retried, kept for diagnosis |
| `RETRY` | bump the attempt count, schedule the next attempt with bounded exponential backoff **plus jitter** |

**Reuse the same `source_event_id` on every attempt.** That is what makes the backend's `200`-on-retry
path work and what prevents a duplicate incident. Never regenerate it.

**On startup, drain the outbox before entering the inference loop.** Events persisted before a crash
must be delivered. This is the entire reason the outbox exists.

### Wiring `accident.py`

`_send_payload` changes from "write image, POST, resume on failure" to:

1. generate `source_event_id`
2. build the snapshot key
3. **write the image atomically** — `cv2.imwrite` to a `.tmp` path, verify it returned `True`, then
   `os.replace` into place, creating parent directories first. A committed incident pointing at a
   half-written JPEG is unrecoverable evidence loss
4. `outbox.enqueue(payload)`
5. return

**Delete the `camera.resume()` calls in both failure branches.** Keeping inference paused while
delivery is pending is required by D-012, and resuming on failure is exactly how detections currently
get lost. Resume is the backend's decision, arriving via `desired_ai_state` on the next heartbeat.

`camera.pause()` at detection time stays where it is — the local blindfold fires before the network
call, which is correct and is why the pause and the DB state converge within one heartbeat.

### `main.py`

- start the delivery worker and drain the outbox before the loop
- replace `start_sync_thread(cameras)` with the supervisor thread
- time each `model(...)` call and write `inference_latency_ms` onto each camera in that batch
- leave `device=0`, `conf=CONFIDENCE_THRESHOLD`, batching, and `r.plot()` alone

---

## Step 7 — Tests

Create `ai_engine/tests/` with a `conftest.py` that inserts `ai_engine/` into `sys.path` (mirroring
what `backend/scripts/_bootstrap.py` does for the backend). Update `pyproject.toml`'s `testpaths`.

| Module | What to assert |
|---|---|
| `events.py` | key format and UTC date segments; a detection at 23:30 local on the 11th lands in the correct **UTC** folder; `detected_at` always carries `+00:00`; payload has exactly the five v2 keys and no extras; two events in the same second produce different keys |
| `backend_client.py` | every row of the outcome table, including `200` vs `201` both mapping to `ACKNOWLEDGED`; timeout and connection error map to `RETRY`; an unexpected `418` maps to `RETRY`, not a crash; `rtsp_url` never appears in log output |
| `outbox.py` | enqueue is atomic (a `.tmp` left behind is ignored on load); FIFO order; `source_event_id` is stable across attempts; each outcome takes the right branch; backoff grows and is jittered; quarantined events are never retried; **a restart with pending events drains them**; a corrupt JSON file is quarantined rather than blocking the queue |
| supervisor logic | if you can extract the reconciliation decision into a pure function taking a snapshot and a set of local camera ids, test it directly: disabled cameras are not started, absent cameras are stopped, `Paused`/`Active` transitions fire, a newer `config_version` triggers reapply |

Mock HTTP with `requests-mock` or `unittest.mock.patch` — **ask before adding a test dependency.**
No test may import `cv2` or `ultralytics` unguarded.

---

## Step 8 — Remove the legacy path

Only after the verification below passes end to end:

- delete `ai_engine/sync.py`
- delete `RTSP_BASE_URL` and `SYNC_URL` from `config.py`
- delete the `ThreadPoolExecutor` from `accident.py`

**Leave the backend's v1 endpoints alone.** `01_CONTRACTS.md` §6.1 keeps them frozen, the backend
tests cover them, and they are the rollback path if the cutover has to be reverted mid-demo. Removing
them is a separate decision for a later session.

---

## Verification

```bash
uv run pytest
```

Then the real end-to-end drill, which is the actual acceptance criterion. You need
`mediamtx mediamtx.yml`, the backend on `:8000`, and `uv run python ai_engine/main.py` with
`--extra ai` synced and a real GPU.

1. **Heartbeat is live.** Within ~3 seconds of starting the engine, the dashboard camera page shows
   `Connected` / `Active` — **not** `Reconnecting`. This is the headline fix; if it still says
   `Reconnecting`, `last_heartbeat_at` is not being written and nothing else in this package matters.
2. **`Unresponsive` appears.** Kill the engine. Within 10 seconds the camera flips to `Unresponsive`
   on both dimensions. Restart it; it recovers.
3. **Disabled cameras are not started.** Disable a camera in the UI. Its runtime stops and its socket
   is released within one heartbeat, and it is not restarted despite still appearing in the snapshot.
4. **RTSP comes from the backend.** Change `RTSP_URL_TEMPLATE` in the backend `.env`, restart the
   backend only, and confirm the engine picks up the new URL with no engine change.
5. **Idempotent delivery.** Trigger a detection; confirm one incident with the engine's own
   `source_event_id` (not a backend-generated one) and the nested `snapshot_key`. The snapshot renders
   through `GET /api/alerts/{log_id}/snapshot`.
6. **Durable delivery — the one that matters most.** **Stop the backend.** Trigger a detection. Confirm
   the JPEG is written, the event is sitting in `OUTBOX_DIR`, and the camera stays paused. Restart the
   backend. The event delivers within one retry cycle and exactly **one** incident is created. Then
   repeat with the *engine* restarted while the backend is down — the outbox must survive and drain.
7. **No duplicates on retry.** Force a delivery timeout so the same event is sent twice. Backend
   returns `201` then `200`; exactly one row exists.
8. **Restore drill now confirms the heartbeat.** Re-run P7's restart drill:
   ```bash
   uv run python -m app.maintenance restart
   ```
   `heartbeat_confirmed` must now be `true` with a real `heartbeat_duration_seconds`. Record it — that
   is the NFR-16 camera-recovery evidence that has been missing.
9. `pnpm check`.

---

## Paper test cases

TC-I-303 (a new camera leads to ingestion starting — now via heartbeat reconciliation),
TC-I-304 (disabling a camera stops that runtime), TC-R-301 (10-second reconnection loop and a
`Disconnected` indicator), TC-U-205 (the payload now carries the AI-generated `source_event_id` — the
paper's wording needs the D-012 amendment already listed in P9), and the AI-recovery half of
TC-R-303 / NFR-16.

Contributes the measurement source for FR-16's inference-speed figures and P5's live FPS and latency.

## Still open after this package

D-012's evidence gate is untouched and still owed by the AI owner: the effective confidence threshold
(`0.90` in code, `0.75` in the paper's test table), whether temporal qualification is enabled and its
exact rule, and the measured batch/FPS/stream-count profile per hardware profile. This package
deliberately changes none of them — record that plainly in the handoff so nobody reads a green test
suite as evidence that the model parameters are validated.
