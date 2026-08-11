# Demo Seeding & Dev Tools — Execution Index

> **Audience:** an AI coding session (or a teammate) executing one work package at a time.
> **Created:** August 11, 2026. **Baseline:** branch `main`, commit `37bcb2f`.
> **Refreshed:** August 11, 2026 against `52a1f7a`. The original baseline predated the
> detection-core port (PR #76) and the A6 perf work (PR #78); the AI-engine and `perf`-fixture
> facts in Packages A and D were re-checked and corrected against what is actually on `main`.

This directory turns "make the demo convenient" into four executable work packages plus a
kickoff-prompt companion. It is a sibling of `be_plan/` and `be_audit/` and follows their
conventions, but it is **not** backend-only — packages C and D touch `frontend/` and `scripts/`.

---

## Why this exists

Running or demoing this system end-to-end today costs five manual terminals (MediaMTX+ffmpeg,
backend, frontend, AI engine, seed script) and a working GPU. Four specific things make that worse
than it needs to be:

1. **`backend/scripts/reseed_dev.py` deletes the SQLite file.** Switching data profiles means
   stopping the backend, reseeding, restarting, and logging in again. On Windows the delete fails
   outright if the server is up — `reset_db.py` raises `SystemExit` telling you to stop it first.
2. **A seed "profile" is only a list of `SeedAlertSpec`s.** Users, cameras and audit rows are
   hard-coded and identical across all four profiles. `sys_health_raw`, `sys_health_hourly`,
   `export_job`, snoozed detections, `auth_session`, the camera telemetry columns, and 23 of the 26
   entries in `AUDIT_ACTIONS` are never seeded at all. System Health, Exports and the Audit viewer
   have nothing to show in a demo.
3. **No seeded detection has a snapshot file on disk.** `seed_dev_data.py` builds `snapshot_key`
   strings but never writes an image, so `GET /api/alerts/{log_id}/snapshot` 404s for every row in
   the demo dataset.
4. **Nothing can produce a live incident without the full RTSP+GPU stack.** The seeders insert
   `detection_log` rows directly — no WebSocket broadcast, no siren, no self-blindfold camera pause.
   The realtime path, which is the most impressive thing this system does, can only be shown with
   MediaMTX, ffmpeg, the (gitignored) sample clips, and an NVIDIA GPU running `ai_engine/epoch50.pt`.

The end state: one launcher command, a seed corpus that populates every page, and an in-app dev
panel that reseeds, fires synthetic incidents, drives camera state and switches accounts — with the
backend staying up the whole time.

---

## Decisions already locked

Recorded here so no executing session re-litigates them.

| #    | Decision                                                                                     | Rationale                                                                                                                               |
| ---- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| DT-1 | The panel does all four: reseed profiles, inject detection, camera/system state, login-as    | Agreed at planning time                                                                                                                 |
| DT-2 | Reseed is a **full wipe**; the endpoint mints a fresh cookie so the operator stays logged in | Preserving users would make a clean user-management demo impossible; kicking to `/login` adds friction on every profile switch          |
| DT-3 | Gated by a `DEV_TOOLS_ENABLED` setting, not by `ENVIRONMENT` alone                           | The panel must be available on the LAN demo box, which may run a production build. See DT-5 for the security consequence                |
| DT-4 | Launcher is PowerShell with one window per process, not `concurrently` in one terminal       | Four processes of interleaved output is unreadable, and MediaMTX/AI-engine don't fit a `run-p` model                                    |
| DT-5 | Dev routes are admin-gated; `login-as` requires an existing session                          | Because DT-3 lets the flag be on outside development, these routes must not be an auth bypass. `login-as` is a _switcher_, not a way in |
| DT-6 | The drawer is a house-style `ui/SidePanel.tsx`, **not** shadcn                               | The frontend has no Radix/CVA/`components.json`. See `03_PKG_dev_panel.md` §Drawer                                                      |

---

## Package graph and branch strategy

| Package | Doc                                          | Branch                       | Depends on | Scope            |
| ------- | -------------------------------------------- | ---------------------------- | ---------- | ---------------- |
| **A**   | [`01_PKG_seed_core.md`](01_PKG_seed_core.md) | `feat/dev-seeding-and-tools` | —          | backend, no HTTP |
| **B**   | [`02_PKG_dev_api.md`](02_PKG_dev_api.md)     | `feat/dev-seeding-and-tools` | A          | backend          |
| **C**   | [`03_PKG_dev_panel.md`](03_PKG_dev_panel.md) | `feat/dev-seeding-and-tools` | B          | frontend         |
| **D**   | [`04_PKG_launcher.md`](04_PKG_launcher.md)   | `chore/dev-launcher`         | —          | scripts + docs   |

**A → B → C are sequential sessions on one shared branch, one commit each, one PR.** They form a
vertical slice: C cannot be tested without B's endpoints, and B cannot be tested without A's
profile registry. They also share files (`backend/app/dev/`, `backend/app/main.py`), so splitting
them into stacked PRs would create merge pain for no review benefit.

**Do not start a session for B until A is committed, or C until B is committed.**

**D is independent and runs in parallel.** It touches only `scripts/`, the root `package.json`,
`README.md` and `CLAUDE.md` — zero overlap with A/B/C. It can be built and merged at any time, in
any order relative to the others. The one soft coupling is documented in its §Non-goals.

### Status

| Package       | Status      | Commit               |
| ------------- | ----------- | -------------------- |
| A — seed core | Not started | —                    |
| B — dev API   | Not started | —                    |
| C — dev panel | Not started | —                    |
| D — launcher  | Complete    | `chore/dev-launcher` |

An executing session updates its own row before opening the PR.

---

## Global rules for every package here

These are in addition to `CLAUDE.md`, which remains authoritative for conventions.

1. **Run everything from the repo root.** `uv run python`, never bare `python` — PATH python is
   3.14, the project is pinned to 3.12.13, and a bare invocation silently uses the wrong one.
2. **Do not modify `ai_engine/`.** Nothing in this directory needs to. The whole point of Package B's
   detection injector is to exercise the backend's ingest path _without_ the engine.
3. **Schema changes go through a reviewed Alembic migration.** None of these four packages should
   need one — verify that claim before writing a model change, and stop and report if you find you
   do. `SQLModel.metadata.create_all()` against the real file stays reserved for the in-memory
   fixture in `backend/tests/conftest.py`.
4. **Every timestamp is UTC-aware**, stored through `UtcDateTime` (`app/core/types.py`).
   `datetime.now(UTC)`, never `datetime.now()`.
5. **Do not edit the repo-root working docs** (`be_decisions_review.md`, `final_paper_text.txt`,
   etc.) or the real `.env`. `CLAUDE.md` and `README.md` are edited only by Package D.
6. **Ask before adding any dependency** not named in a package doc. Packages A and C are both
   specified to avoid one (no Pillow, no shadcn/Radix) — those are deliberate, not oversights.
7. **Commit per numbered step** with a Conventional Commit message (commitlint runs on
   `commit-msg`).
8. **Verification scope**: run the narrowest suite the package names. `pnpm check` runs
   automatically on push via `.husky/pre-push` — don't run it manually first.

---

## The one thing most likely to be got wrong

`audit_log` carries two BEFORE triggers, `trg_audit_log_no_update` and `trg_audit_log_no_delete`,
attached as raw `DDL` via `event.listen(..., "after_create", ...)` in
`backend/app/models/audit.py`. They make `DELETE FROM audit_log` **raise**.

Package B's wipe has to drop and faithfully restore them. A session that re-types the trigger SQL
instead of re-executing the existing `DDL` objects has created a second source of truth for an
append-only guarantee that NFR-21 depends on. A session that drops them without a `try/finally` can
leave the audit table permanently mutable if the delete fails halfway.

`02_PKG_dev_api.md` §3 specifies exactly how to do this. Read it before touching the wipe.

---

## Companion

[`PROMPTS.md`](PROMPTS.md) — a copy-paste kickoff prompt per package, written so a cold session
needs no other context.
