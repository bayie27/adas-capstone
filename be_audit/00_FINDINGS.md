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
| F1 | Test engine never installs the SQLite pragmas, so **`foreign_keys` is OFF for ~500 integration tests** while production runs it ON. An FK violation passes CI and 500s in production. | `backend/tests/conftest.py` | High | open · verified | A2 |
| F2 | `RTSP_URL_TEMPLATE.format(...)` runs on an operator-editable env value with **no startup validation**. One typo'd placeholder → `KeyError` → 500 on **every heartbeat, every 3s** → the engine loses its control channel and every camera goes Unresponsive. Fails at runtime, not at boot. | `backend/app/api/routes/internal.py:59` | High | open · verified | A2 |
| F3 | Two clientless v1 routes survive PR #67. `PATCH /api/internal/cameras/{id}/status` writes AI-owned observed columns **directly, bypassing `apply_observed()`** — no fps sanity check, no `error_message` redaction, no `last_heartbeat_at` stamp. A second writer of observed state, contradicting D-003's single-writer rule. | `backend/app/api/routes/internal.py:249`, `:273` | High | open · verified · **owner decision: delete both** | A3 |
| F4 | `SESSION_COOKIE_SECURE=true` over plain `http://<lan-ip>` — browsers exempt `localhost`, **not** a LAN IP. The cookie is silently dropped; login "succeeds" and every later request is 401. Guaranteed second-laptop failure. The paper also promises HTTPS, which nothing implements. | `backend/app/core/config.py`, `core/security.py::set_session_cookie` | High | **fixed** — real self-signed TLS (`certs/adas-cert.pem`, SAN `adas.local`/`localhost`/`127.0.0.1`/`192.168.50.1`), backend on `https://` via uvicorn `--ssl-keyfile/--ssl-certfile`, frontend opt-in TLS via `ADAS_TLS_CERT_DIR`. Live-verified 2026-08-10: `Set-Cookie` carried `Secure; HttpOnly; SameSite=strict`, follow-up `GET /api/users/me` → 200 | A1 |
| F5 | `CORSMiddleware` sets no `expose_headers`, so browser JS **cannot read `Content-Disposition`** cross-origin. `frontend/src/utils/download.ts:24` reads exactly that to name every CSV/PDF download → every export silently lands under the fallback filename. Invisible to `TestClient` and to the frontend unit tests. | `backend/app/main.py:475` | Med-High | open · **confirmed** 2026-08-10 — real cross-origin request (`Origin: https://localhost:5173` → `https://localhost:8000/api/alerts/export`) returned `content-disposition` on the wire but no `access-control-expose-headers`, which is what actually gates JS visibility regardless of browser. Fix still owned by A2 | A1 → A2 |
| F6 | `04_PKG_realtime.md` Step 5 specifies WebSocket ping/pong and the application never implements one. **Downgraded on 2026-08-10:** `websockets 16.0` is installed and `wsproto` is not, so uvicorn runs its websockets impl with `ping_interval=20s` / `ping_timeout=20s` by default — RFC 6455 keepalive *is* active and a half-open socket *is* reaped. Remaining work is to confirm the setting survives the real launch command and to document it, **not** to build a redundant app-level ping. | `backend/app/main.py:352`, `services/realtime.py` | ~~Med-High~~ **Low** | open · verified | A4 |
| F7 | Export workers start **inside** `if SCHEDULER_ENABLED:`. With the scheduler off, `POST /api/exports/jobs` still returns 202 and the job queues forever. Silent, no error. | `backend/app/main.py:200-202` | Med | open · verified | A2 |
| F8 | `add_exception_handler(Exception, …)` is served by Starlette's `ServerErrorMiddleware`, **outside** the user middleware stack — so on a 500 the `request_id_ctx` is already reset and no `X-Request-ID` header is attached. The one error class that most needs correlation is the one that loses it. `test_logging.py` covers 200s and 404s only. | `backend/app/main.py:336`, `:242` | Med | open · **confirmed** 2026-08-10 — forced a real unhandled exception via a temporary debug route (added, tested, removed same session; `git diff` clean after). The `500` carried no `X-Request-ID`; server log read `[request_id=-]`. Fix still owned by A4 | A1 → A4 |
| F9 | Heartbeat input hardening gaps: `engine_id` has no `max_length` and no null-byte validator (inconsistent with `error_code`/`error_message` beside it) and **is accepted and never used**; `cameras` is an unbounded list; `sent_at` is parsed and discarded (no clock-skew detection). Edge case 1.18 (two engine instances) degrades quietly rather than being noticed. | `backend/app/schemas/internal.py:33` | Med | open · verified | A3 |
| F10 | `services/reports/jobs.py` imports row-shaping helpers **from `app/api/routes/*` at call time** — services depending on routes, inverting the layering `CLAUDE.md` states. Deliberate (byte-identical output) but the correct fix is a shared module both sides import. | `backend/app/services/reports/jobs.py` | Med | open · verified | A8 |
| F11 | Of the edge cases `14_EDGE_CASES.md` flags in bold as "Not covered": **1.7** (AI event arriving while an operator disables that camera) and **1.14** (export artifact cleanup firing during a streaming download) are genuinely open. **1.12** (restore while a backup runs) is already handled — `routes/maintenance.py:237` takes the same shared `maintenance_lock` — and needs only a cross-operation test. Rows 5.5, 6.2, 6.10 and 8.1 have since been covered. | `be_plan/14_EDGE_CASES.md` | Med | open · verified | A5 |
| F12 | P9's edge-case sweep found "**~28 partially- or un-covered rows out of ~150**" — that list lives only in a PR/session report, **not in the repo**, and is unrecoverable context about known gaps. `14_EDGE_CASES.md` has no status column, which is why it went missing. | `be_plan/00_INDEX.md` P9 row | Med | open · verified | A5 |
| F13 | `MANUAL_TESTS.md`'s nine procedures are **written but none executed** — item 6 of P9's own nine-box definition of done. For deployment-first, the NFR-18 60-second restore drill and the NFR-13 / TC-R-401/402 endurance run matter most. | `be_plan/MANUAL_TESTS.md` | Med | open · verified | A6 |
| F14 | ~20 paper-vs-implementation divergences **not on the 5-item amendment list**: HTTPS promised and unplanned; **NFR-22 and NFR-12 appear nowhere in `be_plan`**; the Data Dictionary says bcrypt (P2 removed it for Argon2id) and `gputil` (P5 removed it); the paper specifies the `sqlite3 .backup` **CLI** where P7 uses the Python API; restore documented as systemd-only; `snapshot_path` → `snapshot_key`; FR-15 says "Connecting" where everything else says "Reconnecting"; **UC-4 requires a synchronous RTSP handshake on camera create, which P4 deliberately inverted**; `auth_session` / `export_job` / `help_article` missing from the ERD. | `final_paper_text.txt` vs `be_plan/` | Med | open · verified | A7 |
| F15 | `00_INDEX.md` still shows P9 as "🔶 implemented, not pushed/PR'd" — it merged as PR #70 (`336a967`). Its nine-box definition of done is **all unchecked** though 7–8 are now satisfied. `CONTRIBUTING.md` claims startup "hard-fails if any of the 10 keys are missing"; only **3** are required. `final_paper_text.txt` is untracked despite being a declared source of truth. | `be_plan/00_INDEX.md`, `CONTRIBUTING.md` | Low-Med | open · verified | A7 |
| F16 | Housekeeping: stray 0-byte `backend/adas.db`; orphan bytecode `app/__pycache__/{models,ws_manager}.cpython-312.pyc` for modules deleted in P1/P3; `GET /api/events/schema` is fully unauthenticated (leaks the internal event contract); WS `receive_text()` on a binary client frame raises into the generic handler and logs as an unexpected error. | various | Low | open · verified | A8 |
| F17 | **The live database sits inside a cloud-sync folder.** The repo root is `C:\Users\Dani\OneDrive - dlsl.edu.ph\…`, so `adas.db` and its `-wal`/`-shm` sidecars, plus `ai_engine/snapshots/`, `var/backups/` and `var/exports/`, are all continuously synced by OneDrive. SQLite in WAL mode under a sync client that opens, locks and uploads those files is a known-bad combination — file-locking errors, sync-conflict copies of the database, partially uploaded snapshots. It also silently undermines D-011's backup integrity story. Immediate mitigation is to pause OneDrive for any demo or drill; the real fix is to relocate the runtime data directories outside the synced tree. | repo root layout; `core/config.py` path validators | Med-High | open · verified | A1 (mitigate) → owner decision (fix) |

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
