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
| Date measured | 2026-08-10 (initial pass); refreshed 2026-08-11 post-A1–A4 (`be_audit/A6_manual_evidence.md`) |
| CPU | 12th Gen Intel Core i5-12500H (12 cores / 16 logical processors) |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GB GDDR6 |
| RAM | 16 GB |
| OS | Windows 11 Home Single Language, 64-bit, build 10.0.26200 |
| Python | 3.12.13 |
| SQLite | 3.50.4 |
| Dataset | `backend/scripts/seed_dev_data.py --profile perf` — 100,000 `detection_log` rows, 6 cameras, 4 operators, spread over ~18 months |

This matches D-009's documented demo/development hardware profile exactly.

**A6 re-run note**: the first re-run attempt (2026-08-11) measured the
dashboard query at 4.779s — a real 3s-budget failure. Investigation
found the cause immediately: the LAN/TLS demo stack (mediamtx + 5 ffmpeg
feeds + the AI engine doing live TensorRT inference + the backend + the
frontend dev server) was still running in the background from this same
session's A6 manual drills, competing for the same 12-core/4GB-VRAM
laptop. Stopping that stack and re-running reproduced the original
~1.1–2.0s range immediately — **void, not a finding**: an artifact of
this session's own concurrent load, not a regression. Recorded here so a
future reader doesn't re-raise it. All numbers below are from the
stack-quiet re-run.

---

## NFR-08 — the perf dataset itself

`uv run python backend/scripts/seed_dev_data.py --profile perf`

| Metric | Measured |
|---|---|
| Row count | 100,000 |
| Insert time | **33.12s** (2026-08-10; not re-measured 2026-08-11 — the perf-test fixture bulk-inserts the same row set in-process rather than re-invoking the standalone script) |
| Throughput | ~3,019 rows/sec |
| Target (doc) | under 2 minutes |

Bulk-inserted via batched `session.execute(insert(DetectionLog), batch)` calls
(2,000 rows/batch) inside a single transaction, not 100,000 ORM objects.

---

## NFR-08 / TC-R-202 — dashboard query < 3s on 100,000 rows

`uv run pytest -m slow backend/tests/perf/test_query_performance.py -s`

| Query | Measured (2026-08-11) | Budget |
|---|---|---|
| `GET /api/alerts/` (status filter, sorted by `detected_at desc`, `limit=50`) | **0.188s** (observed range across runs: 0.12–0.47s) | 3s |
| `GET /api/analytics/dashboard` | **2.003s** (observed range across runs: 1.2–2.0s) | 3s |

Both comfortably inside budget. The dashboard endpoint is the slower of
the two by roughly an order of magnitude — expected, since it aggregates
across the full dataset rather than returning one filtered page — but
still has headroom against the 3s NFR even at the high end of observed
variance. The wider variance than the 2026-08-10 pass (previously 1.1–1.8s)
tracks background load on the laptop between runs, not a code change —
see the re-run note above.

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

## NFR-06 / TC-R-203 — export < 5s, real operating envelope (primary evidence)

**Owner decision (`be_audit/A6_manual_evidence.md` Part 2):** the real
operating envelope is **~10 incidents/day** — already generous for Lipa
CDRRMO's estimate. A 30-day export is therefore **~300 rows**, not the
paper's literal ~10,000. This is now the **primary** NFR-06 evidence;
the paper's literal 10,000-row framing is disregarded as a requirement
(but not deleted as a measurement — see "10,000-row ceiling" below).

`uv run pytest -m slow backend/tests/perf/test_export_performance.py -k operating_envelope -s`,
against a dedicated ~10/day-density dataset (`envelope_seeded` fixture,
`backend/tests/perf/conftest.py`) — **not** a date-filtered slice of the
100,000-row/~182-per-day perf dataset used elsewhere in this file.

| Export | Window | Rows | Measured (2026-08-11) | Budget |
|---|---|---|---|---|
| CSV | 30 days | 300 | **0.052s** | 5s |
| PDF | 30 days | 300 | **2.750s** | 5s |

Both pass with real margin at the envelope that actually matters —
CSV with ~100x headroom, PDF with ~1.8x headroom (materially less
comfortable than CSV, but a real pass, not a near-miss requiring a
caveat).

### 10,000-row ceiling (retained, not a requirement)

The paper's literal ~10,000-row framing no longer describes the real
operating envelope, but the measurement is kept as a documented
**ceiling** — a panel asking "what happens if someone exports a year?"
deserves the real answer, and deleting an inconvenient measurement would
undermine the whole evidence file.

`uv run pytest -m slow backend/tests/perf/test_export_performance.py -s`

| Export | Window | Rows (approx.) | TTFB | Total | Budget |
|---|---|---|---|---|---|
| CSV | 48 days | ~8,700 | **0.537s** | **0.537s** | 5s |
| PDF | 1 day | ~180 | — | **1.031s** | 5s |
| PDF | 48 days | ~8,700 | — | **48.4s** (2026-08-10 range was 35.9–43.0s) | 5s |

CSV streams (D-010) and meets budget with wide margin even at the full
~10,000-row ceiling — TTFB and total are identical because the whole
response is one contiguous stream with no artificial delay between
chunks in this test.

**PDF at the 10,000-row ceiling still cannot meet the 5s budget** —
48.4s measured 2026-08-11, consistent with (slightly higher than) the
35.9–43.0s range from 2026-08-10; the gap is `fpdf2`'s `Table` renderer,
not the query or row-formatting phases (see the 2026-08-10 phase
isolation below, not re-run this pass since no code on that path
changed). This is now explicitly a **ceiling measurement, not a failed
requirement** — see the re-scope above. `EXPORT_PDF_MAX_ROWS` stays at
10,000 per owner decision (`be_audit/A6_manual_evidence.md` "Open,
owner's call"); a request between ~2,000 and 10,000 rows can still take
tens of seconds synchronously, which is out of expected use under the
~10/day envelope rather than fixed. The async job path
(`POST /api/exports/jobs`, D-010) has no such row ceiling and is the
intended route for anything beyond a routine report.

`backend/tests/perf/test_export_performance.py::TestIncidentExportLatency::
test_pdf_export_at_10k_row_scale_is_slow` stays `xfail(strict=False)` so
this number keeps getting measured on every perf run without permanently
failing CI.

#### 2026-08-10 phase isolation (for context, not re-measured)

Isolating the three phases of `GET /api/alerts/export?format=pdf` for the
48-day window (~8,685 rows), as measured 2026-08-10:

| Phase | Measured |
|---|---|
| DB query (`session.exec(stmt).all()`) | 1.24s |
| Row formatting (`_incident_pdf_row` per row) | 0.06s |
| `fpdf2` `Table` rendering (`build_incident_pdf`) | **43.0s** |

100% of the overrun was in `fpdf2`'s `Table` context manager — the query
and formatting are not the bottleneck. Measured throughput was roughly
100–200 rows/sec, well under what's needed to render a full
`EXPORT_PDF_MAX_ROWS=10,000` report in 5 seconds (that would require
~2,000 rows/sec).

---

## NFR-04 / TC-R-201 — alert delivery < 2s

`uv run pytest -m slow backend/tests/perf/test_alert_latency.py -s`

Time from `POST /api/internal/alert` to the `NEW_DETECTION` event arriving
on a connected WebSocket client, against the live 100,000-row database:

| Scenario | Measured (2026-08-11) | Budget |
|---|---|---|
| Single connected client | **0.020s** | 2s |
| Healthy client, with a second stalled/non-reading client also connected (D-008) | **0.010s** | 2s |

Both are ~100-200x inside budget. The presence of a stalled peer that
never reads from its socket has no measurable effect on the healthy
client's delivery time, confirming D-008's per-connection queue isolation
holds under real HTTP + WebSocket + 100,000-row-database conditions, not
just the synthetic fake-socket unit test in `test_realtime.py`.

### LAN-measured NFR-04 — attempted 2026-08-17, still not captured

The two-machine drill (`LAN_DEMO_HANDOFF.md`, logged in
`be_audit/DEMO_TOPOLOGY.md` §11) finally ran on real hardware, closing
the physical-execution gap this section used to describe. NFR-04
specifically is still not captured, for two independent reasons found
while genuinely trying:

1. **Clock alignment.** `w32tm /resync` needed an elevated shell that
   wasn't available in that session; the server's un-resynced NTP status
   showed a root dispersion of ~8s — far too loose to support the
   sub-second figure this metric needs.
2. **The one non-destructive measurement method attempted broke instead
   of measuring.** Since the `NEW_DETECTION` WebSocket payload already
   carries the backend's own `occurred_at` timestamp, and Chrome
   DevTools already timestamps every frame's arrival, a small
   console-only patch (no app code touched) was tried: wrap
   `window.WebSocket` in a `Proxy` so every message's client-side
   receive time gets logged next to its server-side `occurred_at`, using
   the `CONNECTION_READY` handshake as a self-calibrating clock-skew
   reference point. On reload, this broke the live WebSocket connection
   entirely (`/ws/alerts` failed with "closed before the connection is
   established", and Vite's own HMR socket failed too) rather than
   producing a number — proxying the native `WebSocket` constructor
   isn't safe in this browser. Reverted via a hard reload, which
   restored the connection cleanly with no lasting effect.

Rather than force a number from a method that had just demonstrably
failed, or fall back to a human eyeballing two screens (which wouldn't
have supported sub-second precision either), this is recorded honestly
as **not captured**. What can be said honestly: during the same drill,
live detections rendered on the client's screen with no perceptible lag
after occurring — a qualitative floor, not a number to publish as
NFR-04.

`be_audit/A6_manual_evidence.md` originally asked for an end-to-end
alert latency figure measured **over the network to a second laptop**,
on the theory that A1's LAN/TLS drill produced one. It didn't: A1's own
resolution log (`be_audit/00_FINDINGS.md`) states plainly that session
"ran on a single physical machine," and the two-laptop physical steps
were **not executed** in that pass — they finally were in the
2026-08-17 drill above, just without a usable NFR-04 number.

The best available data point beyond the `TestClient`-based numbers
above is still A3's live seam drill (`be_audit/00_FINDINGS.md`, A3
resolution log, 2026-08-10): a real running backend + AI engine +
WebSocket client over **loopback** (not `TestClient`, not a second
machine) measured **~0.53s** and **~0.84s** from detection to
`NEW_DETECTION` delivery — still comfortably under the 2s budget, and a
materially more realistic number than a `TestClient` measurement since
it exercises the real ASGI server and a real OS socket. Treat it as a
floor, not the LAN number. A genuine two-laptop measurement remains
owed — see `be_audit/DEMO_TOPOLOGY.md` §11 for what was tried and why
it didn't land.

---

## Summary against the paper's stated NFRs

| NFR | Target | Measured (2026-08-11) | Status |
|---|---|---|---|
| NFR-08 (100k-row dataset, query performance) | < 3s | 0.188s (list), 2.003s (dashboard) | ✅ demo-validated |
| NFR-06 (export performance, real ~10/day envelope) | < 5s | CSV 0.052s ✅ · PDF 2.750s ✅ (both at the 300-row/30-day envelope that matters) | ✅ demo-validated at the real envelope |
| NFR-06 (10,000-row ceiling, retained for context) | < 5s | CSV 0.537s ✅ · PDF realistic (~180 rows) 1.031s ✅ · PDF 10k-row ceiling 48.4s ❌ | ⚠️ documented ceiling, not a requirement under the re-scope |
| NFR-04 (alert delivery, `TestClient`) | < 2s | 0.020s | ✅ demo-validated |
| NFR-04 (alert delivery, real loopback process) | < 2s | ~0.53–0.84s | ✅ demo-validated (loopback, not LAN — see note above) |
| NFR-04 (alert delivery, real two-laptop LAN) | < 2s | not captured (drill ran 2026-08-17; qualitative: no perceptible lag) | ⚠️ drill executed, no defensible number — see note above |
| D-008 (slow-client isolation) | healthy client unaffected | 0.010s, no measurable delay | ✅ demo-validated |

All numbers above are **demo-validated on the laptop described in "Machine
spec"** — they are not evidence of behavior under the paper's enterprise
target (418 cameras, 8×L4 GPU edge server). That gap is explicit and
unavoidable at this stage per D-009; see `be_plan/TRACEABILITY.md` for how
each paper test case's evidence is categorized.
