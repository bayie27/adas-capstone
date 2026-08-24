# P26 — Backup audit rows have no target, and target types print raw

> **Blocked by:** [P25](25_PKG_audit_target_labels.md) — committed on
> `feat/be-p25-audit-target-labels` but **not yet merged**. Step 0 stacks on that branch
> because Steps 2–4 touch the same three frontend files P25 modified.
> **Branch:** `feat/be-p26-audit-backup-target`
> **Runs where:** **worktree-safe.** Backend + frontend code plus pytest and vitest. No
> migration, no schema change, no live stack required (one optional manual UI check).
> **Prerequisite reading:** [`25_PKG_audit_target_labels.md`](25_PKG_audit_target_labels.md)'s
> inventory table — this package corrects one verdict in it — then D-007 (audit trail) and
> D-010 (export contract, for why the CSV `Target` column stays machine-readable).
> **Size:** S. Three small code steps plus tests.
>
> **Why this exists:** P25's inventory classified the `backup` audit family as ✅ already
> correct and told its executing session not to touch it. **That verdict was wrong.** It
> conflated the `detail` payload with the `target_ref` column, and it assumed `backup_id` was
> human-readable when it is a bare 32-char hex. This package corrects it and fixes two
> adjacent defects found while verifying.
>
> **Executing session:** this document is self-contained — you do not need the conversation
> that produced it. Every file path and line number was read and verified against the working
> tree on 2026-08-24. Where a line number has drifted, trust the quoted code and the described
> behaviour over the number.

---

## Context

Observed on the Audit Log screen: a backup row's **Target** column reads just `backup`, with
nothing after it. P25's inventory table classified `target_type="backup"` as ✅ correct on the
grounds that `detail.backup_id` carries the identifier. That reasoning conflated the `detail`
payload with the `target_ref` column, and it was wrong on a second count too — `backup_id` is
not human-readable at all.

Three distinct defects, all verified in the current tree.

### What the Target column renders today

| Action | Target column |
| --- | --- |
| Confirmed Alert | `incident · 118` |
| Enabled Camera | `camera · 3` |
| Disabled User | `user · 7` |
| **Triggered Backup** | **`backup`** — nothing after it |
| **Triggered Restore** | **`restore · a3f9e1c204b84d7a9e6f8b1c2d3e4f50`** — full 32-char blob |

### Finding 1 — `target_ref` is NULL on every `BACKUP_TRIGGER` row

All four sites pass `target_type="backup"` and **no `target_ref` at all**:

| Site | Result | Is a backup id available? |
| --- | --- | --- |
| `routes/maintenance.py:117` — manual backup outcome | success/failure | **yes** — `manifest.backup_id`, already written into `detail` at line 104 |
| `routes/maintenance.py:174` — second concurrent request | denied | no — nothing was created |
| `services/maintenance_schedule.py:122` — scheduled run raised | failure | no — `create_backup` threw |
| `services/maintenance_schedule.py:135` — scheduled outcome | success/failure | **yes** — `manifest.backup_id`, already in `detail` at line 140 |

So two sites can be fixed and two legitimately cannot: a denied or crashed backup has no
object to point at, and `target_ref` must stay NULL there rather than be given a filler value.

In CSV/PDF exports it reads worse than in the UI — `_target()`
(`routes/audit.py:340`) renders `f"{target_type or '?'}:{target_ref or '?'}"`, so every backup
row's Target cell is literally **`backup:?`**.

**The payoff is not cosmetic.** `RESTORE_TRIGGER` already uses `target_ref=body.backup_id`.
Once `BACKUP_TRIGGER` does the same, `?target_ref=<id>` correlates "this backup was created"
with "this backup was restored" in one query. The ledger cannot answer that today, and
`ix_audit_target` (`models/audit.py:66`) is already indexed for exactly that lookup.

### Finding 2 — the Target column cannot shorten a backup id

`formatTargetRef` (`pages/AuditLog.tsx:578`) truncates only via `isUuid`, whose `UUID_RE`
(`utils/auditFormat.ts:71`) requires the dashed 8-4-4-4-12 shape:

```ts
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
```

`new_backup_id()` (`maintenance/manifest.py:44`) returns `uuid.uuid4().hex` — 32 hex chars,
**no dashes**. So `isUuid` is false and no truncation happens. This is why restore rows show a
full 32-character blob **today**, before any change in this package.

Export job ids are unaffected: `jobs.py:583` uses `str(uuid.uuid4())`, which is dashed.

**The correct rule already exists three lines away** — the detail drawer handles this case
explicitly (`AuditLog.tsx:555-558`):

```tsx
// Long hex strings (e.g. non-hyphenated backup IDs)
if (/^[0-9a-f]{24,}$/i.test(strValue)) {
  return <CopyableId value={strValue} />
}
```

So the drawer truncates a backup id and the Target column does not. Two code paths, one rule,
already disagreeing. Fix by extracting the predicate, not by adding a third copy.

### Finding 3 — `target_type` is the one field that skipped the humanising pass

The Target cell prints the stored value verbatim (`AuditLog.tsx:610-613`), and the filter
dropdown uses `label: t` (`AuditLog.tsx:164`). So both show lowercase `backup`, `camera`,
`restore`.

Meanwhile the Action column goes through `AUDIT_ACTION_MAP` → "Triggered Backup"
(`AuditLog.tsx:94`, `:608`), and `utils/auditFormat.ts` already holds `DETAIL_KEY_LABELS`,
`CHECK_LABELS`, `humanizeDetailKey` and `humanizeReasonValue`. Every other display string in
this screen is humanised; `target_type` is the omission.

### Is `backup` the right `target_type`?

**Yes — keep it.** It names the object class, consistent with `camera`, `incident`, `user`,
`session`, `export`.

**The genuine outlier is `restore`.** `RESTORE_TRIGGER` stores `target_type="restore"` with
`target_ref=<a backup id>` — the type names the *action* while the ref identifies a *backup*.
Strictly it should be `target_type="backup"`, since the action column already says
`RESTORE_TRIGGER`.

**Do not rename it.** `audit_log` is append-only, enforced by `trg_audit_log_no_update`
(`models/audit.py:92-117`). Historical rows would keep `restore` forever with no migration
path, so a filter on `backup` would silently miss every pre-change restore while a filter on
`restore` would return only old ones — permanently, in a forensic table whose whole point is
NFR-21's "complete forensic visibility". The frontend's `AUDIT_TARGET_TYPES` array would also
have to carry both values indefinitely with no way to explain the split.

**Decision (confirmed with the owner): leave every stored `target_type` untouched, and fix the
display.** `restore` renders as "Restore Point", `backup` as "Backup".

---

## Step 0 — Branch

**Stack on P25, do not branch from `main`.** P25 is unmerged and already modified
`frontend/src/pages/AuditLog.tsx`, `frontend/src/utils/auditFormat.ts` and
`frontend/src/utils/auditFormat.test.ts` — the same three files Steps 2–4 touch. Branching
from `main` guarantees a conflict.

```bash
git status --short && git branch --show-current
```

Expect `feat/be-p25-audit-target-labels`. Then:

```bash
git checkout -b feat/be-p26-audit-backup-target
```

If P25 has been merged by the time this runs, branch from a freshly pulled `main` instead.

## Step 1 — Give backup rows a `target_ref` and a self-describing `detail`

**Files:** `backend/app/api/routes/maintenance.py`,
`backend/app/services/maintenance_schedule.py`

At the two sites where a `manifest` exists, pass `target_ref=manifest.backup_id` and add the
two fields that make the row readable without a lookup:

```python
detail = {
    "backup_id": manifest.backup_id,
    "created_at": manifest.created_at,   # ISO 8601 UTC string already
    "origin": manifest.origin,           # "manual" | "scheduled" | "pre-restore"
    "checks": manifest.checks,
}
```

`BackupManifest` (`maintenance/manifest.py:90-99`) already carries `created_at` and `origin`,
so this is a read of fields in hand — no new work and no lookup.

> ### The scoping trap at `maintenance.py:117`
>
> `manifest` is bound **only inside the `try`** (line 101); the `except` branch builds
> `detail = {"error_type": ...}` with no manifest, and the `audit.record` call sits after the
> `finally`. So `target_ref=manifest.backup_id` at the call site is an
> `UnboundLocalError` on the failure path.
>
> Introduce a `backup_id: str | None = None` local before the `try`, set it in the success
> branch, and pass `target_ref=backup_id`. `None` is the correct value on the failure path.

At `maintenance_schedule.py:135` `manifest` **is** in scope after the try/except, so
`target_ref=manifest.backup_id` works directly there.

**Leave `maintenance.py:174` and `maintenance_schedule.py:122` alone.** Both fire before any
backup exists. `target_ref` stays NULL, and the UI's "Not applicable" / the export's `?`
is the honest rendering.

> ### Do not add `filename` or any path to `detail`
>
> `backend/tests/test_maintenance.py:953-955` asserts the backup directory path never appears
> in a serialized `detail`:
>
> ```python
> assert str(maintenance_settings.backup_dir).lower() not in serialized
> ```
>
> `created_at` and `origin` are safe. `manifest.filename` is not worth the risk and adds
> nothing the id and timestamp don't already give.

`detail["trigger"]` on the scheduled path (`"scheduled"` vs `"catch_up"`) is **not** the same
thing as `origin` — it records which job fired, not how the backup is classified for
retention. Keep both.

## Step 2 — Humanise `target_type` for display

**Files:** `frontend/src/utils/auditFormat.ts`, `frontend/src/pages/AuditLog.tsx`

Add a label map beside the existing ones in `auditFormat.ts` (section 1, next to
`DETAIL_KEY_LABELS`), following the shape those already use — curated map, generic fallback:

```ts
const TARGET_TYPE_LABELS: Record<string, string> = {
  backup: "Backup",
  camera: "Camera",
  export: "Export",
  incident: "Incident",
  restore: "Restore Point",
  session: "Session",
  user: "User",
}

export function formatTargetType(targetType: string): string { ... }
```

Fall back to title-casing an unlisted value rather than returning it raw, so a future
`target_type` added backend-side degrades gracefully instead of reintroducing lowercase.

Apply it in **both** places that render a target type:

- the Target cell, `AuditLog.tsx:612` — `{entry.target_type}` → `{formatTargetType(entry.target_type)}`
- the filter dropdown, `AuditLog.tsx:164` — `label: t` → `label: formatTargetType(t)`

> The dropdown's `value` must stay the raw stored string — it is sent as the `?target_type=`
> query parameter. Only the `label` changes.

**Do not humanise the exports.** `_target()` in `routes/audit.py:340` and
`services/reports/jobs.py` must keep emitting `backup:a3f9…` — D-010 requires machine-readable
values in CSV, and P25 excluded the same column for the same reason.

## Step 3 — One shared rule for shortening long ids

**Files:** `frontend/src/utils/auditFormat.ts`, `frontend/src/pages/AuditLog.tsx`

Extract the drawer's inline regex into `auditFormat.ts` beside `isUuid`:

```ts
/** True for a long unbroken hex id — e.g. a non-hyphenated backup id
 *  (`uuid4().hex`), which `isUuid` deliberately does not match. */
export function isLongHexId(value: string): boolean {
  return /^[0-9a-f]{24,}$/i.test(value)
}
```

Then use it in the two places that need it:

1. `formatTargetRef` (`AuditLog.tsx:578`) — truncate when `isUuid(ref) || isLongHexId(ref)`.
   This is what fixes the 32-char blob in the Target column, for both backup and restore rows.
2. `DetailValue` (`AuditLog.tsx:556-558`) — replace the inline regex with the shared call.

This removes an existing duplication rather than adding a third copy of the rule.

## Step 4 — Tests

**`backend/tests/test_maintenance.py`**
- `test_trigger_writes_success_audit_row` (line 942) gains: `target_ref` equals the created
  backup's id, and `detail` carries `created_at` and `origin`.
- The **denied** row from `test_second_concurrent_trigger_returns_409` (line 958) has
  `target_ref is None` — pinning that the two no-backup sites are deliberately empty, not
  overlooked.
- A scheduled-backup success row carries `target_ref` and keeps its existing `trigger` key.
- A scheduled-backup **failure** row has `target_ref is None`.
- **The existing path-leak assertion must still pass** — do not weaken it while adding keys.
- One test that a `BACKUP_TRIGGER` row and the `RESTORE_TRIGGER` row for the same backup are
  both returned by `GET /api/audit-logs/?target_ref=<id>`. That correlation is the reason this
  package exists.

**`frontend/src/utils/auditFormat.test.ts`**
- `formatTargetType`: `"restore"` → `"Restore Point"`, `"backup"` → `"Backup"`, and an
  unknown value title-cases rather than passing through raw.
- `isLongHexId`: true for a 32-char `uuid4().hex`, false for a dashed uuid (that is `isUuid`'s
  job), false for a short numeric id like `"118"`.

## Step 5 — Wrap-up

- Add the P26 row to `be_plan/00_INDEX.md`.
- **Correct P25's inventory table.** `be_plan/25_PKG_audit_target_labels.md` still states that
  the `backup` family is ✅ correct because "`detail.backup_id` is the human identifier". That
  row is wrong on both counts and is committed, so a future reader takes it as authoritative.
  Amend that one table row to ❌ with a pointer to this package — do not rewrite the rest of
  P25, and do not delete the original claim; strike it and say what replaced it, so the audit
  trail of the planning docs matches the one in the database.
- No migration, no schema change, no new `target_type` value, no OpenAPI change.

---

## Verification

```bash
uv run pytest backend/tests/test_maintenance.py backend/tests/test_audit.py
```

```bash
pnpm --filter frontend test:run
```

`test_audit.py` is included because Step 1 changes what a `?target_ref=` filter can find.
Do not run the full backend suite — nothing outside these two areas is touched.

**Never run `pnpm check` by hand** — `.husky/pre-push` runs it on every push.

### Manual check

Worth eyeballing once, since the whole package is about what a human reads. Trigger a backup
from the Maintenance page, then open the Audit Log:

- Target column reads `Backup · a3f9e1c2…3e4f50`, not `backup`.
- Expanding the row shows Backup ID (truncated, copyable), Created At, Origin, Validation
  Checks.
- The Target-type filter dropdown reads "Backup" and "Restore Point", not `backup`/`restore`.
- A CSV export of the audit log still shows the machine-readable `backup:a3f9e1c2…` form.

## Paper impact

**None.** No new column, no new `target_type` value, no response-shape change. Table 14
already describes `target_ref` as the identifier of the affected entity and `detail` as
"structured JSON… providing context"; this package makes two rows conform to that description
rather than changing it.

## Deliberately not in this package

- **Renaming `target_type="restore"` to `"backup"`** — rejected above. Append-only table, no
  migration path, permanent filter split.
- **Filling `target_ref` on the denied/failed backup rows** — no backup exists at those two
  sites; a filler value would assert something untrue.
- **Humanising the export `Target` column** — D-010 requires machine-readable values there.
- **The `session` and `export` families** — `session` refs are session ids with the actor
  named on the row; `export` refs are a job id or report type. Both already identify their
  object. Re-checked while verifying this package; still correct.
- **Revisiting P25's other inventory verdicts** — the `restore` family (6 sites +
  `maintenance/restore.py:390`) all pass `target_ref=backup_id` and were confirmed correct
  again here. Only the `backup` verdict was wrong.

## Commits

- Step 1 — `fix(backend): reference the created backup on BACKUP_TRIGGER audit rows`
- Step 2 — `feat(frontend): humanise audit target types for display`
- Step 3 — `fix(frontend): shorten non-hyphenated ids in the audit target column`
- Step 4 — `test: cover backup audit target refs and target-type labels`
- Step 5 — `docs(planning): add P26 package doc`
