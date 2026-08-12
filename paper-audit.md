# Full-codebase audit → Final-Paper edit list

**Date:** 2026-08-12
**Applies to:** `ai_engine/docs/Final-Paper.pdf`
**Supersedes:** `ai_engine/docs/paper-edits-required.md` (AI-engine-only edit list, 2026-08-10 — all 14 of its items carried forward below: seven into Priority 1 and Priority 4, seven into the Deferred test-case section; that file has been deleted)

`Final-Paper.pdf` (109 pp.) was written against an _earlier_ design of the
system. The codebase has since moved on substantially: the detection core was
ported (PR series through #84), the backend grew a desired/observed
reconciliation protocol, a durable outbox, an audit-log subsystem, Argon2id
auth with server-side revocable sessions, and five database tables the
paper's ERD never mentions. This document is the full audit — AI engine,
backend, integration seam, and schema — against the paper, with concrete
replacement text so the paper can be revised before defence.

Edits are grouped by priority. Each gives the location, what the paper says
now, what it should say, and why. Every claim below carries either a
file/line reference or a paper page number.

---

## Priority 1 — Integrity

Claims the evidence directly contradicts. These are the ones a panel member
can falsify by reading the code or the evaluation logs, so they are ordered
first.

### 1.1 Remove mAP as an acceptance criterion — NFR-01, p.17 / p.18 / p.82

**Currently:** _"achieving an operational accuracy that meets or exceeds the strictly defined 85% mAP and 0.50 IoU baseline thresholds."_

**Change to:** an event-level criterion measured on held-out deployment footage. Suggested wording:

> The system achieves event-level recall of at least 75% on standard-difficulty collisions in held-out Lipa CCTV footage, with a false-alarm rate at or below 0.5 events per minute of ordinary traffic.

**Why.** `SPEC.md` §4 records that the v3 training run's mAP50 of 0.956 is
**leaked**: the incident-level validation split failed and was skipped, so
near-duplicate frames of the same crash appeared in both training and
validation. For scale, a model already known to be broken — one that fired
0.89 confidence on a normally-driving red sedan — scored 0.986 by the same
measure.

Quoting mAP as an acceptance threshold commits the study to a number its own
evidence rejects. If a panel member asks how the validation split was
constructed, that is a difficult moment.

The replacement is stronger, not weaker: recall and false-alarms-per-minute
on real deployment footage from the target city is a more demanding and more
relevant claim than a benchmark score, and the reasoning for rejecting mAP is
itself a defensible research finding.

**Numbers available to quote** (SPEC §4, native frame rate): 8/10 standard
recall (80%), 0/6 hard recall, 3 false positives over ~11 minutes
(0.27/min), 0 false positives on the crash-free clip, +3.02s median alert
latency. Report standard and hard **separately** — a blended 8/16 hides which
crashes were winnable.

### 1.2 Report the hard-difficulty result honestly — new text, near NFR-01

**Add.** The clip set was stratified into `standard` and `hard` _before any
model was run_. Every `hard` clip is missed, without exception. This is a
data-coverage limit — the training source never contained crashes of that
geometry — not a tuning shortfall.

**Why.** Stating it plainly, with the pre-registration, converts an apparent
weakness into evidence of honest methodology. Discovered by a panel instead,
it looks like a concealed failure.

### 1.3 Weights, epoch count, and TensorRT — p.83 / p.84

**Currently:** _"The YOLO26n (Nano) architecture was selected..."_, _"The
model was trained over 150 epochs..."_, _"the finalized PyTorch weights
(.pt) were exported and compiled into a highly optimized NVIDIA TensorRT
engine format (.engine)"_ (p.83); _"...before the finalized .engine model
was pulled down and deployed locally to the independent edge server..."_
(p.84).

**Change to:**

> The deployed model is a YOLO detector trained for 50 epochs, loaded directly from its PyTorch checkpoint (`epoch50.pt`), with no TensorRT compilation step in the deployment path.

**Why.** `ai_engine/config.py:44` sets `WEIGHTS_PATH` to `epoch50.pt` and
loads it directly — there is no engine build anywhere in the running system.
`best.pt` and `best.engine` were deleted during the detection-core port:
`best.pt` had lost checkpoint selection across all three training runs, and
`main.py` had been _preferring_ a stale TensorRT build of it, silently
running the wrong model on every launch. `ai-trt` (`pyproject.toml:76`) is an
opt-in extra (`tensorrt>=10.16.1.11`) that nothing in the current codebase
imports — its own comment block (`pyproject.toml:72-75`) tells the installer
to Ctrl-C and carry on without it if the install hangs. Describing a stale,
silently-wrong artifact as the deployed model is a worse position than
describing the checkpoint that is actually loaded, checked into version
control, and cited throughout the rest of this document's evidence.

### 1.4 FP16 export flags presented as enforced execution parameters — p.84

**Currently:** _"The following execution parameters were enforced to
maximize hardware utilization on the edge server's NVIDIA GPUs: FP16
Precision (half=True)... Dynamic Batching (dynamic=True)... Batch Sizing
(batch=8): For the prototype deployment, the batch size was explicitly set
to 8..."_

**Change to:**

> Batching is real and load-bearing — the supervisor groups active cameras into a single inference call per cycle, and per-batch latency was measured directly (17.5 ms at batch=1, rising to 124 ms at batch=16; see §1.5). `half`, `dynamic`, and `batch=8` are TensorRT _export_ flags, meaningful only for an engine build; since no engine is built (§1.3), they describe an export configuration that was prepared but never exercised in the deployed system.

**Why.** This is not a retraction of the batching claim — batching is
measured and real, and is exactly what makes multi-camera throughput viable
on a single GPU. The correction is narrower: these three flags describe
TensorRT export parameters, not something enforced on every inference call
today. Separating "batching happens" (true, measured) from "via a compiled
TensorRT engine" (not true) leaves the stronger claim standing on its own
evidence instead of resting on the weaker one.
→ `ai_engine/supervisor.py`, `ai_engine/machine_profile.json` (`latency_ms_by_batch`)

### 1.5 Deployment hardware — reframe as target spec, not past deployment — p.73

**Currently:** _"The deployment environment employed... Dell PowerEdge R760xa, 8× NVIDIA L4... 418 cameras"_ (past tense, implying this configuration was actually run).

**Change to:**

> The target production specification is a Dell PowerEdge R760xa with 8× NVIDIA L4 GPUs, sized to carry 418 cameras city-wide. This specification was not deployed during the capstone; the system was developed and measured on a single prototype GPU. On that prototype, capacity benchmarking (`ai_engine/capacity.py`) recorded 8 cameras sustainable at 15 FPS and 12 cameras at 10 FPS, with per-batch inference latency scaling from 17.5 ms at batch=1 to 124 ms at batch=16 (`ai_engine/machine_profile.json`). Scaling this measured per-GPU capacity across the L4 fleet is the basis for the 418-camera production target.

**Why.** The paper's wording reads as though the R760xa/8×L4 configuration was
already running, which it never was — there is no evidence for it and no
plausible way to produce evidence for it inside a capstone's resources. Left
as written, this is the single easiest claim in the paper to puncture: "show
me the deployment" has no answer.

Reframed as a target spec derived from measured single-GPU numbers, the
claim becomes something the project _can_ defend: a concrete, reproducible
per-GPU throughput figure, obtained by running `ai_engine/capacity.py` on
the actual training/inference machine, extrapolated linearly across a fleet
size the university partner specified. That is a standard and defensible way
to present a scaling argument in a systems paper — it is not a retreat from
418 cameras, it is the difference between an assumption and a measurement
the assumption is built on.

### 1.6 Password hashing algorithm — p.77 and Data Dictionary Table 4.0

**Currently:** _"passlib with bcrypt for cryptographic password hashing"_ / _"The bcrypt-hashed password"_.

**Change to:**

> Passwords are hashed with Argon2id via `passlib`'s Argon2 backend. Argon2id was the only algorithm the codebase ever used for this purpose; there is no bcrypt code path to migrate away from.

**Why.** `backend/app/core/security.py:10-13` configures
`CryptContext(schemes=["argon2"], deprecated="auto")`, and the adjoining
comment reads _"No bcrypt->argon2 migration path is needed"_ — bcrypt was
never in production use, so there is nothing to reconcile. `pyproject.toml`
lists `argon2-cffi` and `passlib[argon2]`, not `passlib[bcrypt]`. Argon2id is
also the more defensible choice on its own merits (memory-hard, the current
OWASP-recommended default), so the correction upgrades the security story
rather than merely fixing a name.

### 1.7 GPU telemetry library — p.77

**Currently:** _"For hardware monitoring, psutil and gputil are employed to
collect high-resolution server metrics for the system health dashboard."_

**Change to:**

> System health monitoring uses `psutil` for CPU/memory/disk telemetry and `nvidia-ml-py` (the official NVIDIA Management Library binding, imported as `pynvml`) for GPU telemetry.

**Why.** `gputil` is not a dependency anywhere in the project (`pyproject.toml`
has no such entry). `backend/app/services/hardware.py:151` lazily imports
`pynvml` inside `read_gpus()` specifically so importing the health module
doesn't require an NVIDIA driver on machines without a GPU (CI runners,
most dev machines); `backend/app/core/monitor.py:132` calls `read_gpus()` to
populate the `gpus` field of each health sample. `nvidia-ml-py` is the
actively maintained, NVIDIA-published binding — `gputil` has been
unmaintained for years — so this is also a stronger dependency claim, not
just a corrected one.

### 1.8 NFR-16 daily restart — unimplemented (code gap, not a paper error)

**Currently:** _"the system shall automatically restart every 24 hours...
at 3:00 AM, completing memory flush and recovery in under 10 seconds."_

**Finding.** No such scheduled job exists. `backend/app/main.py:150-241`
enumerates every job the scheduler registers at startup — cooldown sweep,
snooze sweep, expired-session cleanup, the five system-health jobs, export
artifact cleanup, WS session revalidation — and none of them is a daily
restart. The only `restart` references in `backend/app/main.py` are code
comments about _unrelated_ crash-resilience behaviour (the dismiss-cooldown
surviving a process restart, line 131-132; interrupted export jobs being
re-queued after a restart, line 252), not a scheduled self-restart.
`backend/app/core/config.py` defines no corresponding interval or cron
setting either.

**This is a code gap, not a documentation error.** The requirement is
real and testable; the implementation simply doesn't exist yet. Two honest
paths forward: implement a scheduled restart job (a `trigger="cron",
hour=3` entry alongside the existing jobs in `main.py`, with a health-check
gate before returning to service), or strike NFR-16 from the requirements
list with a note explaining why a clean-boot cadence was judged unnecessary
for the demonstrated deployment profile. Which of the two is correct is a
team decision outside the scope of this audit — flagging it here so it
isn't discovered live in front of the panel.

---

## Priority 2 — Architecture & schema drift

### 2.1 ERD is missing half the schema — Figure 6.0, p.54

Paper shows 5 tables. The actual schema has 10:

| Table               | In paper's ERD? | Notes                                                         |
| ------------------- | --------------- | ------------------------------------------------------------- |
| `user`              | yes             | see also 2.5/2.6 for auth claims                              |
| `camera`            | yes             | but see 2.2 — column count and desired/observed split missing |
| `detection_log`     | yes             | but see 2.3 — several columns missing                         |
| `sys_health_raw`    | yes             | —                                                             |
| `sys_health_hourly` | yes             | —                                                             |
| `audit_log`         | **no**          | FR-21 and NFR-21 depend on it entirely                        |
| `auth_session`      | **no**          | D-006 server-side revocable sessions (see 2.5)                |
| `alarm_settings`    | **no**          | FR-08 / UC-11 depend on it                                    |
| `export_job`        | **no**          | FR-19 async export jobs (see Priority 3)                      |
| `help_article`      | **no**          | FR-20 Help Center                                             |

**Change to:** add the five missing tables to Figure 6.0 and their column
definitions to the Data Dictionary.

**Why.** The paper argues the schema "strictly adhered to 3NF" (p.55) while
omitting the very tables that carry the audit trail and session state — the
two subsystems the paper's own security and compliance requirements (FR-21,
NFR-21, D-006) most depend on. An ERD that shows the happy-path tables and
quietly drops the accountability tables reads, to a skeptical reader, as if
those concerns were never designed for. The actual schema does the opposite:
`audit_log` and `auth_session` exist, are populated on every mutating
request and every login, and are the mechanism behind two requirements the
paper already claims credit for. Completing the diagram doesn't change what
the system does — it makes the diagram match a system that already does more
than the diagram shows.

### 2.2 `camera` table — Table 5.0, p.56

**Currently:** 9 columns listed.

**Change to:** the actual 20-column definition
(`backend/app/models/camera.py:73-104`), with the desired/observed split
called out explicitly:

> Backend-owned (desired state, set by an operator action, D-003): `desired_ai_state`, `desired_state_reason`, `cooldown_until`, `config_version`.
> AI-owned (observed state, reported on heartbeat): `applied_config_version`, `last_heartbeat_at`, `measured_fps`, `inference_latency_ms`, `last_error_code`, `last_error_message`.
>
> Also correct the naming inconsistency between the paper's own two schema
> artefacts: the ERD (Figure 6.0, p.54) labels the column `channel_no`,
> while the Data Dictionary (Table 5.0, p.56) already correctly calls it
> `channel_id` — matching the code. Align the figure to the dictionary.

**Why.** The desired/observed split is the central design idea of the camera
subsystem, not an implementation detail — it is what lets an operator's
pause action and the AI engine's own self-blindfold coexist without one
silently overwriting the other, and what lets a heartbeat reconcile engine
state with backend intent after a reconnect (see 2.4). Omitting it from the
Data Dictionary means the paper documents a camera table that could not
actually support the HITL guard behaviour the paper describes elsewhere. The
column-name mismatch is minor on its own but worth fixing in the same pass:
it is an inconsistency _within the paper_ — Figure 6.0 and Table 5.0
disagree with each other about the same column — which is harder to defend
than a simple mismatch with the code, because both artefacts are the
authors' own.

### 2.3 `detection_log` table — Table 6.0, p.57

**Currently:** column list omits `source_event_id`, the three snooze
columns, and the audit timestamps; names the snapshot column
`snapshot_path`.

**Change to:**

> Add `source_event_id` (the idempotency key that makes AI-engine retries of the same collision safe — a duplicate POST to `/api/internal/alert` returns 200 rather than creating a second row), `snoozed_at` / `snoozed_until` / `snoozed_by_id` (D-004, described narratively in UC-5 step 4 but never carried in the schema), and `created_at` / `updated_at`. Rename `snapshot_path` to `snapshot_key` — the client never receives a filesystem path; the snapshot is served through `GET /api/alerts/{log_id}/snapshot`, and the stored value is an opaque key, not a path the client could use directly.

Also worth documenting alongside Table 6.0:
`ux_detection_open_camera`, a partial unique index (`detection.py`,
enforced `WHERE detection_status IN ('Unverified','Ongoing')`) guaranteeing
"at most one open incident per camera" **at the database level**, not merely
in application logic.

**Why.** `source_event_id` and the snooze columns aren't cosmetic gaps —
they're the schema-level evidence for two requirements (idempotent AI
ingest, and the snooze behaviour UC-5 already narrates) that would otherwise
look unimplemented on paper despite being implemented in code. The
`snapshot_path` → `snapshot_key` correction matters because "path" implies a
filesystem detail leaking to the client, which is precisely the kind of
design the actual endpoint-mediated access avoids; correcting the name also
correctly documents that access. The partial unique index is a real design
contribution — enforcing a business invariant at the database layer instead
of trusting application code to always check first — and currently appears
nowhere in the paper.
→ `backend/app/models/detection.py:50-83`

### 2.4 The AI↔backend seam is bidirectional, not a one-way webhook

**Currently:** Figure 2.0 (p.42), Figure 5.1 Level-1 DFD (p.52), and the AI
Engine description (p.43) all show a single arrow: AI Engine →
`Internal Webhook (HTTP POST)` → Backend.

**Change to:** a second arrow and a rewritten AI Engine paragraph describing
a two-endpoint reconciliation protocol:

> `POST /api/internal/alert` — idempotent detection ingest. The v2 payload is keyed on `source_event_id`; a duplicate returns 200, a genuinely new event returns 201.
>
> `POST /api/internal/heartbeat` — the engine reports its observed per-camera state, and the backend responds in the same call with the desired state: the camera list, constructed RTSP URLs, `desired_ai_state`, `cooldown_until`, `config_version`, and the heartbeat interval itself.
>
> The engine holds no persistent camera configuration of its own — the backend pushes it down on every heartbeat. This is what lets the self-blindfold pause and the dismiss-cooldown survive an engine restart: on reconnect, the very first heartbeat response re-establishes whatever state the backend already committed.

**Why.** A single outbound arrow describes a fire-and-forget webhook, which
is not what keeps camera pause state consistent across a crash or restart —
if the engine held its own configuration, a restart would silently resume
ingestion on a camera the backend still considers paused. The second arrow
is not a minor addition to the diagram; it's the mechanism the paper's own
self-blindfold and cooldown claims rely on to survive a real-world failure
mode (engine restart mid-cooldown). Documenting it turns "the AI engine
posts detections" into "the backend and AI engine maintain a reconciled view
of camera state across restarts," which is a considerably stronger
reliability claim, and one that is already true of the running system.
→ `backend/app/api/routes/internal.py:108-213`,
`backend/app/schemas/internal.py`, `ai_engine/supervisor.py`

### 2.5 Session authentication — NFR-19 / TC-U-103, p.77

**Currently:** _"token-based authentication [e.g., JWT]"_.

**Change to:**

> Authentication uses a JWT delivered as an `HttpOnly`, `Secure` cookie (`adas_session`), never exposed to JavaScript, backed by a server-side `auth_session` row so individual sessions are revocable ahead of their natural expiry. Seven revocation reasons are tracked: logout, password_change, password_reset, role_change, account_disabled, admin_revoke, expired_cleanup. There is no `OAuth2PasswordBearer` dependency and no `Authorization` header anywhere in the API; the WebSocket handshake authenticates off the same cookie. Session lifetime is 480 minutes.

**Why.** "Token-based authentication [e.g., JWT]" is not wrong, but it
describes the weaker and more common pattern — a bearer token an attacker
who achieves XSS can read out of storage and replay. This system doesn't do
that: the token never touches JS-reachable storage, and because it's backed
by a database row rather than being purely self-contained, a compromised
session can be revoked server-side before its JWT expiry — something a pure
stateless-JWT design cannot do at all. Naming the mechanism precisely (
`HttpOnly` cookie + `auth_session` table + seven enumerated revocation
reasons) is a stronger security claim than the vague one currently in the
paper, and it is fully evidenced in code.
→ `backend/app/core/config.py:31-33` (`SESSION_LIFETIME_MINUTES`,
`SESSION_COOKIE_NAME`, `SESSION_COOKIE_SECURE`),
`backend/app/models/user.py:81-102` (`AuthSession`, revocation reason CHECK
constraint), `backend/app/api/dependencies.py:60`

### 2.6 RBAC enforcement description — p.43

**Currently:** _"The Backend... enforced RBAC through JWT validation."_

**Change to:**

> Authorization is enforced per-route via FastAPI dependencies, and every state-changing action that is subject to audit runs as a single transaction together with its `audit_log` row: if the audit insert fails, the entire action rolls back, so an unaudited state change cannot persist. A `denied` or `failure` outcome is recorded in a separate, short transaction after that rollback, so the attempt itself is never lost even when the primary action is rejected.

**Why.** "RBAC through JWT validation" describes only _authentication_ (is
this token valid) and gestures at authorization without saying how it's
actually enforced or recorded. The real guarantee is stronger and more
specific: the system cannot end up in a state where a privileged action
happened but left no audit trail, because the two are the same database
transaction. That's a concrete, testable integrity property — worth naming
explicitly rather than folding into a generic RBAC sentence.
→ `backend/app/services/audit.py` (`record`, `record_out_of_band`,
`_BANNED_DETAIL_KEYS` redaction), CLAUDE.md "Every audited state change is
one transaction"

---

## Priority 3 — Undocumented subsystems

These exist in the code, are load-bearing, and appear nowhere in the paper.
None require paper _corrections_ in the sense of Priorities 1–2 — they need
to be _added_.

- **Durable outbox (D-012)** — `ai_engine/outbox.py`. One JSON file per
  pending event, atomically written, with a `quarantine/` subdirectory for
  events that fail to parse back (`_load`, line 77-86). If the backend is
  unreachable when a collision fires, the event survives on disk and is
  retried rather than lost. This directly supports the paper's reliability
  narrative and currently goes unclaimed anywhere in it.
- **Audit-log subsystem** — the `audit_log` table (2.1), the transaction
  helpers in `backend/app/services/audit.py`, and `GET /api/audit/` +
  `GET /api/audit/export`. FR-21 and NFR-21 describe the _requirement_ for
  an audit trail; nothing in the paper describes the mechanism that
  satisfies it.
- **Async export jobs** — the `export_job` table and a 4-endpoint lifecycle:
  `POST /api/exports/jobs` (202 Accepted) → poll `GET
/api/exports/jobs/{id}` → `GET /api/exports/jobs/{id}/download`, plus a
  dedicated `POST /api/exports/retraining` for the off-site retraining
  dataset FR-19 mentions. Artifacts expire after 72 hours. UC-7/UC-8's
  "displays a spinner and processes the export asynchronously" undersells
  what's actually a real job queue with crash recovery — jobs left
  `queued`/`processing` by a backend crash are restarted from the beginning
  on next boot (`backend/app/main.py:249-259`).
- **Login rate limiting** — a sliding-window limiter
  (`backend/app/core/rate_limit.py`), 10 failed attempts per 300 seconds
  (`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`,
  `backend/app/core/config.py:44-46`), counting only failures — a successful
  login resets it. No NFR currently covers this; there probably should be
  one, since it's a real defence against credential-stuffing that the paper
  gets no credit for.
- **Backup/restore** — the paper's "Flag and Restart" description
  (pp. 70–71) is broadly right in outline, but says "Linux systemd
  pre-start script" where the code's own comment (`restore.py:6`) says the
  restore is _"called by the external orchestrator (PowerShell/systemd)
  only"_ — both platforms are supported, not just Linux — and the paper
  omits rollback, post-restore health finalisation, and an audit record of
  the outcome, all of which the implementation performs. Retention is 30
  daily backups / 10 manual. → `backend/app/maintenance/restore.py`
- **Three health routers by design** — `routes/system.py` (unauthenticated
  `/healthz/*`, for load balancers/orchestrators that can't hold a session
  cookie), `routes/system_health.py` (authenticated telemetry for the
  dashboard), and `routes/maintenance.py` (backup/restore). Worth one
  sentence in the architecture section explaining the split is deliberate,
  not an organisational accident.
- **`GET /api/events/schema`** — a published WebSocket event-schema
  endpoint (`backend/app/api/routes/events.py:26`), letting a client
  discover the shape of `/ws/alerts` payloads without reading the backend
  source. Undocumented anywhere in the paper's API surface.

---

## Priority 4 — Descriptive corrections

### 4.1 Grayscale inference normalisation — undocumented

**Add** to the AI Engine Layer description (p.79) and to the model training
discussion.

> All frames are converted to grayscale and replicated to three channels before inference, matching the training pipeline. The accident source is 100% grayscale and the vehicle source ~98% colour, so without this normalisation the cheapest rule available to the model is "colour ⇒ vehicle, grayscale ⇒ accident" — which on colour deployment footage means it never fires.

**Why.** This is the single most consequential preprocessing decision in the
system and it is currently undocumented. It is also a good defence answer:
it shows a shortcut was anticipated and eliminated before it could reach
deployment footage.

### 4.2 The two-class design and the discarded foil

**Add** to the model description.

> The model is trained on two classes, `accident` and `vehicle`, but only `accident` is alerted on (`ACCIDENT_CLASS_ID = 0`; class 1 is discarded at inference). The `vehicle` class is a discriminative foil. Under single-class training an ordinary car is background, and since nearly every accident image is a crash scene full of vehicles, the two concepts entangle and the model degenerates into a vehicle detector — which measurably happened to an earlier model that reported 0.986 mAP50 and then fired 0.89 confidence on a normally-driving red sedan.

**Why.** Currently the paper describes a YOLO model detecting collisions
without explaining the class structure behind that. The foil is the core
design insight and reads well as a research contribution — it's the
difference between "we trained a detector" and "we identified and corrected
a specific, measured failure mode of a naive single-class detector."
→ `ai_engine/config.py:48` (`ACCIDENT_CLASS_ID`)

### 4.3 Alert latency is a designed floor, not a shortfall

**Add** wherever detection latency is discussed.

> Alerts land a median 3.02 seconds after impact. This is a deliberate consequence of requiring evidence to persist before firing, and is what buys the system's precision. It is a floor, not a defect.

**Why.** Pre-empts "why isn't it instant?" with the trade-off, rather than
leaving it looking like a performance limitation.

### 4.4 State the operator-facing false-alarm rate

**Add** to the significance or limitations discussion.

> At 0.27 false alarms per minute per camera, an operator monitoring a single camera can expect roughly 16 false alerts per hour. The system is a triage aid that keeps a human in the loop, not an autonomous dispatcher.

**Why.** This number is a design input for the HITL workflow, and the
paper's own click-efficiency criteria (≤3 clicks per incident) exist because
of it. Stating it makes those requirements look derived rather than
arbitrary, and it is far better volunteered than extracted under
questioning.

### 4.5 The 10–15 FPS band is a thermal constraint — not a detection limit

**Currently:** p.74 justifies the 10–15 FPS cap by GPU thermal throttling.
That is correct and needs no change.

**Add**, near it or in the limitations discussion:

> Detection performance was measured across sampling rates from 3 to 30 frames per second on the full clip set. Event-level recall was unchanged (8 of 16 at every rate but one), and false-alarm counts varied between 2 and 5 with no relationship to rate. The 10–15 FPS operating band is therefore a compute and thermal constraint, not a detection requirement: the accumulator integrates evidence over elapsed time rather than counting frames, so sampling less often does not slow evidence accumulation.

**Why.** This is a genuine measured finding and it strengthens the design
section — it shows the frame-rate choice was validated rather than assumed,
and it explains _why_ the architecture tolerates the frame drops a live
RTSP feed produces. Source: `ai_engine/docs/cadence-measurement.md`.

**Do not overclaim it.** 16 crashes and 2–5 false positives per run is a
small sample; the honest statement is "no measured effect", not "no
effect." Nothing below 3 FPS was tested.

### 4.6 `DETECTOR_CONF = 0.15` is a closed lever, not a tuning knob

**Add** to the model discussion, alongside 4.2's discussion of class
structure.

> The detector confidence threshold is fixed at 0.15, deliberately low. Measured false positives score _higher_ than measured genuine detections (0.869 / 0.844 / 0.649 versus 0.536 / 0.459 / 0.741), so any confidence threshold high enough to remove the false alarms removes the real crashes first. Precision in this system comes from the temporal accumulator — evidence persisting across frames — not from the per-frame confidence gate.

**Why.** This single measured fact is also what makes the confidence-gating
test cases (TC-U-302, TC-AI-301 — see Deferred section) describe behaviour
the system cannot exhibit: any test that expects a confidence threshold to
separate real detections from false ones is testing a mechanism this system
deliberately does not use. Stating the reason here, once, is the anchor the
deferred test items point back to.

### 4.7 `confidence_score` semantics changed post-port

**Currently:** the Data Dictionary (p.58) and Figure 7.4 ("AI-CONFIDENCE
SCORE 94.2%") describe `confidence_score` as a single-frame YOLO detection
probability.

**Change to:**

> `confidence_score` is the peak per-frame confidence observed within an accumulated event, not a single-frame probability. Because genuine detections measure 0.459–0.741 (§4.6), a displayed value in the 90%+ range is neither achievable nor representative under the current model; wireframes and worked examples should cite a value inside the measured range (e.g., "AI-CONFIDENCE SCORE 68.5%").

**Why.** This is a small correction with an outsized effect on credibility:
94.2% is a number the deployed system cannot produce, and a panel member
who has just seen the 0.459–0.741 range from §4.6/1.1 will notice the
contradiction immediately if Figure 7.4 still shows 94.2%. Fixing the
worked example to a real, achievable number costs nothing and removes an
easy inconsistency to catch.

### 4.8 NFR-05 telemetry cadence — live push interval, Table 3.1, p.24

**Currently:** _"For live user interface viewing, the backend shall
transmit real-time hardware and AI inference metrics to the System Health
dashboard every 10 to 15 seconds using in-memory data. For historical chart
generation, the system shall record high-resolution telemetry logs to the
database at 5-minute intervals, with logs pruned after 48 hours.
Aggregated, low-resolution trends shall be computed hourly and retained for
a rolling 30-day period."_

**Change to:**

> Live telemetry pushed to the dashboard is sampled every 5 seconds (`HEALTH_SAMPLE_SECONDS`), not every 10–15 seconds. Persistence and retention are unaffected by this correction: raw samples are persisted every 300 seconds, pruned after 48 hours, rolled up hourly, and retained for 30 days — all four figures already match the implementation.

**Why.** The persist/retention side of NFR-05 was already correct and is
carried into "Verified correct" below; only the _push_ cadence needed
checking against the code, and it turned out to be faster than stated
(5s, not 10–15s) — a strictly stronger real-time claim, not a weaker one.
→ `backend/app/core/config.py:84-85` (`HEALTH_SAMPLE_SECONDS = 5`,
`HEALTH_PERSIST_SECONDS = 300`), `backend/app/main.py:179-213` (the five
scheduled health jobs)

---

## Deferred — test-case chapter (pp. 87–101, out of scope this pass)

The paper's test-case chapter gets its own overhaul once the system is
final; these items are **parked here, not dropped**. They remain valid
input for that overhaul and should not need to be re-discovered.

### TC-U-302 — Confidence thresholding, p.89

**Currently:** _"YOLO mock outputs [0.45, 0.88, 0.60] against a set
threshold of 0.75. Expected: the filtering function strips out the 0.45 and
0.60 values, returning only the 0.88 detection object."_

**For the eventual rewrite:** a test of class filtering and accumulator
hand-off, not confidence gating —

> A mock YOLO output containing both `accident` (class 0) and `vehicle` (class 1) boxes is passed to the filter. Expected: all class-1 boxes are discarded, and every class-0 box above the 0.15 detector confidence is forwarded to the accumulator regardless of its individual score.

Reasoning to carry forward: under `conf = 0.15` all three mock values pass
through, and the old expectation is backwards — genuine crash detections
measure 0.536 / 0.459 / 0.741, false alarms measure 0.869 / 0.844 / 0.649
(§4.6); a 0.75 gate removes real crashes before it removes any false alarm.

### TC-AI-301 — Sub-threshold false-positive suppression, p.96

**Currently:** _"System threshold is 75%. Video shows a 'near-miss' or
heavy braking, yielding a 60% AI confidence score. Expected: the threshold
filter successfully intercepts the detection and drops it."_

**For the eventual rewrite:** a persistence test —

> A near-miss produces intermittent `accident` detections that do not persist in one location. Expected: accumulated evidence decays below the firing threshold and no alert is emitted.

Reasoning to carry forward: 60% is squarely inside the range where genuine
crash detections live (§4.6); the mechanism that actually suppresses
near-misses is temporal (a transient detection never accumulates the ~2
seconds of evidence needed to fire), not a confidence cutoff.

### TC-AI-103 — Sustained tracking / flicker, p.95

**Currently:** _"The model consistently outputs bounding box coordinates
across the entire 10-second sequence without the detection 'flickering' or
dropping."_

**For the eventual rewrite:** a test of the accumulator's tolerance for
gaps —

> Across a 10-second sequence of a stationary wreck, the accumulator maintains a single linked region and fires exactly one event, despite intermittent frames in which the detector produces no box.

Reasoning to carry forward: the detector does flicker, and the design
assumes it will — a postmortem clip held 302 candidate frames and 12.35s of
dwell that never assembled an unbroken run under the old logic, and emitted
nothing. The accumulator replaced that logic precisely so a dropped frame
costs progress rather than erasing it.

### TC-AI-202 / 203 / 204 — Environmental robustness claims, pp.95–96

**Currently:** expected true-positive detection under heavy rain (202),
correct rejection of headlight glare (203), and successful detection with
30% line-of-sight occlusion (204).

**For the eventual rewrite:** remove, or restate as untested limitations.
None of the 17 evaluation clips cover rain, glare, or partial occlusion, so
there is no evidence for any of these expected results. TC-AI-204 is the
most exposed: a fully-occluded clip was deliberately excluded from the
label set on the grounds that no camera-based system could detect it, which
makes a 30%-occlusion success claim hard to defend.

Night is the exception and is worth keeping when this chapter is rewritten
— 8 of 17 clips are night footage, and night recall exceeds day recall.
Night is a precision weakness only: all three false positives are
night-time.

### TC-R-302 — Fault isolation mechanism, p.98

**Currently:** _"A deliberate Python exception is injected into Camera 1's
YOLO worker thread. Camera 1's thread crashes safely. The FastAPI
application and the parallel AI threads for Cameras 2 and 3 remain entirely
unaffected and continue processing."_

**For the eventual rewrite:** the same guarantee, described against the
batched pipeline —

> A deliberate exception is injected into the inference step for Camera 1's frame. Expected: the engine isolates the failure to Camera 1, marks that camera as errored in its heartbeat report, and continues processing Cameras 2 and 3 in subsequent cycles without interruption. The FastAPI application is unaffected.

Reasoning to carry forward: the ported engine batches all active cameras
through a single inference call, which is what makes multi-camera
throughput viable on one GPU, so "per-camera worker thread" no longer
describes the pipeline. The isolation guarantee is preserved — a failing
batch is re-run frame by frame to identify the culprit, which is then
excluded — but the mechanism is different. Decode-side isolation is
unchanged and already matches the original wording: each camera has its own
reader thread, so a dropped stream never affects its neighbours.

### TC-R-201 — UI alert latency, p.98

**Currently:** _"A stopwatch is initiated at the moment of detection... in
strictly under 2.0 seconds."_

**For the eventual rewrite:** _"A stopwatch is initiated at the moment the
alert is emitted by the AI engine... in strictly under 2.0 seconds."_

Reasoning to carry forward: this test measures backend → WebSocket → UI
plumbing. Anchoring it to impact folds ~3 seconds of AI accumulation into a
2-second budget, failing a path that is genuinely fast. This is a
clarification of what the test always measured, not a relaxation of it.

### TC-S-103 — Operator response time, p.100

**Currently:** _"...click 'Confirm' in strictly under 15 seconds from the
moment of actual detection."_

**For the eventual rewrite:** _"...click 'Confirm' in strictly under 15
seconds from the moment of collision."_

Reasoning to carry forward: this is the metric that supports the study's
central claim of reducing the notification gap from minutes to seconds
(p.8), so it should honestly include the detector's own latency. After the
port, `detected_at` in the database _is_ the estimated collision time, so
this becomes directly measurable as `verified_at − detected_at`.

**Budget check to redo before committing to 15s:** ~3s accumulating + <2s
plumbing leaves ~10s of operator time. Achievable, but tighter than the
original wording implies — confirm during live testing.

---

## Frontend recheck list (provisional)

**This section is provisional because the frontend is still work in
progress.** No replacement wording is proposed here — the UI hasn't settled
enough to write text the panel would still see accurately described by
defence day. Revisit this list, item by item, once the frontend stabilises.

- Wireframes Fig. 7.1–7.10 vs. actual components — full visual recheck
  needed.
- Sidebar (Fig. 7.2) shows Dashboard / Cameras / Detections / System Health
  / AI Performance / Users / Help Center; the router also has `/profile`
  and no separate Alarm Settings route — UC-11 describes an "Alarm Settings
  panel," currently reached via profile. Confirm the final information
  architecture before rewriting UC-11.
- FR-07 (audible re-alarm), FR-08 (alarm config), NFR-10 (three-click
  workflow), NFR-12 (learnability), NFR-17 (async alert recovery) — all
  need UI verification against the settled frontend.
- Fig. 7.4 confidence figure — wording already drafted in §4.7 above, but
  the number should be re-confirmed against whatever the UI actually
  renders once the component is final.

---

## Verified correct — no change needed

Carried from the superseded file and re-confirmed during this pass:
p.74 10–15 FPS thermal justification; p.73 deployment hardware as a
_target_ spec (per §1.5); TC-I-203 60-second dismiss cooldown
(`DISMISS_COOLDOWN_SECONDS = 60`); TC-R-301 10-second reconnect
(`RECONNECT_INTERVAL_SECONDS = 10`); TC-AI-402 (p.97) steady 10–15 FPS under
a continuous feed; TC-AI-401 (p.97) under 100ms per-frame latency — the
engine's per-camera latency reporting is being corrected specifically so
this is measured correctly, since whole-batch reporting would have
overstated it by the batch size.

Newly confirmed correct in this pass:

- Snooze bounds 15–60 s (UC-11 steps 7a/7b) — `SNOOZE_MIN_SECONDS` /
  `SNOOZE_MAX_SECONDS` (`backend/app/core/config.py:78-79`) and a DB CHECK
  constraint agree.
- NFR-05 persist/retention: 5-minute raw persistence, 48-hour prune, hourly
  rollup, 30-day retention — all four scheduled jobs exist and match
  (`backend/app/main.py:179-213`). (Only the _push_ cadence needed
  correcting — see §4.8.)
- SQLite + WAL + SQLModel; APScheduler; PyJWT; FastAPI/Uvicorn ASGI
  rationale (pp. 77–78) — accurate as written.
- HITL state machine `Unverified → Ongoing → Resolved` / `→ Dismissed`, and
  the self-blindfold pause ordering — matches `alerts.py` and the schema's
  CHECK constraints.
- FR-19 CSV **and** PDF export — `fpdf2` is present with fonts bundled;
  both formats are real, not just CSV.
