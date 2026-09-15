# ADAS Testing Guide and AI Handoff

This is the canonical execution guide for the ADAS test work. An engineer or an AI agent should be able to read this file, inspect the named source files, run the commands, and understand which observations are valid evidence and which prerequisites remain open.

The live Google Sheet is the acceptance record. This guide explains how to reproduce and interpret evidence. It does not replace the live tracker, the defense paper, or the repository's engineering rules in `CLAUDE.md`.

## Operating rules

Run every command from the repository root:

```powershell
uv sync
pnpm install
```

Use Python 3.12.13 through `uv`. Never use a bare `python` command. Capture the exact commit with `git rev-parse HEAD` before a run and record the working tree with `git status --short`.

The current test scope has these fixed interpretations:

- Video is 2K and main stream only. There is no substream scope.
- The processing target is 5 to 15 FPS, with 15 FPS as the design target.
- Operator UAT decision timing is 25 seconds.
- Snooze timing remains 15 seconds where the case or configuration names it.
- `FPS_BAND_MIN` is not changed to force a performance result.
- AI Model Validation and backup or restore execution are skipped when the run instruction excludes them.
- TC-PERF-002 remains skipped when the configured engine does not match the requested FPS band.
- TC-SYS-019 remains skipped when the run would restore the isolated database.

Do not convert a simulation, a fixture result, a single-request result, or an inspection-only result into a full pass when the case requires a different environment, duration, operator action, or artifact.

## Evidence and isolation

Backend tests use disposable databases through `backend/tests/conftest.py`. Performance fixtures use a file-backed disposable database seeded with 100,000 rows. Do not point test commands at `adas.db`, a city camera, DSS Pro, or an existing application database. Do not reseed a running instance.

The prior isolated stack used these values when available:

| Component | Address                    | Purpose                         |
| --------- | -------------------------- | ------------------------------- |
| Backend   | `127.0.0.1:8001`           | Isolated FastAPI instance       |
| Frontend  | `127.0.0.1:5174`           | Isolated browser target         |
| MediaMTX  | `127.0.0.1:8555`           | Local RTSP simulator            |
| Database  | `var/test-int/adas-int.db` | Disposable integration database |

Verify ports and the database path before using a live browser. Record the host, GPU model and driver, stream count, resolution, FPS, batch size, and test duration for performance results.

Portable evidence belongs under `var/test-evidence/`. That directory is local and ignored. A local path is not a hosted evidence link. Upload reviewed evidence to the team evidence library before replacing a hosted tracker link.

## Test family map

### Unit Testing

Tracker-bound selectors are grouped by component:

```powershell
uv run pytest backend/tests/test_tc_unit_users.py backend/tests/test_tc_unit_incidents.py backend/tests/test_tc_unit_settings.py backend/tests/test_tc_unit_platform.py -ra
uv run pytest ai_engine/tests/test_tc_unit_accumulator.py -ra
pnpm --filter frontend test:run -- --pool=forks --maxWorkers=1 src/components/layouts/Sidebar.tracker.test.tsx src/utils/dateRange.test.ts src/pages/Detections.test.tsx src/pages/SystemHealth.test.tsx --reporter=default
```

The binding comments at the top of each tracker-bound test module map selectors to case IDs. The current code-backed fixes covered password validation response redaction, case-insensitive usernames, camera configuration versioning, audit free-text redaction, date-range validation, and System Health recovery polling.

Run the complete backend and frontend checks when the change is cross-cutting:

```powershell
uv run pytest -n auto
pnpm --filter frontend lint
pnpm --filter frontend typecheck
pnpm --filter frontend test:run
pnpm --filter frontend build
```

### Integration Testing

Integration cases exercise backend to AI webhook authentication, database transactions, WebSocket alert delivery, export jobs, and lifecycle boundaries. Start from the existing tests rather than writing a second harness for the same seam:

```powershell
uv run pytest backend/tests/test_internal.py backend/tests/test_alerts.py backend/tests/test_exports.py backend/tests/test_realtime.py -ra
```

Use disposable fixtures and record whether the check is an in-process integration test or a live two-process test. An in-process test does not prove network, browser, GPU, or multi-node behavior.

### System and E2E Testing

The supported Playwright functional project is the Chromium project in `playwright.config.ts`. It starts and stops the backend and frontend unless live deployment mode is explicitly selected.

```powershell
pnpm exec playwright install --with-deps chromium
pnpm test:e2e
```

The named E2E cases executed in the current run were TC-SYS-002, TC-SYS-003, TC-SYS-008, TC-SYS-010, TC-SYS-012, TC-SYS-013, TC-SYS-014, TC-SYS-015, TC-SYS-019, and TC-SYS-021. TC-SYS-008 needs two operator sessions. TC-SYS-019 stays last and is skipped when it would restore the isolated database.

For live deployment mode, both variables are required and the configuration must not silently start loopback services:

```powershell
$env:E2E_LIVE_DEPLOYMENT = "1"
$env:E2E_BASE_URL = "https://<verified-host>:5173"
pnpm test:e2e
```

The visual project is separate and is not the functional gate:

```powershell
pnpm test:visual
```

Visual baselines are Linux-only. Do not commit Windows snapshots generated by accident.

The repository also has Playwright configuration tests:

```powershell
pnpm exec vitest run playwright.config.test.ts
```

If a team workflow supplies Playwright YAML snapshots or action logs, treat them as execution artifacts. Validate their referenced URLs, selectors, and timestamps against the actual run. A YAML artifact alone does not prove that a case passed.

### Performance and Load Testing

The slow backend suite creates the 100,000-row disposable dataset and prints measured timings:

```powershell
uv run pytest -m slow backend/tests/perf/ -s -ra --junitxml=var/test-evidence/performance-backend.xml
```

Use `backend/tests/perf/test_query_performance.py` for query budgets and query-plan evidence. Use the export, alert-latency, and slow-client modules for their named cases. Record both the measured value and the acceptance condition.

The following distinctions are mandatory:

- A single dashboard request does not prove a 20-request concurrent p95.
- A PyTorch checkpoint measurement does not prove the TensorRT prerequisite.
- A browser-injected event simulation does not prove an AI clip replay.
- A short burst does not prove an eight-hour or 24-hour duration requirement.
- A test on one laptop does not prove a production two-node capacity claim.

### Reliability and Endurance

Use the reusable long-run harness only against the isolated stack:

```powershell
uv run python var/test-int/long_run_harness.py
```

The harness records health, FPS, latency, CPU, memory, GPU telemetry, WebSocket delivery, and scripted operator actions. A bounded run can prove that the loop, logging, and recovery path work. It cannot prove a complete duration requirement unless the recorded elapsed time reaches the case requirement.

For daily restart scheduling, inspect the registration script and the host task state:

```powershell
Get-Content scripts/register-maintenance-task.ps1
Get-ScheduledTask -TaskName '*adas*' -ErrorAction SilentlyContinue
```

Do not register a persistent task or restart the production port as part of an isolated test without explicit, current authorization. A script inspection or dry-run remains Blocked for the full scheduled-task acceptance.

### Security Testing

Run the reviewed security batch through the portable runner:

```powershell
uv run python scripts/testing/run_tracker.py --batch security
uv run python scripts/testing/run_tracker.py --case TC-SEC-001
```

The runner creates a UTC evidence directory with one log and JUnit XML per case plus `run.json`. The runner proves only the selectors it invokes. Authentication timings use cheap fixture hashing and are diagnostic, not production benchmarks.

Security cases must preserve the distinction between authentication, authorization, audit integrity, hostile input handling, transport behavior, and data localization. Do not mark a case from a neighboring selector unless its written acceptance is fully asserted.

### Backup and Recovery

Backup and restore is destructive to the isolated database and is excluded when the current run instruction says to skip it. Keep it last when it is authorized. Use a disposable copy and a verified rollback path. Never restore over a user's working database merely to obtain a pass.

## Tracker update workflow

1. Export or copy the current workbook before editing.
2. Preserve all tabs, columns, validations, row order, and case IDs.
3. Update only cells for cases whose acceptance was observed.
4. Keep exact measured values and deviations in Actual Result or Notes.
5. Use `Pass`, `Fail`, or `Blocked` according to the written acceptance. Do not use Pass as a placeholder for work not performed.
6. Recalculate Summary formulas through Excel after saving.
7. Read back the edited rows and verify the saved result.

The local helpers do not edit the live Google Sheet:

```powershell
uv run python scripts/testing/read_tracker.py <exported-workbook.xlsx>
uv run python scripts/testing/report_tracker.py <exported-workbook.xlsx> <run.json> <handoff.md>
```

The Google Sheet is updated through the approved browser or connector workflow, not by silently replacing a local workbook.

## Current known limitations

The latest execution history contains evidence and open limitations. Check the live tracker before repeating work. Known examples include missing TensorRT artifacts, FPS configuration mismatch for TC-PERF-002, cold SQLite contention for dashboard concurrency, human-paced operator timing, and persistent Windows scheduled-task execution. These are not silently converted into passes.

Open defect decisions remain in the tracker and Defect Log. When code fixes close a defect, rerun the originating selector and update both the evidence path and the defect note.

## AI execution recipe

When an AI agent receives this file, it should:

1. Read this guide, `AGENTS.md`, and `CLAUDE.md`.
2. Run `git status`, capture the build, and confirm the current branch.
3. Inspect the live tracker or supplied export and select only the requested unfinished cases.
4. Check whether each acceptance needs code, API, script, browser, operator, hardware, duration, or destructive environment evidence.
5. Use the smallest valid method that proves the acceptance and record any deviation.
6. Run the named selector and preserve its output under `var/test-evidence/`.
7. Update only the intended tracker cells after a backup and verify the readback.
8. Report passed, failed, blocked, skipped, simulated, and unobserved states separately.

Never invent a result, erase an open defect, alter a protected configuration value, or claim a duration or human action that did not occur.
