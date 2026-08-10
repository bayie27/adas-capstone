# P6 — Reports, Exports, and Retraining Packages

> **Blocked by:** P4 (final filter and response shapes).
> **Branch:** `feat/be-p6-reports`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §§1.4, 1.5, 3.8, 5.10,
> `be_decisions_review.md` D-010.
> **Size:** L. Seven steps.

## Why this package exists

FR-19 requires CSV **and PDF** export of incident records, analytical summaries, and AI performance
datasets, plus a retraining package for off-site model work. Today there is CSV only, no PDF anywhere,
and both export families load the **entire** filtered result set into a `StringIO` and return it as a
single `Response` — `/api/alerts/export` has no limit at all.

There is also a correctness problem worth fixing first: `_validate_common_filters` exists in both
`alerts.py` and `analytics.py` with **different signatures** (`camera_ids` vs `camera_id`, and only
one has a user-id branch), so the same filter can behave differently depending on which endpoint you
hit. D-010 requires an export to match its screen's filters *exactly*.

---

## Step 1 — Shared filter and sort builders

**File:** `backend/app/services/filters.py` (created as a stub in P1 Step 3 — finish it here)

One implementation used by list routes, export routes, and export jobs alike:

```python
@dataclass(frozen=True)
class IncidentFilters:
    start_date: datetime | None
    end_date: datetime | None
    statuses: tuple[DetectionStatus, ...]
    camera_ids: tuple[int, ...]
    user_ids: tuple[int, ...]      # matches verified_by OR closed_by
    search: str | None

def apply_incident_filters(stmt, f: IncidentFilters): ...
def apply_sort(stmt, model, sort_by: str, sort_order: str, allowed: set[str]): ...
```

- `sort_by` outside the per-resource allowlist → `422`. `sort_order` is `asc`/`desc` only. Clients
  never supply raw SQL.
- Datetime bounds go through the P1 `parse_utc_query_datetime` helper.
- Inverted ranges and non-positive ids stay `422` — existing tests cover this, keep them green.
- Analytics status definitions come from one place: accidents = `Ongoing + Resolved`,
  false positives = `Dismissed`, `Unverified` excluded (D-002/D-010).

There is one live SQLite lock-in to note while you are here: `analytics.py` uses
`func.strftime("%H", …)` for the 24-hour peak-times bucket. That is SQLite-only. Leave it — D-005
locks SQLite — but add a comment so nobody is surprised later.

Also fix the current `performance` endpoint's `search` filter, which is applied **in Python** after
fetching rather than in SQL. Move it into the query so filtered exports do not scan everything.

---

## Step 2 — Streaming CSV

**File:** new `backend/app/services/reports/csv_writer.py`

- `StreamingResponse` over a generator, with `session.exec(stmt).yield_per(500)`. Never materialize
  the dataset.
- Deterministic UTF-8, stable documented columns, `\r\n` line endings, BOM only if Excel
  compatibility is required (decide once, document it).
- **Formula-injection neutralization**: any value whose first character is `=`, `+`, `-`, or `@` is
  prefixed with a single quote. Required by D-010 and easy to forget on the "Camera Name" column,
  which is operator-supplied.
- Prefer raw machine-readable values over presentation strings (`0.8734`, not `87.34%`).
- Empty datasets still emit valid headers.
- `snapshot_url` becomes the authorized API path `/api/alerts/{log_id}/snapshot`. The current export
  embeds absolute URLs built from `request.base_url`, which leaked a publicly readable snapshot link;
  P4 removed that mount.

---

## Step 3 — PDF

**File:** new `backend/app/services/reports/pdf_writer.py`. **Dependency:** `fpdf2>=2.8`.

D-010 selects `fpdf2` and explicitly rejects WeasyPrint (its HTML/CSS engine and native graphical
dependencies buy nothing for table reports, and it is painful on Windows).

Shared components — headers, filter summaries, tables, footers, pagination, value formatting — live in
one module so all four reports look like one system.

Every PDF contains (this list is the contract, not a suggestion):

- ADAS title and the branding asset (`frontend/public/adas-logo.png`)
- generated UTC timestamp **and** a configured local-display timestamp
- the requesting user's display identity
- applied filters and sorting, in readable form
- a KPI/summary section where the report has one
- repeated table headings across pages, wrapped cell values, stable `N/A` rendering
- current page and total page count
- a report-specific filename

PDFs never contain credentials, filesystem paths, raw exceptions, or internal configuration.

Four reports: **Incident** (filtered records + HITL lifecycle fields), **Dashboard** (KPIs, location
frequency, peak times), **Performance** (global + per-camera AI metrics), **Audit** (filtered
append-only records).

---

## Step 4 — Export endpoints

Add `?format=csv|pdf` (default `csv`) to all four, sharing Step 1's builders:

```
GET /api/alerts/export
GET /api/analytics/export/dashboard
GET /api/analytics/export/performance
GET /api/audit-logs/export          Admin only
```

Synchronous within the configured limits: PDF 10,000 rows, CSV 50,000 rows. Over the limit →
`413 PAYLOAD_TOO_LARGE` with a body naming `POST /api/exports/jobs` as the alternative.

Every attempt writes `REPORT_EXPORT` (or `AUDIT_EXPORT`) with report type, format, filters, sorting,
row count, sync/job mode, and result.

**The recursion trap:** `AUDIT_EXPORT` must be selected from a stable dataset snapshot taken *before*
its own audit row is committed, so an audit export never contains the record of itself. Materialize
the id range or take the snapshot first — do not stream straight from a live query and commit the
audit row midway.

Also give the four analytics endpoints real `response_model`s. They currently return bare `dict`s, so
OpenAPI documents nothing and the frontend has no contract.

---

## Step 5 — Export jobs

**Files:** new `backend/app/api/routes/exports.py`, `backend/app/services/reports/jobs.py`

```
POST /api/exports/jobs                    -> 202 {job_id, status: "queued"}
GET  /api/exports/jobs/{job_id}           -> status + progress
GET  /api/exports/jobs/{job_id}/download  -> the artifact
```

- One bounded local worker (an `asyncio` task or a single-slot executor) on the demo profile;
  concurrency is configurable for future hardware. **No Celery, no Redis, no broker, no cloud storage**
  — D-010 rejects all of them explicitly.
- Artifacts live under `EXPORT_DIR`, **outside any static mount**. Download requires authorization:
  the requester or an Admin. `artifact_path` is never returned to a client.
- On startup, any job left `processing` by a crash is restarted from the beginning or marked `failed`.
  It must never sit in `processing` forever.
- Artifacts expire after `EXPORT_ARTIFACT_TTL_HOURS` and are deleted by a cleanup job. **Cleanup never
  touches source incidents or snapshots.** The audit record outlives the artifact.
- A successful async audit entry means the artifact was generated and made available — not that a
  browser finished downloading it.

---

## Step 6 — Retraining package

```
POST /api/exports/retraining     Admin only
```

Produces a local ZIP:

```
manifest.csv
snapshots/
```

Only human-labeled incidents are included:

| Status | Label |
|---|---|
| `Ongoing`, `Resolved` | `true_positive` |
| `Dismissed` | `false_positive` |
| `Unverified` | **excluded** |

`manifest.csv` columns: `log_id`, `source_event_id`, camera id and name, `detected_at`,
`confidence_score`, `human_label`, snapshot filename, SHA-256 checksum, availability flag, and
verification/closure metadata.

**Missing snapshots are represented explicitly** in both the manifest and the job result — never
silently omitted (D-010). A row can outlive its file, and whoever retrains the model needs to know.

ZIP entry paths are relative and validated; no absolute paths, no traversal, no symlinks. Everything
stays on the edge server (NFR-20).

---

## Step 7 — Screen/export parity tests

D-010's core requirement is that an export matches the screen exactly. Write a parametrized test that,
for a matrix of filter combinations, calls the list endpoint and the export endpoint with identical
parameters and asserts the same row ids in the same order. Cover: date range, status multi-select,
camera multi-select, user multi-select, search, each allowed `sort_by`, both `sort_order` values, and
a few combinations.

---

## Verification

```bash
uv run pytest backend/tests/test_reports.py backend/tests/test_exports.py
```

Manually:

1. Export 10,000 incidents as CSV → download starts within 5 seconds (NFR-06 / TC-R-203) and memory
   stays flat, proving it streams. Record the measured number; P9 collects it as evidence.
2. Export the same as PDF → opens cleanly, headers repeat on every page, page numbers are right, the
   filter summary matches what you asked for.
3. Seed a camera named `=cmd|'/c calc'!A1`, export CSV, open in Excel → **no formula executes**.
4. Request an export above the row limit → `413` naming the jobs endpoint.
5. Create an export job, poll it to `completed`, download it. Try downloading as a different
   non-admin user → `403`.
6. Run the retraining export with one snapshot file deleted → the manifest marks it unavailable and
   the job still completes.
7. Export the audit log → the export's own `AUDIT_EXPORT` row is **not** in the file.
8. `pnpm check`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Filter parity | list and export return identical ids and order across the filter matrix |
| Sorting | disallowed `sort_by` → 422; each allowed field sorts both directions |
| CSV escaping | quotes, commas, newlines, unicode; `=`/`+`/`-`/`@` neutralized |
| CSV streaming | the response is a generator; memory does not scale with row count |
| Empty datasets | header-only CSV, valid PDF with an empty-state section |
| PDF parsing | with `pypdf`: title, metadata, page count, repeated headings, filter summary present, **no filesystem path anywhere in the text** |
| Row limits | PDF at 10,000 and 10,001; CSV at 50,000 and 50,001 |
| Job lifecycle | queued → processing → completed; failure sets a safe category and no traceback |
| Job restart | a `processing` job at startup is restarted or failed, never left hanging |
| Job authz | non-owner non-admin → 403 |
| Artifact expiry | expired artifact deleted, job marked `expired`, audit row survives, **source snapshots untouched** |
| Retraining | label mapping, `Unverified` excluded, checksums correct, missing snapshot reported, no absolute paths in the ZIP |
| Audit recursion | an audit export does not contain its own row |
| Audit export RBAC | Operator → 403 |

## Paper test cases covered

FR-14, FR-17, FR-18, FR-19. TC-I-403 (filters → CSV/PDF → streamed payload), TC-I-305 (dashboard KPIs
via `COUNT`/`GROUP BY`), TC-S-301 (overlapping Date + Status + Camera filters intersect correctly),
TC-R-203 (5-second export of a 30-day / ~10,000-record dataset — measured, not assumed).

## Deliberately not in this package

Backup archives (P7 — a different concern from report exports), Help Center (P8), the 100k-row
performance seed and its measured evidence (P9).
