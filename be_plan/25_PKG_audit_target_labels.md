# P25 — Human-readable target labels on audit rows

> **Blocked by:** nothing. Parallel-safe with anything not touching `services/audit.py`,
> `routes/{alerts,cameras,users,settings}.py` or `services/reports/`.
> **Branch:** `feat/be-p25-audit-target-labels` — cut from a freshly pulled `main` (Step 0).
> **Runs where:** **worktree-safe.** Pure backend code plus pytest, and one one-line frontend
> constant. No live stack, no OS configuration, no hardware, no migration.
> **Prerequisite reading:** this document's Context section, then
> [`01_CONTRACTS.md`](01_CONTRACTS.md) §1.6 (redaction) and D-007/D-010 for the audit and
> export contracts.
> **Size:** M. Eight steps, of which 2–4 are mechanical and 5–6 carry the real design.
>
> **Executing session:** this document is self-contained — you do not need the conversation
> that produced it. Every file path and line number below was read and verified against
> `main` on 2026-08-24. Where a line number has drifted, trust the quoted code and the
> described behaviour over the number.

---

## Context

The frontend owner raised a backend follow-up:

> Alert actions only carry `camera_id: <number>` with no camera name in the payload. A
> `target_label` field should be added to the audit record backend-side so the frontend can
> display something like "Camera 2 — Front Entrance". Administrators should not have to
> memorize numerical camera IDs to understand which camera triggered an alert.

**The gap is real and was verified, not taken on trust. The proposed mechanism is wrong, and
the gap is wider than reported.** This package fixes it the way the table already solves this
problem for actors.

### What was verified

`audit.record()` (`backend/app/services/audit.py:51`) accepts `target_type` + `target_ref`
only, and `target_ref` is always a stringified integer id. There is **no** `target_label`
column (`backend/app/models/audit.py:69-85`), and there is **no join** to `camera` or `user`
anywhere in the read path — `GET /api/audit-logs/` is a bare `select(AuditLog)`
(`backend/app/api/routes/audit.py:126`), and both export paths
(`routes/audit.py:217`, `services/reports/jobs.py:298`) reuse the same query. The frontend
renders `JSON.stringify(entry.detail, null, 2)` into an expando
(`frontend/src/pages/AuditLog.tsx:446`) with no formatter of any kind. So an administrator
genuinely sees `{"camera_id": 3}` and a `Target` column reading `incident:118`.

The `username` / `role` columns on `audit_log` are the **actor**, not the target. A
`USER_DISABLE` row therefore records who did it but not to whom.

### Complete inventory — every audit write site in `backend/app`

42 sites across 8 files. Every one was read and classified. **18 are genuine gaps**, 3 are
uniformity-only, 1 needs normalising, 20 are already correct and must not be touched.

| target_type | Sites | Verdict |
| --- | --- | --- |
| *(none)* — `LOGIN_FAILURE` | auth.py:57, 77 | ✅ correct — carries `actor_username`, the only identity that exists for a failed login |
| `session` | auth.py:118 (`LOGIN_SUCCESS`), 171 (`LOGOUT`) | ✅ correct — actor **is** the session owner, so the `username` column already identifies it |
| `incident` | alerts.py:479, 541, 618, 670 | ❌ **4 gaps** — see Step 2 |
| `camera` | cameras.py:288 (`CAMERA_CREATE`) | ✅ already snapshots `camera_name` — the precedent this package generalises |
| `camera` | cameras.py:389, 400, 410, 462 | ❌ **4 gaps** — see Step 3 |
| `user` | users.py:276 (`USER_CREATE`) | ⚠️ has the name under key `username` — **normalise** to `target_username` (Step 4) |
| `user` | users.py:108, 156; settings.py:81 | ⚠️ self-targeting; actor `username` already covers it — **included for uniformity** (Step 4) |
| `user` | users.py:326, 341, 384, 395, 406, 416, 465, 498, 515, 533 | ❌ **10 gaps** — see Step 4 |
| `backup` | maintenance.py:117, maintenance_schedule.py:135 | ✅ `detail.backup_id` is the human identifier |
| `backup` | maintenance.py:174, maintenance_schedule.py:122 | ✅ failure/denied paths — **no backup exists to name**; correctly absent |
| `restore` | maintenance.py:216, 234, 251, 270, 286, 302 | ✅ `target_ref = body.backup_id` |
| `restore` | `maintenance/restore.py:390` (raw `sqlite3` INSERT) | ✅ `target_ref = state.backup_id` |
| `export` | 11 sites, all via `record_export_attempt` | ❌ **1 seam to fix** — `detail.filters.camera_id` is a bare id list (Step 5) |
| *(not an audit row)* | 4 PDF filter-summary builders | ❌ **`Camera IDs: 3, 7`** in every camera-filtered PDF export (Step 6) |

> **Do not invent gaps beyond these.** The `session`, `backup` and `restore` families were
> each checked and are correct as written. Changing them adds noise to an append-only ledger.

### Why not a `target_label` column

1. **Wrong semantics for the actual ask.** Alert rows use `target_type="incident"`, so a
   `target_label` would label the incident. "Camera 2 — Front Entrance" is not the target of
   an `ALERT_CONFIRM`; it is context about it.
2. **Schema change on a trigger-protected append-only table.** `trg_audit_log_no_update` /
   `trg_audit_log_no_delete` (`models/audit.py:92-117`) force a reviewed Alembic migration,
   and no historical row can be backfilled either way.
3. **Paper cost.** A new column requires a Data Dictionary Table 14 revision and a
   `paper_sync` tracker row. Adding a key to `detail` requires neither — Table 14 already
   describes `detail` as "Structured JSON or text providing context and state diffs."

### Why not resolve id → name client-side

`useCameraOptions` (`frontend/src/hooks/useCameraOptions.ts`) already caches a camera list,
which makes this tempting. It is wrong for an audit trail:

- `ux_camera_name_active` is a partial unique index on `lower(camera_name) WHERE is_active =
  1` (`backend/app/models/camera.py:52-57`), so **a soft-deleted camera's name can be re-taken
  by a new camera**. A read-time lookup would attach today's name to a historical act — worse
  than a bare id, under an NFR-21 promising "complete forensic visibility."
- `GET /api/cameras/` caps `limit` at 100, so camera #101 resolves to nothing.
- Deleted cameras drop out of the list entirely, so historical rows would show no name at all.

Write-time snapshotting is what this table already does: `username` and `role` are
denormalized onto the row at write time (`services/audit.py:72-73`) for exactly this reason.

### How this renders in each surface

All three audit surfaces already pass `detail` straight through, so none of them needs a code
change to show the new keys. Verified rendering:

**Web UI** — `frontend/src/pages/AuditLog.tsx:446` pretty-prints the parsed dict at 2-space
indent inside the expando:

```json
{
  "camera_id": 3,
  "camera_name": "Front Entrance"
}
```

**CSV / PDF** — both export paths read the `AuditLog` **model** directly and never go through
`AuditLogRead`, so the `Detail` cell holds the **raw one-line JSON string**, not a parsed
object. `stringify_cell` (`services/reports/csv_writer.py:47`) renders a `None` detail as the
literal `N/A`, which is what `CAMERA_ENABLE`/`DISABLE`/`RESTORE`/`DELETE` and most `USER_*`
rows show today.

```csv
Audit ID,Created At,Actor,Action,Target,Result,Detail
101,2026-08-24T09:14:22+00:00,jdoe (Administrator),ALERT_CONFIRM,incident:118,success,"{""camera_id"": 3, ""camera_name"": ""Front Entrance""}"
102,2026-08-24T09:15:03+00:00,jdoe (Administrator),CAMERA_ENABLE,camera:3,success,"{""camera_name"": ""Front Entrance""}"
103,2026-08-24T09:16:41+00:00,jdoe (Administrator),USER_DISABLE,user:7,success,"{""target_username"": ""mreyes""}"
```

Rows 102 and 103 read `N/A` in that last column today.

`build_audit_pdf` (`services/reports/pdf_writer.py:297`) gives `Detail` a width of 60 out of
238 (`col_widths=(18, 30, 35, 35, 40, 20, 60)`), and `add_table` (`pdf_writer.py:135-160`)
**wraps** cell values rather than truncating — a longer detail makes the row taller and is
never cut off. No column-width change is needed, and none should be made.

**PDF filter-summary header** — a separate block above the table
(`pdf_writer.py:108 add_filter_summary`), fed by its own builders rather than by `detail`.
Step 6 changes it from the first form to the second:

```text
Date range: 2026-08-01 to 2026-08-24     Date range: 2026-08-01 to 2026-08-24
Camera IDs: 3, 7                    →    Cameras: 3 (Front Entrance), 7 (Gate B)
```

CSV exports have **no** filter-summary block at all (`csv_writer.py:101 csv_response` takes
only columns and rows), so in CSV the names arrive solely through the `Detail` column.

### What this buys

- No schema change, no migration, no paper impact.
- **No new queries** for Steps 2–4 — the camera/user row is already loaded at every site.
- **No rendering change needed for the `detail` payload.** The web expando and both export
  formats already pass `detail` through unchanged, so Steps 2–5 land in all three surfaces
  with no read-side work. (Step 6 changes the PDF's *filter-summary header*, which is a
  separate code path.)
- **Free search.** `?search=` already does `icontains` on `detail`
  (`routes/audit.py:77-82`), so "search the audit log by camera name" starts working with
  zero route changes. Step 6 pins this with a test.

---

## Step 0 — Branch from a fresh `main`

**Do not build on whatever branch you find yourself on.** When this package was written
(2026-08-24) the tree sat on `feat/fe-p23-camera-restore` — 1 commit *behind* `main` with no
unique commits of its own, plus uncommitted changes. Start from a freshly pulled `main`
regardless of what you find.

Check first, and stash only if there is something to stash:

```bash
git status --short && git branch --show-current
```

```bash
git stash push -u -m "wip before p25"
```

```bash
git checkout main && git pull
```

```bash
git checkout -b feat/be-p25-audit-target-labels
```

Restore the stash afterwards if it held anything you still need (`git stash pop` on the
original branch, not on this one). Confirm the starting point is clean before editing:

```bash
git status --short && git log --oneline -1
```

---

## Step 1 — Add the shared name resolver

**File:** `backend/app/services/cameras.py`

Two helpers, used by Steps 5 and 6. Put them next to `presented_statuses()`. The second,
`format_camera_filter_line`, is specified in Step 6 — write both here so Step 6 is a pure
call-site change.

```python
def resolve_camera_names(
    session: Session, camera_ids: Iterable[int]
) -> dict[str, str]:
    """Map camera ids to their current names for audit `detail` payloads.

    Keys are stringified because `detail` is JSON-serialized (services/audit.py:88)
    and JSON object keys are always strings. Ids with no matching row — a
    hard-deleted camera, or a bad id echoed back from a request — are simply
    absent from the result rather than mapped to None: the audit row should say
    what was resolvable, not assert a null name.
    """
```

Implement as a single `select(Camera.camera_id, Camera.camera_name).where(col(Camera.camera_id).in_(ids))`.
Return `{}` for an empty input **without issuing a query**. Do **not** filter on `is_active` —
a soft-deleted camera still has a name, and an export filtered on it should still say which.

## Step 2 — Alert actions (4 sites)

**File:** `backend/app/api/routes/alerts.py`

Add `camera_name` alongside the existing `camera_id`:

| Line | Action | Name expression — **already in scope, do not re-query** |
| --- | --- | --- |
| 484 | `ALERT_CONFIRM` | `log.camera.camera_name if log.camera else None` — same expression as line 495; the relationship is eager-loaded via `selectinload(DetectionLog.camera)` at alerts.py:416 |
| 546 | `ALERT_DISMISS` / `ALERT_CORRECTION` | `camera.camera_name if camera is not None else None` — `camera` is loaded at line 529, *before* this record call; same expression as line 557 |
| 623 | `ALERT_RESOLVE` | same as above — `camera` loaded at line 610, expression at line 637 |

```python
detail={"camera_id": log.camera_id, "camera_name": <expression from the table>},
```

`ALERT_SNOOZE` (line 675) gains **both** keys — it is the only HITL transition whose audit row
carries no camera reference at all:

```python
detail={
    "snoozed_until": log.snoozed_until.isoformat(),
    "camera_id": log.camera_id,
    "camera_name": log.camera.camera_name if log.camera else None,
},
```

> **Do not move any `audit.record` call.** Each sits inside the single audited transaction
> that CLAUDE.md's "every audited state change is one transaction" rule depends on, and each
> sits before its `session.commit()`. This step widens dict literals only; call ordering must
> not shift.

> **Keep the `if log.camera` / `is not None` guards.** They are reachable and their `None`
> result is correct — do not "simplify" them away.

## Step 3 — Camera lifecycle actions (4 sites)

**File:** `backend/app/api/routes/cameras.py`

Add `"camera_name": db_camera.camera_name` to `detail` at lines 389 (`CAMERA_UPDATE`), 400
(`CAMERA_ENABLE`/`CAMERA_DISABLE`), 410 (`CAMERA_RESTORE`) and 462 (`CAMERA_DELETE`). The last
three currently pass no `detail=` kwarg at all and gain one. Leave line 288
(`CAMERA_CREATE`) alone — it already carries the name.

> ### The rename trap
>
> `PATCH /api/cameras/{id}` can itself change `camera_name`, and by the time the
> `CAMERA_UPDATE` row is written at line 389 the new name is already on `db_camera`. The
> existing `before = snapshot_ai_relevant_fields(db_camera)` at line 361 captures only the
> AI-relevant fields (`channel_id`, `is_enabled`, …) — **it does not carry `camera_name`**, so
> it cannot be reused here.
>
> Capture the old name into a local **before** the mutation loop, and when
> `"camera_name" in other_changed_fields` record both:
>
> ```python
> detail={
>     "changed_fields": sorted(other_changed_fields.keys()),
>     "camera_name": db_camera.camera_name,          # after the change
>     **({"previous_camera_name": old_name} if renamed else {}),
> }
> ```
>
> The other three sites cannot rename, so `db_camera.camera_name` is unambiguous there.

## Step 4 — User actions (14 sites)

**File:** `backend/app/api/routes/users.py` (13 sites), `backend/app/api/routes/settings.py` (1 site)

Add `"target_username"` to `detail` at **every** `target_type="user"` site. The key is
deliberately *not* `"username"` — that name already means the actor on the row itself, and
reusing it in `detail` would be ambiguous in the ledger.

| Sites | Expression |
| --- | --- |
| users.py:326, 341, 384, 395, 406, 416, 465, 498, 515, 533 | `target.username` — `target` is in scope at all ten |
| users.py:108 (`USER_PROFILE_UPDATE`), 156 (`USER_PASSWORD_CHANGE`) | `current_user.username` |
| settings.py:81 (`ALARM_SETTINGS_UPDATE`) | `current_user.username` |
| users.py:276 (`USER_CREATE`) | **normalise**: rename the existing `"username"` key to `"target_username"`, keeping `"role"` |

Three notes the executing session must not skip:

1. **The four `record_out_of_band` denied sites (326, 341, 498, 515) are included.** They
   already have `target` loaded. Omitting them would leave denied rows as the one place with
   no target name — precisely the rows an auditor cares most about.
2. **The three self-targeting sites (users.py:108, 156; settings.py:81) are included on
   purpose**, even though the actor `username` column already holds the same value. A uniform
   key means the read side is one unconditional lookup with no actor-equals-target special
   case. This was an explicit decision, not an oversight.
3. **`USER_CREATE`'s rename is a breaking change to that row's `detail` shape.**
   `backend/tests/test_users.py` asserts on the current `"username"` key — update those
   assertions in the same commit. Grep for `"username"` inside test assertions on
   `USER_CREATE` before changing the route.

> `_BANNED_DETAIL_KEYS` (`services/audit.py:16-31`) contains none of `camera_name`,
> `target_username`, or `previous_camera_name`, so nothing added by Steps 2–5 is masked. Every
> string value still passes through `redact_text()` — correct, and must not be bypassed.

## Step 5 — Export filters (one seam, 11 call sites)

**File:** `backend/app/services/reports/common.py`

`record_export_attempt` writes `detail.filters` as a verbatim echo of the request, so a
camera-filtered export records `"camera_id": [3, 7]` with no names
(built at `alerts.py:131`, `analytics.py:346`, `analytics.py:735`, and round-tripped from
`ExportJob.filters_json` at `jobs.py:50`).

**Fix it in `record_export_attempt` itself, not at the 11 call sites.** That function already
receives both `session` and `filters`, so one edit covers every sync route *and* the async job
worker:

```python
camera_ids = filters.get("camera_id") or ()
if camera_ids:
    detail["camera_names"] = resolve_camera_names(session, camera_ids)
```

The resulting row:

```json
{
  "report_type": "incidents",
  "format": "csv",
  "mode": "sync",
  "filters": {
    "start_date": "2026-08-01", "end_date": "2026-08-24",
    "status": ["Resolved"],
    "camera_id": [3, 7],
    "user_id": [], "search": null,
    "camera_names": { "3": "Front Entrance", "7": "Gate B" }
  },
  "sort": { "sort_by": "detected_at", "sort_order": "desc" },
  "row_count": 412
}
```

Four constraints:

- **`camera_names` is a sibling key inside `filters`, not a replacement for `camera_id`.**
  `filters` must stay a faithful record of what the caller sent; the names are an annotation
  on top. D-010 requires the filters as sent.
- **Only add the key when there is something to add.** An unfiltered export must not gain an
  empty `"camera_names": {}` — that is noise on the overwhelming majority of rows.
- **`AUDIT_EXPORT` is unaffected.** `_audit_filters_dict` (`routes/audit.py:159-179`) has no
  `camera_id`, so `.get()` returns `None` and this branch never fires. Do not add one.
- **Do not touch `ExportJob.filters_json`.** The job's stored filters are replayed through
  `_incident_filters_from_dict` (`jobs.py:58`) to rebuild the query; enriching them there
  would persist a derived value into a request record. Enriching only inside
  `record_export_attempt` keeps the stored job pristine while still reaching the async audit
  rows, because the worker calls the same function.

> The PDF's rendered filter-summary header is a **separate** code path — it reads
> `IncidentFilters`, not this dict. It is handled by Step 6, not here.

## Step 6 — Camera names in the PDF filter-summary header

**Files:** `backend/app/services/cameras.py`, `backend/app/api/routes/alerts.py`,
`backend/app/api/routes/analytics.py`, `backend/app/services/reports/jobs.py`

Every PDF export prints a filter-summary block above the table
(`pdf_writer.py:108 add_filter_summary`). Today a camera-filtered export's header reads:

```text
Date range: 2026-08-01 to 2026-08-24
Camera IDs: 3, 7
```

After this step:

```text
Date range: 2026-08-01 to 2026-08-24
Cameras: 3 (Front Entrance), 7 (Gate B)
```

> **CSV exports have no filter-summary block at all** — `csv_response`
> (`csv_writer.py:101`) takes only columns and rows. Do not go looking for one. In CSV the
> names arrive via the `Detail` column (Step 5) and nowhere else.

### The four sites

`"Camera IDs: " + ", ".join(str(c) for c in ...)` is written out **four** times:

| Site | Shared by |
| --- | --- |
| `alerts.py:152`, inside `_filters_summary(f: IncidentFilters, …)` | the sync incidents export (`alerts.py:391`) and the async worker (`jobs.py:103`, which imports it) |
| `analytics.py:313`, inside `_dashboard_filters_summary(…)` | the sync dashboard export (`analytics.py:397`) and `jobs.py:141` |
| `analytics.py:790` — **inline, no helper** | the sync performance export only |
| `jobs.py:255` — **inline, a verbatim copy of the above** | the async performance job only |

`_audit_filters_summary` (`audit.py:182`) has no camera filter and is **not** touched.

### The formatter

One pure function in `backend/app/services/cameras.py`, next to `resolve_camera_names`:

```python
def format_camera_filter_line(
    camera_names: Mapping[str, str], camera_ids: Iterable[int]
) -> str:
    """'Cameras: 3 (Front Entrance), 7 (Gate B)' for a PDF filter-summary block.

    Takes an already-resolved map rather than a session so it stays pure and
    testable, and so a caller that also writes an audit row resolves once.
    An id absent from the map renders bare ('7') rather than '7 (None)' — a
    hard-deleted camera should still show that it was filtered on.
    """
```

Each of the four sites resolves once via `resolve_camera_names` (Step 1) and calls this.

> **Collapse the performance duplication rather than editing both copies.**
> `analytics.py:784-793` and `jobs.py:248-257` are the same ten lines. Extract
> `_performance_filters_summary(...)` in `analytics.py` — mirroring the
> `_dashboard_filters_summary` that already exists right beside it — and have `jobs.py` import
> it, exactly as `jobs.py:124` already imports `_dashboard_filters_summary`. Editing both
> copies identically would double a duplication this package is already touching.

### Resolve once per export

Steps 5 and 6 both need the same map in the same request. Resolve it once at the top of each
export route and pass it to both:

- Give `record_export_attempt` an optional `camera_names: dict[str, str] | None = None`
  parameter. When supplied it uses it; when omitted it resolves internally (Step 5's default),
  so the CSV-only paths and any future caller stay a one-liner.
- The PDF paths resolve first, pass the map to `record_export_attempt(camera_names=...)`, then
  to `format_camera_filter_line`.

In `alerts.py` note the ordering: `record_export_attempt` is called at lines 347 and 363, and
`_filters_summary` at line 391 — so the resolve must happen before line 347.

### The label change

`Camera IDs:` becomes `Cameras:`, because the line now carries names as well as ids.

This is safe where the CSV `Target` column was not: the filter summary is a **human-readable
prose block rendered into a PDF**, not a machine-parseable column. Nothing consumes it
programmatically. Check `backend/tests/test_exports.py` for any assertion on the literal
string `"Camera IDs:"` and update it in the same commit.

## Step 7 — Frontend action catalog

**File:** `frontend/src/api/audit.ts:15-42`

`AUDIT_ACTIONS` mirrors 26 entries; the backend catalog (`models/audit.py:10-38`) has 27 since
migration `b0a3652a3d4d`. **`CAMERA_RESTORE` is missing**, so it cannot be selected in the
Audit Log filter. Verified present-on-`main`-backend and absent-on-`main`-frontend.

Add `"CAMERA_RESTORE",` after `"CAMERA_DELETE",` and update the docstring at line 6 from
"26-entry action catalog" to "27-entry action catalog".

Nothing else in that file changes — `AUDIT_TARGET_TYPES` (lines 60-68) is already complete, and
`AuditLogEntry.detail` is already typed `Record<string, unknown> | null`, which accommodates
the new keys with no type change.

## Step 8 — Wrap-up

- Add the P25 row to `be_plan/00_INDEX.md`'s status table. This document already lives at
  `be_plan/25_PKG_audit_target_labels.md`; commit it as `docs(planning):` if it is still
  untracked.
- No OpenAPI description changes — no route signature or response model changed.
- No `paper_sync` finding. See "Paper impact" below.
- Update `be_plan/EVIDENCE.md` only if that document quotes a PDF filter-summary header
  (Step 6 changes `Camera IDs:` to `Cameras:`). Grep before assuming either way.

---

## Verification

Narrow scopes per CLAUDE.md's verification policy — this touches five unrelated areas and the
full suite proves nothing extra about any of them:

```bash
uv run pytest backend/tests/test_alerts.py backend/tests/test_cameras.py backend/tests/test_users.py backend/tests/test_audit.py backend/tests/test_exports.py
```

Reach for `uv run pytest -n auto` **once**, immediately before opening the PR.

**Never run `pnpm check` by hand** — `.husky/pre-push` already runs it on every push; running
it first just doubles the wait for identical signal. For Step 6, `pnpm --filter frontend test:run`
is enough locally if you want signal before pushing.

### What to assert

Per CLAUDE.md's testing policy: boundaries and failure paths, not the same happy path five
ways. Assert on the **parsed dict** that `AuditLogRead`'s `field_validator`
(`schemas/audit.py:24-31`) produces — never on the raw JSON string.

**`test_alerts.py`**
- Confirm / dismiss / resolve / snooze each write a row whose `detail` carries `camera_id`
  **and** the correct `camera_name`.
- One case where the camera row is absent asserts `camera_name is None` rather than raising.
  That `if log.camera` branch is reachable and must stay reachable.

**`test_cameras.py`**
- `CAMERA_ENABLE`, `CAMERA_DISABLE`, `CAMERA_RESTORE`, `CAMERA_DELETE` now have a non-null
  `detail` containing `camera_name`.
- **The rename case (Step 3's trap):** a `PATCH` that changes `camera_name` records the new
  name under `camera_name` *and* the old one under `previous_camera_name`. A `PATCH` that
  changes something else records no `previous_camera_name` key at all.

**`test_users.py`**
- A `USER_DISABLE` row identifies its target by name, not only by `target_ref`.
- **At least one denied row** (last-admin demote, users.py:326) carries `target_username` —
  that path goes through `record_out_of_band` in a separate session and would be easy to miss.
- `USER_CREATE`'s key is now `target_username`; the pre-existing assertion on `"username"` is
  updated, not deleted.

**`test_exports.py`** — audit row (Step 5)
- A camera-filtered incident export's audit row carries `filters.camera_names` mapping each
  filtered id to its name, and `filters.camera_id` is **unchanged**.
- An **unfiltered** export's audit row has **no** `camera_names` key (not an empty dict).
- An `AUDIT_EXPORT` row has no `camera_names` key.
- A filter naming a soft-deleted camera still resolves its name; an id matching no row is
  simply absent from the map.

**`test_exports.py`** — PDF header (Step 6)
- The incidents, dashboard and performance PDFs each render `Cameras: 3 (Front Entrance)`
  for a camera-filtered export. **All three, because they are three separate code paths** —
  a test on only one would not catch the inline performance copy.
- An id with no matching camera renders bare (`7`), not `7 (None)`.
- An unfiltered export's summary has no camera line at all.
- The **async job** path produces the same header as its sync counterpart. `jobs.py` imports
  these helpers rather than owning them, and that is exactly the kind of import that rots
  silently.
- `AUDIT_EXPORT`'s PDF header is unchanged.
- Only one `resolve_camera_names` query is issued per PDF export, not two — this is the
  point of threading the map through `record_export_attempt`.

**`test_audit.py`**
- `GET /api/audit-logs/?search=<camera name>` returns the alert rows for that camera. This is
  the behaviour that comes for free from the `detail` `icontains` filter and is a large part of
  why `detail` beats a new column — it deserves a guard so a future refactor cannot lose it.

## Paper impact

**None.** No new column, no changed response shape, no new endpoint, no changed constant.
Data Dictionary Table 14's `detail` row already reads "Structured JSON or text providing
context and state diffs," which this satisfies. No `paper_sync` finding or tracker row is
needed for this package.

(The unrelated, already-filed
`paper_sync/findings/2026-08-18-audit-log-detail-redaction.md` stands on its own and is not
affected.)

## Deliberately not in this package

- **A `target_label` column and its migration** — rejected above on semantics and cost.
- **Backfilling historical rows** — impossible; `trg_audit_log_no_update` aborts any UPDATE.
  Rows written before this change keep showing a bare id, and that is correct: the ledger
  records what was known at write time.
- **The `session`, `backup` and `restore` audit families** — all checked, all already carry a
  human-readable identifier. Touching them would be inventing a gap.
- **A humanising formatter for the `detail` expando** (`frontend/src/pages/AuditLog.tsx:446`) —
  the raw JSON blob solves the stated problem once the name is in it. Per-action templating is
  a real frontend improvement but separate, larger work.
- **The export `Target` column** — `_target()` in both `routes/audit.py:340` and
  `services/reports/jobs.py` renders `f"{target_type}:{target_ref}"`. The name now arrives in
  the adjacent `Detail` column; changing the `Target` format **would** break anyone parsing
  those CSVs, which is why it is excluded where Step 6's prose header is not.
- **PDF column widths** — `add_table` wraps rather than truncates, so a longer `Detail` cell
  makes the row taller and stays fully legible. Do not retune `col_widths`.
- **Seeded demo audit rows** (`backend/app/dev/profiles.py:858`) — they use synthetic
  `target_ref=str(index + 1)` values pointing at arbitrary ids, so adding names there is
  cosmetic only. Worth a follow-up if the demo's Audit Log page is on the defense script.

## Commits

Conventional Commits, enforced by commitlint on `commit-msg`. One commit per numbered step:

- Step 1 — `feat(backend): add camera name resolver and filter-line formatter`
- Steps 2–5 — `fix(backend): …` (each closes an existing gap, not new capability)
- Step 6 — `feat(backend): show camera names in PDF export filter summaries`
- Step 7 — `fix(frontend): add CAMERA_RESTORE to the audit action catalog`
- Step 8 — `docs(planning): …`
