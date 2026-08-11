# Test-Case Traceability Matrix

> **10_PKG_migration_evidence.md Step 4.** One row per paper test case (82
> total, extracted from `final_paper_text.txt`'s Tables 9.1–9.4, 10.1–10.4,
> 11.1–11.4, 12.1–12.4, 13.1–13.4, 14.1). Per **D-001's boundary rule**, a
> test case owned by someone else (AI model accuracy, physical VLAN/NAS,
> frontend UI) is never left blank — every row carries an explicit owner,
> interface, prerequisite, and acceptance evidence, even when that evidence
> is "not yet produced."
>
> **Evidence type** is one of: `automated` (a named backend/AI test),
> `manual` (a procedure in `be_plan/MANUAL_TESTS.md`), or `external`
> (owned outside this repo's backend — frontend, AI model tuning, or
> physical deployment — with the interface/prerequisite named here).
>
> **Status** is one of: `pass` (evidence exists and is green), `pending`
> (owner identified, evidence not yet produced), or `blocked` (waiting on
> something outside this package's control).

---

## Table 9.1 — Frontend UI Components (TC-U-1xx)

All eight rows are frontend-owned by the paper's own table title. CLAUDE.md's
testing policy keeps frontend coverage deliberately minimal (a handful of
smoke tests on pure utils/presentational components); none of these
component-level behavioral tests exist yet in `frontend/src/**/*.test.*`
(currently: `StatCard.test.tsx`, `cn.test.ts`, `env.test.ts`) or in
`e2e/login.spec.ts` (one happy-path login test only). Interface for all
eight is the REST/validation contract in `01_CONTRACTS.md`; prerequisite is
the frontend team writing the corresponding Vitest/Playwright coverage.

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-U-101 | FR-01 | frontend | external | Interface: `POST /api/auth/login`'s generic `AUTH_INVALID_CREDENTIALS` error contract. Prerequisite: frontend form validation + submit-disable logic. Acceptance evidence: not yet written (no frontend test exercises SQLi strings or empty-field disable). | pending |
| TC-U-102 | FR-03 | frontend | external | Interface: password complexity rule the backend also enforces server-side (`01_CONTRACTS.md` — length 8–128, one digit; backend evidence: `test_auth.py::TestBoundaryValues::test_password_length_boundary`, `test_password_with_exactly_one_digit_passes`). Prerequisite: frontend mirrors the same rule client-side. Acceptance evidence: not yet written. | pending |
| TC-U-103 | FR-02 | frontend | external | Interface: the `role` claim surfaced by `GET /api/users/me`. Prerequisite: React route/nav guards read that role. Acceptance evidence: not yet written. | pending |
| TC-U-104 | FR-14 | frontend | external | Interface: `GET /api/alerts/`'s `start_date`/`end_date` (backend rejects `start_date > end_date` with 422 — `test_alerts.py`, `validate_common_filters`). Prerequisite: frontend date-picker mirrors that rule locally. Acceptance evidence: not yet written. | pending |
| TC-U-105 | FR-07, FR-09, NFR-10 | frontend | external | Interface: `POST /api/alerts/{id}/confirm`\|`/dismiss`\|`/snooze`. Prerequisite: modal UI limits the operator to ≤2 clicks and renders the Snooze toggle. Acceptance evidence: not yet written (TC-S-105 covers the related 3-click NFR-10 case at UAT level). | pending |
| TC-U-106 | FR-20 | frontend | external | Interface: `GET /api/help/articles/{slug}`'s `body_markdown` field (backend evidence: `test_help.py`). Prerequisite: React markdown renderer. Acceptance evidence: not yet written. | pending |
| TC-U-107 | FR-03 | frontend | external | Interface: account creation/edit form. Prerequisite: client-side password-confirmation match check. Acceptance evidence: not yet written. | pending |
| TC-U-108 | FR-08 | frontend | external | Interface: `PUT /api/settings/alarm`'s `snooze_duration` bounds (backend evidence: `test_settings.py::test_snooze_duration_boundaries`, 15–60s). Prerequisite: frontend mirrors the same bounds client-side. Acceptance evidence: not yet written. | pending |

---

## Table 9.2 — Backend API and Auth Middleware (TC-U-2xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-U-201 | NFR-19 | backend | automated (indirect) | No standalone unit test asserts the Argon2id hash/verify roundtrip in isolation. Proven indirectly through every successful login (`test_auth.py::TestLogin::test_login_success_sets_cookie_no_token_in_body`) and the timing-safety test that runs a real verification against a dummy hash on the unknown-user path (`test_auth.py::TestLogin::test_unknown_username_still_runs_a_real_password_verification`, edge case 8.8). `app/core/security.py::get_password_hash`/`verify_password` use `passlib[argon2]`. | pass |
| TC-U-202 | NFR-19, D-006 | backend | automated (indirect) | No standalone unit test decodes and asserts on `create_session_token`'s claim values in isolation; proven indirectly — every authenticated route test depends on a correctly shaped JWT (`sub`, `sid`, `role`, `exp`, `iss`, `aud`), and `test_auth.py::TestJWTVerification` (below) proves the same claims are actually checked. | pass |
| TC-U-203 | NFR-19, D-006 | backend | automated | `backend/tests/test_auth.py::TestJWTVerification::test_expired_token_returns_auth_expired` | pass |
| TC-U-204 | FR-02 | backend | automated | `backend/tests/test_auth.py::TestRBAC::test_operator_cannot_access_user_management`, `test_operator_403_creates_denied_user_create_row` (403 before payload processing, audited as `denied`) | pass |
| TC-U-205 | NFR-04, FR-06 | backend | automated | `backend/tests/test_websocket.py::test_internal_alert_broadcasts_to_websocket_client` — asserts the exact field set (`log_id`, `camera_id`, `detected_at`, `confidence_score`, `snapshot_url`, `detection_status="Unverified"`) inside the versioned envelope. **Paper amendment needed**: TC-U-205 must acknowledge the AI-generated `source_event_id` in the payload (D-012) — see the amendments list below. | pass |

---

## Table 9.3 — AI Utility and Data Processing (TC-U-3xx)

Owner: AI engine for all three (D-001: model tuning, frame processing, and
detection math are the AI owner's domain). Interface: `ai_engine/` internal
modules; prerequisite: the AI owner's own pytest suite under `ai_engine/tests/`.

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-U-301 | NFR-03 | AI engine | external | Interface: the ingestion buffer's frame-selection logic (`ai_engine/` streaming module). Prerequisite: a unit test feeding 30 synthetic frames and asserting 10–15 survive. No matching test found in `ai_engine/tests/` today. | pending |
| TC-U-302 | NFR-01, FR-05 | AI engine | external | Interface: the confidence-threshold filter applied to YOLO output. Prerequisite: a unit test with mock scores `[0.45, 0.88, 0.60]` against threshold 0.75. No matching test found in `ai_engine/tests/` today. | pending |
| TC-U-303 | NFR-01 | AI engine | external | Interface: the bounding-box tensor→dict parser. Prerequisite: a unit test against a mock YOLO tensor. No matching test found in `ai_engine/tests/` today. | pending |

---

## Table 9.4 — Database Concurrency and Query Logic (TC-U-4xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-U-401 | FR-06, FR-13 | backend | automated | `backend/app/models/detection.py`'s `detection_status: str = Field(default=DetectionStatus.UNVERIFIED.value)` + `backend/tests/test_schema.py` (schema-level CHECK/default coverage); every `make_alert`/`ensure_alert` seed helper across the suite relies on this default. | pass |
| TC-U-402 | NFR-08, D-005 | backend | automated | `backend/tests/test_db_pragmas.py::test_journal_mode_is_wal_on_fresh_connection` (WAL is on) + `backend/tests/test_maintenance.py::TestBackupCore::test_online_backup_succeeds_during_concurrent_writes` (a concurrent writer thread hammers the DB during a live backup read with zero "database is locked" errors — the closer real-world analog of TC-U-402's scenario). | pass |
| TC-U-403 | FR-13 | backend | automated | `backend/tests/test_alerts.py::TestConfirm::test_confirm_unverified_alert` — asserts `verified_by_id`/`verified_at` are set and `detected_at` is never touched. | pass |
| TC-U-404 | NFR-05 | backend | automated | `backend/tests/test_system_health.py::TestPruneRaw::test_boundary_is_inclusive` (exactly-48h-old pruned, 47h59m kept — edge case 2.14) | pass |
| TC-U-405 | NFR-05 | backend | automated | `backend/tests/test_system_health.py::TestRollupHour::test_twelve_five_minute_rows_produce_one_row_with_correct_stats` | pass |

---

## Table 10.1 — Video Stream Ingestion (TC-I-1xx)

Owner: AI engine (RTSP/MediaMTX handling is D-001's AI-integration scope).
Interface: `ai_engine/`'s RTSP client against the demo `mediamtx.yml`
(`rtsp://localhost:8554/channel{1..6}`). Prerequisite: `mediamtx` running
with `ai_engine/sample_vids/` (gitignored, ask the team).

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-I-101 | FR-04 | AI engine | external / manual | Live-drilled for real per P10's completion report (00_INDEX.md): real `mediamtx`, real ffmpeg-published RTSP streams, engine connected and detected an accident within ~1s. No standing automated integration test (would require a running MediaMTX process in CI). | pass (live-drilled, not CI-automated) |
| TC-I-102 | FR-04, NFR-03 | AI engine | external | Interface: `RTSP_URL_TEMPLATE`'s `subtype=1` parameter (`01_CONTRACTS.md` §7.2). No dedicated test asserting the resolved stream is the 720p substream rather than the 4K main stream. | pending |
| TC-I-103 | FR-04 | AI engine | external / manual | Covered incidentally by the same P10 live drill (real frames decoded via `cv2.VideoCapture`, no gray-frame tearing observed) — not a standing automated test. | pass (live-drilled, not CI-automated) |
| TC-I-104 | FR-04, NFR-07 | AI engine | external / manual | P10's live drill used 2 simultaneous camera streams (`car_car.mp4`, `red-car-motorcycle.mp4`), not 3+; `ai_engine/tests/test_supervisor.py` unit-tests the supervisor's per-camera start/stop decisions with simulated state, not real concurrent RTSP handshakes. | pending (partial) |

---

## Table 10.2 — AI Telemetry Handover (TC-I-2xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-I-201 | FR-06 | AI engine | external | Interface: the `POST /api/internal/alert` payload the AI engine posts. `ai_engine/tests/test_accident.py` and `test_backend_client.py` cover the AI-side serialization; the backend's receipt/validation side is covered by `backend/tests/test_internal.py`. | pass |
| TC-I-202 | FR-12, D-002, D-003 | backend + AI engine | automated | `backend/tests/test_alerts.py::TestConfirm::test_confirm_keeps_camera_paused_no_camera_broadcast` (desired state stays `Paused`/`incident` on Confirm). **Paper amendment needed** (D-012, flagged below): the paper's "ceases frame ingestion" wording is wrong — the locked behavior is that YOLO inference and event generation cease while bounded RTSP draining continues, so resume starts from live footage, not a stale buffer. | pass (acceptance wording needs the amendment below) |
| TC-I-203 | FR-11 | backend | automated | `backend/tests/test_alerts.py::TestDismiss::test_dismiss_unverified_starts_cooldown_and_schedules_job` + `backend/tests/test_camera_reconciliation.py` (cooldown desired-state derivation, including the exactly-now boundary — edge case 2.12). | pass |
| TC-I-204 | FR-16 | backend | automated | `backend/tests/test_system_health.py::TestHealthLiveEndpoint::test_fresh_sample_reports_readings_and_is_not_stale` | pass |

---

## Table 10.3 — API & Data Persistence (TC-I-3xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-I-301 | NFR-04, FR-06 | backend (dispatch) + frontend (modal/alarm) | automated (backend half) | Backend dispatch: `backend/tests/test_websocket.py::test_internal_alert_broadcasts_to_websocket_client`; end-to-end latency: `backend/tests/perf/test_alert_latency.py` (0.016s measured, budget 2s). Frontend modal/alarm trigger: external, not automated in this repo. | pass (backend) / pending (frontend) |
| TC-I-302 | FR-14 | backend (query) + frontend (hydration) | automated (backend half) | `backend/tests/test_alerts.py::test_filter_by_date_range`. Frontend table hydration: external. | pass (backend) / pending (frontend) |
| TC-I-303 | FR-15, D-003 | backend + AI engine | automated | `backend/tests/test_cameras.py::test_create_sets_desired_active` (DB commit, `config_version` bump). AI-side pickup: `ai_engine/tests/test_supervisor.py::test_missing_enabled_active_camera_is_started`. | pass |
| TC-I-304 | FR-15, D-003 | backend + AI engine | automated | `backend/tests/test_cameras.py::test_disable_sets_inactive_and_bumps_version`. AI-side teardown: `ai_engine/tests/test_supervisor.py::test_disabled_local_camera_is_stopped`. | pass |
| TC-I-305 | FR-18 | backend | automated | `backend/tests/test_analytics.py::test_dashboard_returns_kpis_frequency_and_full_hour_series` | pass |
| TC-I-306 | FR-08 | backend | automated | `backend/tests/test_settings.py::test_full_replacement_roundtrip` | pass |
| TC-I-307 | FR-08, D-004 | backend (scoping) + frontend (audio isolation) | automated (backend half) | Backend: snooze fields live on the specific `DetectionLog` row (schema-enforced isolation); `backend/tests/test_alerts.py::test_snooze_broadcasts_snooze_activated` proves the event carries the specific `log_id`/`camera_id`. Frontend per-camera audio muting: external, not automated. | pass (backend) / pending (frontend) |
| TC-I-308 | FR-07, D-004 | backend | automated | `backend/tests/test_snoozes.py::TestSweepExpiredSnoozes::test_clears_a_due_snooze` + `backend/tests/test_alerts.py::test_snooze_broadcasts_snooze_activated`'s `RE_ALARM` counterpart (`test_snoozes.py::test_duplicate_call_after_clearing_is_a_no_op` — exactly one broadcast). | pass |

---

## Table 10.4 — Audit Trail & Security Synchronization (TC-I-4xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-I-401 | FR-13, NFR-19 | backend | automated | `backend/tests/test_alerts.py::TestConfirm::test_confirm_unverified_alert` (JWT-authenticated actor's `user_id` lands in `verified_by_id`) | pass |
| TC-I-402 | FR-03 | backend | automated | `backend/tests/test_users.py::test_admin_creates_operator` | pass |
| TC-I-403 | FR-19 | backend | automated | `backend/tests/test_alerts.py::test_export_alerts_csv` | pass |
| TC-I-404 | NFR-19, D-006 | backend | automated | `backend/tests/test_realtime.py::test_logout_closes_only_that_sessions_socket` | pass |

---

## Table 11.1–11.4 — AI Model Validation (TC-AI-1xx…4xx)

**All twelve rows are AI-owner evidence per D-001 and D-012.** Owner: AI
engine / model training. Interface: the D-012 contract in
`be_plan/12_AI_ENGINE_CONTRACT.md` (not committed to this repo — see the
docs-tracking commit; it is the AI-owner-only handoff doc). Prerequisite:
the confidence-threshold, temporal-qualification rule, and measured
hardware/batch profile the AI owner locks per
`be_plan/17_AI_OWNER_OPEN_ITEMS.md`. **This backend completion effort
explicitly does not mock a model and claim mAP** (`14_EDGE_CASES.md`'s
"Coverage gaps that are acceptable"). None of these twelve are met by
anything in `backend/` or `ai_engine/`'s current test suite — they require
a labeled benchmark dataset and a trained model evaluation run this package
does not have.

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-AI-101 | NFR-01 | AI engine | external | Interface: offline mAP/IoU evaluation harness against a labeled benchmark set. Prerequisite: ≥85% mAP, ≥0.50 IoU thresholds locked (D-012 gate). | pending |
| TC-AI-102 | NFR-01 | AI engine | external | Same harness, per-frame IoU ≥0.50 against ground-truth boxes. | pending |
| TC-AI-103 | NFR-01 | AI engine | external | Temporal-qualification rule (D-012 gate) — consistent detection across a 10s sequence without flicker. | pending |
| TC-AI-201 | NFR-01 | AI engine | external | Environmental robustness benchmark set — low-light/nighttime. | pending |
| TC-AI-202 | NFR-01 | AI engine | external | Environmental robustness benchmark set — heavy rain/noise. | pending |
| TC-AI-203 | NFR-01 | AI engine | external | Environmental robustness benchmark set — lens flare/glare false-positive suppression. | pending |
| TC-AI-204 | NFR-01 | AI engine | external | Environmental robustness benchmark set — 30% occlusion. | pending |
| TC-AI-301 | NFR-01 | backend + AI engine | automated (backend half) | Backend's threshold enforcement is config-driven, not hardcoded (`CONFIDENCE` gate lives in `ai_engine/`); the backend's `confidence_score` CHECK constraint (`backend/tests/test_schema.py::test_confidence_score_out_of_range_rejected`) only bounds 0.0–1.0, it doesn't implement the 75% suppression threshold itself — that is AI-owned. | pending (AI half) |
| TC-AI-302 | NFR-01 | AI engine | external | Algorithmic bias benchmark — 0 false positives on pedestrian/motorcycle traffic. | pending |
| TC-AI-401 | NFR-02 | AI engine | external | Inference-latency benchmark, <100ms/frame — measured via `ai_engine/`'s own timing, not this repo's test suite. Related backend telemetry field (`inference_latency_ms`) is schema-tested in `backend/tests/test_schema.py`, but the AI owner's actual sub-100ms claim is unverified here. | pending |
| TC-AI-402 | NFR-03 | AI engine | external | FPS-maintenance benchmark, 10–15 FPS sustained over 5 minutes. | pending |
| TC-AI-403 | NFR-07 | AI engine | external | VRAM-stability benchmark, 3 concurrent streams, no OOM — demo GPU is 4GB (D-009). | pending |

---

## Table 12.1 — VMS Proxy Simulation (TC-R-1xx)

Owner: AI engine / deployment (MediaMTX and network-layer behavior).

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-R-101 | FR-04 | AI engine / deployment | external / manual | Interface: `mediamtx.yml` at the repo root + `RTSP_URL_TEMPLATE`. Live-drilled per P10's report (real MediaMTX, real RTSP handshake). No standing automated test (would need a running MediaMTX process in CI). | pass (live-drilled, not CI-automated) |
| TC-R-102 | NFR-07 | AI engine / deployment | external | Interface: same MediaMTX simulation, scaled to 5 concurrent streams. Not drilled at that concurrency (P10's drill used 2 streams) — see TC-I-104. | pending |

---

## Table 12.2 — Concurrency & Load Testing (TC-R-2xx)

All three are backend-owned and now have **measured** evidence (P9 Step 3)
against a real 100,000-row database — see `be_plan/EVIDENCE.md` for full
numbers, machine spec, and date.

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-R-201 | NFR-04 | backend | automated | `backend/tests/perf/test_alert_latency.py::TestAlertDeliveryLatency::test_alert_reaches_a_connected_client_under_2s` — measured 0.016s (budget 2s), against the 100k-row perf dataset. | pass |
| TC-R-202 | NFR-08 | backend | automated | `backend/tests/perf/test_query_performance.py::TestListAndDashboardLatency` — measured 0.111s (list) / 1.112s (dashboard) on 100,000 rows (budget 3s); `TestQueryPlans` confirms no `SCAN detection_log`. | pass |
| TC-R-203 | NFR-06 | backend | automated | **Re-scoped 2026-08-11** (`be_audit/A6_manual_evidence.md` Part 2, owner decision): the real operating envelope is ~10 incidents/day, so a 30-day export is ~300 rows, not the paper's literal ~10,000. Primary evidence is now `TestOperatingEnvelopeExportLatency` in `backend/tests/perf/test_export_performance.py` — CSV 0.052s, PDF 2.750s, both at 300 rows/30 days (budget 5s) ✅. The 10,000-row measurement is retained as a documented **ceiling**, not a requirement: CSV 0.537s at ~8,700 rows ✅; PDF 1.031s at a realistic ~180-row report ✅; PDF **48.4s at the ~10,000-row ceiling** ❌ (`xfail(strict=False)`) — see `EVIDENCE.md`'s NFR-06 section. | **pass at the real envelope** (primary) / documented 10k-row PDF ceiling retained for context, not a requirement |

---

## Table 12.3 — Disaster Recovery, Isolation & Fault Tolerance (TC-R-3xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-R-301 | NFR-14 | AI engine | external | Interface: the AI engine's per-camera reconnect loop (D-003: retry every 10s, `Unresponsive` after 3 failures). No automated test found in `ai_engine/tests/` exercising an actual disconnect/reconnect cycle. Backend-side staleness (`Unresponsive` after 10s of no heartbeat) is covered by `backend/tests/test_camera_reconciliation.py` and was live-drilled per P10 (engine killed, `Unresponsive` appeared within budget, recovered on restart). | pending (AI reconnect loop itself) / pass (backend staleness half) |
| TC-R-302 | NFR-15 | AI engine | external | Interface: per-camera exception boundary in the supervisor. `ai_engine/tests/test_supervisor.py` tests state-transition logic with simulated inputs, not a literal injected exception in one camera's worker leaving others unaffected. No matching test found. | pending |
| TC-R-303 | NFR-16 | backend + deployment | manual | `be_plan/MANUAL_TESTS.md`'s 3 AM restart drill procedure (10_PKG_migration_evidence.md Step 5), **executed 2026-08-11** (manually triggered, not the literal 3 AM window — see the pack's own note that this is expected). Downtime measured at 8.13s against the <10s NFR-16 budget. Automated pieces it depends on: `backend/app/maintenance/cli.py`'s `restart` command, tested in `backend/tests/test_maintenance.py`. | **pass** — see `MANUAL_TESTS.md` §1 Results |
| TC-R-304 | NFR-17 | backend (recovery endpoint) + frontend (reconnect trigger) | manual + automated (backend half) | `be_plan/MANUAL_TESTS.md`'s browser-crash-and-reopen procedure (Step 5), **executed 2026-08-11** (tab close + fresh tab against the same origin, the closest faithful analog available to a literal OS process kill — session cookie and full alert queue both survived with zero data loss). Backend half automated: `backend/tests/test_alerts.py::test_filter_by_status` (the `GET /api/alerts/?status=Unverified` the frontend calls on reconnect exists and is filter-correct). | **pass** (manual + backend half) — see `MANUAL_TESTS.md` §7 Results |

---

## Table 12.4 — Endurance Testing (TC-R-4xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-R-401 | NFR-13 | AI engine / deployment | manual | `be_plan/MANUAL_TESTS.md`'s 24-hour endurance procedure (RAM at start/6h/12h/24h). **Deliberately not executed 2026-08-11** — owner decision when `be_audit/A6_manual_evidence.md` ran: a genuine 24-hour continuous run was weighed against a shortened proxy or an honest non-run, and the owner chose the latter rather than accept a proxy or a session held open for a full day. Still owed; not silently downgraded. | pending — see `MANUAL_TESTS.md` §4-5 Results |
| TC-R-402 | NFR-13 | AI engine / deployment | manual | `be_plan/MANUAL_TESTS.md`'s 24-hour endurance procedure (GPU thermal + VRAM). Same 2026-08-11 owner decision as TC-R-401. | pending — see `MANUAL_TESTS.md` §4-5 Results |

---

## Table 13.1 — End-to-End HITL Workflow (TC-S-1xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-S-101 | FR-06, FR-09, FR-12, D-002 | frontend + backend + AI engine (system-level) | manual (live-drilled) | P4's completion report (00_INDEX.md): dismissed/confirmed incidents live-drilled twice against a real running server with real state changes, durable cooldown confirmed across a real restart. P10's report: a real detection end-to-end (real TensorRT engine, real RTSP, real backend) — camera paused, incident created, confirm/pause verified. No standing full-stack E2E test exists in this repo (`e2e/login.spec.ts` covers login only). | pass (live-drilled) / pending (no standing E2E test) |
| TC-S-102 | FR-06, FR-11, D-002 | frontend + backend + AI engine (system-level) | manual (live-drilled) | Same P4 live-drill session covered the dismiss/cooldown path (dismissed an `Unverified` incident, verified the 60s cooldown survives a real restart both before and after the deadline). | pass (live-drilled) / pending (no standing E2E test) |
| TC-S-103 | NFR-09 | frontend (operator UX) | external | Timing an operator's click-through is a UAT-style measurement, not a unit/integration test. Paper's own "User Acceptance Testing" section is the intended evidence source, not this backend package. | pending |
| TC-S-104 | NFR-11 | frontend | external | Interface: `frontend/public/detection_sound.mp3` (the one alarm asset per `00_INDEX.md`'s "context you won't find in the code"). Prerequisite/acceptance: a listening test in a simulated command-center environment — not automatable. | pending |
| TC-S-105 | NFR-10 | frontend | external | Same UAT category as TC-S-103. | pending |

---

## Table 13.2 — System Security & Route Protection (TC-S-2xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-S-201 | FR-02 | frontend | external | Interface: the `role` claim from `GET /api/users/me`, same as TC-U-103. React router guard not automated in this repo. | pending |
| TC-S-202 | FR-02 | backend (JWT validation) + frontend (route render) | automated (backend half) | Backend: `backend/tests/test_auth.py::TestRBAC::test_admin_can_access_user_management`. Frontend route render: external. | pass (backend) / pending (frontend) |
| TC-S-203 | NFR-19 | backend (session mechanism) | manual | `be_plan/MANUAL_TESTS.md`'s 4-hour idle-session procedure (10_PKG_migration_evidence.md Step 5 names this case explicitly). **Deliberately not executed 2026-08-11** — same owner decision as TC-R-401/402: a genuine 4-hour idle window was weighed against a shortened proxy or an honest non-run, and the owner chose the latter. Supporting automated evidence: `SESSION_LIFETIME_MINUTES` defaults to 480 (8h), so 4h sits inside the window by construction — `backend/tests/test_auth.py::TestSessionAuthority::test_session_expiry_exact_boundary_is_rejected` proves the boundary itself is enforced correctly. | pending (manual procedure deliberately not run) — see `MANUAL_TESTS.md` §6 Results |

---

## Table 13.3 — System Utility, Analytics, & Export (TC-S-3xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-S-301 | FR-14 | backend (filter correctness) + frontend (UI composition) | automated (backend half) | `backend/tests/test_alerts.py::test_combined_filters_narrow_results` | pass (backend) / pending (frontend) |
| TC-S-302 | FR-19 | backend | automated | `backend/tests/test_reports.py::test_camera_id_filter_parity`, `test_user_id_filter_parity` (screen/export parity — D-010's literal requirement); PDF header/metadata format verified in `test_reports.py`. | pass |
| TC-S-303 | FR-20 | backend (role filter) + frontend (rendering) | automated (backend half) | `backend/tests/test_help.py::test_operator_list_excludes_admin_only_articles`, `test_admin_sees_operator_articles_too`. Frontend rendering split: external. | pass (backend) / pending (frontend) |

---

## Table 13.4 — UI Stability (TC-S-4xx)

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-S-401 | NFR-15, D-008 | backend (delivery) + frontend (DOM stacking) | manual + automated (backend half) | `be_plan/MANUAL_TESTS.md`'s 3-simultaneous-camera procedure (Step 5, named explicitly), **executed 2026-08-11** — 3 v2 `POST /api/internal/alert` payloads fired in rapid succession against 3 distinct cameras (`seed_alerts_via_api.py` no longer exists post-F3/F19; used the v2-shaped substitute F19 named), all 3 received, correctly attributed, no drops, no unexpected 409s. Backend half automated: edge case 1.5/1.6 (`ux_detection_open_camera`, idempotent `source_event_id` under genuine concurrency) — covered in `backend/tests/test_internal.py`; P10's live drill also observed two genuinely concurrent detections resolve to exactly one incident via the `409` backstop. | **pass** (manual + backend concurrency half) — see `MANUAL_TESTS.md` §8 Results |
| TC-S-402 | FR-08, D-004 | backend (data isolation) + frontend (state rendering) | automated (backend half) | Snooze fields are scoped to one `DetectionLog` row by schema construction — no cross-incident bleed is structurally possible. `backend/tests/test_snoozes.py` and `test_alerts.py::test_snooze_broadcasts_snooze_activated` cover the backend half. Frontend dual-state rendering: external. | pass (backend) / pending (frontend) |

---

## Table 14.1 — Activity Audit Trail Testing (TC-S-5xx)

All five are backend-owned (D-007) and extensively automated.

| Test case | Requirement | Owner | Evidence type | Evidence | Status |
|---|---|---|---|---|---|
| TC-S-501 | FR-21 | backend | automated | `backend/tests/test_alerts.py`'s per-transition tests (Confirm/Dismiss/Resolve/Correction each write the mapped `ALERT_*` action — `01_CONTRACTS.md` §8) + `backend/tests/test_audit.py::test_viewer_stable_pagination_no_duplicates_or_gaps` for retrieval. | pass |
| TC-S-502 | FR-21 | backend | automated | `backend/tests/test_audit.py::test_camera_rename_and_disable_writes_exactly_two_rows`, `test_disabling_alone_writes_only_camera_disable` | pass |
| TC-S-503 | FR-21 | backend | automated | `backend/tests/test_exports.py::test_no_audit_row_written_until_the_job_actually_completes` (async jobs); `backend/app/services/reports/common.py::record_export_attempt` is called from every sync export route too, exercised throughout `test_alerts.py`/`test_analytics.py`/`test_audit.py`'s export tests. | pass |
| TC-S-504 | FR-21, NFR-19 | backend | automated | `backend/tests/test_auth.py::test_login_success_writes_login_success_row`, `test_failed_logins_write_denied_login_failure_rows` | pass |
| TC-S-505 | FR-21 | backend | automated | `backend/tests/test_audit.py::test_user_update_base_action_plus_role_change` | pass |

---

## Contract amendments the paper needs

Carried forward from `10_PKG_migration_evidence.md` Step 4 (D-012 already
flagged these) — **someone on the writing team edits the paper; this was
not done from a code session**, per this package's hard rules:

1. **TC-I-202** says the AI worker "ceases frame ingestion" on Confirm.
   Locked behavior (D-002, D-003): YOLO inference and event generation
   cease while bounded RTSP draining continues, so resume starts from live
   footage instead of a stale buffer. The acceptance wording must change.
2. **TC-U-205** must acknowledge the AI-generated `source_event_id` in the
   WebSocket payload (D-012) — the current wording lists only `log_id`,
   `camera_id`, `detected_at`, `confidence_score`, `snapshot_path`,
   `detection_status`.
3. The **Data Dictionary** defines five tables and has no home for
   **FR-08 alarm settings** (`alarm_settings`) or the **FR-21 audit trail**
   (`audit_log`). Both now exist as full tables (`01_CONTRACTS.md` §3.5,
   §3.6) — the ERD needs updating.
4. **Use Case 5 step 10** says the status becomes "Closed"; the canonical
   status is `Resolved` (D-002). `Closed` is not a stored value anywhere in
   this schema.
5. **Internal numbering**: the Evaluation Scope cites **NFR-03** for the
   two-second alert target — it is **NFR-04**. It also cites **NFR-06** for
   the fifteen-second detection-to-dispatch target — it is **NFR-09**.

---

## Summary

- **82 / 82** rows have an explicit owner — no blank Owner cells (D-001).
- **Backend-owned, automated, passing**: 38 rows.
- **Backend-owned, measured performance evidence**: 3 rows (TC-R-201/202/203
  — one with a flagged real finding, not silently omitted).
- **Manual procedures** (written in `MANUAL_TESTS.md`, not yet executed
  against real 24h/4h/3AM windows): 8 rows.
- **Frontend-owned, no automated evidence yet** (CLAUDE.md's deliberately
  minimal frontend testing policy): ~20 rows, all with a named interface
  and prerequisite.
- **AI-owner evidence gate, untouched by this package** (D-012, correctly
  out of scope per D-001): 12 `TC-AI-*` rows plus several AI-side pieces of
  `TC-I-1xx`/`TC-R-1xx`/`TC-R-3xx`.

This is not a claim that 82/82 test cases pass — it is a claim that every
one of the 82 has a real, named place evidence for it lives or will live,
with nothing silently dropped because it belongs to someone else.
