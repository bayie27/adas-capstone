# P9 — Migrations, Performance Evidence, and Traceability

> **Blocked by:** every other package. This is the last one.
> **Branch:** `feat/be-p9-migration-evidence`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §12, `be_decisions_review.md`
> D-001 (the boundary rule) and D-005.
> **Size:** L. Seven steps.

## Why this package exists

Two things the project cannot defend without:

1. **Migrations.** D-005 defers Alembic until the schema is decision-complete, precisely so the first
   migration describes a stable production schema instead of a throwaway chain. That moment is now.
   Until this package lands, any schema change means deleting the database — including in production.
2. **Evidence.** D-001 puts "traceability and acceptance evidence for all 82 unique paper test cases"
   in scope and forbids silently omitting one because it belongs to another owner. Several NFRs are
   *numbers* (< 2s alert, < 3s query on 100,000 rows, < 5s export, 99.9% uptime) that must be measured
   rather than asserted.

---

## Step 1 — Alembic

**Dependency:** `alembic>=1.14`. **Location:** `backend/alembic/` with `alembic.ini` at the repo root.

D-005's sequence, in order:

1. Reset the development database and validate the complete schema.
2. Add Alembic configuration and the versions directory.
3. Generate **one** initial migration representing the full intended schema — then **manually review
   it**. Autogenerate reliably misses things you have in this schema:
   - partial and expression indexes (`WHERE is_active = 1`, `lower(camera_name)`)
   - `CHECK` constraints
   - the `audit_log` immutability triggers
   - the FTS5 virtual table and its sync triggers

   Every one of those needs a hand-written `op.execute(...)`. Do not trust the generated file.
4. Test applying it to a **new empty SQLite file**.
5. Verify constraints, indexes, seeding, and the recorded revision.
6. Use it for the first production deployment.

Configure Alembic's `env.py` to use the app's `Settings` so `DATABASE_URL` resolution and the SQLite
pragmas match the running app. Enable `render_as_batch=True` — SQLite cannot `ALTER` most things in
place and batch mode is what makes future migrations possible at all.

### Startup revision check

At startup in production, compare the database's revision against the code's `head`:

- older → refuse to start with a clear message naming `alembic upgrade head`
- unexpectedly newer → refuse to start
- development → warn only

D-005: "ordinary application startup never silently changes the production schema."
`SQLModel.metadata.create_all()` may **remain in the fast isolated unit-test fixtures** and nowhere
else. Add a separate test that runs the real migration against a real file — migration tests must
exercise Alembic, not `create_all`.

### Wire the revision into backups

P7's backup manifest has an `alembic_revision: None` stub. Populate it, and make the restore
validation reject a backup whose revision is incompatible with the running code.

### Post-deployment policy (document in `CONTRIBUTING.md`)

Every later schema change gets its own reviewed migration. Before a production migration: create and
verify a WAL-safe backup. After: run integrity and revision checks. Once new-version data has been
written, operational rollback restores the verified pre-migration backup rather than attempting a
destructive schema downgrade.

---

## Step 2 — The performance seed

**File:** `backend/scripts/seed_dev_data.py`, new `perf` profile

Generates **100,000** incidents (NFR-08) across the six cameras, spread over ~18 months, with a
realistic status mix (roughly 60% Resolved, 25% Dismissed, 14% Ongoing, and — respecting
`ux_detection_open_camera` — at most one open incident per camera), varied confidence scores, and
plausible verifier/closer assignments.

Bulk-insert (`session.exec(insert(...), rows)` in batches), not 100,000 ORM objects. Target under two
minutes; document the actual figure.

Snapshot files are **not** generated — reuse a handful of real filenames and let the missing-file path
be exercised. That is realistic anyway.

---

## Step 3 — Measured performance evidence

**File:** new `backend/tests/perf/` (marked `@pytest.mark.slow`, excluded from the default run)

Each of these produces a **recorded number**, not just a pass/fail:

| Target | Test |
|---|---|
| NFR-08 / TC-R-202 — dashboard query < 3s on 100,000 rows | time `GET /api/alerts/` with realistic filters, and `GET /api/analytics/dashboard` |
| NFR-06 / TC-R-203 — export < 5s for a 30-day / ~10,000-row dataset | time both CSV and PDF, time-to-first-byte and total |
| NFR-04 / TC-R-201 — alert delivery < 2s | time from `POST /api/internal/alert` to the event arriving at a connected WebSocket client |
| D-008 — slow-client isolation | with one stalled client, a healthy client still receives an alert within 2s |

Also capture SQLite query plans for the main list and analytics queries and confirm the P1 indexes are
actually used:

```bash
uv run python -c "…EXPLAIN QUERY PLAN…"
```

D-005 requires this — "confirm index use with SQLite query plans and the paper's 100,000-incident
performance test". A `SCAN detection_log` in the plan for a filtered list query means an index is
missing or unusable.

Write results to `be_plan/EVIDENCE.md` with the machine spec, date, and dataset size. **Label every
number as demo-validated on the laptop.** D-009 is explicit: laptop results are not proof of
enterprise-scale capacity, and the paper must distinguish measured from simulated from
pending-production-hardware.

---

## Step 4 — The traceability matrix

**File:** new `be_plan/TRACEABILITY.md`

A table with one row per paper test case. Extract the full list from `final_paper_text.txt`
(TC-U-1xx…4xx, TC-I-2xx…4xx, TC-AI-1xx…4xx, TC-R-2xx…4xx, TC-S-1xx…5xx).

| Column | Content |
|---|---|
| Test case | `TC-I-307` |
| Requirement | `FR-07` |
| Owner | backend / frontend / AI / deployment |
| Evidence type | automated test · manual procedure · external |
| Evidence | `backend/tests/test_snooze.py::test_snooze_mutes_only_target_incident`, or a procedure reference, or the external interface + prerequisite |
| Status | pass / pending / blocked |

**The D-001 boundary rule is the point of this document:** a test case owned by someone else may not
be silently omitted. It must still carry an explicit interface, owner, prerequisite, and acceptance
evidence. Concretely:

- **TC-AI-1xx…4xx** (mAP, IoU, night/rain/glare, occlusion, sub-threshold suppression, FPS, VRAM) —
  owner: AI engine. Interface: the D-012 contract in `12_AI_ENGINE_CONTRACT.md`. Prerequisite: the
  open evidence gate (threshold, temporal-qualification rule, batch/FPS profile).
- **Physical VLAN, NAS, Dahua DSS** — owner: deployment. Interface: `RTSP_URL_TEMPLATE` and the
  archive destination path.
- **UI-only cases** (click counts, modal behavior, alert perception) — owner: frontend. Interface: the
  REST and WebSocket contracts.

Also record the **contract amendments the paper needs**, which D-012 already flags:

- **TC-I-202** currently says the worker "ceases frame ingestion" on Confirm. The locked behavior is
  that YOLO inference and event generation cease while bounded RTSP draining continues, so resume
  starts from live footage instead of a stale buffer. The acceptance wording must change.
- **TC-U-205** must acknowledge the AI-generated `source_event_id` in the payload.
- The Data Dictionary defines five tables and has no home for **FR-08 alarm settings** or the
  **FR-21 audit trail**. Both now exist; the ERD needs updating.
- Use Case 5 step 10 says the status becomes "Closed"; the canonical status is `Resolved`.
- Internal numbering: the Evaluation Scope cites NFR-03 for the two-second alert target (it is NFR-04)
  and NFR-06 for the fifteen-second detection-to-dispatch target (it is NFR-09).

Someone has to actually edit the paper. Flag these to the team; do not edit it from a code session.

---

## Step 5 — Manual procedure playbook

**File:** new `be_plan/MANUAL_TESTS.md`

Write step-by-step procedures with result blanks for everything that cannot be automated:

- **TC-R-303** — 3:00 AM restart drill: trigger, time backup separately from downtime, confirm cameras
  re-ingesting, record model-load / service-ready / camera-recovery timings.
- **NFR-18 / 60-second restore drill** — the P7 sequence, timed.
- **Rollback drill** — deliberately fail startup and confirm automatic recovery.
- **TC-R-401 / TC-R-402** — 24-hour endurance: record RAM at start/6h/12h/24h (flat, no leak), GPU
  temperature, VRAM (locked, no creep).
- **TC-S-203** — four-hour idle session still receives WebSocket pushes with no re-auth.
- **TC-R-304** — force-close the browser, reopen, confirm `Unverified` alerts repopulate.
- **TC-S-401** — three cameras detecting simultaneously; alerts queue and stack, none dropped.
- **Bi-annual restore drill** — pull the archive into an isolated staging environment and validate the
  flag-and-restart architecture. Owner: deployment.

---

## Step 6 — Documentation

| File | Changes |
|---|---|
| `CLAUDE.md` | **The "0-byte placeholders are intentional" gotcha is now false** — `monitor.py` (P5), `routes/system.py` (P1, plus `system_health.py` in P5 and `maintenance.py` in P7), and `daily_restart.sh` (P7) are implemented. Replace it. Add: services layer, `UtcDateTime`, cookie auth, audit coupling, `ux_detection_open_camera`, and "reset the DB via Alembic now, not by deleting the file". **Also update the testing-policy bullet**: "don't overdo it" stays, but edge cases at boundaries, races, and failure paths are in scope beyond the paper's 82 cases — see `be_plan/14_EDGE_CASES.md` |
| `README.md` | New endpoints, cookie auth, backup/restore operations, maintenance CLI, `SNAPSHOT_ROOT` / `BACKUP_DIR` / `EXPORT_DIR` |
| `CONTRIBUTING.md` | Migration workflow, the post-deployment schema policy, how to run the perf suite |
| `backend/README.md` | Currently lists `analytics.py` as "(planned)" (it has been complete with a 620-line test suite for months) and its test-coverage table omits four test files. Rewrite it |
| `backend/scripts/README.md` | Claims `_bootstrap.py` normalizes the working directory — it stopped doing that in the DX package. Fix, and document the `perf` profile |
| `.env.example` | Every new setting from `01_CONTRACTS.md` §4, comments on their own lines |

---

## Step 7 — CI

**File:** `.github/workflows/ci.yml`

Add to the existing four jobs:

- `uv run pytest --cov=backend/app --cov-report=term-missing` in the `backend` job. **Report only, no
  hard gate** — `CLAUDE.md`'s testing policy is explicit about not chasing a coverage number.
- A **migration job**: fresh checkout → empty database → `alembic upgrade head` → assert the schema
  matches `SQLModel.metadata` → `alembic downgrade base` if downgrades are supported. This is what
  catches a hand-edited migration drifting from the models.
- A **perf job**, `workflow_dispatch` only (too slow for every PR): seed the `perf` profile and run
  `backend/tests/perf/`, uploading the timings as an artifact.
- Keep the default `pytest` run excluding `@pytest.mark.slow`.

Branch protection on `main` requiring these checks is a **manual GitHub setting** and cannot be
committed. Note it in `CONTRIBUTING.md`.

---

## Verification

```bash
uv run alembic upgrade head
```

against a fresh empty file, then:

1. Diff the migrated schema against `SQLModel.metadata` — no differences, including indexes,
   constraints, and triggers.
2. Start the backend against the migrated database and confirm the seeded admin can log in.
3. Take a P7 backup and confirm the manifest now records the real Alembic revision.
4. Attempt to start the app against a database one revision behind → it refuses with a clear message.
5. `uv run python backend/scripts/seed_dev_data.py --profile perf` → 100,000 rows; record the time.
6. `uv run pytest -m slow backend/tests/perf/` → record every number in `EVIDENCE.md`.
7. `EXPLAIN QUERY PLAN` on the main list query shows index use, not `SCAN detection_log`.
8. `be_plan/TRACEABILITY.md` has a row for every test case in the paper and **no blank Owner cell**.
9. `pnpm check` and a full CI run, including the migration job.

---

## Definition of done for the whole effort

- [ ] All nine packages merged.
- [ ] `pnpm full:check` green.
- [ ] One reviewed Alembic migration applies cleanly to an empty database.
- [ ] `EVIDENCE.md` records measured numbers for NFR-04, NFR-06, and NFR-08 with the machine spec.
- [ ] `TRACEABILITY.md` covers all 82 test cases with no unowned rows.
- [ ] `MANUAL_TESTS.md` procedures executed and results recorded.
- [ ] The frontend has migrated to cookie auth and the new response shapes.
- [ ] The AI owner has either cut over to contract v2 or confirmed v1 remains in use for the demo.
- [ ] The paper's amendments (TC-I-202, TC-U-205, the ERD, the "Closed"/`Resolved` wording, the NFR
      numbering) are listed for the writing team.
