# ADAS Backend Completion — Execution Index

> **Audience:** an AI coding session (or a teammate) executing one work package at a time.
> **Created:** August 9, 2026. **Baseline:** branch `dx/ci-tooling-foundation`, commit `543e7f7`.

This directory turns `be_decisions_review.md` (D-001 … D-012, all Locked) and the paper's
requirements into nine executable work packages plus three companion handoff docs.

---

## Read this before touching any code

### Source-of-truth hierarchy

When two documents disagree, the higher one wins:

1. **`be_decisions_review.md`** (repo root) — the only decision-locking document. D-001…D-012.
2. **`be_plan/01_CONTRACTS.md`** — the frozen technical contract derived from those decisions.
   If you find a contract detail that contradicts a locked decision, **stop and report it**; do not
   silently pick one.
3. **`final_paper_text.txt`** (repo root) — functional/non-functional requirements and the 82 test cases.
4. **`CLAUDE.md`** (repo root) — conventions, commands, gotchas.
5. `be_decisions.md`, `backend_assessment.md`, `be_masterplan_text.txt` — **superseded**. Read for
   background only. Never implement from them.

`ai_engine_detection_pipeline_handoff.md` and `backup_restore_explained.md` are companions to D-012
and D-011 respectively and remain valid as explanatory material.

**None of the repo-root working docs may be edited by an executing agent.** They are the team's notes.

### Non-negotiable global rules

1. **Run everything from the repo root.** `uv run …`, never bare `python` (PATH python is 3.14; the
   project is pinned to 3.12.13).
2. **Do not modify `ai_engine/`** — except in **P10**, which exists specifically to do so. Every
   other package keeps the *existing* internal contract working and adds a v2 alongside it. See
   `12_AI_ENGINE_CONTRACT.md` for the full picture and `15_PKG_ai_engine_integration.md` for the
   scoped subset actually being built.
3. **Do not modify `frontend/`** except where a package doc explicitly says so. Breaking contract
   changes are collected in `11_FRONTEND_MIGRATION.md` for the frontend owner.
4. **No Alembic until P9.** Per D-005 the dev database is disposable while the schema evolves. Break
   the schema freely and reseed: `uv run python backend/scripts/reseed_dev.py`.
5. **Every timestamp stored and returned is UTC-aware.** Use the `UtcDateTime` type from P1. Never
   `datetime.now()` — always `datetime.now(UTC)`.
6. **No network call, file I/O, PDF render, or WebSocket send inside an open DB transaction** (D-005).
   Broadcasts are enqueued *after* commit, always.
7. **Ask before adding a dependency** not listed in this doc set.
8. **Conventional Commits.** commitlint runs on `commit-msg`. Commit per numbered step, not per package.
9. **`pnpm check` must pass before you push.** It runs format check, lint, typecheck, and both test suites.
10. **Testing policy.** `CLAUDE.md` says *test when it's needed, don't overdo it* — that means don't
    write tests for happy-path permutations a single test already proves. It does **not** mean
    skipping boundaries, races, failure paths, and hostile input, which is where production bugs
    live. Each package doc names its core behaviours; [`14_EDGE_CASES.md`](14_EDGE_CASES.md) is the
    cross-cutting register every package is checked against before it is called done. Coverage
    percentage is still not a target.

### Branching

One branch per package, branched from the previous package's merge:

```
feat/be-p1-foundation → feat/be-p2-auth-audit → feat/be-p3-realtime → …
```

P7 (backup) and P8 (help center) only depend on P1+P2 and may branch off P2 directly.

---

## Dependency graph

```
P1 foundation ──┬─> P2 auth+audit ──┬─> P3 realtime ──> P4 incidents+cameras ──┬─> P5 health
                │                   │                                          ├─> P6 reports
                │                   ├─> P7 backup/ops   (parallel-safe)        │
                │                   └─> P8 help center  (parallel-safe)        │
                └───────────────────────────────────────────────────────────────┴─> P9 evidence
```

`12_AI_ENGINE_CONTRACT.md` is handed to the AI owner **immediately**, before P1 starts.
`11_FRONTEND_MIGRATION.md` is handed to the frontend owner **before P2 merges** — P2 is the breaking
auth change.

---

## Work packages

| # | Doc | Covers | Size | Blocked by |
|---|---|---|---|---|
| **P1** | [`02_PKG_foundation.md`](02_PKG_foundation.md) | Config, SQLite policy, UTC type, logging, app factory, scheduler, probes, **full target schema**, test-harness fix, reseed | XL | — |
| **P2** | [`03_PKG_auth_audit.md`](03_PKG_auth_audit.md) | D-006 revocable cookie sessions, Argon2id, rate limiting · D-007 append-only audit | XL | P1 |
| **P3** | [`04_PKG_realtime.md`](04_PKG_realtime.md) | D-008 authenticated WebSocket, versioned envelope, per-client queues | M | P2 |
| **P4** | [`05_PKG_incidents_cameras.md`](05_PKG_incidents_cameras.md) | D-002 atomic lifecycle · D-003 desired/observed camera model + heartbeat · D-004 snooze + alarm settings · snapshot auth | XL | P3 |
| **P5** | [`06_PKG_system_health.md`](06_PKG_system_health.md) | D-009 telemetry collector, raw/hourly history, camera KPIs | L | P4 |
| **P6** | [`07_PKG_reports.md`](07_PKG_reports.md) | D-010 shared filters, streaming CSV, fpdf2 PDF, export jobs, retraining ZIP | L | P4 |
| **P7** | [`08_PKG_backup_ops.md`](08_PKG_backup_ops.md) | D-011 backup, verify, restore, rollback, daily restart, archive | L | P2 |
| **P8** | [`09_PKG_help_center.md`](09_PKG_help_center.md) | FR-20 help articles, role filter, FTS5 search | S | P2 |
| **P9** | [`10_PKG_migration_evidence.md`](10_PKG_migration_evidence.md) | Alembic initial migration, 100k-row perf evidence, 82-test-case traceability, docs, CI | L | all |
| **P10** | [`15_PKG_ai_engine_integration.md`](15_PKG_ai_engine_integration.md) | AI engine → v2 heartbeat, `source_event_id`, durable outbox, `snapshot_key`. **The only package that modifies `ai_engine/`** | L | P4 |

Companions (not work packages):

| Doc | For | When |
|---|---|---|
| [`PROMPTS.md`](PROMPTS.md) | you, starting a session | copy-paste kickoff prompt per package |
| [`01_CONTRACTS.md`](01_CONTRACTS.md) | every executing agent | read first, every package |
| [`14_EDGE_CASES.md`](14_EDGE_CASES.md) | every executing agent | walk your package's rows before calling it done |
| [`11_FRONTEND_MIGRATION.md`](11_FRONTEND_MIGRATION.md) | frontend owner | hand over before P2 merges |
| [`12_AI_ENGINE_CONTRACT.md`](12_AI_ENGINE_CONTRACT.md) | AI engine owner | background — superseded in practice by P10 |
| [`16_HEARTBEAT_VS_POLLING.md`](16_HEARTBEAT_VS_POLLING.md) | AI engine owner | explains what P10 changed and why, with an honest assessment |
| [`17_AI_OWNER_OPEN_ITEMS.md`](17_AI_OWNER_OPEN_ITEMS.md) | AI engine owner | the D-012 evidence gate — threshold, qualification, hardware profile, TC-AI cases |
| [`13_WSL2_LINUX_PATH.md`](13_WSL2_LINUX_PATH.md) | whoever validates Linux deployment | optional, after P7 |

---

## Status

Update this table as packages land. Put the merge commit SHA in the last column.

| Package | Status | Branch | Merged |
|---|---|---|---|
| P1 foundation | ✅ merged — [PR #56](https://github.com/bayie27/adas-capstone/pull/56), [PR #57](https://github.com/bayie27/adas-capstone/pull/57) | `feat/be-p1-foundation` | `88adb5c` |
| P2 auth + audit | ✅ merged — [PR #58](https://github.com/bayie27/adas-capstone/pull/58) | `feat/be-p2-auth-audit` | `5f430a8` |
| P3 realtime | ✅ merged — [PR #60](https://github.com/bayie27/adas-capstone/pull/60) | `feat/be-p3-realtime` | `2c7beb4` |
| P4 incidents + cameras | ✅ merged — [PR #65](https://github.com/bayie27/adas-capstone/pull/65) | `feat/be-p4-incidents-cameras` | `882cfb1` |
| P5 system health | ✅ merged — [PR #68](https://github.com/bayie27/adas-capstone/pull/68) | `feat/be-p5-system-health` | `bf9b26d` |
| P6 reports | ✅ merged — [PR #69](https://github.com/bayie27/adas-capstone/pull/69) | `feat/be-p6-reports` | `4f10a0e` |
| P7 backup + ops | ✅ merged — [PR #61](https://github.com/bayie27/adas-capstone/pull/61), follow-up [PR #62](https://github.com/bayie27/adas-capstone/pull/62) | `feat/be-p7-backup-ops`, `fix/p7-orchestrator-live-drill-fixes` | `5d572ac` |
| P8 help center | ✅ merged — [PR #59](https://github.com/bayie27/adas-capstone/pull/59) | `feat/be-p8-help-center` | `9040ba4` |
| P9 migration + evidence | ☐ not started | | |
| Frontend migration | ✅ merged — [PR #63](https://github.com/bayie27/adas-capstone/pull/63), [PR #66](https://github.com/bayie27/adas-capstone/pull/66) | `feat/fe-cookie-auth`, `feat/fe-authenticated-snapshots` | `48f2d03`, `c1497ec` |
| AI engine cutover (P10) | ✅ merged — [PR #67](https://github.com/bayie27/adas-capstone/pull/67) | `feat/ai-p10-backend-integration` | `20fd987` |

---

## How to execute one package

**Copy-paste kickoff prompts for every package live in [`PROMPTS.md`](PROMPTS.md).** Start a fresh
session, paste the one for your package, and it covers the steps below.

1. Read `01_CONTRACTS.md` in full. It is long; you need all of it.
2. Read the package doc in full before writing anything.
3. Confirm the prerequisite packages are merged (`git log --oneline`).
4. Create the branch. Work through the numbered steps **in order** — later steps assume earlier ones.
5. Commit after each numbered step with a Conventional Commit message.
6. Run the package's own verification block, then `pnpm check`.
7. Update the status table above and note anything you deviated from, and why.

**When to stop and ask the user instead of guessing:**

- A locked decision and the paper conflict, and the contract doc does not resolve it.
- A step requires modifying `ai_engine/` or `frontend/` and the doc did not say to.
- You need a dependency not listed.
- A step turns out to be substantially larger than described.

Report deviations plainly. A package that lands 90% complete with the remaining 10% named is far
more useful than one that silently narrowed its scope.

---

## Context you will want and won't find in the code

- **Deployment is a Windows laptop** (i5-12500H, RTX 3050 Ti 4 GB) for the demo. The paper's target is
  a Linux edge server with 8× L4 GPUs. Everything must run on Windows; Linux artifacts ship as
  reviewed-but-unverified and are labeled production-target. See `13_WSL2_LINUX_PATH.md`.
- **`psutil` cannot read CPU temperature on Windows.** D-009 already requires `null` + an availability
  flag for missing sensors. This is a designed-for gap, not a bug to work around.
- **Only one alarm sound asset exists** (`frontend/public/detection_sound.mp3`), so the D-004 sound
  enum starts as a one-entry config allowlist.
- **Camera simulation:** `mediamtx mediamtx.yml` from the repo root serves
  `rtsp://localhost:8554/channel{1..5}`. `ai_engine/sample_vids/` is gitignored — ask the team for it.
- **The AI engine currently polls `GET /api/internal/cameras` every 3 seconds** and posts a flat
  webhook payload. Both must keep working after every single package. This is verified manually.
