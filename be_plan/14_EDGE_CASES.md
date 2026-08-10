# Edge Case Register

> **Cross-cutting.** Not a work package — a checklist every package is reviewed against.
> Each package doc has its own "Tests to write" table covering *that package's* core behaviours.
> This document covers the categories that cut across all of them, which is where production bugs
> actually live.

## On the testing policy

`CLAUDE.md` says *"test when it's needed, don't overdo it… don't chase a coverage number."* That is
still right, and this document is not a contradiction of it. The distinction:

- **Chasing coverage** = writing tests for happy-path permutations that a single test already proves.
  Don't.
- **Edge cases** = boundaries, races, failure paths, and hostile input. This is where a system that
  demos perfectly falls over in production. Do.

A backend that a CDRRMO operations centre runs 24/7 against 418 cameras needs the second kind. P9
should update the `CLAUDE.md` testing-policy bullet to say exactly this.

**How to use this:** before declaring a package done, walk the rows tagged with that package. Skip a
row only if it is genuinely inapplicable, and say so in your report rather than silently dropping it.

---

## 1. Concurrency and races

The system has three concurrent actors — multiple operators, the AI engine, and scheduler jobs — all
mutating the same rows. Everything here is realistic, not contrived.

| # | Case | Pkg | Why it matters |
|---|---|---|---|
| 1.1 | Two operators confirm + dismiss the same incident simultaneously | P4 | Exactly one wins; the loser gets `409` with the winner's identity. The current read-then-write code lets both succeed |
| 1.2 | Two operators resolve the same `Ongoing` incident | P4 | Same rule; second gets `409` |
| 1.3 | Snooze racing a Confirm | P4 | Snooze must lose cleanly with `409`, not leave a snooze on an `Ongoing` incident |
| 1.4 | Re-snooze racing the previous snooze's expiry job | P4 | The expiring job must find a future deadline and do nothing. **Zero `RE_ALARM` events**, not two |
| 1.5 | Two AI events for one camera arriving simultaneously | P4 | `ux_detection_open_camera` rejects the second; it becomes `409`, not a 500 |
| 1.6 | The same `source_event_id` posted twice concurrently | P4 | One `201`, one `200`, one row. Test with genuinely parallel requests, not sequential |
| 1.7 | **AI event arriving while an operator disables that camera** | P4 | Not covered in the package doc. Either outcome is acceptable — incident created then camera goes `Inactive`, or `404` — but it must not deadlock, orphan, or 500 |
| 1.8 | Cooldown job firing while a new incident opens on that camera | P4 | `recompute_desired_state` must keep it `Paused` with reason `incident`, not resume it |
| 1.9 | Camera soft-deleted while its cooldown job is pending | P4 | Job runs, finds `is_active=0`, sets `Inactive`, does not resurrect it |
| 1.10 | Session revoked mid-request | P2 | An in-flight request completes or fails cleanly. The *next* one is 401. No half-applied writes |
| 1.11 | Same user logging in twice | P2 | Two independent sessions. Revoking one must not touch the other |
| 1.12 | **Restore requested while a backup is running** | P7 | Not covered. Must be `409 CONFLICT_BUSY` — a restore mid-backup would capture a torn state |
| 1.13 | Backup running during heavy incident ingestion | P7 | Already in the doc; keep it. This is the NFR-18 claim |
| 1.14 | **Export artifact cleanup firing while a download is streaming** | P6 | Not covered. Deleting a file mid-stream must not 500 the client or leave a zombie job |
| 1.15 | Two export jobs for the same user at once | P6 | Bounded worker queues them; neither is lost |
| 1.16 | WebSocket broadcast during a client disconnect | P3 | Enqueue to a closing connection must not raise into the broadcaster |
| 1.17 | Hourly rollup running twice for the same hour | P5 | Already covered via the `hour_start` unique key; keep it |
| 1.18 | Two heartbeats from different engine instances | P4 | Last write wins per camera, no corruption. Real if someone starts the engine twice by accident |

---

## 2. Boundary values

Test the value **at** the boundary and **one past it**, on both sides. Off-by-one at a boundary is
the single most common validation bug.

| # | Field | Boundary | Pkg |
|---|---|---|---|
| 2.1 | `limit` | 0 → 422, 1 → ok, 100 → ok, 101 → 422 | P4, P6 |
| 2.2 | `offset` | −1 → 422, 0 → ok, beyond total → empty page with correct `total_filtered` | P4, P6 |
| 2.3 | `confidence_score` | 0.0 ok, 1.0 ok, −0.001 and 1.001 rejected by the DB CHECK | P1 |
| 2.4 | `snooze_duration` | 14 → 422, **15 → ok**, **60 → ok**, 61 → 422 | P4 |
| 2.5 | `volume` | −1 → 422, 0 → ok, 100 → ok, 101 → 422 | P4 |
| 2.6 | `channel_id` | 0 → rejected, 1 → ok, negative → rejected | P1 |
| 2.7 | `username` | 2 → 422, 3 → ok, 20 → ok, 21 → 422 | P2 |
| 2.8 | `first_name` / `last_name` | 0 → 422, 1 → ok, 20 → ok, 21 → 422 | P2 |
| 2.9 | `password` | 7 → 422, 8 → ok, 128 → ok, 129 → 422; exactly-one-digit passes | P2 |
| 2.10 | `camera_name` | 0 → 422, 1 → ok, 100 → ok, 101 → 422 | P4 |
| 2.11 | Date range | `start == end` → valid, returns that instant's rows; `start > end` → 422 | P4, P6 |
| 2.12 | `cooldown_until` | exactly `== now` → treated as expired, camera resumes | P4 |
| 2.13 | `snoozed_until` | exactly `== now` → due, fires once | P4 |
| 2.14 | Raw retention | exactly 48h old → pruned; 47h59m → kept | P5 |
| 2.15 | Hourly retention | exactly 30d old → pruned; 29d23h → kept | P5 |
| 2.16 | Session expiry | at `expires_at` exactly → rejected | P2 |
| 2.17 | Export row limits | 10,000 PDF ok / 10,001 → 413; 50,000 CSV ok / 50,001 → 413 | P6 |
| 2.18 | Heartbeat staleness | exactly 10s → `Unresponsive`; 9.9s → fresh | P4, P5 |

---

## 3. Empty, null, and degenerate states

Every list and aggregate needs a zero-rows path. These are cheap tests and they catch division bugs
and `None` crashes that only appear on a freshly deployed system — i.e. on demo day.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 3.1 | Analytics with **zero** incidents | P6 | KPIs are 0, `precision_score` is `null` (never `0`), all 24 hour buckets present and zeroed |
| 3.2 | Analytics with only `Unverified` incidents | P6 | Same as 3.1 — `Unverified` is excluded from every analytics number |
| 3.3 | Precision when confirmed = 0 and dismissed = 0 | P6 | `null`, not `0`, not a `ZeroDivisionError` |
| 3.4 | Precision when confirmed = 0 and dismissed > 0 | P6 | `0.0` — this one *is* zero, and it differs from 3.3 |
| 3.5 | Camera with zero incidents in the performance breakdown | P6 | Appears with null confidence averages, not omitted |
| 3.6 | Zero cameras registered | P4, P5 | KPI invariants still hold with all counts 0; heartbeat returns an empty snapshot |
| 3.7 | Export with zero matching rows | P6 | Valid header-only CSV; valid PDF with an empty-state section and correct page count |
| 3.8 | Help search matching nothing | P8 | Empty `items`, populated `top_faqs` |
| 3.9 | Help search with an empty string | P8 | Returns all role-visible articles, not an error |
| 3.10 | System health with no GPU present | P5 | Empty per-GPU list, null aggregates, still `200` |
| 3.11 | System health before the first sample completes | P5 | Explicit "no sample yet" state, not nulls masquerading as readings |
| 3.12 | History range containing a collection gap | P5 | Missing points, **never zeros** |
| 3.13 | Hourly rollup for an hour with zero raw rows | P5 | No row created. `sample_count` never 0 |
| 3.14 | Audit viewer on a fresh database | P2 | Empty page, correct `total_filtered`, no crash |
| 3.15 | Incident whose snapshot file was deleted | P4, P6 | Detail returns fine; `/snapshot` returns `404`; retraining manifest marks it unavailable |
| 3.16 | Backup list with zero backups | P7 | Empty list; restore of a nonexistent id → `404` |

---

## 4. Hostile and malformed input

Operator-supplied strings reach a CSV, a PDF, a log line, a filesystem path, and an FTS5 query. Each
is a different injection surface.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 4.1 | Camera named `=cmd\|'/c calc'!A1` | P6 | Neutralized in CSV. Already in the doc; keep it |
| 4.2 | Same name rendered into a PDF | P6 | Renders as text, does not break `fpdf2` layout |
| 4.3 | Camera name with a newline or embedded `"` | P6 | Correctly quoted in CSV; wrapped in PDF |
| 4.4 | Unicode names: emoji, RTL marks, combining characters, zero-width joiners | P4, P6 | Stored, returned, exported, and PDF-rendered without mojibake or crash. `fpdf2` needs a Unicode-capable font — verify this early, the default font is Latin-1 only |
| 4.5 | Name that is exactly max length in **characters** but longer in bytes | P1 | Length validation counts characters consistently |
| 4.6 | Null byte (`\x00`) in any string field | P1 | Rejected, not stored — SQLite will happily truncate at it |
| 4.7 | Leading/trailing whitespace and Unicode whitespace in `username` | P2 | Stripped consistently; `" admin "` cannot become a second account |
| 4.8 | SQL injection strings in `search` params | P4, P6 | The ORM parameterizes, but write one test per search endpoint as evidence — the paper tests this at the login form |
| 4.9 | `snapshot_key` traversal: `../../../.env`, `/etc/passwd`, `C:\Windows\win.ini`, `..%2f..%2f`, UNC `\\host\share`, and a symlink pointing outside the root | P4 | All rejected. Already in the doc — keep every variant |
| 4.10 | `backup_id` traversal, same variants | P7 | Rejected before any filesystem access |
| 4.11 | ZIP entry paths in the retraining package | P6 | Relative only; no absolute paths, no `..`, no symlinks |
| 4.12 | FTS5 metacharacters in help search: `"`, `*`, `NEAR(a b)`, `OR`, unbalanced quotes | P8 | Clean empty result, never a 500 |
| 4.13 | Extremely long `search` string (10 KB) | P4, P6, P8 | Rejected or handled; no timeout |
| 4.14 | Malformed JSON body, wrong content type, missing required field | all | `422` with the `VALIDATION_ERROR` envelope, never a 500 |
| 4.15 | Extra unexpected fields in a request body | all | Ignored or rejected — pick one and be consistent |
| 4.16 | Heartbeat reporting an unknown `camera_id` | P4 | Ignored, not an error |
| 4.17 | Heartbeat with `measured_fps` negative or absurd (1e9) | P4 | Rejected or clamped; never poisons the health averages |
| 4.18 | AI error message containing a credential-bearing URL | P4 | Redacted before storage in `last_error_message` |

---

## 5. Time, clocks, and timezones

The AI engine currently sends **naive local time**. The backend stores UTC. Scheduler jobs run in
UTC except the maintenance window, which is deliberately local. That is three time domains in one
system.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 5.1 | Query param with `+08:00` offset | P1 | Converted to UTC. **This is a live bug today** — the offset is stripped, giving an 8-hour window error |
| 5.2 | Query param with no offset | P1 | Interpreted as UTC, documented in the OpenAPI description |
| 5.3 | Query param with `Z` suffix | P1 | Same as `+00:00` |
| 5.4 | Naive datetime reaching the DB layer | P1 | Raises. Loud failure beats silent corruption |
| 5.5 | **`detected_at` in the future** (AI clock ahead) | P4 | Not covered in the package doc. Decide and test: reject, clamp to now, or accept with a warning. Currently it would silently sort above everything else forever |
| 5.6 | `detected_at` far in the past (engine replaying an old outbox after a long outage) | P4 | Accepted — an outbox drain after a 2-hour network failure is legitimate |
| 5.7 | Incident exactly at a UTC hour boundary | P5, P6 | Lands in exactly one hourly bucket, not zero and not two |
| 5.8 | Rollup at midnight UTC | P5 | Correct date attribution |
| 5.9 | Peak-hours bucket at 00:00 and 23:00 | P6 | Both present; all 24 buckets always returned |
| 5.10 | `MAINTENANCE_HOUR_LOCAL` across a DST transition | P7 | The Philippines has no DST, so this is inert *there* — but assert the behavior is defined rather than accidental, since the code is portable |
| 5.11 | Scheduler misfire after a system suspend/resume | P4, P5, P7 | Coalescing means one catch-up run, not a burst of backlogged firings |
| 5.12 | Server clock stepping backwards | P4 | A snooze deadline in the future stays pending rather than firing repeatedly |

---

## 6. Failure injection and resource exhaustion

Nothing here is exotic. Every one of these has a plausible cause on a 24/7 edge server.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 6.1 | SQLite lock timeout | P1 | `503 TEMPORARILY_UNAVAILABLE`, logged, never a hang |
| 6.2 | **Unhandled exception inside a scheduler job** | P1 | Not covered. APScheduler must log it and **keep the job scheduled** — one bad run must not silently kill snooze expiry or health collection for the rest of the process lifetime. This is a high-consequence, easy-to-miss failure |
| 6.3 | Scheduler job overrunning its interval | P5 | `max_instances=1` prevents pile-up |
| 6.4 | Disk full during a snapshot write | P4 | Incident is not created, or is created and flagged — but never committed pointing at a truncated file |
| 6.5 | Disk full during an export | P6 | Job fails with a safe category; partial artifact removed |
| 6.6 | Disk full during a backup | P7 | Already covered; aborts before starting, prior backups intact |
| 6.7 | NVML unavailable or raising mid-run | P5 | Degrades to no-GPU; other metrics still returned |
| 6.8 | `psutil` raising on a single reading | P5 | That metric unavailable; endpoint still `200` |
| 6.9 | Snapshot root unwritable at startup | P1 | Clear startup failure, not a per-request 500 |
| 6.10 | **Rate-limiter key dictionary growth** | P2 | Not covered. Distinct usernames and IPs must not accumulate unboundedly — expire entries past the window. A slow credential-stuffing attempt is a memory leak otherwise |
| 6.11 | WebSocket queue overflow | P3 | Already covered — closes that connection only |
| 6.12 | Many simultaneous WebSocket connections | P3 | Limit enforced; established dashboards never displaced |
| 6.13 | Client disconnecting mid-CSV-stream | P6 | Generator closed, session released, no leaked connection |
| 6.14 | Backend restart with export jobs `processing` | P6 | Restarted or failed — never left `processing` forever |
| 6.15 | Backend restart mid-cooldown | P4 | Already covered and mandatory. The headline durability fix |
| 6.16 | Backend restart with active snoozes | P4 | Unexpired rescheduled; expired cleared and alarm-active |
| 6.17 | FTS5 unavailable in the SQLite build | P8 | Falls back to `LIKE` with a logged warning; app still starts |
| 6.18 | Restore failing at the readiness gate | P7 | Automatic rollback to the emergency backup. Already covered and mandatory |
| 6.19 | AI engine down for an extended period | P4, P5 | Cameras present as `Unresponsive`; health reports `sample_camera_count: 0`; no crash, no runaway logging |

---

## 7. State machine exhaustiveness

Four statuses give sixteen ordered pairs. Four are legal. **Parametrize the other twelve** — including
self-transitions — and assert every one is rejected with the right code.

| From \ To | Unverified | Ongoing | Dismissed | Resolved |
|---|---|---|---|---|
| **Unverified** | reject | ✅ confirm | ✅ dismiss | reject |
| **Ongoing** | reject | reject | ✅ correction | ✅ resolve |
| **Dismissed** | reject | reject | reject | reject |
| **Resolved** | reject | reject | reject | reject |

Also assert, for each of the four legal transitions: the audit action is the right one of
`ALERT_CONFIRM` / `ALERT_DISMISS` / `ALERT_RESOLVE` / `ALERT_CORRECTION`; the correct actor field is
populated per §10.1 of the contracts doc; `detected_at` and `created_at` are never modified; snooze
fields are cleared; and the camera desired state matches the §10.2 table.

Terminal states have no reopen path and no edit or delete API. Assert that too — the absence of a
route is a requirement (D-002), not an omission.

---

## 8. Authentication attacks

The paper's TC-S-2xx cases cover the basics. These are the ones a security review asks about.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 8.1 | **JWT with `alg: none`** | P2 | Rejected. Classic algorithm-confusion bypass — `jwt.decode` must pass an explicit `algorithms=` list |
| 8.2 | JWT signed with a different key | P2 | Rejected |
| 8.3 | JWT with wrong `iss` or wrong `aud` | P2 | Rejected. Only fails if `issuer=`/`audience=` are actually passed to `decode` — writing the claims without verifying them is the common mistake |
| 8.4 | JWT missing the `sid` claim | P2 | Rejected, not treated as sessionless-but-valid |
| 8.5 | JWT whose `sid` belongs to a **different** `sub` | P2 | Rejected |
| 8.6 | Valid JWT, session row deleted / revoked / expired | P2 | Rejected in all three cases |
| 8.7 | Empty or malformed cookie value | P2 | `401`, not a 500 |
| 8.8 | Login timing for unknown vs known username | P2 | Comparable — verify a dummy hash on the not-found path so timing does not enumerate accounts |
| 8.9 | Response body identical for unknown user / wrong password / inactive account | P2 | Byte-identical. The current code returns a distinguishable `400` for inactive |
| 8.10 | Role escalation via `PATCH /api/users/me` | P2 | The schema has no `role` field; assert it is ignored, not applied |
| 8.11 | Operator hitting every admin route | P2 | `403` before any payload processing (TC-U-204) |
| 8.12 | Cookie-auth unsafe method with a foreign `Origin` | P2 | `403 ORIGIN_REJECTED` |
| 8.13 | Missing `x-api-key` on `/api/internal/*` | P1 | `401`, not `422`. Currently returns `422` |
| 8.14 | Wrong `x-api-key` | P1 | `401`, constant-time comparison |
| 8.15 | Password reset does not leak the old hash or the new password into audit `detail` | P2 | Redacted |
| 8.16 | Last-admin guards: demote, deactivate, delete, and **self-delete** | P2 | All refused, all audited as `denied` |

---

## 9. Soft delete and referential edges

`is_active` on users and cameras exists so history survives deletion (D-005). That creates a class of
edges where a row is invisible but still referenced.

| # | Case | Pkg | Expected |
|---|---|---|---|
| 9.1 | Incident verified by a **since-deactivated** user | P4, P6 | Detail and export still render that user's name from the FK; the row is not orphaned |
| 9.2 | Audit row for a since-renamed user | P2 | Shows the `username` snapshot from the time of the action, not the current name |
| 9.3 | Creating a camera reusing a **soft-deleted** camera's name | P1, P4 | Succeeds. This is currently an unhandled `IntegrityError` → 500 |
| 9.4 | Creating a camera reusing a soft-deleted camera's `channel_id` | P1, P4 | Succeeds |
| 9.5 | Two soft-deleted cameras with the same name | P1 | Allowed — the unique index is partial on `is_active = 1` |
| 9.6 | Soft-deleting a camera with an open incident | P4 | Refused with `400 PRECONDITION_FAILED`. Otherwise the incident is unreachable and the partial index blocks that camera forever |
| 9.7 | Soft-deleted camera still appearing in historical analytics | P6 | Yes — history must not change when a camera is removed |
| 9.8 | Soft-deleted camera excluded from KPI counts | P5 | Yes — all four invariants use `is_active = 1` as the population |
| 9.9 | Hard-deleting a referenced user | P1 | Blocked by `ON DELETE RESTRICT` |
| 9.10 | Deleting a user cascades their `alarm_settings` | P1 | Yes — the one `ON DELETE CASCADE` in the schema |

---

## 10. Idempotency and replay

| # | Case | Pkg | Expected |
|---|---|---|---|
| 10.1 | Same `source_event_id` twice, sequentially | P4 | `201` then `200`, one row, same `log_id` |
| 10.2 | Same `source_event_id` after the incident was resolved | P4 | `200` returning the resolved incident. **Does not** create a new one or reopen it |
| 10.3 | Same `source_event_id` from a different `camera_id` | P4 | Decide and test — most likely `409`. A silent overwrite would be worst |
| 10.4 | `PUT /api/settings/alarm` twice with identical values | P4 | Both `200`; **only the first writes an audit row** (UC-11) |
| 10.5 | Logout twice | P2 | Both `204` |
| 10.6 | Re-seeding help content with no file changes | P8 | Zero writes |
| 10.7 | Re-running the hourly rollup | P5 | One row, unchanged values |
| 10.8 | Duplicate `RE_ALARM` attempt from two processes | P4 | Exactly one broadcast — enforced by the conditional UPDATE, not by a lock |
| 10.9 | Client receiving a duplicate `event_id` after reconnect | P3 | Backend may emit it; the frontend deduplicates. Assert `event_id` is unique per emission |

---

## Coverage gaps that are acceptable

Stated so nobody spends time on them:

- **Multi-worker behavior.** D-005 locks a single Uvicorn worker. Cross-process state is out of scope.
- **Multi-instance / broker fan-out.** D-008 explicitly rejects Redis, Kafka, and cross-instance
  delivery for this deployment.
- **Non-SQLite databases.** The backend is deliberately SQLite-bound (`strftime` in analytics, WAL
  pragmas, partial indexes). Do not write portability tests.
- **Model accuracy.** AI-owner evidence per D-012. Do not mock a model and claim mAP.
- **Browser and UI behavior.** Frontend-owned; the backend tests the contract, not the rendering.
- **Real 8× L4 hardware capacity.** Unvalidatable on the demo laptop; stays `Needs Evidence` (D-009).
