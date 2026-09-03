# P28 — Rename Resolved incidents to Cleared

> **Branch:** `feat/be-p28-cleared-incident`  
> **Runs where:** worktree-safe. No live AI engine is required.  
> **Size:** XL, cross-stack and migration-bearing.  
> **Integration:** merge before P29 is finalized because both touch analytics, help, and tests.

## Goal and locked vocabulary

The terminal state currently called `Resolved` means only that the accident is no longer visible
in the monitored camera and detection can resume. It does not certify that the real-world case is
resolved. Replace the active contract completely:

| Surface | Old | New |
| --- | --- | --- |
| Stored/API status | `Resolved` | `Cleared` |
| Enum member | `RESOLVED` | `CLEARED` |
| REST transition | `POST /api/alerts/{id}/resolve` | `POST /api/alerts/{id}/clear` |
| Audit/realtime action | `ALERT_RESOLVE` | `ALERT_CLEAR` |
| KPI fields | `total_resolved*` | `total_cleared*` |
| Modal action button | `Resolve Accident` | `Cleared` |
| Tray CTA | `Review & Resolve` | `Review Incident` |

There is no compatibility alias. The button remains an immediate action: no confirmation modal,
warning, or new explanatory UI. Keep `closed_by_id`/`closed_at`; they are also used by an
Ongoing-to-Dismissed correction and are intentionally generic terminal metadata.

## Step 0 — inventory and migration design

Read `CLAUDE.md`, `be_plan/01_CONTRACTS.md` §§5, 8, 9, 10, this package, and
`be_plan/14_EDGE_CASES.md` §§1, 7, 10. Search `Resolved|RESOLVED|resolve|ALERT_RESOLVE|total_resolved`
across tracked code and content. Classify every hit before editing; generic path/URL/name resolution
is out of scope.

Create one new Alembic migration. Do not edit historical migrations. The migration must:

1. Rewrite `detection_log.detection_status='Resolved'` to `Cleared`.
2. Rewrite `audit_log.action='ALERT_RESOLVE'` to `ALERT_CLEAR`, as explicitly authorized.
3. Temporarily remove the append-only audit triggers only for the migration, rebuild the affected
   SQLite CHECK constraints, and recreate both triggers.
4. Preserve primary keys, timestamps, actors, targets, results, details, indexes, and row counts.
5. Test upgrade from the preceding real Alembic revision and prove UPDATE/DELETE are blocked again.

## Step 1 — backend domain, REST, events, and analytics

Update the enum and model constraints, incident transition map/conflict attribution, route/function,
audit catalog, event schemas/builders, filters, dashboard/performance analytics, synchronous and
async reports, CSV/PDF labels, retraining mappings, schemas, dev/UAT profiles, scripts, and tests.
The ordering contract remains camera status broadcast first, then alert status broadcast.

The old route must be absent (404), `Resolved` query values must fail validation, and all response
types emit only `Cleared`/`ALERT_CLEAR`/`total_cleared*`.

## Step 2 — frontend and help content

Update frontend API/event types, mutation names, stores, status tones, filters, badges, dashboard
KPIs, AI Performance filters, audit labels, Detections, Cameras messages, and tray tests. In the
shared `IncidentDetailModal`, the Ongoing action is a single button whose visible text is exactly
`Cleared`; clicking it immediately invokes the clear mutation.

Rename incident-help filenames/slugs and every internal link that contains resolve/resolved. Content
may define Cleared as the camera-view terminal state, but do not add runtime confirmation copy.
Seeding must delete the obsolete slugs and remain idempotent.

## Step 3 — verification

Run narrow tests while editing, then:

```powershell
uv run pytest -n auto
pnpm --filter frontend test:run
pnpm full:check
```

Do not run `pnpm check` manually. Add explicit tests for migration preservation, triggers/indexes,
the absent legacy route, illegal/self transitions, lost races, immediate button behavior, tray CTA,
event ordering, exports, KPI field names, help links, and seed idempotency. Finish with an allowlisted
`rg` sweep proving no active contract use remains; historical planning/evidence and generic
resolution helpers are allowed only when individually justified.

## Step 4 — documentation, paper sync, and test tracker

Update `01_CONTRACTS.md` and this package's completion notes only; do not edit the shared index or
PROMPTS concurrently. Run `adas-paper-sync` in described/diff mode against the live paper, audit Doc,
and audit tracker. Create a new Cleared-terminology finding with one OLD/NEW block per site and redraw
blocks for affected figures. Regenerate `paper_sync/TRACKER.md`. Do not write to Drive without the
three normal approval gates.

Prepare a separate approval manifest for the ADAS Test Execution Tracker:

- `Unit Testing!A23:J24`
- `Integration Testing!A9:J9`
- `System / E2E Testing!A3:J3`
- `UAT Journeys!A8:J8`
- the terminology half of `UAT Journeys!A10:J10`
- `Guide & Examples!A8:E8`

Never relabel old evidence as proof. Rerun before replacing execution cells; otherwise preserve the
old evidence and mark `Retest Required`. Every changed content cell receives only the existing
`#D9EAD3` background fill, with validation/links/formulas preserved and read back. Do not perform
these Sheet writes before the separate tracker approval.

## Deliberately out of scope

- Renaming `closed_by_id` or `closed_at`.
- Compatibility aliases for the old route, status, action, KPI fields, or help slugs.
- AI-engine changes; the engine consumes desired camera state, not incident status.
- Editing historical UAT evidence prose as though it were newly executed.

