# Session Kickoff Prompts

Copy-paste one of these into a **fresh session** at the repo root. Each is self-contained — the
session starts cold and needs everything up front.

**Before pasting any of them:** check `00_OVERVIEW.md`'s status table and confirm the prerequisite
package is actually committed.

---

## Order

`A → B → C` are sequential on **one** branch. Do not start B until A is committed, or C until B is
committed — B imports A's module layout, and C codes against B's endpoints.

`D` is independent and can be run at any time, including at the same time as A/B/C, by a different
session.

---

## Package A — Seed core refactor and enriched profiles

```
Execute dev_plan/01_PKG_seed_core.md in this repo.

Read these in full before writing any code, in this order:
  1. dev_plan/00_OVERVIEW.md
  2. dev_plan/01_PKG_seed_core.md
  3. CLAUDE.md
  4. backend/scripts/README.md

Then read the code you are about to move — all of backend/scripts/seed_dev_data.py
(~1180 lines), plus reseed_dev.py, reset_db.py, _bootstrap.py, and
backend/tests/perf/conftest.py.

This is the first package on its branch. Create branch feat/dev-seeding-and-tools
off main.

Work through the seven numbered steps in order, committing after each with a
Conventional Commit message. Steps 2-7 assume Step 1's file moves.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT add any HTTP route, settings flag, or anything under app/api/. That is
  Package B, a separate session.
- Do NOT add an Alembic migration. Every column this package populates already
  exists. If you conclude you need a schema change, STOP and report it.
- Do NOT add a dependency. Step 6 is specified the way it is precisely because
  Pillow is not available in a plain `uv sync` (it is only a transitive of the
  `ai` extra). No image generation.
- Do NOT change perf's 100,000-row behaviour or its statistical distribution.
  backend/tests/perf/ asserts against it.
- Run everything from the repo root. Always `uv run python`, never bare `python`.

The mistake to avoid: Step 1 is a MOVE, not a rewrite. Move the functions verbatim,
change only how they get their engine (Step 2). If you find yourself improving the
seed logic while moving it, you have made the diff unreviewable.

The second mistake: Step 4 unifies two enforcers that currently disagree about
which open incident survives. Check whether that changes the output of the existing
demo/analytics/edge profiles and say so in the commit message.

Done means: the verification block at the bottom of the doc passes, all five
profiles run from the CLI, `uv run pytest -n auto` is green, the status table in
dev_plan/00_OVERVIEW.md is updated, and you have reported the three items under
"Report back".
```

---

## Package B — Dev API and in-process reseed

```
Execute dev_plan/02_PKG_dev_api.md in this repo.

Read these in full before writing any code, in this order:
  1. dev_plan/00_OVERVIEW.md
  2. dev_plan/02_PKG_dev_api.md
  3. dev_plan/01_PKG_seed_core.md  (what Package A built, which you import)
  4. CLAUDE.md  (the audit-transaction rule and the services-layer rule)

Then read: backend/app/models/audit.py, backend/app/api/routes/internal.py,
backend/app/api/routes/auth.py, backend/app/api/dependencies.py,
backend/app/services/sessions.py, backend/app/services/cameras.py,
backend/app/core/config.py, backend/app/main.py, and backend/tests/conftest.py.

PREREQUISITE CHECK: Package A must already be committed. Confirm backend/app/dev/
exists with profiles.py and seed.py, and that `uv run python
backend/scripts/reseed_dev.py --profile empty` works. If it does not, STOP — you
are on the wrong branch or A has not landed.

Stay on branch feat/dev-seeding-and-tools. Do not create a new branch.

Work through the six numbered steps in order, committing after each.

Hard rules:
- Do NOT modify ai_engine/ or frontend/.
- Do NOT add an Alembic migration. Nothing here changes the schema.
- Do NOT add a new EventType. Reuse MAINTENANCE_NOTICE.
- Do NOT write audit rows for dev actions. The doc explains why this is the one
  deliberate exception to CLAUDE.md's audit-transaction rule; put that reasoning
  in the module docstring.
- Run everything from the repo root. Always `uv run python`, never bare `python`.

The mistake that matters most: audit_log has BEFORE UPDATE/DELETE triggers that
make `DELETE FROM audit_log` raise. Step 3 specifies dropping and restoring them by
re-executing the EXISTING DDL objects from app/models/audit.py, inside a
try/finally. Do not re-type the trigger SQL — that creates a second source of truth
for an append-only guarantee NFR-21 depends on. Do not drop them without the
finally — a failed delete would leave the audit table permanently mutable. There is
a required test for exactly this.

The second mistake: Step 2 refactors backend/app/api/routes/internal.py, which is a
recently audited seam (be_audit/A3_ai_seam.md, the F20 fix in commit e7c80ef). It
must be behaviour-preserving — same ordering, same status codes, same error codes.
Run test_internal.py, test_realtime.py and test_websocket.py before moving on. If
the extraction seems to require an ordering change, STOP and report it.

Done means: the verification block passes, `uv run pytest -n auto` is green, the
manual smoke check in the doc works against a running server, the status table in
dev_plan/00_OVERVIEW.md is updated, and you have reported the three items under
"Report back" — Package C needs your exact endpoint shapes.
```

---

## Package C — Frontend dev panel

```
Execute dev_plan/03_PKG_dev_panel.md in this repo.

Read these in full before writing any code, in this order:
  1. dev_plan/00_OVERVIEW.md
  2. dev_plan/03_PKG_dev_panel.md
  3. dev_plan/02_PKG_dev_api.md, section 5  (the endpoint shapes you code against)
  4. CLAUDE.md  (TypeScript conventions and the testing policy)

Then read: frontend/src/App.tsx, main.tsx, components/ui/Modal.tsx,
components/ui/NoticeBanner.tsx, components/GlobalAlerts.tsx,
components/RealtimeAlertsBridge.tsx, store/useAlertStore.ts, store/useAuthStore.ts,
services/api.ts, utils/api.ts, and components/ui/StatCard.test.tsx.

PREREQUISITE CHECK: Package B must already be committed. Start the backend with
DEV_TOOLS_ENABLED on and confirm GET /api/dev/status returns 200. If it 404s, STOP —
B has not landed.

Stay on branch feat/dev-seeding-and-tools. Do not create a new branch.

Work through the six numbered steps in order, committing after each.

Hard rules:
- Do NOT modify backend/ or ai_engine/. If an endpoint is wrong, report it — do not
  patch the backend from this session.
- Do NOT add shadcn/ui, Radix, class-variance-authority, a toast library, or any
  other dependency. This frontend is hand-rolled components + Tailwind v4 +
  @remixicon/react. The doc's Drawer section explains why; this is a decision, not
  an omission.
- Do NOT refactor query keys into a central factory. Tempting, out of scope.
- Gate the panel on the runtime probe of GET /api/dev/status, NOT on
  import.meta.env.DEV. The panel must work in a `pnpm build` bundle.
- Do NOT run `pnpm check` manually. .husky/pre-push runs it on every push.

The mistake that matters most: after a reseed the client holds stale state in three
places — the TanStack Query cache (ad-hoc keys across 8 pages), useAlertStore's
handledIds in sessionStorage (which would silently suppress freshly seeded alerts),
and useAuthStore in localStorage. Step 5 gives the exact reset sequence. Get this
wrong and the panel looks like it works while showing stale data.

The second mistake: Step 1 extracts Modal's overlay effect into a shared hook.
Modal's rendered output and props must not change — it is used by
ConfirmDeleteModal and several pages, and has no test today. Add one.

Done means: `pnpm --filter frontend test:run` passes, the nine manual checks in the
verification block pass — including check 9, that the panel still appears after
`pnpm build && pnpm --filter frontend preview` — the status table in
dev_plan/00_OVERVIEW.md is updated, and you have reported the two items under
"Report back".
```

---

## Package D — Dev launcher scripts

```
Execute dev_plan/04_PKG_launcher.md in this repo.

Read these in full before writing any code, in this order:
  1. dev_plan/00_OVERVIEW.md
  2. dev_plan/04_PKG_launcher.md
  3. scripts/start-sim.ps1  (the shape to follow)
  4. README.md, the "Running the System" section
  5. be_audit/DEMO_TOPOLOGY.md, section 5  (the real demo-day bring-up order)
  6. CLAUDE.md

This package has no prerequisites and runs in parallel with the others. Create
branch chore/dev-launcher off main.

Work through the four numbered steps in order, committing after each.

Hard rules:
- Touch ONLY scripts/, the root package.json, README.md and CLAUDE.md. Nothing
  under backend/, frontend/ or ai_engine/. Another session may be working on those
  branches right now.
- Do NOT add concurrently, Docker, compose, or a Makefile.
- Do NOT hardcode the seed profile list in PowerShell. -Reseed passes its value
  straight through to `reseed_dev.py --profile` and lets Python validate. Package A
  adds an `empty` profile on a different branch; a ValidateSet here would couple
  the two.
- Always `uv run python` in the spawned commands, never bare `python`, and set the
  working directory to the repo root for every process.

The mistake that matters most: killing the `uv run fastapi` wrapper PID does NOT
stop the server on Windows — uv spawns the real Python process as a child and port
8000 stays bound. stop-dev.ps1 must resolve the listening PID by port
(Get-NetTCPConnection, or parse netstat -ano). Verification check 5 exists
specifically to catch this; do not skip it.

The second thing: -Reseed must run BEFORE the backend starts. reseed_dev.py deletes
the SQLite file, which only works while nothing holds it open. If the reseed fails,
start nothing.

Done means: the six manual verification checks pass, README.md and CLAUDE.md are
updated, the status table in dev_plan/00_OVERVIEW.md is updated, and you have
reported the three items under "Report back".
```
