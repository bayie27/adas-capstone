# A5 — Edge-case closure and coverage register

Two genuine gaps, one test-only gap, and the recovery of a list that was lost outside the repo.

> **Read before starting:** `be_plan/14_EDGE_CASES.md` (all ten categories),
> `be_plan/TRACEABILITY.md`, `be_audit/00_FINDINGS.md`.

---

## Part 1 — Close the three flagged rows (F11)

`14_EDGE_CASES.md` bolds seven rows as "Not covered in the package doc." Four of them
(5.5 future `detected_at`, 6.2 scheduler job exception, 6.10 rate-limiter key growth, 8.1
`alg:none`) **have since been covered** — verify that before touching them:

| Row | Now covered by |
|---|---|
| 5.5 | `test_internal.py::test_v2_future_detected_at_is_accepted` |
| 6.2 | `test_scheduler.py::test_unhandled_exception_in_a_job_keeps_it_scheduled` |
| 6.10 | `test_rate_limit.py::test_expired_keys_are_pruned_not_retained` |
| 8.1 | `test_auth.py::TestJWTVerification` (`alg=none`) |

### 1.12 — Restore requested while a backup is running → **test only**

Already handled by construction: `routes/maintenance.py:237` calls `try_acquire_maintenance_lock()`
on the restore path and `:160` does the same on the backup path, against the **same**
module-level `threading.Lock` in `app/maintenance/backup.py:57`.

Existing tests (`test_second_concurrent_backup_raises_busy`,
`test_second_concurrent_restore_returns_409`) only exercise the *same-operation* case. Add the
**cross-operation** ones:

- backup holding the lock → `POST /api/system/restores` returns `409` with code `CONFLICT_BUSY`
  and **writes no restore flag file** (that last assertion is the one that matters — a flag file
  written during a backup would trigger a restore on the next boot);
- restore holding the lock → `POST /api/system/backups` returns `409 CONFLICT_BUSY`.

### 1.7 — AI event arriving while an operator disables that camera → **open**

`receive_ai_alert` (`routes/internal.py:88-93`) reads `camera.is_enabled` and later commits an
incident plus a desired-state change. `update_camera` can flip `is_enabled` to false concurrently
in its own transaction.

`14_EDGE_CASES.md` states the requirement: **either outcome is acceptable** (incident created and
camera immediately goes `Inactive`/`disabled`, or the alert is rejected `404`) — what must never
happen is a deadlock, an orphaned incident on a disabled camera with a stale desired state, or a
500.

Test with **genuinely parallel requests** (threads against the `TestClient`, in the style of
`test_alerts.py::TestConcurrency`), not sequential calls. Assert:
- no 500, no `OperationalError` escaping as anything but the documented 503;
- whichever outcome lands, `camera.desired_ai_state` and `desired_state_reason` are self-consistent
  with `is_enabled` afterwards — run `recompute_desired_state`'s invariant and compare;
- if an incident was created on a camera that ended up disabled, the camera is `Inactive`/`disabled`
  and the incident is still resolvable by an operator (not stranded).

Fix only if the assertions fail. Write down which of the two outcomes actually occurs.

### 1.14 — Export artifact cleanup during a streaming download → **open**

`cleanup_expired_artifacts` runs hourly and unlinks artifact files;
`GET /api/exports/jobs/{job_id}/download` serves them via `FileResponse`.

**This behaves differently on the two platforms and the demo platform is the strict one:**
- POSIX: unlinking an open file succeeds, the inode survives, the download completes.
- **Windows: unlinking a file with an open handle raises `PermissionError`** — so the cleanup job
  raises instead. APScheduler keeps the job scheduled (6.2 is covered), but the artifact is then
  never reclaimed and the `export_job` row's state and the filesystem disagree.

Define the intended behaviour, implement it, and test it **on Windows**: the download should either
complete or fail cleanly, and cleanup must not leave the row and the disk permanently out of sync.
Deleting an artifact that is actively being read is the case to handle — a retry on the next sweep
is a perfectly good answer, as long as it is deliberate and tested.

---

## Part 2 — Recover the lost coverage list (F12)

`00_INDEX.md`'s P9 row records that the final sweep "found ~28 partially- or un-covered rows out of
~150 (full list in the PR/session report)". **That list is not in the repo.** It is the single
highest-value piece of context the project has lost, and it went missing because
`14_EDGE_CASES.md` has no status column — there was nowhere to write the answer down.

**Deliverable: `be_audit/EDGE_CASE_COVERAGE.md`** — every row of all ten categories of
`14_EDGE_CASES.md`, with:

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|

`Status` ∈ `covered` · `partial` · `uncovered` · `accepted-gap` · `inapplicable`.
`Evidence` names the actual test (`file::Class::test_name`) for anything `covered` or `partial`.
`accepted-gap` and `inapplicable` require a one-line rationale — `14_EDGE_CASES.md`'s own
instruction is "Skip a row only if it is genuinely inapplicable, and **say so in your report**
rather than silently dropping it."

Method: work category by category against the current suite. The test inventory is large but
well-named — `rg` for the concept, then confirm the test actually asserts the edge case rather
than the happy path next to it. Do not mark a row `covered` on the strength of a plausible test
name; open it.

Start from the "coverage gaps that are acceptable" section at the end of `14_EDGE_CASES.md` —
multi-worker, multi-instance, non-SQLite, model accuracy, browser behaviour and real 8×L4 capacity
are all pre-declared `accepted-gap` and should be recorded as such rather than re-investigated.

Anything found `uncovered` that looks materially risky gets added to `00_FINDINGS.md` as `F17+`,
not silently listed.

---

## Acceptance criteria

- 1.12 cross-operation tests pass; 1.7 and 1.14 have defined, tested behaviour with the outcome
  written down.
- `be_audit/EDGE_CASE_COVERAGE.md` exists, covers every row, and has no blank Status cell.
- `14_EDGE_CASES.md` gains a pointer to it at the top so the next reader finds the status.
- `uv run pytest` and `pnpm check` green.

## Commits

`test(backend):` for the three edge cases · `docs(audit):` for the coverage register.
