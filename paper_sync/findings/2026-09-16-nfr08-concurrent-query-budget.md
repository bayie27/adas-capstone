---
section: NFR-08 Database Performance
page/s: "p. 72; p. 172 (native ranges verified 2026-09-16; page mapping uses the cached 2026-09-14 PDF because the fresh export endpoint returned 403)"
required_revision: Separate the 3-second single-request target from the 10-second p95 concurrent-use acceptance budget.
notes: "TC-PERF-012 clean retest returned 20/20 HTTP 200 responses, p95 5.986 s, and maximum 5.991 s on the demo host. TC-PERF-002 is explicitly out of scope for this update. The revised concurrent budget is recorded openly; it is not a hidden status-only change."
status: In progress
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — NFR-08 Database Performance requirement body

Page/s: p. 72; native range `103274–103440`, tab `t.y7ms6bhlk4qn` (`__main__`)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the NFR-08 description cell
Preserve: the NFR-08 heading, table structure, surrounding requirements, and existing typography
Comment target: the complete new NFR-08 description

#### OLD

> The system’s database shall remain responsive with up to 100,000 stored incident records and monitoring data points, with dashboard screens loading within 3 seconds.

#### NEW

The system’s database shall remain responsive with up to 100,000 stored incident records and monitoring data points. Dashboard screens shall load within 3 seconds for a normal single-user request; under the defined 20-request concurrent authenticated-use profile, the 95th-percentile response shall remain within 10 seconds.

#### Evidence

The live paper text was read from the native `__main__` tab on 2026-09-16. The live test tracker `Performance & Load Testing!A13:J13` records the concurrent profile. The clean retest evidence at `var/test-evidence/retest-perf012-20260916.json` records 20/20 HTTP 200 responses, aggregate p95 5.986 seconds, maximum 5.991 seconds, and the revised 10-second concurrent p95 limit. The 3-second single-request target remains separately preserved.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the NFR-08 description cell is the single changed logical unit.

Previous: The system’s database shall remain responsive with up to 100,000 stored incident records and monitoring data points, with dashboard screens loading within 3 seconds.

Codex ID: PS-20260916-NFR08-CONCURRENT-QUERY-BUDGET

Done by Codex.

### 2. Defense paper — Database Technologies, SQLite performance paragraph

Page/s: p. 172; native range `209633–210213`, tab `t.y7ms6bhlk4qn` (`__main__`)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the SQLite selection and NFR-08 performance paragraph
Preserve: the SQLite rationale, WAL discussion in the following paragraph, and surrounding typography
Comment target: the complete new logical paragraph

#### OLD

> SQLite was selected for its serverless, embedded architecture, which reads and writes directly to a single file via an in-process library, eliminating inter-process communication overhead and reducing query latency to that of a local filesystem operation on the edge server's storage. The projected data volumes remain well within SQLite's documented performance thresholds. The non-functional requirement to query up to 100,000 historical incident logs within 3 seconds was met by implementing appropriate indexing on detection status, camera identifier, and timestamp columns.

#### NEW

SQLite was selected for its serverless, embedded architecture, which reads and writes directly to a single file via an in-process library, eliminating inter-process communication overhead and reducing query latency to that of a local filesystem operation on the edge server's storage. The projected data volumes remain well within SQLite's documented performance thresholds. NFR-08 retains a 3-second single-request dashboard target and defines a 10-second 95th-percentile budget for the 20-request concurrent authenticated-use profile. On the demo host, the clean retest returned 20 of 20 HTTP 200 responses with a 5.986-second p95 and 5.991-second maximum. Appropriate indexing on detection status, camera identifier, and timestamp columns supports these query paths.

#### Evidence

The live paper paragraph was read from the native `__main__` tab on 2026-09-16. The isolated retest used 100,000 seeded rows and 20 concurrent authenticated requests with video processing excluded from the API concurrency measurement. The retained single-request 3-second target is covered by the existing slow performance tests; the new 10-second value is the explicitly defined concurrent-use acceptance budget.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the SQLite performance paragraph changes its NFR-08 framing and adds the measured concurrent result.

Previous: SQLite was selected for its serverless, embedded architecture, which reads and writes directly to a single file via an in-process library, eliminating inter-process communication overhead and reducing query latency to that of a local filesystem operation on the edge server's storage. The projected data volumes remain well within SQLite's documented performance thresholds. The non-functional requirement to query up to 100,000 historical incident logs within 3 seconds was met by implementing appropriate indexing on detection status, camera identifier, and timestamp columns.

Codex ID: PS-20260916-NFR08-CONCURRENT-QUERY-BUDGET

Done by Codex.

## Direct-edit status

The two approved NFR-08 replacements were applied to the live native defense paper on 2026-09-16 with a required revision guard and read back from the `__main__` tab. The attached comments were created and verified with provider anchors `AAACHMGPyHE` and `AAACHMGPyHM`; both quoted the exact new text and carry the package ID. The fresh PDF export endpoint returned 403 and its fallback signed URL was stale, so final rendered-page visual QA remains unverified; the cached 2026-09-14 PDF mapped the unchanged target locations to pp. 72 and 172.

The requested ADAS Test Execution tracker rows were applied and read back: `System E2E Testing!F8:J8`, `Performance & Load Testing!D13:J13`, `Performance & Load Testing!D15:J15`, and `Reliability & Endurance!D13:J13`. `Performance & Load Testing!G3:J3` (TC-PERF-002) was read back unchanged and was not included in any write.

## Approval / sync ledger

Package ID: `PS-20260916-NFR08-CONCURRENT-QUERY-BUDGET`
Approval source: User explicitly approved updating the tracker and applying the corresponding paper changes on 2026-09-16; the user requested a 10-second PERF-012 concurrent threshold. The threshold change is recorded transparently rather than concealed.

| Target                              | Approved scope                                                                                                   | Applied/read back                                                                                                | Skipped/pending | Blocked |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------- | ------- |
| Defense paper                       | Blocks 1–2 and attached comments                                                                                 | Blocks 1–2 read back; comments `AAACHMGPyHE` and `AAACHMGPyHM` created/read back with non-empty provider anchors | —               | —       |
| Tracker Sheet — ADAS Test Execution | NFR-08 result and acceptance cells in `Performance & Load Testing!D13:J13`; unrelated `TC-PERF-002` row excluded | Requested rows applied/read back; TC-PERF-002 row confirmed unchanged                                            | —               | —       |
| ADAS_Paper_Audit_Tracker            | No separate live audit-row write requested; local finding records the package                                    | —                                                                                                                | pending         | —       |
| Standalone comments                 | None proposed                                                                                                    | —                                                                                                                | none            | —       |
