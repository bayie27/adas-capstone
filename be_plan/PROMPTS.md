# Session Kickoff Prompts

Copy-paste one of these into a **fresh session** at the repo root. Each is self-contained — the
session starts cold and needs everything up front.

**Before pasting any of them:** check `00_INDEX.md`'s status table and confirm the prerequisite
packages are actually merged.

---

## How these are built

Every prompt has the same six parts. If you write your own, keep them:

1. **Which doc to execute**, and the docs to read first.
2. **Prerequisite check** — so the session fails loudly instead of building on missing foundations.
3. **The branch to create.**
4. **The rules that are easy to violate** — don't touch `ai_engine/` or `frontend/`, `uv run` not
   bare `python`, commit per step, ask before adding a dependency.
5. **The one or two mistakes reviewers actually make** in that package.
6. **What "done" means** — the doc's verification block, the edge-case walk, `pnpm check`, status
   table updated, deviations reported.

---

## P1 — Foundation and schema

```
Execute be_plan/02_PKG_foundation.md in this repo.

Read these in full before writing any code, in this order:
  1. be_plan/01_CONTRACTS.md  (long — read all of it, it is the frozen spec)
  2. be_plan/02_PKG_foundation.md
  3. be_plan/14_EDGE_CASES.md
  4. be_decisions_review.md, decision D-005

This is the first package, so there are no prerequisites. Create branch
feat/be-p1-foundation off the current branch.

Work through the ten numbered steps in order. Commit after each step with a
Conventional Commit message. Later steps assume earlier ones.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs (be_decisions_review.md, final_paper_text.txt,
  backend_assessment.md, etc.) or the real .env.
- Do NOT add Alembic or any migration. That is P9. The dev DB is disposable — break it
  and reseed with: uv run python backend/scripts/reseed_dev.py
- routes/system.py holds the health probes and NOTHING else. P5 and P7 add their own
  route modules; keeping them separate is what lets those packages run in parallel.
- Run everything from the repo root. Always `uv run python`, never bare `python`.
- Ask me before adding any dependency not named in the doc.

This package is XL. If you want to plan your approach before executing, do that first.

Step 6 is the acceptance-critical one: it fixes a live bug where `uv run pytest`
mutates the developer's real adas.db. Do not skip its verification — delete adas.db,
run pytest, and confirm the file is NOT recreated.

When done: run the doc's Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P1 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report anything you
deviated from and why, and name any edge-case row you deliberately skipped. If a step
turns out to be much larger than described, or a locked decision conflicts with
01_CONTRACTS.md, stop and tell me instead of guessing.
```

---

## P2 — Auth, sessions, RBAC, audit

```
Execute be_plan/03_PKG_auth_audit.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md
  2. be_plan/03_PKG_auth_audit.md
  3. be_plan/14_EDGE_CASES.md  (sections 8 and 1 especially)
  4. be_decisions_review.md, decisions D-006 and D-007

Prerequisite: P1 must be merged. Verify with `git log --oneline` before starting —
if you cannot find the P1 work, stop and tell me.

Create branch feat/be-p2-auth-audit.

Work through the eleven numbered steps in order, committing after each one.

Hard rules:
- Do NOT modify ai_engine/ or frontend/. This package intentionally breaks the
  frontend; the migration guide is be_plan/11_FRONTEND_MIGRATION.md and is a
  teammate's job, not yours.
- Do NOT edit the repo-root working docs or the real .env.
- No Alembic. Reseed instead: uv run python backend/scripts/reseed_dev.py
- Run from the repo root. Always `uv run python`.
- Ask before adding a dependency not named in the doc.

This package is XL. Plan first if that helps.

Three things reviewers get wrong here:
1. Audit transaction coupling — a successful action and its audit row must commit
   together, and a denied/failed attempt must be written in a SEPARATE transaction
   after rollback.
2. Over-revoking sessions — a profile/username change must NOT revoke, because
   identity is user_id, not username.
3. JWT verification that writes iss/aud claims but never passes issuer= and audience=
   to jwt.decode, so they are never actually checked. Same for algorithms= — an
   alg:none token must be rejected.

/api/internal/* must keep working throughout — it authenticates with x-api-key and
is unaffected by the cookie change. Verify it with the real AI engine running.

When done: run the doc's Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P2 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any edge-case row you skipped. Stop and ask rather than guess if something
conflicts.
```

---

## P3 — Realtime WebSocket

```
Execute be_plan/04_PKG_realtime.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§9 especially)
  2. be_plan/04_PKG_realtime.md
  3. be_plan/14_EDGE_CASES.md
  4. be_decisions_review.md, decision D-008

Prerequisite: P2 must be merged (this needs auth_session and the revocation service).
Verify with `git log --oneline` first.

Create branch feat/be-p3-realtime.

Work through the seven numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- Run from the repo root. Always `uv run python`.
- Ask before adding a dependency.

The existing backend/tests/test_websocket.py will fail because it connects with no
credentials. Update it to log in first and reuse the cookie jar, but KEEP every
existing assertion about payload content and broadcast ordering — only the handshake
changes.

The acceptance criterion for this package is slow-client isolation: with one client
that has stopped reading, a healthy client must still receive an alert within two
seconds. `broadcast()` must be synchronous and non-blocking — if you find yourself
awaiting a network send inside it, you have reintroduced the bug this package exists
to remove.

When done: run the doc's Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P3 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any edge-case row you skipped.
```

---

## P4 — Incidents, cameras, snooze

```
Execute be_plan/05_PKG_incidents_cameras.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§§5.3, 6, 7, 10, 11 especially)
  2. be_plan/05_PKG_incidents_cameras.md
  3. be_plan/14_EDGE_CASES.md  (sections 1, 5, 7, 9, 10 especially)
  4. be_decisions_review.md, decisions D-002, D-003, D-004, D-012

Prerequisite: P3 must be merged. Verify with `git log --oneline` first.

Create branch feat/be-p4-incidents-cameras.

Work through the eleven numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/. The v2 contract is written down in
  be_plan/12_AI_ENGINE_CONTRACT.md for its owner. The LEGACY contract
  (GET /api/internal/cameras, the flat webhook payload) must keep working — verify
  it with the real AI engine running before you call this done.
- Do NOT modify frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- No Alembic. Reseed instead.
- Run from the repo root. Always `uv run python`.
- Ask before adding a dependency.

This is the largest package in the set. Expect to split it across sessions — the
steps are ordered so you can stop cleanly after any of them. Plan first.

Three things that are easy to get wrong:
1. Transitions must be conditional UPDATEs checked by rowcount, never read-then-write.
2. Snooze expiry: ONLY the process whose UPDATE actually affected a row may broadcast
   RE_ALARM. A duplicate or obsolete job updates zero rows and stays silent.
3. Legacy `detected_at` is naive LOCAL time from the AI engine — interpret it as
   server-local and convert to UTC. Treating it as UTC shifts every legacy detection
   by eight hours.

Section 7 of 14_EDGE_CASES.md is a 4x4 transition matrix. Parametrize all twelve
illegal transitions including self-transitions, not just the four legal ones.

Verification item 4 is mandatory and is the reason this package exists: dismiss an
Unverified incident, kill the backend within 60 seconds, restart it, and confirm the
camera still returns to Active at the original deadline.

When done: run the doc's full Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P4 — there are many — and add tests for any not
already covered, then `pnpm check`, then update the status table in
be_plan/00_INDEX.md. Report deviations and any edge-case row you skipped.
```

---

## P5 — System health

```
Execute be_plan/06_PKG_system_health.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§3.7 especially)
  2. be_plan/06_PKG_system_health.md
  3. be_plan/14_EDGE_CASES.md  (sections 3 and 6 especially)
  4. be_decisions_review.md, decision D-009

Prerequisite: P4 must be merged (this needs heartbeat FPS/latency data).
Verify with `git log --oneline` first.

Create branch feat/be-p5-system-health.

Work through Step 0 then the five numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- Your route module is backend/app/api/routes/system_health.py — a NEW file. Do NOT
  add endpoints to routes/system.py; that holds the P1 probes only, and P7 is adding
  routes/maintenance.py in parallel. The URL prefix is still /api/system/...
- Run from the repo root. Always `uv run python`.
- Step 0 swaps gputil for nvidia-ml-py — that swap is approved. Ask before adding
  anything else.

Note: CLAUDE.md says backend/app/core/monitor.py is an intentional 0-byte placeholder
that must not be "fixed". This package is the explicit instruction to implement it.
P9 updates that CLAUDE.md note — leave it alone for now.

Three things reviewers get wrong:
1. Missing sensors must be null with an availability flag, never zero. psutil cannot
   read CPU temperature on Windows at all, and that is expected, not a bug to work
   around.
2. Aggregate GPU MEMORY is the MAX device percentage, not the mean, because a mean
   hides one nearly exhausted GPU. GPU utilization is the mean and GPU temperature is
   the max. These three differ deliberately.
3. An unhandled exception inside a scheduler job must be logged and the job must stay
   scheduled. One bad run must not silently kill telemetry for the rest of the process
   lifetime.

When done: run the doc's Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P5 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any edge-case row you skipped.
```

---

## P6 — Reports and exports

```
Execute be_plan/07_PKG_reports.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§§1.4, 1.5, 3.8, 5.10 especially)
  2. be_plan/07_PKG_reports.md
  3. be_plan/14_EDGE_CASES.md  (sections 3 and 4 especially)
  4. be_decisions_review.md, decision D-010

Prerequisite: P4 must be merged (final filter and response shapes).
Verify with `git log --oneline` first.

Create branch feat/be-p6-reports.

Work through the seven numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- Run from the repo root. Always `uv run python`.
- fpdf2 and pypdf are approved by the doc. Ask before adding anything else — in
  particular do NOT add Celery, Redis, or any broker; D-010 rejects them explicitly.

Step 1 first, always: there are currently TWO copies of _validate_common_filters, in
alerts.py and analytics.py, with DIFFERENT signatures. Unifying them is what makes the
rest of the package correct.

Two subtle ones:
1. The audit recursion trap — an audit export must be selected from a dataset snapshot
   taken BEFORE its own AUDIT_EXPORT row is committed, or the export contains the
   record of itself.
2. fpdf2's default font is Latin-1 only. Camera names and operator names can contain
   Unicode. Verify a Unicode-capable font is configured EARLY, not after you have
   built four report layouts on top of a broken assumption.

When done: run the doc's Verification section — including the spreadsheet-formula
injection check with a camera named =cmd|'/c calc'!A1 — then walk every row in
be_plan/14_EDGE_CASES.md tagged P6 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any edge-case row you skipped.
```

---

## P7 — Backup, restore, ops

```
Execute be_plan/08_PKG_backup_ops.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§3.10 especially)
  2. be_plan/08_PKG_backup_ops.md
  3. be_plan/14_EDGE_CASES.md  (sections 1 and 6 especially)
  4. be_decisions_review.md, decision D-011
  5. backup_restore_explained.md  (the approved plain-language companion — it explains
     WHY restore must happen offline; read it, do not skip it)

Prerequisite: P2 must be merged. P4/P5/P6 are NOT required — this package is
parallel-safe. Verify P2 with `git log --oneline` first.

Create branch feat/be-p7-backup-ops off the P2 merge.

Work through the eight numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- Your route module is backend/app/api/routes/maintenance.py — a NEW file. Do NOT add
  endpoints to routes/system.py; that holds the P1 probes only, and P5 is adding
  routes/system_health.py in parallel. The URL prefix is still /api/system/...
- Run from the repo root. Always `uv run python`.
- Ask before adding a dependency.
- Deployment is a WINDOWS laptop. Everything must work there. Linux systemd units
  ship as reviewed-but-unverified, labeled production-target.

The architectural constraint that drives everything: a running FastAPI process cannot
replace its own WAL-mode database. Backup is ONLINE via sqlite3.Connection.backup();
restore is OFFLINE via an external orchestrator. FastAPI only writes a flag file — it
never replaces the DB and never gets shell execution.

The detail most likely to be implemented wrong: restore state is a FILE
(BACKUP_DIR/restore_state.json), not a table. A restore replaces adas.db, so anything
recorded in the database about the restore is destroyed by the restore itself.

When done: run the doc's Verification section — including the full restore drill AND
the rollback drill, both timed — then walk every row in be_plan/14_EDGE_CASES.md
tagged P7 and add tests for any not already covered, then `pnpm check`, then update
the status table in be_plan/00_INDEX.md. Record the measured timings; they are paper
evidence. Report deviations and any edge-case row you skipped.
```

---

## P8 — Help Center

```
Execute be_plan/09_PKG_help_center.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§§3.9, 5.11 especially)
  2. be_plan/09_PKG_help_center.md
  3. be_plan/14_EDGE_CASES.md

Prerequisite: P2 must be merged. Nothing else is required — this package is
parallel-safe. Verify with `git log --oneline` first.

Create branch feat/be-p8-help-center off the P2 merge.

Work through the four numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit the repo-root working docs or the real .env.
- Run from the repo root. Always `uv run python`.
- Ask before adding a dependency (the frontmatter parser is a judgement call the doc
  flags — tell me which way you went).

This is the smallest package. The content itself matters as much as the code: write
the starter articles to describe the behavior the backend ACTUALLY has. An article
describing a workflow that does not exist is worse than no article. Cross-check
against the implemented routes as you write.

FR-20 appears in none of the locked decisions D-001…D-012 — it was resolved
separately in favor of this backend module so FR-20 has real test evidence.

When done: run the doc's Verification section, then walk every row in
be_plan/14_EDGE_CASES.md tagged P8 and add tests for any not already covered, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any edge-case row you skipped.
```

---

## P9 — Migrations, evidence, traceability

```
Execute be_plan/10_PKG_migration_evidence.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§12 especially)
  2. be_plan/10_PKG_migration_evidence.md
  3. be_plan/14_EDGE_CASES.md
  4. be_decisions_review.md, decisions D-001 (the boundary rule) and D-005
  5. final_paper_text.txt — you need the complete list of 82 test cases from it

Prerequisite: ALL other packages (P1–P8) must be merged. Verify with
`git log --oneline` and the status table in be_plan/00_INDEX.md before starting.
If any package is missing, stop and tell me which.

Create branch feat/be-p9-migration-evidence.

Work through the seven numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT edit final_paper_text.txt or any repo-root working doc. Step 4 produces a
  LIST of amendments the paper needs; the writing team makes the edits, not you.
- Run from the repo root. Always `uv run python`.
- alembic is approved. Ask before adding anything else.

Step 1 warning: do NOT trust `alembic revision --autogenerate`. It reliably misses
partial indexes (WHERE is_active = 1), expression indexes (lower(camera_name)), CHECK
constraints, the audit_log immutability triggers, and the FTS5 virtual table plus its
sync triggers. Every one of those needs a hand-written op.execute(). Review the
generated file line by line against 01_CONTRACTS.md §3.

Step 4 is the defense evidence. Per D-001's boundary rule, a test case owned by
someone else (AI model accuracy, physical VLAN/NAS, frontend UI) may NOT be left
blank — it needs an explicit owner, interface, prerequisite, and acceptance evidence.
No row in TRACEABILITY.md may have an empty Owner cell.

Also do a final sweep of be_plan/14_EDGE_CASES.md across ALL packages and report which
rows ended up with no test anywhere. That list is a real finding, not a formality —
include it in your report even if it is long.

Record real measured numbers in EVIDENCE.md with the machine spec and date, and label
every one as demo-validated on the laptop, not production hardware.

Also update the CLAUDE.md testing-policy bullet: "test when it's needed, don't overdo
it" stays, but add that edge cases at boundaries, races, and failure paths are in
scope even beyond the paper's 82 test cases.

When done: run the doc's Verification section, then `pnpm full:check`, then walk the
"Definition of done for the whole effort" checklist at the end of the doc and report
which items are met and which are not.
```

---

## P10 — AI engine backend integration

```
Execute be_plan/15_PKG_ai_engine_integration.md in this repo.

Read in full first, in this order:
  1. be_plan/01_CONTRACTS.md  (§§6 and 7 especially — the v2 contract)
  2. be_plan/15_PKG_ai_engine_integration.md
  3. be_plan/12_AI_ENGINE_CONTRACT.md  (background: the full D-012 picture)
  4. be_plan/14_EDGE_CASES.md
  5. be_decisions_review.md, decisions D-003 and D-012

Prerequisite: P4 must be present — the v2 endpoints POST /api/internal/heartbeat and
the DetectionLogCreateV2 payload. Verify by checking that
backend/app/api/routes/internal.py has a receive_heartbeat function and that
backend/app/schemas/internal.py exists. If either is missing, stop and tell me.

Create branch feat/ai-p10-backend-integration.

Work through the eight numbered steps in order, committing after each.

THIS IS THE ONE PACKAGE THAT MODIFIES ai_engine/. Every other package doc forbids it;
that prohibition is lifted here and only here.

Hard rules:
- Do NOT modify backend/ or frontend/. If you believe the backend is wrong, stop and
  tell me — do not adapt the engine around a backend bug.
- Do NOT touch the AI-owner parameters: CONFIDENCE_THRESHOLD stays 0.90, no temporal
  qualification, no FPS capping, no change to ACCIDENT_CLASS_ID, model artifact,
  imgsz, batch size, or device=0. D-012 reserves those pending measured evidence.
  Measuring FPS is in scope; throttling it is not.
- Do NOT delete the backend's v1 legacy endpoints. They are the rollback path.
- Run from the repo root. Always `uv run python`.
- Ask before adding any dependency, including a test dependency.

THE CONSTRAINT THAT SHAPES THE WHOLE DESIGN: CI runs plain `uv sync`, and cv2 /
torch / ultralytics live in the `ai` optional extra. Any test importing camera.py or
main.py will pass locally and FAIL in CI. All new logic therefore goes in modules
importing neither cv2 nor ultralytics — events.py, outbox.py, backend_client.py — and
only those get tests. Guard anything that genuinely needs cv2 with
pytest.importorskip("cv2"). Read the "testability constraint" section before writing
any code; getting this wrong means restructuring later.

Three things that are easy to get wrong:
1. The v2 heartbeat returns ALL is_active cameras INCLUDING disabled ones
   (is_enabled: false), unlike the v1 poll which pre-filtered to enabled-only. The
   engine must filter, or it will start a stream for every disabled camera.
2. DetectionLogCreateV2 is extra="forbid". One misspelled or extra field makes the
   whole payload fall back to the v1 model and then fail validation with a confusing
   error. Exactly five keys.
3. detected_at must carry a UTC offset. The backend runs v2 payloads through
   parse_utc_query_datetime, which treats a naive value as UTC — so naive local time
   silently shifts every incident by eight hours in Philippine time.

Verification item 6 is the one that matters most and cannot be faked: stop the
backend, trigger a real detection, confirm the JPEG is written and the event is
sitting in OUTBOX_DIR with the camera still paused, restart the backend, confirm
exactly ONE incident is created. Then repeat with the engine restarted while the
backend is down. The full drill needs mediamtx, a real GPU, and `uv sync --extra ai`.

When done: run the doc's Verification section, then walk be_plan/14_EDGE_CASES.md
sections 1, 4, 5 and 10 for anything that now applies to the engine side, then
`pnpm check`, then update the status table in be_plan/00_INDEX.md. Report deviations
and any verification step you could not run (e.g. no GPU available) — say so
explicitly rather than marking it passed.
```

---

## Extra — Frontend migration (for a frontend session, or for Seb)

```
Execute be_plan/11_FRONTEND_MIGRATION.md in this repo.

Read be_plan/11_FRONTEND_MIGRATION.md in full first. Read be_plan/01_CONTRACTS.md
sections 5 and 9 for the exact response and event shapes.

Prerequisite: backend package P2 must be merged — the backend now sets an HttpOnly
session cookie and no longer returns a token from POST /api/auth/login. Verify with
`git log --oneline` first.

Create branch feat/fe-cookie-auth.

Do "Breaking change 1" only for now (the five auth files). Breaking changes 2 and 3
depend on backend P3 and P4 and should wait until those land.

Hard rules:
- Do NOT modify backend/ or ai_engine/.
- Keep the existing 401 -> clearSession -> redirect flow and the sessionStorage
  "auth-message" expiry banner. Those still work and are still correct — only the
  JWT-decode expiry check in useAuthStore goes away.
- Keep the ApiUserRole ("Admin") -> AppUserRole ("Administrator") mapping unchanged.
- Prettier here is semi: false. Do not let your editor add semicolons.

Verify: `pnpm --filter frontend typecheck`, `pnpm --filter frontend test:run`, then
log in through the real backend in a browser and confirm the session cookie is set,
/api/users/me works with no Authorization header, and the WebSocket connects (it
should need no change — the browser attaches the cookie to the handshake
automatically). Then `pnpm check`.
```

---

## Extra — WSL2 Linux verification lane (optional)

```
Execute be_plan/13_WSL2_LINUX_PATH.md in this repo.

Read be_plan/13_WSL2_LINUX_PATH.md in full first, then be_plan/08_PKG_backup_ops.md
for the maintenance commands and systemd units you will be exercising.

Prerequisite: backend package P7 must be merged.

This is a VERIFICATION exercise, not a feature. Scope is backend + SQLite only — no
AI engine, no GPU, no RTSP. Do not attempt WSL2 GPU passthrough.

Do not change application logic to make Linux work. If something genuinely fails on
Linux, that is a finding — report it to me, and we decide whether to fix the shared
Python core (correct) or add a platform branch (usually wrong).

Run the five drills in the doc's table and record every timing. Write results into
be_plan/EVIDENCE.md labeled "WSL2 Ubuntu 24.04, not production hardware", alongside
whatever Windows numbers are already there.
```

---

## Optional add-on — fresh-context review for the XL packages

P1, P2, and P4 are large enough that the session which wrote them is a poor judge of
whether they match the spec. If you want a second pass, append this to those three prompts:

```
Before you report done, spawn ONE fresh subagent to review your diff against
be_plan/01_CONTRACTS.md and this package doc. Give it the branch name and the doc
paths, nothing else — it must form its own view from the spec, not from your summary.
Ask it specifically: which numbered steps are incompletely implemented, and where does
the code diverge from the contract? Relay its findings to me verbatim, including ones
you disagree with.
```

This costs a chunk of tokens. It is worth it on the XL packages and wasteful on the rest.
