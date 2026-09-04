# P29 — Make AI Performance Administrator-only

> **Branch:** `feat/be-p29-admin-ai-performance`  
> **Runs where:** worktree-safe.  
> **Size:** M.  
> **Integration:** implementation may start beside P28, but final rebase/verification is against P28.

## Goal and access boundary

AI Performance becomes Administrator-only end to end. Operators retain Dashboard KPIs, Detections,
System Health, incident/dashboard exports, Profile, and Help. Security is enforced from the database
role on the backend; hiding a route or sidebar link is not authorization.

The Administrator sidebar group order is exactly: Users, Audit Log, Maintenance, AI Performance.
Monitoring retains only System Health. `/admin/ai` remains; `/user/ai` redirects to `/user`.

## Step 0 — rebase and inventory

Read `CLAUDE.md`, `be_plan/01_CONTRACTS.md` §§5 and 8, this package, and authentication edge cases in
`14_EDGE_CASES.md`. Inventory synchronous performance routes, async export job create/list/detail/
download, frontend routes/sidebar, help frontmatter and shared links, UAT profiles, and tests.

P29 can implement isolated files in parallel, but before completion it must rebase onto the completed
P28 branch/main, replace Cleared terminology correctly, resolve shared analytics/help/test changes,
and rerun every verification command. Do not claim done on the pre-P28 base.

## Step 1 — backend authorization

- Require `get_current_admin` for `GET /api/analytics/performance` and
  `GET /api/analytics/export/performance`.
- Reject Operator `POST /api/exports/jobs` when `report_type='performance'`.
- Prevent Operators from listing, polling, or downloading performance jobs, including legacy jobs
  they created before this change. Admins retain owner-or-admin access.
- Preserve Operator access to dashboard and incident exports.
- Keep routine view denials unaudited; existing report export audit behavior remains.

Use consistent `403 FORBIDDEN` responses and validate authorization before expensive payload/query
work. No migration and no new audit action.

## Step 2 — frontend and help

Move AI Performance into the Admin-only Administration link array after Maintenance. Remove it from
Monitoring. Keep `/admin/ai`; add deterministic `/user/ai` redirect to `/user`. Do not depend on the
client role for security.

Change the dedicated AI Performance and precision FAQ articles to Admin-only. Rewrite shared articles
that currently promise or link Operators to the page so an Operator never receives a dead link.
Correct UAT/dev descriptions that currently assign performance exports to Operators.

## Step 3 — verification

```powershell
uv run pytest backend/tests/test_auth.py backend/tests/test_analytics.py backend/tests/test_exports.py backend/tests/test_help.py
pnpm --filter frontend test:run
pnpm full:check
```

Do not run `pnpm check` manually. Cover Admin success and Operator denial for sync endpoints, async
create/list/detail/download including a seeded legacy Operator-owned job, Admin sidebar ordering,
Operator direct-route redirect, help list/search/detail, and unchanged Operator dashboard/incident
exports.

## Step 4 — paper sync and test tracker

Run `adas-paper-sync` against the live paper, audit Doc, and audit tracker. Create a new Admin-only AI
Performance finding for FR-02, UC-7, actor/DFD/UAT claims; coordinate with the pending logical-DFD
finding instead of duplicating its blocks. Regenerate `paper_sync/TRACKER.md`. No Drive writes before
the normal three gates.

Prepare, but do not apply before separate approval, exact Test Execution Tracker edits:

- refresh `Unit Testing!A35:J35` with Admin evidence;
- add `TC-UNIT-051` and `TC-UNIT-052` using the next verified blank rows;
- add `TC-INT-012` using the next verified blank Integration row;
- update Operator journeys OP-J01, OP-J03, OP-J09;
- update Administrator journey AD-J02 to locate AI Performance after Maintenance and cover CSV/PDF;
- update `UAT Traceability!A17:G17` so FR-16 maps only to AD-J02;
- combine P28+P29 changes to OP-J09 in one final write.

Copy native row structure/validation, write only changed cells, apply `#D9EAD3` only to those cells,
and read back values, validation, and formatting. New execution rows start `Not Executed` until real
evidence exists.

