# Frontend Handoff — Q13, Q14 and the export-job gaps are closed

> **Audience:** the frontend owner (and their agent).
> **Hand over:** when backend package **P21** merges. **Section 3 is the one that breaks your
> typecheck** — deliberately, and it is the change you asked for.
> **Companion to:** [`20_FRONTEND_HANDOFF.md`](20_FRONTEND_HANDOFF.md) (P19) and
> [`11_FRONTEND_MIGRATION.md`](11_FRONTEND_MIGRATION.md) (P2–P4). This one covers P21.
> **Where the backend work lives:** [`21_PKG_camera_telemetry_and_client_gaps.md`](21_PKG_camera_telemetry_and_client_gaps.md).

Across PRs #104–#112 you recorded four backend gaps and shipped honest "Unavailable" states around
them rather than fabricating data. All four are now closed. Every contract is stated in full below,
so you do not need to read the backend package doc.

| § | What you raised | Status |
|---|---|---|
| 1 | Q14 — `CameraRead` exposes no engine telemetry, and there is no detail route | **fixed** — new endpoint |
| 2 | Q13 — alarm sound allowlist and snooze bounds unreachable | **fixed**, additive |
| 3 | PR #105 — `snoozed_by` is an id an Operator can't resolve | **fixed — breaking type change** |
| 4 | PR #111 — no export-jobs list; job create can't carry audit filters | **fixed**, additive |

---

## 1. Camera detail panel: the two "Unavailable" sections become real

### What changed

New endpoint. `CameraRead` and `GET /api/cameras/` are **unchanged** — no list payload grew.

```
GET /api/cameras/{camera_id}     →  CameraDetailRead
```

`CameraDetailRead` is `CameraRecord` plus seven fields:

```ts
export interface CameraDetail extends CameraRecord {
  // Convergence — desired vs. applied
  applied_config_version: number | null
  // Engine telemetry
  last_heartbeat_at: string | null
  measured_fps: number | null
  inference_latency_ms: number | null
  last_error_code: string | null
  last_error_message: string | null
  /** Admin only — null for an Operator. Credentials are masked. */
  rtsp_url_redacted: string | null
}

export async function getCamera(cameraId: number): Promise<CameraDetail>
```

`connection_status` and `ai_status` are staleness-presented exactly as the list presents them, so
the panel and the row can never disagree. A soft-deleted or unknown camera is a **404**.

### What to build

`CameraDetailPanel.tsx` currently ships Convergence and Engine telemetry as labelled "Unavailable"
(D-9/D-10). Fetch the detail on open — `useQuery(["camera", id], () => getCamera(id))` — and render
both sections for real. Fetching on open rather than reading the list row is the point: the panel
gets fresh telemetry rather than whatever the table fetched minutes ago.

Every field is nullable by design. A camera the engine has never reported on has `measured_fps:
null`, which is *"no measurement yet"* — not zero. Same null-vs-value discipline as your PR #100
precision fix.

> ### On the RTSP URL — read before rendering it
>
> The route is **operator-visible**, but `rtsp_url_redacted` is **admin-only within it**: an
> Operator gets `200` with that one field `null`. So keep your existing unavailable state for that
> field specifically — do not assume a `null` means the request failed or that the viewer is an
> admin.
>
> It arrives **masked** (`rtsp://***:***@host:port/path`). In production the real URL interpolates
> the VMS username and password, and `08_PKG_backup_ops.md` already forbids any `rtsp://` string
> from leaving the system in an archive for that reason. The masked form still answers the question
> the panel is asking — *is the engine pointed at the right stream?* Do not build anything that
> tries to reconstruct or "un-mask" it, and do not put it in a copy-to-clipboard affordance framed
> as a working connection string.

**Also unblocked:** the per-camera FPS/latency display you deferred out of Phase 10 (System Health)
onto Phase 19's surface. If you still want it on System Health, note it would cost one detail
request per camera — the drawer is the cheaper home for it.

**Files:** `frontend/src/api/cameras.ts`, `frontend/src/pages/cameras/CameraDetailPanel.tsx`.

---

## 2. Alarm settings are now self-describing (Q13)

### What changed

`GET` **and** `PUT /api/settings/alarm` both now return a nested `options` object alongside the
three values:

```diff
 export interface AlarmSettings {
   alarm_sound: string
   volume: number
   snooze_duration: number
+  options: AlarmSettingsOptions
 }
+
+export interface AlarmSettingsOptions {
+  alarm_sound_keys: string[]
+  snooze_min_seconds: number
+  snooze_max_seconds: number
+  volume_min: number
+  volume_max: number
+}
```

Every value is sourced from the backend's own config and field constraints — there is no second copy
of a bound anywhere, which is the whole reason this shipped as a response field rather than as
documentation.

You asked for `GET /api/settings/alarm/options`. It went on the existing response instead: the form
needs values and bounds together, one round trip serves both, and the two can never go stale
relative to each other. Purely additive.

### What to build

- `alarm_sound` becomes a real `<select>` over `options.alarm_sound_keys` instead of the read-only
  field D-3 settled for. Today that array is `["default"]` — a one-option select is the honest
  render, and it grows on its own the day another sound is added.
- `snooze_duration` gets client-side `min`/`max` from `options`, so an operator sees the bound before
  submitting instead of discovering it through a 422. Keep rendering the backend's 422 message as
  the backstop.
- `volume_min`/`volume_max` confirm the 0–100 slider you already built from first principles. Nothing
  to change; they are there so the assumption is no longer an assumption.

> **One thing to fix while you are in the file.** `AlarmSettingsUpdate` is currently
> `export type AlarmSettingsUpdate = AlarmSettings`. That alias breaks now: the **PUT body must not
> carry `options`** — it is read-only, server-owned. Split the two types, with the update type
> keeping exactly the three writable fields. The backend ignores an unexpected `options` key rather
> than rejecting it, so this will not fail loudly if you miss it; it just sends noise.

**Files:** `frontend/src/api/settings.ts`, the alarm settings form.

---

## 3. `snoozed_by` is now a name — **breaking**

### What changed

```diff
 export interface SnoozeActivatedData {
   log_id: number
   camera_id: number
-  snoozed_by: number | null
+  snoozed_by: string | null
   snoozed_until: string
 }
```

The `SNOOZE_ACTIVATED` payload now carries the formatted display name, built by the same
`format_user_name` helper that has always produced `AlertStatusUpdateData.handled_by`. The two events
are now consistent; snooze was the one that was wrong.

This is the change your PR #105 asked for — it records that the phase's own notes assumed a name and
the schema turned out to be an id, and that `GET /api/users/` being admin-only made an id
unresolvable for an Operator. That constraint is gone: **every role now sees the name**, no user
lookup required.

### What to build

- Update the type, and update `asSnoozeActivatedData` in `frontend/src/api/events.ts` — its runtime
  validator currently checks for a number and will reject every real envelope until it checks for a
  string. **This is the one place P21 fails your typecheck**, which is the intended blast radius.
- Render "Muted by {name}" wherever you were rendering the raw id, and drop any admin-only
  conditional you built around resolving it.
- `null` still means "unknown" (the snoozing user was deleted); keep that branch.

**Files:** `frontend/src/api/events.ts`, `GlobalAlerts` and the muted-row description slot.

---

## 4. Export jobs: a real list, and audit filters that survive the round trip

### What changed — the list

```
GET /api/exports/jobs  →  { total_filtered: number, items: ExportJobRead[] }
```

Query params: `status` (repeatable), `limit`, `offset`. Sorted `created_at` descending.
`ExportJobRead` is **unchanged** — same shape your polling already consumes.

- **Scope is the caller's own jobs by default, for every role including Admin.** An admin may pass
  `?all_users=true` to widen; an Operator passing it gets a **403**. The narrow default is
  deliberate — an admin's own tray should answer "where is my export?", not show the whole system's.
- **`expired` jobs are included.** That status is exactly what an operator is investigating when a
  download stops working, so hiding it would answer the question with silence.

### What changed — job creation

`ExportJobCreate` gains `action`, `result` and `target_type` (all `string[] | null`). It is still
`extra: forbid`. An unknown `action` is a 422 against the same 26-entry catalog the synchronous route
validates against, and the filters genuinely reach the worker — the backend has an end-to-end test
asserting the produced artifact contains only the filtered rows, not merely that the field was
accepted.

`POST /api/exports/jobs` with `report_type: "audit"` is now Admin only — a **403** for an Operator,
matching the synchronous `/api/audit-logs/export` route. This closes a gap the same package found
in passing: `/api/audit-logs` itself is Admin only, but the async job path had no equivalent gate, so
an Operator could create (and, as the job's owner, download) an audit-report export. Since your Audit
Log page is already Admin-gated in the UI, no client change is required — this is defensive-in-depth
against a caller that bypasses the UI, not a new state your existing flow needs to render.

### What to build

- `useExportJobsStore` can list account-scoped jobs instead of reconstructing state from
  `localStorage`. Your PR #111 documented that limitation explicitly as browser-scoped rather than
  account-wide; it no longer has to be. Keep the store if you want optimistic local state, but the
  server is now the source of truth and a cleared browser no longer loses a finished export.
- **Drop the Audit Log narrowing.** PR #111 disables the async fallback whenever an
  `action`/`result`/`target_type` filter is active, precisely because the job could not carry those
  and would have exported a different set than the screen showed. The job carries them now.

**Files:** `frontend/src/api/exports.ts`, `frontend/src/store/useExportJobsStore.ts`, the export tray,
`Audit Log`'s `ExportButton` fallback.

---

## Verification

Your usual gate: `tsc --noEmit`, `eslint .`, `pnpm --filter frontend test:run`. §3 will fail the
typecheck until you update both the interface and `asSnoozeActivatedData` — that is the intended
signal, not a merge problem.

Visual baselines are `*-visual-linux.png`, so CI remains the only place that gate means anything, and
both Playwright projects still need `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` on Windows.

---

## What we deliberately did not change

So you are not waiting on any of it:

- **`OUTBOX_QUARANTINED`, `CAPACITY_EXCEEDED`, `ENGINE_CLOCK_SKEW`.** Your PR #104 built a
  forward-compatible renderer for these so they would cost zero frontend work later. Worth knowing:
  those three strings appear **nowhere in this repo** — not in the backend, not in `ai_engine/`, not
  in the planning docs. The backend emits five codes (`GPU_TEMP_CRITICAL`, `RAM_CRITICAL`,
  `DISK_CRITICAL`, `DISK_WARNING`, `AI_HEARTBEAT_STALE`). Your unknown-code fallback means you are
  not blocked, and two of the three would need the AI engine to report state it does not currently
  send — so it is the engine owner's call, not the backend's. The renderer is still worth keeping.
- **Real async export progress.** `progress_total`/`progress_current` are still only set together at
  completion, so the status-badge-not-percentage-bar decision in PR #111 stands. Making progress real
  needs the worker to update the row mid-generation; not a gap you raised, so not done.
- **Cameras KPI period-over-period deltas.** Still no endpoint. Your M2 stays open there — the
  Dashboard cards got deltas in P19, the Cameras cards did not.
- **The two-tab HITL drill** from PR #98 — simultaneous confirm race, backend kill/restart recovery,
  alarm-sound edge trigger across tabs. Still owed, still shared QA against a live stack rather than
  backend code.
