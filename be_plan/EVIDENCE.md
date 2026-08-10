# Performance Evidence

> **10_PKG_migration_evidence.md Step 3.** Every number below is
> **demo-validated on the laptop** described in "Machine spec" — it is not
> proof of production/enterprise-scale capacity (D-009). The paper and
> presentation must present these as measured-on-demo-hardware, distinct
> from the production-target 8×L4 Linux edge server, which remains
> **Needs Evidence** until tested on representative hardware.

## Machine spec

| | |
|---|---|
| Date measured | 2026-08-10 |
| CPU | 12th Gen Intel Core i5-12500H (12 cores / 16 logical processors) |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GB GDDR6 |
| RAM | 16 GB |
| OS | Windows 11 Home Single Language, 64-bit, build 10.0.26200 |
| Python | 3.12.13 |
| SQLite | 3.50.4 |
| Dataset | `backend/scripts/seed_dev_data.py --profile perf` — 100,000 `detection_log` rows, 6 cameras, 4 operators, spread over ~18 months |

This matches D-009's documented demo/development hardware profile exactly.

---

## NFR-08 — the perf dataset itself

`uv run python backend/scripts/seed_dev_data.py --profile perf`

| Metric | Measured |
|---|---|
| Row count | 100,000 |
| Insert time | **33.12s** |
| Throughput | ~3,019 rows/sec |
| Target (doc) | under 2 minutes |

Bulk-inserted via batched `session.execute(insert(DetectionLog), batch)` calls
(2,000 rows/batch) inside a single transaction, not 100,000 ORM objects.

---

## NFR-08 / TC-R-202 — dashboard query < 3s on 100,000 rows

`uv run pytest -m slow backend/tests/perf/test_query_performance.py -s`

| Query | Measured | Budget |
|---|---|---|
| `GET /api/alerts/` (status filter, sorted by `detected_at desc`, `limit=50`) | **0.111s** | 3s |
| `GET /api/analytics/dashboard` | **1.112s** (observed range across runs: 1.1–1.8s) | 3s |

Both comfortably inside budget. The dashboard endpoint is the slower of
the two by roughly an order of magnitude — expected, since it aggregates
across the full dataset rather than returning one filtered page — but
still has ~1.9–2.7x headroom against the 3s NFR even at the high end of
observed variance.

### Query plans — confirming index use (D-005)

```
EXPLAIN QUERY PLAN for /api/alerts/ (status filter + sort):
  SEARCH detection_log USING INDEX ix_detection_status_time (detection_status=?)
  USE TEMP B-TREE FOR ORDER BY

EXPLAIN QUERY PLAN for analytics status/date-range aggregate:
  SEARCH detection_log USING COVERING INDEX ix_detection_status_time (detection_status=? AND detected_at>?)

EXPLAIN QUERY PLAN for per-camera breakdown (camera_id + detected_at):
  SEARCH detection_log USING INDEX ix_detection_camera_time (camera_id=?)
```

No `SCAN detection_log` anywhere — every filtered query path resolves
through a P1 index. The status+sort query falls back to a temp B-tree for
the `ORDER BY` (expected: the covering index is on `(detection_status,
detected_at)`, not `detected_at` alone, once a second status value is
in the `IN (...)` filter) — this is a sort cost, not a scan, and stays
well inside budget as shown above.

---

## NFR-06 / TC-R-203 — export < 5s for a 30-day / ~10,000-row dataset

`uv run pytest -m slow backend/tests/perf/test_export_performance.py -s`

| Export | Window | Rows (approx.) | TTFB | Total | Budget |
|---|---|---|---|---|---|
| CSV | 48 days | ~8,700 | **0.585s** | **0.585s** | 5s |
| PDF | 1 day | ~180 | — | **0.826s** | 5s |
| PDF | 48 days | ~8,700 | — | **35.9s** (35.9–43.0s across runs) | 5s |

CSV streams (D-010) and meets budget with wide margin even at the full
~10,000-row target — TTFB and total are identical because the whole
response is one contiguous stream with no artificial delay between
chunks in this test.

### Real finding: PDF export cannot meet the 5s budget at ~10,000 rows

This is a genuine measured limitation, not a test artifact. Isolating
the three phases of `GET /api/alerts/export?format=pdf` for the 48-day
window (~8,685 rows):

| Phase | Measured |
|---|---|
| DB query (`session.exec(stmt).all()`) | 1.24s |
| Row formatting (`_incident_pdf_row` per row) | 0.06s |
| `fpdf2` `Table` rendering (`build_incident_pdf`) | **43.0s** |

100% of the overrun is in `fpdf2`'s `Table` context manager — the query
and formatting are not the bottleneck. Measured throughput is
roughly 100–200 rows/sec depending on run, well under what's needed to
render a full `EXPORT_PDF_MAX_ROWS=10,000` report in 5 seconds (that would
require ~2,000 rows/sec).

At a realistic single-day filtered report (~180 rows, the shape most real
incident exports actually are), PDF export finishes in well under a
second — the mechanism itself is correct and performant at the scale most
operators would actually request. The gap is specifically the "export the
whole current row-limit ceiling as one PDF" scenario.

**Recorded, not silently dropped**: `backend/tests/perf/
test_export_performance.py::TestIncidentExportLatency::
test_pdf_export_at_10k_row_scale_is_slow` is `xfail(strict=False)` so this
number keeps getting measured on every perf run without permanently
failing CI. This is flagged as an open finding for the team, not treated
as fixed by this package — see the final report's recommendations.
**Recommendation**: lower `EXPORT_PDF_MAX_ROWS` from 10,000 to a value the
laptop can actually render inside 5 seconds (a few hundred to ~1,000
rows, pending a decision on whether async export jobs should absorb the
rest), or revisit the PDF table-rendering approach. Out of scope for P9
to fix — D-010 already provides the async export-job path
(`POST /api/exports/jobs`) for exactly this "too large for synchronous"
case; large PDF requests should probably be steered there rather than
attempted synchronously at all.

---

## NFR-04 / TC-R-201 — alert delivery < 2s

`uv run pytest -m slow backend/tests/perf/test_alert_latency.py -s`

Time from `POST /api/internal/alert` to the `NEW_DETECTION` event arriving
on a connected WebSocket client, against the live 100,000-row database:

| Scenario | Measured | Budget |
|---|---|---|
| Single connected client | **0.016s** | 2s |
| Healthy client, with a second stalled/non-reading client also connected (D-008) | **0.010s** | 2s |

Both are ~100-200x inside budget. The presence of a stalled peer that
never reads from its socket has no measurable effect on the healthy
client's delivery time, confirming D-008's per-connection queue isolation
holds under real HTTP + WebSocket + 100,000-row-database conditions, not
just the synthetic fake-socket unit test in `test_realtime.py`.

---

## Summary against the paper's stated NFRs

| NFR | Target | Measured | Status |
|---|---|---|---|
| NFR-08 (100k-row dataset, query performance) | < 3s | 0.111s (list), 1.112s (dashboard) | ✅ demo-validated |
| NFR-06 (export performance) | < 5s | CSV 0.585s ✅ · PDF 0.826s (realistic size) ✅ · PDF 35.9s (10k-row ceiling) ❌ | ⚠️ partial — see finding above |
| NFR-04 (alert delivery) | < 2s | 0.016s | ✅ demo-validated |
| D-008 (slow-client isolation) | healthy client unaffected | 0.010s, no measurable delay | ✅ demo-validated |

All numbers above are **demo-validated on the laptop described in "Machine
spec"** — they are not evidence of behavior under the paper's enterprise
target (418 cameras, 8×L4 GPU edge server). That gap is explicit and
unavoidable at this stage per D-009; see `be_plan/TRACEABILITY.md` for how
each paper test case's evidence is categorized.
