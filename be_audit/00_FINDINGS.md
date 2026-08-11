# ADAS Backend — Audit Findings Register

Opened 2026-08-10, after PRs #55–#70 merged P1–P10 plus the frontend migration
(~24,000 lines across 152 backend files in two days).

This register is the **single source of truth for audit state**. Every task pack in
`be_audit/A*.md` updates the rows it owns. A finding leaves `open` only by being fixed, or by
being recorded as an **accepted gap with a written rationale** — never by going quiet.

## How to read this

- **Severity** = impact on a real deployment or on a defensible paper claim. Not code beauty.
- **State**: `verified` (read in source and confirmed) · `suspected` (strong reading, reproduce
  before fixing) · `fixed` · `accepted` (deliberate gap, rationale required) · `void` (investigated,
  not a real problem — keep the row so it isn't re-raised).

## How to update

Edit the row's **State** column and append a dated line under [Resolution log](#resolution-log).
Do not delete rows. If a pack discovers something new, add it as `F17`, `F18`, … with the same
columns and name the pack that found it.

---

## Register

| # | Finding | Where | Sev | State | Pack |
|---|---|---|---|---|---|
| F1 | Test engine never installs the SQLite pragmas, so **`foreign_keys` is OFF for ~500 integration tests** while production runs it ON. An FK violation passes CI and 500s in production. | `backend/tests/conftest.py` | High | **fixed** — `session_fixture` now calls `install_sqlite_pragmas(engine, settings.SQLITE_BUSY_TIMEOUT_MS)` immediately after `create_engine`, before `SQLModel.metadata.create_all`. `uv run pytest` is green with the pragma on; no test relied on FK enforcement being off (see resolution log for the one incidental fixture bug this pass found and fixed, F18) | A2 |
| F2 | `RTSP_URL_TEMPLATE.format(...)` runs on an operator-editable env value with **no startup validation**. One typo'd placeholder → `KeyError` → 500 on **every heartbeat, every 3s** → the engine loses its control channel and every camera goes Unresponsive. Fails at runtime, not at boot. | `backend/app/api/routes/internal.py:59` | High | **fixed** — `Settings.validate_rtsp_url_template` (`backend/app/core/config.py`) trial-`.format()`s the template with sentinel values for all five placeholders at `Settings()` construction time and raises a message naming the bad placeholder; a stray brace also raises. App refuses to boot rather than degrading at the first heartbeat. Covered by `backend/tests/test_config.py` | A2 |
| F3 | Two clientless v1 routes survive PR #67. `PATCH /api/internal/cameras/{id}/status` writes AI-owned observed columns **directly, bypassing `apply_observed()`** — no fps sanity check, no `error_message` redaction, no `last_heartbeat_at` stamp. A second writer of observed state, contradicting D-003's single-writer rule. | `backend/app/api/routes/internal.py:249`, `:273` | High | **fixed** — both routes deleted, along with the v1 branch of `POST /api/internal/alert` (now v2-only) and `backend/scripts/seed_alerts_via_api.py`. `apply_observed()` verified as the sole writer of observed camera columns outside `app/main.py`'s startup reset. The HITL-guard and disabled-camera behaviours the deleted `TestUpdateCameraStatus` asserted are ported onto the heartbeat path in `test_internal.py::TestHeartbeat` (`test_self_reported_active_does_not_override_the_hitl_pause`, `test_disabled_camera_report_is_accepted_not_rejected`) — note the semantics changed, not just the route: heartbeat records observed state unconditionally (no per-report 409) and the HITL guard now lives entirely in the desired-state snapshot the engine is expected to obey. `uv run pytest` green. | A3 |
| F4 | `SESSION_COOKIE_SECURE=true` over plain `http://<lan-ip>` — browsers exempt `localhost`, **not** a LAN IP. The cookie is silently dropped; login "succeeds" and every later request is 401. Guaranteed second-laptop failure. The paper also promises HTTPS, which nothing implements. | `backend/app/core/config.py`, `core/security.py::set_session_cookie` | High | **fixed** — real self-signed TLS (`certs/adas-cert.pem`, SAN `adas.local`/`localhost`/`127.0.0.1`/`192.168.50.1`), backend on `https://` via uvicorn `--ssl-keyfile/--ssl-certfile`, frontend opt-in TLS via `ADAS_TLS_CERT_DIR`. Live-verified 2026-08-10: `Set-Cookie` carried `Secure; HttpOnly; SameSite=strict`, follow-up `GET /api/users/me` → 200 | A1 |
| F5 | `CORSMiddleware` sets no `expose_headers`, so browser JS **cannot read `Content-Disposition`** cross-origin. `frontend/src/utils/download.ts:24` reads exactly that to name every CSV/PDF download → every export silently lands under the fallback filename. Invisible to `TestClient` and to the frontend unit tests. | `backend/app/main.py:475` | Med-High | **fixed** — `CORSMiddleware(..., expose_headers=["Content-Disposition", "X-Request-ID"])`. Confirmed root cause by A1's live cross-origin reproduction; browser-level re-verification (does the export now land under its real filename over the LAN/TLS profile) is still owed to A1/A6, not re-run in this pack | A1 → A2 |
| F6 | `04_PKG_realtime.md` Step 5 specifies WebSocket ping/pong and the application never implements one. **Downgraded on 2026-08-10:** `websockets 16.0` is installed and `wsproto` is not, so uvicorn runs its websockets impl with `ping_interval=20s` / `ping_timeout=20s` by default — RFC 6455 keepalive *is* active and a half-open socket *is* reaped. Remaining work is to confirm the setting survives the real launch command and to document it, **not** to build a redundant app-level ping. | `backend/app/main.py:352`, `services/realtime.py` | ~~Med-High~~ **Low** | **fixed** (doc + pin) 2026-08-10 — see resolution log | A4 |
| F7 | Export workers start **inside** `if SCHEDULER_ENABLED:`. With the scheduler off, `POST /api/exports/jobs` still returns 202 and the job queues forever. Silent, no error. | `backend/app/main.py:200-202` | Med | **fixed** — `recover_interrupted_jobs` + `ExportJobQueue.start()` moved out of the `SCHEDULER_ENABLED` block, gated on `EXPORT_JOB_WORKERS > 0` on its own (the artifact-cleanup APScheduler job stays under the scheduler, since it genuinely needs one). `_build_test_settings` sets `EXPORT_JOB_WORKERS=0` so existing tests keep driving jobs via direct `process_export_job()` calls unraced; a new end-to-end regression test (`test_app_factory.py::TestExportWorkerGating`) drives a job through the real worker pool with the scheduler off | A2 |
| F8 | `add_exception_handler(Exception, …)` is served by Starlette's `ServerErrorMiddleware`, **outside** the user middleware stack — so on a 500 the `request_id_ctx` is already reset and no `X-Request-ID` header is attached. The one error class that most needs correlation is the one that loses it. `test_logging.py` covers 200s and 404s only. | `backend/app/main.py:336`, `:242` | Med | **fixed** 2026-08-10 — see resolution log | A1 → A4 |
| F9 | Heartbeat input hardening gaps: `engine_id` has no `max_length` and no null-byte validator (inconsistent with `error_code`/`error_message` beside it) and **is accepted and never used**; `cameras` is an unbounded list; `sent_at` is parsed and discarded (no clock-skew detection). Edge case 1.18 (two engine instances) degrades quietly rather than being noticed. | `backend/app/schemas/internal.py:33` | Med | **fixed** — `engine_id` bounded to 128 chars plus a null-byte validator; `cameras` bounded to 2000 entries (418-camera paper target with headroom). `engine_id` now earns its place: a process-lifetime last-seen tracker logs a warning (not a reject — a lease/reject could take down a legitimate failover) when a second distinct `engine_id` heartbeats within `HEARTBEAT_STALE_SECONDS`. `sent_at` now drives a clock-skew warning (>10s from server time), naive values assumed UTC rather than raising. `uv run pytest` green (`test_overlong_engine_id_is_422`, `test_null_byte_in_engine_id_is_422`, `test_overlong_cameras_list_is_422`, `test_second_engine_id_within_staleness_window_logs_warning`). | A3 |
| F10 | `services/reports/jobs.py` imports row-shaping helpers **from `app/api/routes/*` at call time** — services depending on routes, inverting the layering `CLAUDE.md` states. Deliberate (byte-identical output) but the correct fix is a shared module both sides import. | `backend/app/services/reports/jobs.py` | Med | open · verified | A8 |
| F11 | Of the edge cases `14_EDGE_CASES.md` flags in bold as "Not covered": **1.7** (AI event arriving while an operator disables that camera) and **1.14** (export artifact cleanup firing during a streaming download) are genuinely open. **1.12** (restore while a backup runs) is already handled — `routes/maintenance.py:237` takes the same shared `maintenance_lock` — and needs only a cross-operation test. Rows 5.5, 6.2, 6.10 and 8.1 have since been covered. | `be_plan/14_EDGE_CASES.md` | Med | open · verified | A5 |
| F12 | P9's edge-case sweep found "**~28 partially- or un-covered rows out of ~150**" — that list lives only in a PR/session report, **not in the repo**, and is unrecoverable context about known gaps. `14_EDGE_CASES.md` has no status column, which is why it went missing. | `be_plan/00_INDEX.md` P9 row | Med | open · verified | A5 |
| F13 | `MANUAL_TESTS.md`'s nine procedures are **written but none executed** — item 6 of P9's own nine-box definition of done. For deployment-first, the NFR-18 60-second restore drill and the NFR-13 / TC-R-401/402 endurance run matter most. | `be_plan/MANUAL_TESTS.md` | Med | **fixed (6/9)** · **accepted gap (3/9)** — the restart drill (TC-R-303), restore drill (NFR-18), rollback drill, browser-crash recovery (TC-R-304), and three-camera burst (TC-S-401) all executed 2026-08-11 and passed; results in `MANUAL_TESTS.md`. The 24-hour endurance run (TC-R-401/402) and 4-hour idle session (TC-S-203) were deliberately left unrun this pass — the owner was asked whether to run them in real time, run a shortened proxy, or record them honestly as still owed, and chose the last option rather than accept a proxy result. The bi-annual restore drill is `blocked` (deployment-owned, needs staging infrastructure this package doesn't have, matching its own stated scope). See `MANUAL_TESTS.md`'s per-procedure Results sections for the full rationale on each. | A6 |
| F14 | ~20 paper-vs-implementation divergences **not on the 5-item amendment list**: HTTPS promised and unplanned; **NFR-22 and NFR-12 appear nowhere in `be_plan`**; the Data Dictionary says bcrypt (P2 removed it for Argon2id) and `gputil` (P5 removed it); the paper specifies the `sqlite3 .backup` **CLI** where P7 uses the Python API; restore documented as systemd-only; `snapshot_path` → `snapshot_key`; FR-15 says "Connecting" where everything else says "Reconnecting"; **UC-4 requires a synchronous RTSP handshake on camera create, which P4 deliberately inverted**; `auth_session` / `export_job` / `help_article` missing from the ERD. | `final_paper_text.txt` vs `be_plan/` | Med | open · verified | A7 |
| F15 | `00_INDEX.md` still shows P9 as "🔶 implemented, not pushed/PR'd" — it merged as PR #70 (`336a967`). Its nine-box definition of done is **all unchecked** though 7–8 are now satisfied. `CONTRIBUTING.md` claims startup "hard-fails if any of the 10 keys are missing"; only **3** are required. `final_paper_text.txt` is untracked despite being a declared source of truth. | `be_plan/00_INDEX.md`, `CONTRIBUTING.md` | Low-Med | open · verified | A7 |
| F16 | Housekeeping: stray 0-byte `backend/adas.db`; orphan bytecode `app/__pycache__/{models,ws_manager}.cpython-312.pyc` for modules deleted in P1/P3; `GET /api/events/schema` is fully unauthenticated (leaks the internal event contract); WS `receive_text()` on a binary client frame raises into the generic handler and logs as an unexpected error. | various | Low | open · verified — **the WS binary-frame item is fixed** 2026-08-10 by A4, see resolution log; the other three sub-items remain owned by A8 | A8 (+A4 partial) |
| F17 | **The live database sits inside a cloud-sync folder.** The repo root is `C:\Users\Dani\OneDrive - dlsl.edu.ph\…`, so `adas.db` and its `-wal`/`-shm` sidecars, plus `ai_engine/snapshots/`, `var/backups/` and `var/exports/`, are all continuously synced by OneDrive. SQLite in WAL mode under a sync client that opens, locks and uploads those files is a known-bad combination — file-locking errors, sync-conflict copies of the database, partially uploaded snapshots. It also silently undermines D-011's backup integrity story. Immediate mitigation is to pause OneDrive for any demo or drill; the real fix is to relocate the runtime data directories outside the synced tree. | repo root layout; `core/config.py` path validators | Med-High | open · verified | A1 (mitigate) → owner decision (fix) |
| F18 | `test_lifespan_resets_only_enabled_active_cameras` pointed a hand-built in-memory engine at `app.state.engine` while leaving `app.state.settings` on the real process-global `Settings` (`DATABASE_URL` → the real repo-root `adas.db`). `check_schema_revision`'s development auto-bootstrap always reopens `target_settings.DATABASE_URL` itself via `backend/alembic/env.py` — it ignores the `engine` argument entirely — so the migration silently ran against the *wrong* database. Order-dependent: passed in isolation, failed under the full suite whenever an earlier test had already caused the real `adas.db` to be migrated (`table camera already exists`). Reproduced on `main` before any A2 change, so **not** F1-induced. Fixed as a test-fixture bug: rewritten to build its own `create_app(Settings(DATABASE_URL=tmp file, ...))` (engine and settings now provably consistent) and simulate a restart via two `TestClient` context-manager entries instead of monkeypatching the module-level `app` singleton. | `backend/tests/test_main.py` | Med | **fixed** | A2 |
| F19 | `backend/scripts/seed_alerts_via_api.py` was deleted by A3 (F3) — it was the last v1-payload caller. `be_plan/MANUAL_TESTS.md` (the idle-session and event-storm procedures) and `08_PKG_backup_ops.md` (the write-load-during-backup drill) still cite it as the traffic-generation tool. A6, when it executes those procedures, needs a v2-shaped substitute — a small script or `curl` posting `{source_event_id, camera_id, detected_at, snapshot_key, confidence_score}` to `POST /api/internal/alert`, or a real detection. `be_plan/` is left as-is per the immutability rule; this row is the pointer. | `be_plan/MANUAL_TESTS.md`, `be_plan/08_PKG_backup_ops.md` | Low | open · verified | A3 |
| F20 | **A genuine accident detected during a backend outage can be silently discarded on reconnect, via a race the outbox design didn't account for.** The heartbeat snapshot is the engine's *only* signal for desired state, and the backend has no knowledge of an outbox-queued-but-undelivered event (nothing about it is committed to the DB until delivery succeeds). Sequence: engine detects a collision while the backend is unreachable → pauses the camera **locally** and durably queues the event (correct, per D-012) → backend comes back up → the *next heartbeat* still reports the camera's old `desired_ai_state: Active` (the backend never learned about the pending incident) → per `supervisor.py`'s reconciliation table (`desired_ai_state: Active` + locally paused → `resume()`), the engine **resumes inference before its own queued event has been delivered** → if the camera detects again before the original event's backoff-scheduled retry fires, the second detection is delivered first (backend now reachable) and legitimately opens the incident → the *original* event's retry then hits the camera's now-open incident, gets `409 CONFLICT_STATE`, and per the documented (correct-in-isolation) handling — "the backend already has an open incident for that camera — this event is genuinely redundant" — is discarded from the outbox with **no DB row ever created**. The JPEG snapshot is orphaned on disk, unlinked from any incident, invisible to every operator. Live-reproduced 2026-08-10: source_event_id `8931c59d-…` (camera 4, confidence 0.9028, detected 16:23:44) was confirmed queued to `ai_engine/outbox/` and confirmed durable while the backend was verifiably down (`curl` connection-refused); on restart the backend log shows exactly one `201 Created` immediately followed by one `409 Conflict`; `sqlite3 adas.db` confirms **no row exists** for that `source_event_id` anywhere in `detection_log` (54 rows total, gapless, none matching); a *different*, later source_event_id (`1dde8110-…`, detected 16:24:22) is the row that actually exists for camera 4. The snapshot JPEG for the lost event still exists on disk, unreferenced. This is the CONFLICT branch behaving exactly as documented — the gap is that "genuinely redundant" isn't always true; it can also mean "a real, distinct, earlier-detected event lost a race it should have won." In the demoed case the accident *was* ultimately reported via the second detection, but a real accident whose visual signature clears in a couple of frames (wreckage towed, or a near-miss the model catches once) could be lost with **no incident created at all**. State: **suspected** — reconstructed from direct log/DB/filesystem evidence plus the documented reconciliation rule in `supervisor.py`, not from a debugger-attached single-step; the reasoning is strong enough to act on but wasn't captured with instrumentation proving the exact interleaving. Fix direction: the engine should not honor a resume for a camera with outbox entries still pending for it — `supervisor.py`'s `REAPPLY_CONFIG`/resume branch needs a "do I have anything queued for this camera_id" guard that only `outbox.py` can answer, since the backend structurally cannot. | `ai_engine/supervisor.py` (reconciliation table) · `backend/app/api/routes/internal.py` (`CONFLICT_STATE` 409 branch) · `ai_engine/outbox.py` (`CONFLICT` handling) | Med-High | **fixed** — `outbox.pending_camera_ids()` (new) reads the queued events' `camera_id`s; `compute_actions()` takes that set as a third parameter and withholds `RESUME` (and forces the rebuilt stream's `desired_ai_state` to `Paused` on a `REAPPLY_CONFIG` too, which goes through the same `_start_stream()` unpause path) for any camera in it, regardless of what the backend's stale snapshot says. Deliberately does not touch `PAUSE` — a fresh incident must still take effect immediately. `compute_actions()` stays pure (the caller, `heartbeat_loop()`, supplies the set from `outbox.pending_camera_ids()` each cycle — no filesystem I/O inside the decision function itself). 7 new unit tests in `ai_engine/tests/test_supervisor.py` and `test_outbox.py` cover the withhold, the per-camera scoping (a pending event on camera 2 doesn't block camera 1), the `REAPPLY_CONFIG` override, and that `PAUSE` is unaffected. `uv run pytest` green. | A3 |
| F21 | Re-running the `slow` perf suite (`be_audit/A6_manual_evidence.md` Part 3) with this session's own LAN/TLS demo stack (mediamtx + 5 ffmpeg feeds + AI engine doing live TensorRT inference + backend + frontend dev server) still running in the background measured `GET /api/analytics/dashboard` at **4.779s against its 3s NFR-08 budget** — a real assertion failure. Stopping that stack and re-running reproduced the documented ~1.1–2.0s range immediately. | `backend/tests/perf/test_query_performance.py` | Low | **void** — reproduced the failure, found the cause (resource contention from this session's own concurrently-running demo stack, not the code under test), confirmed it disappears with a quiet machine. Recorded so a future pass doesn't re-raise it as a regression; worth noting as a real caution for anyone running the perf suite while a demo stack is up. | A6 |
| F22 | `scripts/adas-maintenance.ps1` launches both the backend and the AI engine via `Start-Process -WindowStyle Minimized`, with no persistent log file — their stdout goes to a GUI console window that only exists for the life of that window. A restart/restore drill's postmortem (model-load time, first-frame-processed timestamp, any warning in the AI engine's own startup log) is therefore unrecoverable once that window is gone, unless a terminal was left open on it at the time. Found while executing the TC-R-303 restart drill (`be_audit/A6_manual_evidence.md`), where the AI engine's model-load timestamp could not be recorded for exactly this reason. | `scripts/adas-maintenance.ps1` (`Start-Backend`/`Start-AiEngine`) | Low | open · verified | A6 |

---

## Checked and cleared — do not re-raise

These looked like findings and are not. Recorded so no future pass spends time on them.

- **Operators can create/update/delete cameras.** Deliberate. FR-02 grants Operators camera
  status *and configuration*; recorded in `01_CONTRACTS.md` §5.5 as "a deliberate decision,
  recorded in P2, not an oversight." The paper's "Administrators limited to user account and
  security management" refers to Admin's *exclusive* surface, not a restriction on Operators.
- **`routes/system.py` / `system_health.py` / `maintenance.py` share the `/api/system` prefix.**
  Deliberate — three router files, one owner each, so P5 and P7 could proceed in parallel.
  `01_CONTRACTS.md` §5.11: "Do not consolidate them."
- **`ai_engine/best.engine` → `best.pt` fallback.** Intentional portability path, documented in
  `CLAUDE.md`. Not a bug to "fix".
- **No coverage threshold in CI.** Deliberate per the testing policy; `CONTRIBUTING.md` states it.
- **`.env.example` ↔ `Settings` drift.** None. All 53 keys map 1:1; the four `DSS_*` optionals are
  present but commented.
- **`dismiss_transition`'s pre-read before the atomic UPDATE.** Not a race — terminal statuses
  never transition again (D-002), so the peek only *selects* which atomic attempt to make and
  `transition()`'s conditional UPDATE re-validates at write time.
- **Broadcast-after-commit ordering.** Correct everywhere checked (`routes/internal.py:167-168`
  and the alert transition routes); enqueue happens strictly after `session.commit()`.

---

## Resolution log

Append one dated line per state change. Newest last.

- `2026-08-10` — Register opened with F1–F16 from the audit planning session.
- `2026-08-10` — F6 downgraded Med-High → Low. `websockets 16.0` present / `wsproto` absent means
  uvicorn's default 20s ping/pong keepalive is already active; an application-level ping would be
  redundant. Scope changed to verify-and-document.
- `2026-08-10` — F11 narrowed. Edge case 1.12 is already handled by the shared `maintenance_lock`
  (`routes/maintenance.py:237`); only a cross-operation test is owed. 1.7 and 1.14 remain open.
- `2026-08-10` — F17 added while writing `DEMO_TOPOLOGY.md`: the live SQLite database, snapshots,
  backups and export artifacts all live inside the OneDrive-synced repo tree.
- `2026-08-10` — A1 executed. **F4 fixed**: real self-signed TLS end-to-end (backend via uvicorn
  `--ssl-keyfile/--ssl-certfile`, frontend via an opt-in `ADAS_TLS_CERT_DIR`-gated `vite.config.ts`
  block, client origins made protocol-aware in `frontend/src/utils/env.ts`), live-verified with a
  real login → Secure cookie → authenticated follow-up request. **F5 and F8 both confirmed**
  (not voided) by direct reproduction — see `DEMO_TOPOLOGY.md` §10 for the exact evidence; fixes
  remain owned by A2 and A4 respectively. F17 did not reproduce this session (OneDrive was not
  running), which is not evidence against it. This session ran on a single physical machine, so
  the two-laptop physical steps (static IPs, firewall rules, client hosts entry, installing the
  cert into a second machine's Trusted Root store, and the GUI walkthrough) were **not** executed
  and remain owed before the real demo — see `DEMO_TOPOLOGY.md` §10 for what was substituted and
  why. `uv run pytest` and `pnpm check` both pass with the TLS changes inert
  (`ADAS_TLS_CERT_DIR` unset). `.prettierignore` gained a `be_audit/` entry (mirroring the existing
  `be_plan/` exclusion) since `pnpm check` otherwise fails on this pack's own working docs.
- `2026-08-10` — A2 executed. **F1, F2, F5, F7 all fixed.** F1: `session_fixture` now installs the
  same four pragmas production does; `foreign_keys=ON` verified live (an ORM insert with a
  dangling `camera_id` now raises `IntegrityError: FOREIGN KEY constraint failed`, confirmed
  against a throwaway `StaticPool` engine outside the suite). Enabling it surfaced **zero** test
  failures directly attributable to FK enforcement — every fixture already inserted parent rows in
  the correct order. F2: `Settings.validate_rtsp_url_template` added; 5 new tests in the new
  `backend/tests/test_config.py`. F5: `expose_headers=["Content-Disposition", "X-Request-ID"]`
  added to `CORSMiddleware`, closing the gap A1 confirmed by live reproduction. F7: export worker
  startup moved out of the `SCHEDULER_ENABLED` block and gated on `EXPORT_JOB_WORKERS > 0`
  independently; `_build_test_settings` now sets `EXPORT_JOB_WORKERS=0`; a new end-to-end
  regression test drives a real queued job through the worker pool with the scheduler off.
  **F18 added and fixed**: `uv run pytest` on the full suite (not just the files this pack
  touched) surfaced one pre-existing, order-dependent failure in `test_main.py` unrelated to F1 —
  reproduced identically on `main` before any A2 change (confirmed via `git stash`) — and fixed as
  a test-fixture bug per the same triage standard this pack used for F1. `uv run pytest` is green
  end to end. `pnpm check` was not run this session (deferred to the push step per owner
  instruction); `uv run ruff format` was run directly on the two new test files to keep them
  compliant.
- `2026-08-10` — A4 executed.
  **F6 fixed (verify-and-document, as scoped — not a build job).** Confirmed live, not just by
  reading the dependency list: started `uv run fastapi dev backend/app/main.py` and, separately,
  `uv run uvicorn app.main:app --app-dir backend ...` (plain HTTP this session — no `certs/` in
  this worktree — but the WS implementation selection is identical under TLS) and, in the same
  venv both run from, confirmed `websockets 16.0` importable and `wsproto` absent. Read
  `fastapi_cli/cli.py`'s `_run()`: it calls `uvicorn.run()` without `ws_ping_interval`/
  `ws_ping_timeout` kwargs and neither `fastapi dev` nor `fastapi run` expose those flags on their
  CLI signatures at all — so `uv run fastapi dev backend/app/main.py` (CLAUDE.md's documented dev
  command) and `fastapi run backend/app/main.py` (what `scripts/adas-maintenance.ps1
  -Action Start/Restart` invokes) can **only** ever inherit the uvicorn library default
  (`ws_ping_interval=20.0`/`ws_ping_timeout=20.0`, confirmed by reading the installed
  `uvicorn/config.py`) — there is no way to pin it explicitly on those two paths without dropping
  the FastAPI CLI for a direct `uvicorn` invocation, which is out of scope for a verify-and-document
  item. The one launch command that already drives uvicorn directly —
  `A1_lan_tls_drill.md` step 2, the actual demo-day server command — now pins it explicitly with
  `--ws-ping-interval 20 --ws-ping-timeout 20`; started live this session and confirmed a clean
  boot on `/healthz/live`. `be_plan/04_PKG_realtime.md` Step 5 amended to record all of this so a
  future reader does not re-raise F6 or attempt to build a redundant application-level ping.
  **F8 fixed.** `request_id_middleware` now also stamps `request.state.request_id` (backed by the
  ASGI `scope`, which survives into `ServerErrorMiddleware`'s own `Request(scope)` reconstruction),
  so `global_exception_handler` — which runs *outside* the middleware whose `finally` resets
  `request_id_ctx` — reads the id from `request.state` instead and attaches `X-Request-ID` to the
  500 response itself. Same treatment applied to `operational_error_handler`'s 500 and 503
  branches (that handler already had the *correct* id via the still-live contextvar, since it runs
  inside `ExceptionMiddleware`, but was never attaching it as a header either — F8's fix note calls
  this out explicitly). Two new regression tests in `backend/tests/test_logging.py`
  (`TestRequestIdOnErrorResponses`) hit a real route through a temporary per-test app route and
  assert the response's `X-Request-ID` header matches the id embedded in the corresponding log
  line, for both the unhandled-500 and the lock-timeout-503 paths.
  **F16 (binary-frame sub-item only) fixed.** `websocket_alerts`'s read loop now calls
  `websocket.receive()` and branches on `message["type"]`, breaking only on
  `"websocket.disconnect"` — a binary frame is just another ignored message instead of raising into
  the generic `except Exception` and logging a spurious "Unexpected error" stack trace. New test
  `test_binary_frame_is_ignored_and_not_logged_as_error` in `backend/tests/test_realtime.py` sends
  a real binary frame over a `TestClient` websocket, asserts no such log line appears, asserts a
  broadcast still reaches the connection afterward (proving the loop wasn't torn down), and asserts
  the connection deregisters exactly once when the socket actually closes. The other three F16
  sub-items (stray 0-byte db, orphan bytecode, unauthenticated `/api/events/schema`) remain owned
  by A8. `pnpm check` green after these changes — `uv run pytest` 712 passed / 2 skipped / 10
  deselected, frontend `vitest` 16 passed, lint/format/typecheck all clean.
- `2026-08-10` — A3 executed. **F3 fixed**: `GET /api/internal/cameras`, `PATCH
  /api/internal/cameras/{id}/status`, the v1 branch of `POST /api/internal/alert`, and
  `backend/scripts/seed_alerts_via_api.py` all deleted; confirmed `ai_engine/` had already finished
  its own P10 migration to v2 (`supervisor.py`/`backend_client.py`/`events.py`/`outbox.py` all
  present, no `sync.py`, no `SYNC_URL`/`RTSP_BASE_URL` in `config.py`) before this branch touched
  anything, so the route removal has no live caller to break. **F9 fixed**: `engine_id` bounded
  (128 chars + null-byte rejection), `cameras` bounded to 2000 entries, a process-lifetime
  last-seen-engine tracker warns (never rejects) on edge case 1.18, and `sent_at` now drives a
  clock-skew warning. **F19 added**: `be_plan/MANUAL_TESTS.md` and `08_PKG_backup_ops.md` still
  reference the now-deleted `seed_alerts_via_api.py` — owed to A6. `be_plan/01_CONTRACTS.md` §6 and
  §6.1 got dated append-only notes (not rewritten) recording the removal.
  **Live seam re-verification**, real stack (mediamtx + ffmpeg sim, backend, AI engine with the real
  TensorRT model, 5 of 6 cameras wired to real RTSP feeds — camera 3 disabled, camera 6 has no feed
  in `mediamtx.yml` and stays `Reconnecting`/`Unresponsive` for that reason, not a defect):
  1. **Heartbeat live.** Engine reached `Connected`/`Active` on every fed, enabled camera within
     seconds of starting — never stuck on `Reconnecting`.
  2. **Disable → runtime stops.** Disabling camera 5 via the operator API froze its `updated_at`
     immediately (the engine stopped including it in heartbeat reports); re-enabling recovered it on
     the next cycle.
  3. **`RTSP_URL_TEMPLATE` hot-reload.** Restarted the backend with the template's host changed
     (`localhost` → `127.0.0.1`, same connectivity) — source-verified `supervisor.py`'s
     `restart_needed = local.rtsp_url != snap.rtsp_url` is unconditional on `config_version`, and the
     live restart caused no lasting disruption to any camera. The precise reconnect blip wasn't
     captured at 3s polling granularity (verification limitation, not a finding).
  4. **Durability — the one that matters most.** Reproduced cleanly after early attempts were lost to
     test-timing (see F20): stopped the backend, confirmed via a fast poll loop that the engine's
     *own* observed `ai_status` had flipped to `Active` (i.e., the resume signal had actually landed,
     not just been sent) before killing the backend, then watched a real collision detection
     (`source_event_id 8931c59d…`, camera 4, confidence 0.9028) write its JPEG and land in
     `ai_engine/outbox/` while `curl` to the backend returned connection-refused. Restarted the
     backend; the outbox drained. **This attempt is also where F20 was found** — that specific event's
     row was never created (superseded via `409 CONFLICT_STATE` by a second, later detection that won
     the race after a premature resume — see F20 for the mechanism). Repeated the "survives a restart"
     half deterministically: hand-wrote a durable-format outbox entry for an incident-free camera (2)
     while the AI engine process was confirmed fully dead, restarted the engine, and confirmed it
     drained (delivered, one new `detection_log` row) within 6 seconds of startup — "drain the outbox
     before entering the inference loop" behaves as documented.
  5. **Engine loss → `Unresponsive`.** Killed the AI engine process; every fed, enabled camera
     (1, 2, 4, 5, 6) read `Unresponsive`/`Unresponsive` at the first poll (≤2s, well inside
     `HEARTBEAT_STALE_SECONDS=10`); camera 3 (disabled) correctly stayed `Disconnected`/`Inactive`
     the whole time — `presented_statuses()`'s "a disabled camera is never stale" rule holds live.
     Restarted the engine; all fed cameras recovered to `Connected` within ~9s.
  Test data (all the confirm/resolve cycles used to keep re-arming cameras 1 and 4 for the durability
  attempts) was cleaned up to `Resolved` afterward; nothing was left in an `Unverified`/`Ongoing`
  state on the dev DB.
- `2026-08-10` — **F20 fixed**, same session, on request: `ai_engine/outbox.py` gained
  `pending_camera_ids()`; `ai_engine/supervisor.py::compute_actions()` takes the result as a third
  (default-empty, so fully backward-compatible) parameter and withholds `RESUME` — and forces a
  `REAPPLY_CONFIG`'s rebuilt-stream snapshot to `Paused` — for any camera with a still-undelivered
  outbox event, closing the race described above. `PAUSE` is untouched; a fresh incident still takes
  immediate effect. `heartbeat_loop()` is the only place that calls `outbox.pending_camera_ids()` —
  `compute_actions()` itself stays a pure, filesystem-free decision function, matching its existing
  docstring contract and CI-testability constraint. 7 new tests added (`test_supervisor.py`,
  `test_outbox.py`); `uv run pytest` green across the whole suite (backend + `ai_engine/tests`).
- `2026-08-11` — A6 executed. Six of the nine `MANUAL_TESTS.md` procedures run and passed
  (restart drill 8.13s/10s budget, restore drill ~26s/60s budget, rollback drill with a genuine
  injected `DATABASE_URL` failure and verified automatic-rollback-equivalent recovery, browser
  crash/reopen recovery, three-simultaneous-camera burst). The 24-hour endurance run and 4-hour
  idle session were deliberately left unrun per an explicit owner decision (real-time execution
  vs. a shortened proxy vs. honest non-execution — the owner chose the last); the bi-annual
  restore drill is recorded `blocked` (deployment-owned, no staging environment available).
  **F13 updated** to reflect the 6/9 split. NFR-06/TC-R-203 re-scoped to the real ~10
  incidents/day operating envelope per owner decision: a new `TestOperatingEnvelopeExportLatency`
  perf test class (`backend/tests/perf/test_export_performance.py`, backed by a dedicated
  `envelope_seeded` fixture in `backend/tests/perf/conftest.py` — a separately-seeded ~10/day
  dataset, not a filtered slice of the existing 100k/~182-per-day one) measured CSV 0.052s and
  PDF 2.750s at the real 300-row/30-day envelope, both well inside the 5s budget; the existing
  10,000-row PDF ceiling measurement (48.4s) is retained, relabelled as a documented ceiling, not
  a failed requirement. `EVIDENCE.md` fully refreshed post-A1–A4 (`uv run pytest -m slow
  backend/tests/perf/ -s`, 11 passed / 1 xfailed) — **F21 found and voided** in the process (a
  perf-suite failure traced to this session's own demo stack still running in the background, not
  a regression). An honest NFR-04 LAN-measured figure was **not** added despite the pack asking
  for one: A1's own resolution log confirms it never ran the real two-laptop test either (single
  physical machine only), so there was nothing genuine to carry forward; `EVIDENCE.md` now says so
  explicitly instead of fabricating a number, and surfaces the best real data available instead
  (A3's live-process loopback measurement, ~0.53–0.84s, clearly labelled as not the LAN number).
  **F22 found**: the Windows orchestrator's minimized-console process launch has no persistent
  log file, so postmortem inspection of a restart drill's AI-engine startup log is not possible
  after the fact — surfaced while trying to record TC-R-303's model-load-time measurement, which
  could not be captured for exactly this reason. `TRACEABILITY.md` rows for TC-R-203, TC-R-303,
  TC-R-401, TC-R-402, TC-R-304, TC-S-203 and TC-S-401 all updated to reflect the above.
