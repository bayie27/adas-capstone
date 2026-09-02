# ADAS UAT Readiness Dry-Run Handoff

> **Run status:** Complete — Not Ready  
> **Document role:** Executable handoff and the single continuous dry-run report  
> **Task owner:** The separate Luna Max Codex task launched from this checkout

## 1. Objective and completion standard

Perform an evidence-based, UAT-only readiness dry run of ADAS using the current saved-project checkout, its uncommitted changes, the current development database, the live Google artifacts, the real browser interface, and real RTSP/AI detections wherever applicable.

The run is complete only when all of the following are true:

1. Every authoritative source has been read completely according to the source rules below.
2. A separately stored pre-run safety backup has been created and independently verified before any reseed.
3. OP-01 has completed the full Operator core journey, OP-J01 through OP-J09.
4. OP-02 through OP-06 account/reset/export variants have been checked without representing them as human participant sessions.
5. ADM-01 has completed the full Administrator core journey, AD-J01 through AD-J06.
6. ADM-02 account/reset/lifecycle/audit variants have been checked.
7. Every UAT-relevant formula, validation, denominator, readiness gate, traceability mapping, timing definition, click definition, export assignment, and SUS scoring formula has been audited without writing synthetic results to the live tracker.
8. Every finding, intervention, metric, limitation, consent decision, approved fix, and retest has been recorded in this file as it occurs.
9. A final `Ready`, `Ready with conditions`, or `Not Ready` verdict has been justified using the rules in this handoff.
10. Every process started by the task has been stopped, while the database and generated UAT state remain exactly as produced by the dry run.

This dry run can validate execution mechanics, technical behavior, artifact consistency, and script clarity. It cannot supply legitimate participant SUS responses or prove human usability.

## 2. Authority rules and required read order

Read all sources completely before reseeding, editing, or executing a journey. If the live topology differs from the IDs below, record the difference in the report and resolve the authoritative live tab by its exact title. Do not silently substitute another source.

### 2.1 Test plan

- **Title:** `Capstone Test Execution and Validation`
- **Document URL:** https://docs.google.com/document/d/1EAoDetxkq6a3gzihU4iqp8pEXm4LcXfxmb8p5bCnBow/edit
- **Document ID:** `1EAoDetxkq6a3gzihU4iqp8pEXm4LcXfxmb8p5bCnBow`
- **Read order:**
  1. `__main__` — tab ID `t.gu7j5a4nobzi`
  2. `claude v2` — tab ID `t.69pznq56gm30`
- **Authority rule:** `__main__` is the consolidated and authoritative plan. Compare `claude v2` only to detect possible omissions. Do not import its content blindly or let it override `__main__`.
- **Change posture:** The test plan is treated as final unless a critical validity problem is found.

### 2.2 Revised ADAS tracker

- **Spreadsheet URL:** https://docs.google.com/spreadsheets/d/1yX-asNF-jsEZwIVSGFDvKyjF0Frh4IjWLY0Svfe82vU/edit
- **Spreadsheet ID:** `1yX-asNF-jsEZwIVSGFDvKyjF0Frh4IjWLY0Svfe82vU`
- **Authority rule:** Read and audit all 18 tabs, including examples, formulas, validations, metrics, readiness gates, the 66-row participant-stage structure, traceability, and export assignments.

| Read order | Tab                        | Sheet ID | Required focus                                                                   |
| ---------: | -------------------------- | -------: | -------------------------------------------------------------------------------- |
|          1 | Summary                    |  4101000 | Activity totals, readiness summary, formulas, and formal eligibility gate        |
|          2 | Guide & Examples           |  4101009 | Instructions, example rows, and formula-exclusion rules                          |
|          3 | Unit Testing               |  3000001 | UAT prerequisite/status validation review                                        |
|          4 | Integration Testing        |  3000002 | UAT prerequisite/status validation review                                        |
|          5 | System / E2E Testing       |  3000003 | UAT prerequisite/status validation review                                        |
|          6 | AI Model Validation        |  3000004 | UAT trigger assumptions and frozen-model dependencies only                       |
|          7 | Performance & Load Testing |  3000005 | Timing/readiness dependencies only                                               |
|          8 | Reliability & Endurance    |  3000006 | UAT readiness dependencies only                                                  |
|          9 | Security Testing           |  3000008 | Role, login, privacy, and audit prerequisites only                               |
|         10 | Backup & Recovery          |  3000007 | Recovery workflow and restore-safety prerequisites                               |
|         11 | Session Control            |  4101001 | Participant assignments, credentials, reset controls; do not copy passwords here |
|         12 | UAT Journeys               |  4101002 | Every column, ordered actions, setup, results, metrics, prompts, requirements    |
|         13 | Execution Log              |  4101003 | Exactly 66 planned participant-stage units and one-attempt rule                  |
|         14 | SUS Questionnaire          |  4101004 | Wording, administration order, scale, scoring inputs                             |
|         15 | Usability Results          |  4101005 | SUS formulas, denominators, blank/error behavior, acceptance gates               |
|         16 | UAT Results                |  4101006 | Final-status logic, denominators, gates, sign-off calculations                   |
|         17 | Defect Log                 |  4101007 | Severity/status definitions and links to readiness decisions                     |
|         18 | UAT Traceability           |  4101008 | FR/NFR-to-stage mappings and uncovered/overstated claims                         |

The non-UAT technical tabs are inspected for UAT prerequisites and consistency; this handoff does not authorize rerunning the entire technical test program.

### 2.3 UAT acceptance and sign-off record

- **Title:** `ADAS User Acceptance Testing (UAT) Acceptance and Sign-Off Record`
- **Document URL:** https://docs.google.com/document/d/1d2nSnoi95E_QJikl9Hp93zW18MHXJaUi3lDJlhqWKWQ/edit
- **Document ID:** `1d2nSnoi95E_QJikl9Hp93zW18MHXJaUi3lDJlhqWKWQ`
- **Read order:**
  1. `Tab 1` — tab ID `t.0`; main acceptance and sign-off record
  2. `Scripts` — tab ID `t.gl2h436x42hu`; preparation and facilitator guidance
  3. `Journey Script` — tab ID `t.ha3mobdsx1ni`; manually maintained words spoken during the session
- **Authority rule:** Treat the manually maintained `Journey Script` as authoritative for what the facilitator says, while checking it against `Scripts`, the UAT Journeys, and actual behavior. Do not overwrite manual wording merely because another tab phrases it differently.

### 2.4 Defense paper

- **Title:** `Group7_Capstone Project Defense Document - ITCAPROJ1`
- **Document URL:** https://docs.google.com/document/d/1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw/edit
- **Document ID:** `1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw`
- **Authority rule:** Use the paper only for requirements and whole-project context.
- **Explicit exclusion:** Every testing section and every test case in the defense paper is stale. Ignore them. They must not be used to correct, supplement, or score the current plan or tracker.

### 2.5 Current implementation

Read the relevant code and configuration after the live artifacts, including:

- The current dirty working tree and all uncommitted UAT seed/reset changes.
- `mediamtx-uat.yml`.
- UAT seed profiles, Dev Tools, reset handlers, journey-related UI, alert state, exports, Help Center, audit, maintenance, and restore coordinator.
- Current runtime configuration, available clips, model, ports, service lifecycle scripts, and actual running processes.

Do not infer UI behavior from old documentation when it can be observed in the current browser or verified in current code.

## 3. Build identity and owner-authorized environment choice

- **Plan reference supplied by the owner:** `main@15604283d2863e476222779e457b3dd3b390d8ef` plus uncommitted changes.
- **Verified launch identity on 2026-08-30:** `main@8385a4398174c2dc1d3b09ec7c873f662344fdd7` plus uncommitted changes.
- **Required handling:** Record the launch-time `git rev-parse HEAD`, branch, dirty-file list, and timestamp under Run Metadata. The verified launch identity controls this run. Do not reset, switch, pull, merge, commit, or push.

The owner explicitly chose the current development database rather than an isolated copy and explicitly chose to leave it and all generated UAT state in their final post-dry-run condition. The mandatory external safety backup protects recoverability but is not restored automatically at the end.

## 4. Non-negotiable guardrails

1. Preserve unrelated working-tree changes and untracked files.
2. Do not commit or push.
3. Do not expose passwords, secret keys, internal API keys, tokens, or full environment-file contents in this document, task messages, commands, or excerpts.
4. Obtain credentials from the restricted live `Session Control` tab only when needed; identify accounts by participant ID or username, never by password in this report.
5. Do not write synthetic dry-run results into the formal Execution Log, SUS, Usability Results, UAT Results, or any other live Google range.
6. Keep all live Google artifacts read-only unless an approved Blocker fix specifically requires an edit.
7. Do not fabricate success, timing, click counts, participant actions, SUS answers, or human usability conclusions.
8. Do not change public APIs, database schema, or migrations unless a Blocker proposal explicitly identifies that change and the user approves it.
9. Do not delete or modify original evaluation clips.
10. Do not create screenshots or a separate evidence package. Put concise timestamps, measurements, observed behavior, and short error excerpts in this report.
11. Stop only the dependent path when blocked; continue independent audits or variants when their evidence remains valid.
12. Append or update this report continuously. Do not wait until the end to reconstruct findings from memory.

## 5. Finding, consent, and mutation policy

### 5.1 Severity definitions

| Severity    | Definition                                                               |
| ----------- | ------------------------------------------------------------------------ |
| Blocker     | Prevents continued or valid UAT execution.                               |
| Major       | Execution can continue, but formal results may be invalid or misleading. |
| Minor       | Clarity, consistency, or efficiency issue without validity risk.         |
| Observation | Optional improvement.                                                    |

### 5.2 Required response

- **Every issue:** Enter it in the Finding Ledger immediately, before discussing or fixing it.
- **Blocker:** Stop only the dependent path. In the Luna task, show the user the exact proposed fix, affected local files and/or Google ranges, risks, rollback, and verification plan. Wait for explicit consent in that task. After consent, document the decision, apply only the approved change, rerun the affected stage and dependent checks, and record before/after behavior.
- **Major, Minor, Observation:** Do not edit code, configuration, Docs, Sheets, or scripts. Record the exact location, evidence, impact, and recommended correction, then continue wherever valid.
- **Expected runtime state:** Browser actions, seeding, targeted resets, backups/restores, exports, snapshots, database rows, accounts, audit events, and MediaMTX profile switching are authorized parts of the dry run and are not “fixes.”
- **This report:** Updating this file is always authorized and required.

## 6. Preflight and safety gate

Record every result under Preflight Results. Do not reseed until the safety gate passes.

### 6.1 Inspect without mutation

1. Record local time, branch, `HEAD`, `git status --short`, and this handoff's path.
2. Inspect running ADAS-related processes and listening ports. Distinguish existing processes from processes the task later starts.
3. Inspect `.env` only through targeted configuration checks; never print its complete contents or secrets.
4. Confirm the expected database path and record only the path, size, and last-modified time.
5. Confirm the UAT seed/reset implementation and the available Dev Tools controls.
6. Confirm the restore coordinator command/lifecycle and readiness indicator.
7. Confirm the MediaMTX binary, FFmpeg, and all required clips are present.
8. Confirm the model and AI runtime are available. Record the observed model identity/device without dumping proprietary weights or secrets.
9. Read `mediamtx-uat.yml` and verify exactly one whole `paths:` profile is active.
10. Resolve any stale process or port conflict using the repository lifecycle scripts and exact process ownership. Do not use broad process-kill commands.

Expected MediaMTX binary location:

`C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64\mediamtx.exe`

Expected clip directory:

`ai_engine/eval/clips`

At minimum, verify `airbase.mp4`, `dekwatro.mp4`, `car-motor-motor.mp4`, and `red-car-motor.mp4`.

### 6.2 Create the separately stored safety backup

Create a unique directory under `var/uat-safety-backups/` rather than the normal configured backup-retention directory. A suggested directory name is `pre-dry-run-YYYYMMDDTHHMMSS`.

From the repository root, use a task-specific PowerShell variable and a temporary process environment override:

```powershell
$uatSafetyDir = Join-Path (Get-Location) "var\uat-safety-backups\pre-dry-run-<timestamp>"
New-Item -ItemType Directory -Path $uatSafetyDir | Out-Null
$env:BACKUP_DIR = $uatSafetyDir
uv run --directory backend python -m app.maintenance backup
uv run --directory backend python -m app.maintenance verify <backup_id>
Remove-Item Env:BACKUP_DIR
```

Requirements:

1. Capture the backup ID from the backup result.
2. Require both creation success and an independent `verify` result of valid/healthy.
3. Confirm that the manifest and database backup exist inside the safety directory.
4. Record the safety directory, backup ID, validation result, timestamp, and a redacted restoration command in Safety Backup Record.
5. If verification fails, log a Blocker and do not reseed.
6. Never point ordinary backup retention at this directory during the dry run.
7. Remove the temporary `BACKUP_DIR` override before starting the app so ordinary in-app UAT backup/restore continues to use the configured normal backup directory.

## 7. Environment start, profile switching, and shutdown

### 7.1 Start

1. After the safety gate passes, reseed the `uat` profile exactly once using the current implementation.
2. Activate the `OP-J01 to OP-J03 — BASELINE / SILENT` block in `mediamtx-uat.yml` and keep all other complete `paths:` blocks commented.
3. Start MediaMTX with the dedicated configuration from the repository root.
4. Start backend, frontend, AI engine, and the restore coordinator using the repository lifecycle commands. Do not use the generic simulation profile in place of `mediamtx-uat.yml`.
5. Wait for health/readiness; verify the actual browser URL and API/AI connections before beginning OP-J01.

Preferred component startup shape, subject to current-script verification:

```powershell
& "C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64\mediamtx.exe" mediamtx-uat.yml
pwsh -File scripts/start-dev.ps1 -Backend -Frontend -Ai
```

Use controlled process handles or repository lifecycle scripts. If the exact current scripts require a different safe order, record the deviation and reason.

### 7.2 Switch whole MediaMTX blocks

The real-session handler procedure is intentionally simple:

1. Comment the entire active `paths:` block.
2. Uncomment the entire next `paths:` block.
3. Save `mediamtx-uat.yml`.
4. In the dedicated MediaMTX terminal press `Ctrl+C`, then `Up Arrow`, then `Enter` to restart the same command.
5. Confirm that the expected publishers reconnect before continuing.

Use exactly one active block at a time:

| Profile | Intended stages | Expected active content                                                               |
| ------- | --------------- | ------------------------------------------------------------------------------------- |
| 1       | OP-J01–OP-J03   | Baseline/silent streams                                                               |
| 2       | OP-J04–OP-J07   | Channel 1 `dekwatro.mp4`; Channel 2 `car-motor-motor.mp4`; multi-alert follow-through |
| 3       | OP-J08–OP-J09   | Channel 3 `red-car-motor.mp4`; recovery and handover                                  |
| 4       | AD-J01–AD-J04   | Administrator baseline/silent streams                                                 |
| 5       | AD-J05–AD-J06   | Channel 1 `dekwatro.mp4`; post-restore positive alert                                 |

Do not alter individual clip paths during the run. A file edit that merely switches already-defined whole blocks is expected runtime state. Record every switch/restart time and readiness time in the Trigger Log.

### 7.3 Shutdown and required final state

At completion or safe termination:

1. Stop all frontend, backend, AI, restore-coordinator, MediaMTX, and FFmpeg processes started by this task using controlled/repository-supported shutdown.
2. Do not stop unrelated pre-existing processes.
3. Verify that the started service ports are no longer listening and no task-started FFmpeg child remains.
4. Do not restore the pre-run safety backup.
5. Leave the development database, normal backups, exports, snapshots, replacement accounts, audit trail, and `mediamtx-uat.yml` in their actual final post-dry-run state.
6. Preserve the separately verified safety backup and document how to restore it if the owner later chooses.
7. Do not commit or push.

## 8. Artifact and script audit protocol

Audit before and during execution. Record exact tab/section/cell or range locations when available.

### 8.1 Cross-artifact checks

Check the test plan, tracker, `Scripts`, `Journey Script`, and current behavior for:

- Contradictions or authority confusion.
- Missing setup, transition, trigger, fallback, cleanup, or end-state steps.
- Answer leakage that tells a participant what to conclude rather than presenting a scenario.
- Stale statements, especially old testing material from the defense paper.
- Incorrect statements about alert queue navigation, global snooze, live context, countdowns, cooldowns, blocking states, Ongoing behavior, restore behavior, exports, or role boundaries.
- Unclear handoffs between demonstration, guided practice, participant action, and facilitator-only intervention.
- Prompts that require reinterpretation or coaching.
- Expected results that are not observable by a participant or facilitator.
- Requirements mappings that are unsupported, missing, or overclaimed.
- Metric definitions that do not match their requirement or observable start/stop event.

### 8.2 Full script review

Review the complete casual-Filipino briefing, system tour, consent/privacy text, stage introductions, journey prompts, assistance/fallback language, facilitator trigger cues, debrief, and sign-off transition.

Assess whether the flow is natural for a non-technical, first-time CDRRMO participant who is already an operations professional. Explicitly check:

1. Whether the opening distinguishes orientation/demo from scored participant action.
2. Whether the tour teaches locations and quirks without leaking journey answers.
3. Whether each journey starts with enough scenario context and no hidden prerequisite.
4. Whether facilitator-only operations are clearly separated from participant actions.
5. Whether silence/waiting periods and real AI trigger delays are explained naturally.
6. Whether the script handles unexpected alerts, trigger failure, reconnection, restoration delay, and participant questions consistently.
7. Whether assistance is logged and whether the wording preserves the validity of the task.
8. Whether the debrief and SUS administration avoid leading or pressuring the participant.
9. Whether privacy and behind-the-scenes photo wording matches the actual evidence plan.

Do not invent participant reactions. Label naturalness judgments as expert/script review observations unless a real user supplies them.

## 9. Core Operator dry run: OP-01

Use OP-01's actual account from `Session Control`. Read the corresponding `Journey Script` wording exactly as written and operate the browser as the participant would. Complete OP-J01 through OP-J09 in order. The UAT Journeys tab remains the authority for exact setup, numbered participant actions, expected results, measurements, and requirement links.

At minimum, the continuous flow must exercise and record:

- First login and orientation boundary.
- Dashboard/camera understanding and the intended OP-J03 camera condition/action.
- Real multi-alert generation through Profile 2.
- Alert queue navigation, including arrows and visible ongoing-detection affordances.
- The implementation's **global snooze** behavior; do not reinterpret it as per-alert snooze.
- Genuine-alert confirmation and false-alert dismissal.
- Any defined re-alarm, cooldown, and monitoring-resumption behavior.
- Ongoing tray handling, including resolution and correction/dismissal where the current journey requires it.
- Pending alert recovery through controlled refresh/reconnect using Profile 3.
- Handover state and the intended active incident.
- The assigned Help Center lookup.
- OP-01's assigned `Detections CSV` export.
- Every required elapsed-time and click measurement using the tracker's exact definitions.
- Every point where the written prompt required reinterpretation, extra coaching, or unexpected facilitator intervention.

For each journey, record the setup, trigger, actual numbered actions performed, actual outcome, timing/click observations, deviations, findings, and whether the next stage remained valid. Do not mark a formal participant Pass/Fail in the live tracker.

## 10. Operator variants: OP-02 through OP-06

These are reproducibility and account/export checks, not simulated human sessions. Do not repeat or claim six full UAT journeys.

For each account:

1. Use `Prepare next Operator` through the current Dev Tools UI/behavior.
2. Confirm the expected fixture resets without erasing earlier required audit evidence.
3. Sign in with the distinct assigned account and verify account isolation/role.
4. Execute only the assigned export below through the real UI.
5. Confirm the exported file exists, opens or parses, has the correct format/scope, and produces the expected audit accumulation.
6. Record reset reproducibility, login result, export result, audit preservation, and any limitation.

| Operator | Assigned export    |
| -------- | ------------------ |
| OP-02    | Detections PDF     |
| OP-03    | Dashboard CSV      |
| OP-04    | Dashboard PDF      |
| OP-05    | AI Performance CSV |
| OP-06    | AI Performance PDF |

OP-01's core run covers Detections CSV. Do not populate formal Execution Log or SUS rows for any dry-run account.

## 11. Core Administrator dry run: ADM-01

Switch to the Administrator baseline block and use ADM-01's actual account from `Session Control`. Complete AD-J01 through AD-J06 in order using the live `Journey Script` and exact UAT Journey columns.

At minimum, exercise and record:

- A separate signed-out browser/profile route-boundary check for Operator access restrictions.
- Channel 4 readiness assessment and the participant's correct proceed/escalate decision.
- `Restore AD-J02 healthy baseline` before later administrator work.
- The complete `uat_replacement01` account lifecycle.
- A reliable denied login while that replacement account is deactivated, followed by the required reactivation/cleanup state.
- One Administrator-only Help Center lookup, including backup/restore guidance if that is the assigned journey.
- Creation of a new manual backup, waiting until that exact backup is `Valid`, selecting that same backup, and completing the password plus exact `RESTORE DATABASE` safeguards.
- Successful controlled restoration and sign-in after restart.
- Verification of the expected restored camera configuration, known historical anchor, participant-account survival, and prior audit evidence.
- Switch to Profile 5 only when the post-restore alert stage is ready and the intended camera is clean.
- A fresh real RTSP/AI positive event after restore and its required handling before continuing.
- Audit filtering, retrieval of the known denied action, and the assigned audit export.
- Restore readiness behavior and any timing metric whose exact start/stop is defined by the tracker.

The newly created and validated AD-J04 backup is the approved restore target for the same stage. Do not restore an older pre-UAT point.

## 12. Administrator variants: ADM-02

Do not repeat backup/restore unless the ADM-01 run exposes a reproducibility concern that makes repetition necessary and valid.

1. Use `Prepare next Administrator`.
2. Confirm ADM-02 is distinct and has the intended role/access.
3. Verify the Channel 4 condition and healthy-baseline reset are reproducible.
4. Exercise the complete `uat_replacement02` lifecycle.
5. Attempt the distinct denied login while that account is deactivated.
6. In the AD-J06 audit flow, retrieve the distinct ADM-02 denial rather than ADM-01's event.
7. Confirm earlier audit evidence remains available.
8. Record all checks without representing the variant as a second human journey.

## 13. Metrics, formulas, and tracker audit

### 13.1 Mechanical measurements

Use the exact current tracker definitions for every required timer and click count. Before measuring, copy the exact start event, stop event, inclusions, and exclusions into the Metrics table in this report. Record clock source and units.

For cross-stage timing, keep one continuous timer anchored to the defined visible/observable start rather than restarting at the next stage. Do not substitute alert-creation time for visible-collision time, or participant speech for a click, unless the tracker explicitly defines it that way.

### 13.2 Formula and validation audit

Without writing synthetic values to the live spreadsheet:

1. Inspect formulas and validation rules directly.
2. Use a local scratch calculation or a disposable local workbook representation if boundary-value evaluation is required; do not upload it as evidence.
3. Verify that blank cells do not become false passes or distort denominators.
4. Verify the denominator remains 66 unique Participant ID + Stage ID units: 54 Operator units and 12 Administrator units.
5. Verify the one-attempt rule and the absence of active retest/Attempt logic that would inflate the denominator.
6. Verify readiness gates use the intended eligible/final records rather than raw or example rows.
7. Verify Pass/Fail/Blocked, severity, and defect linkage are consistent across Summary, Execution Log, UAT Results, and Defect Log.
8. Verify SUS reverse scoring, total conversion, participant denominator, missing-response behavior, threshold, and aggregation.
9. Verify all six export assignments are represented exactly once.
10. Verify all timing fields and click-count definitions map to a journey with observable start/stop/counting events.
11. Verify UAT Traceability against current FR/NFR requirements and actual executable coverage.
12. Verify examples are visibly examples and cannot be counted in formal results.

SUS review is limited to questionnaire wording, administration flow, and scoring-formula verification. State explicitly in the final verdict that AI execution cannot produce valid SUS responses or establish actual human usability.

## 14. Verdict rules

| Verdict               | Rule                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| Ready                 | No unresolved Blocker or Major, and every core and variant check is executable and consistent.       |
| Ready with conditions | No unresolved Blocker, but one or more Major issues require mitigation before real UAT.              |
| Not Ready             | An unresolved Blocker, invalid core journey, broken metric/formula, or unsafe recovery path remains. |

Do not weaken a severity merely to obtain a better verdict. Distinguish technical execution readiness from the human usability evidence that can exist only after real participants complete the session.

---

# Continuous Dry-Run Report

Luna must update this section throughout the run. Use `Not run`, `In progress`, `Pass`, `Fail`, `Blocked`, or `Not applicable` precisely. Add rows rather than deleting evidence. Never record credentials.

## A. Run metadata

| Field                            | Value                                                                                                                                                                                                                                                        |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Run start                        | 2026-08-30T04:03:19+08:00                                                                                                                                                                                                                                    |
| Run end                          | 2026-08-30T06:22:19+08:00                                                                                                                                                                                                                                    |
| Operator/task                    | Luna Max Codex task                                                                                                                                                                                                                                          |
| Branch                           | `main`                                                                                                                                                                                                                                                       |
| HEAD                             | `8385a4398174c2dc1d3b09ec7c873f662344fdd7`                                                                                                                                                                                                                   |
| Dirty working tree summary       | 11 modified files and 14 untracked files at launch; current UAT seed/reset changes preserved. See launch `git status --short` in Preflight.                                                                                                                  |
| Database path/size/modified time | `C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\adas-capstone\adas.db`; final 1,519,616 bytes; modified 2026-08-30 06:08:03 +08:00 after the accidental `analytics` reseed; pre-run state was separately backed up before the authorized UAT reseed. |
| Browser and viewport             | Codex In-app Browser; browser viewport dimensions not independently recorded.                                                                                                                                                                                |
| Frontend URL                     | `http://localhost:5173` (Vite bound to `::1`; `127.0.0.1:5173` refused).                                                                                                                                                                                     |
| Backend/API URL                  | `http://127.0.0.1:8000` during the managed run.                                                                                                                                                                                                              |
| AI model/device                  | `ai_engine/epoch50.engine` (TensorRT engine); NVIDIA GeForce RTX 3050 Ti Laptop GPU, CUDA available.                                                                                                                                                         |
| MediaMTX binary/version          | MediaMTX v1.18.0, Windows amd64, dedicated `mediamtx-uat.yml`.                                                                                                                                                                                               |
| FFmpeg version                   | FFmpeg 8.1.1 essentials build.                                                                                                                                                                                                                               |
| Safety backup ID                 | `4ae548354a9a40c1806e17912464fae5`                                                                                                                                                                                                                           |
| Safety backup directory          | `C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\adas-capstone\var\uat-safety-backups\pre-dry-run-20260830T041215`                                                                                                                                    |
| Final verdict                    | `Not Ready` — B-006 invalidated the UAT-only run before operator variants and administrator execution; no automatic restore/reseed was performed.                                                                                                            |

## B. Source read coverage

| Source           | Tab/section                        | Read completely? | Authority/exception confirmed? | Notes                                                                                                                                                  |
| ---------------- | ---------------------------------- | ---------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Test plan        | `__main__`                         | Pass             | Pass                           | Live tab `t.gu7j5a4nobzi`; consolidated authoritative plan; revision read 2026-08-30.                                                                  |
| Test plan        | `claude v2`                        | Pass             | Pass                           | Live tab `t.69pznq56gm30`; complete comparison source only; not used to override `__main__`.                                                           |
| Tracker          | `Summary`                          | Pass             | Pass                           | Live spreadsheet `1yX-asNF-jsEZwIVSGFDvKyjF0Frh4IjWLY0Svfe82vU`, sheet ID `4101000`; formulas/values/notes read.                                       |
| Tracker          | `Guide & Examples`                 | Pass             | Pass                           | Sheet ID `4101009`; examples, instructions, and exclusions read.                                                                                       |
| Tracker          | `Unit Testing`                     | Pass             | Pass                           | Sheet ID `3000001`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Integration Testing`              | Pass             | Pass                           | Sheet ID `3000002`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `System / E2E Testing`             | Pass             | Pass                           | Sheet ID `3000003`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `AI Model Validation`              | Pass             | Pass                           | Sheet ID `3000004`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Performance & Load Testing`       | Pass             | Pass                           | Sheet ID `3000005`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Reliability & Endurance`          | Pass             | Pass                           | Sheet ID `3000006`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Security Testing`                 | Pass             | Pass                           | Sheet ID `3000008`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Backup & Recovery`                | Pass             | Pass                           | Sheet ID `3000007`; empty case rows plus strict Result validation read; prerequisite-only review.                                                      |
| Tracker          | `Session Control`                  | Pass             | Pass                           | Sheet ID `4101001`; fields, eight participant rows, credentials (redacted), and nine readiness rows read.                                              |
| Tracker          | `UAT Journeys`                     | Pass             | Pass                           | Sheet ID `4101002`; all 9 columns and all 15 stage rows read.                                                                                          |
| Tracker          | `Execution Log`                    | Pass             | Pass                           | Sheet ID `4101003`; exactly 66 rows, one-attempt structure, formulas/notes/validations read.                                                           |
| Tracker          | `SUS Questionnaire`                | Pass             | Pass                           | Sheet ID `4101004`; wording, 1–5 validation, reverse scoring, formulas, and blank behavior read.                                                       |
| Tracker          | `Usability Results`                | Pass             | Pass                           | Sheet ID `4101005`; participant formulas, timing/click/assistance metrics, and blank behavior read.                                                    |
| Tracker          | `UAT Results`                      | Pass             | Pass                           | Sheet ID `4101006`; gates, formulas, statuses, and eligibility logic read.                                                                             |
| Tracker          | `Defect Log`                       | Pass             | Pass                           | Sheet ID `4101007`; severity/status validation and empty state read.                                                                                   |
| Tracker          | `UAT Traceability`                 | Pass             | Pass                           | Sheet ID `4101008`; 20 FR, 22 NFR, and 2 acceptance mappings read.                                                                                     |
| Sign-off         | `Tab 1`                            | Pass             | Pass                           | Live tab `t.0`; acceptance/sign-off record read completely.                                                                                            |
| Sign-off         | `Scripts`                          | Pass             | Pass                           | Live tab `t.gl2h436x42hu`; briefing, tour, facilitator, trigger, recovery, debrief and evidence rules read completely.                                 |
| Sign-off         | `Journey Script`                   | Pass             | Pass                           | Live tab `t.ha3mobdsx1ni`; manually maintained spoken wording authoritative and read completely.                                                       |
| Defense paper    | Requirements/context only          | Pass             | Pass                           | Requirements, use cases, architecture, data dictionary and deployment context read; all testing sections explicitly excluded as stale.                 |
| Current checkout | Relevant UAT implementation/config | Pass             | Pass                           | Dirty UAT seed/reset implementation, Dev Tools UI/API, lifecycle scripts, model/config, clips, and `mediamtx-uat.yml` inspected; focused tests passed. |

## C. Preflight results

| Check                                   | Timestamp                                                                                            | Status | Evidence/observed result                                                                                                                                                                                           | Finding ID |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| Git identity and dirty tree captured    | 04:03:19 +08:00                                                                                      | Pass   | `main`, HEAD `8385a4398174c2dc1d3b09ec7c873f662344fdd7`; 11 modified and 14 untracked files recorded; no reset/switch/pull/merge/commit/push.                                                                      |            |
| Existing processes/ports inventoried    | 04:03–04:13 +08:00                                                                                   | Pass   | No listener on 8000, 5173, 8554, or 8555; no matching backend/AI/restore process remained before backup. Existing unrelated Node/PowerShell processes left untouched.                                              |            |
| Database path/state confirmed           | 04:05–04:13 +08:00                                                                                   | Pass   | Resolved `adas.db` path is repo-root absolute; live DB 528,384 bytes with WAL/SHM sidecars; normal backup dir is `var\backups`.                                                                                    |            |
| UAT seed/reset controls confirmed       | 04:06–04:11 +08:00                                                                                   | Pass   | Dirty Dev Tools controls expose UAT seed/reset phases; 45 focused backend tests passed and 6 focused frontend tests passed.                                                                                        |            |
| MediaMTX/FFmpeg/clips confirmed         | 04:03–04:05 +08:00                                                                                   | Pass   | MediaMTX v1.18.0 exists at the expected path; FFmpeg 8.1.1 exists; `airbase.mp4`, `dekwatro.mp4`, `car-motor-motor.mp4`, and `red-car-motor.mp4` exist.                                                            |            |
| AI model/device                         | `ai_engine/epoch50.engine` (TensorRT engine); NVIDIA GeForce RTX 3050 Ti Laptop GPU, CUDA available. |
| Restore coordinator lifecycle confirmed | 04:06–04:10 +08:00                                                                                   | Pass   | `start-dev.ps1 -Backend -Frontend -Ai` creates a controlled launch profile, starts `watch-restores --platform windows` only for managed backend+AI, and `stop-dev.ps1` stops it fail-closed via tracked PID/state. |            |
| Exactly one MediaMTX profile active     | 04:04 +08:00                                                                                         | Pass   | `mediamtx-uat.yml` has exactly one uncommented `paths:` block: OP-J01–OP-J03 Baseline/Silent; all other complete blocks remain commented.                                                                          |            |

## D. Safety backup record

| Field                             | Value                                                                                                                                                                                                                                  |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Created at                        | 2026-08-30T04:12:15 +08:00                                                                                                                                                                                                             |
| Separate directory                | `C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\adas-capstone\var\uat-safety-backups\pre-dry-run-20260830T041215`                                                                                                              |
| Backup ID                         | `4ae548354a9a40c1806e17912464fae5`                                                                                                                                                                                                     |
| Creation result                   | Pass — manual backup created; database file 528,384 bytes; manifest recorded SHA-256 and schema revision.                                                                                                                              |
| Independent verify result         | Pass — `checksum_matches=true`, `integrity_check=true`, `foreign_key_check=true`, `verify_exit=0`; quick check also true.                                                                                                              |
| Manifest/database files confirmed | Pass — `adas_backup_4ae548354a9a40c1806e17912464fae5.db` and matching `.json` manifest present in the separate directory.                                                                                                              |
| Retention isolation confirmed     | Pass — temporary `BACKUP_DIR` override was used only for creation/verification and removed before app start; normal `var\backups` was not redirected.                                                                                  |
| Redacted restore procedure        | If later authorized: stop the controlled stack, run the repository maintenance restore for backup ID `<backup_id>` with `BACKUP_DIR=<safety-directory>`, verify readiness, and finalize; do not run automatically during this dry run. |

**Safety gate:** `PASSED` — creation and independent verification completed before reseed; the verified safety backup is preserved and will not be restored automatically.

## E. Trigger and profile log

| Entry | Stage(s)      | Profile               | Save/restart time                                                          | Publishers ready time                                                                                  | Intended alert time(s) | Observed alert time(s)/IDs                                                                                                                                                                                                                              | Result/deviation                                                                                                                                                                                                  |
| ----: | ------------- | --------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|     1 | OP-J01–OP-J03 | Baseline/silent       | 2026-08-30T04:31:19+08:00                                                  | 2026-08-30T04:31:20+08:00 (five publishers observed; exact last-ready line not separately timestamped) | None                   | None; seeded Channel 6 remained an ongoing tray record and had no configured MediaMTX path                                                                                                                                                              | Pass mechanically with limitation — baseline/silent flow and camera state were exercised; Channel 6 had no stream in the dedicated five-channel config.                                                           |
|     2 | OP-J04–OP-J07 | Multi-alert           | 2026-08-30T05:43:02+08:00; repeat after AI ready 2026-08-30T05:48:19+08:00 | 2026-08-30T05:43:03+08:00; repeat publishers reconnected after 05:48:19                                | Two queued alerts      | Real rows 17/18 at 04:44:43/04:45:04; current profile-2 run also produced rows 19/20/21 at 05:52:27/05:52:55/05:54:22. Rows were visible in the browser and handled; no fabricated event.                                                               | Pass mechanically with deviations — the MediaMTX PTY closed on Ctrl+C so a fresh exact-command terminal substituted for Up/Enter; the continuous profile produced repeat alerts after cameras resumed; see M-003. |
|     3 | OP-J08–OP-J09 | Recovery/handover     | 2026-08-30T05:56:24+08:00                                                  | 2026-08-30T05:56:24+08:00 (Channel 3 publisher; subsequent AI reader verified)                         | Channel 3 positive     | Real row 22 (Channel 3) was detected at 06:00:20, survived browser reload, and was confirmed Ongoing at 06:02:01; Help rendered. Detections CSV request returned HTTP 200, but the in-app Blob download was not surfaced for file/content verification. | Pass for executed OP-J08 mechanics; OP-J09 export-file verification limited to HTTP 200/header evidence.                                                                                                          |
|     4 | AD-J01–AD-J04 | Admin baseline        | Not started                                                                | Not started                                                                                            | None                   | Not run because B-006 replaced the UAT fixture before Administrator execution.                                                                                                                                                                          | Blocked by B-006 — no admin result inferred.                                                                                                                                                                      |
|     5 | AD-J05–AD-J06 | Post-restore positive | Not started                                                                | Not started                                                                                            | Channel 1 positive     | Not run because B-006 replaced the UAT fixture before Administrator execution and no AD-J04 restore was authorized.                                                                                                                                     | Blocked by B-006 — no post-restore result inferred.                                                                                                                                                               |

## F. Core Operator stage results

| Stage  | Setup/trigger executed                                                         | Written prompt followed                                                                                         | Numbered participant actions actually performed                                                                                                                                                                                                    | Expected result                                                                                                                                                                                             | Actual result                                                                                                                   | Timing/click evidence                                                                                                                                                                                                   | Intervention/deviation | Status       | Finding IDs |
| ------ | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------------ | ----------- |
| OP-J01 | Profile 1 baseline/silent; browser Cameras route at 2026-08-30T04:35:43+08:00. | Yes — live UAT Journey and Journey Script wording had been read; no answer was supplied to a human participant. | Navigated to Cameras and inspected all six cards; no participant alert action.                                                                                                                                                                     | Six cameras displayed; 5/6 enabled; Channels 1, 2, 3, and 5 Connected/Active; Channel 4 Disabled/Disconnected/Inactive; Channel 6 retained the seeded Ongoing incident and displayed Unresponsive/Inactive. | No participant timer or click metric was captured; this was a mechanical state observation.                                     | Channel 6 has no configured stream in the five-channel MediaMTX profile; this is an execution limitation, not a fabricated pass.                                                                                        | Pass                   | M-002        |
| OP-J02 | Baseline profile; Profile > Alarm Settings.                                    | Yes — live UAT Journey and Journey Script read; no human briefing or response was simulated.                    | Changed the visible snooze value from 30 to 15 and selected Save; observed the success toast; reloaded and verified 15 persisted. Tone remained Default and volume 50 because no concrete participant values were assigned.                        | Required 15-second snooze setting persisted without changing the other settings.                                                                                                                            | No exact participant timing/click metric captured.                                                                              | No human learnability or preference conclusion claimed.                                                                                                                                                                 | Pass                   |              |
| OP-J03 | System Health, AI Performance, and Cameras routes.                             | Yes — stage wording and acceptance expectations were read.                                                      | Observed two host warnings on System Health; reloaded AI Performance after the first stale lazy-route snapshot and verified heading/KPIs/table/filters/export; enabled only the assigned Channel 4 readiness camera and verified Connected/Active. | The assigned camera changed to enabled/connected/active; AI Performance rendered after route readiness.                                                                                                     | No valid human NFR-09/timing measurement; only route/state timestamps were observed.                                            | Two host warnings conflicted with the single-condition script; first AI snapshot was stale but retest passed; no code fix applied.                                                                                      | Pass                   | M-002, B-003 |
| OP-J04 | Profile 2 active; MediaMTX publishers/restart verified.                        | Yes — two-alert spoken scenario read; no prompt answer was supplied.                                            | Observed the real queued alert dialog showing Alert 1 of 2, then left both alerts untouched initially. Real rows 17 and 18 were visible with their camera names, timestamps, and snapshots.                                                        | Two queued alerts remained available for inspection.                                                                                                                                                        | Real event rows: log 17 at 04:44:43 and log 18 at 04:45:04 +08:00; no synthetic trigger.                                        | The rows were generated by a real earlier profile-2 run; subsequent live profile-2 loops also produced repeat alerts, recorded under M-003.                                                                             | Pass                   | M-003        |
| OP-J05 | Continued profile 2; one global snooze then alert handling.                    | Yes — optional global snooze/confirm wording read.                                                              | Clicked Snooze once; then Confirm on the selected log 18 and later on log 17. Database readback showed log 18 Ongoing at 05:49:52 and log 17 Ongoing at 05:51:45 +08:00.                                                                           | Snooze control silenced both queued Unverified alerts; a confirm action moved the selected alert to Ongoing.                                                                                                | No valid NFR-09 elapsed time or participant click metric; only database timestamps and actual action sequence were recorded.    | The first confirm landed on the false-alert row before the intended true-positive-first sequence; the false row was later corrected. A later concurrent alert also made action-to-row attribution ambiguous; see M-003. | Pass                   | M-003        |
| OP-J06 | Profile 2 follow-through after the first confirmation.                         | Yes — false-alert decision wording read.                                                                        | Corrected log 18 through the Ongoing tray using Dismiss Accident at 05:52:09 +08:00; it was not dismissed while Unverified because it had already been confirmed. No second attempt or synthetic reset was used.                                   | The false alert ended Dismissed and the correction path remained available.                                                                                                                                 | Exact database transition recorded; no human timing/click metric.                                                               | This is a valid Ongoing-to-Dismissed correction but deviates from the intended Unverified false-positive path because of the earlier action order.                                                                      | Pass                   | M-003        |
| OP-J07 | Profile 2 follow-through and seeded tray.                                      | Yes — clearing/correction wording read.                                                                         | Resolved genuine log 17; opened the tray; dismissed seeded Ongoing log 16; handled extra real profile-2 rows 19–21 when they arrived, leaving no open profile-2 incident before stopping MediaMTX.                                                 | Confirmed incident resolved and seeded ongoing false incident corrected; two active records were observed before final clearing.                                                                            | Database readback: log 17 Resolved, log 16 Dismissed, log 18/20 Dismissed, log 19/21 Resolved; no exact human metric.           | Continuous looping produced extra genuine/false-labelled fixture alerts after camera resume, requiring additional handling; see M-003.                                                                                  | Pass                   | M-003        |
| OP-J08 | Profile 3 recovery; real Channel 3 `red-car-motor.mp4` publisher.              | Yes — refresh/reconnect wording read.                                                                           | Real log 22 appeared on Channel 3 at 06:00:20 +08:00; reloaded the browser while it was Unverified; the alert remained after reload; clicked Confirm Accident and verified Ongoing.                                                                | Pending alert survived browser recovery and remained Ongoing after confirmation.                                                                                                                            | Real row 22; confirmation read back at 06:02:01 +08:00; no human timing metric.                                                 | Initial 55-second observation found no Channel 3 event, so a managed AI/backend/coordinator restart was performed; the complete retest then produced log 22.                                                            | Pass                   | B-005        |
| OP-J09 | Recovery profile remained active; Help and Detections UI.                      | Yes — handover/export assignment wording read.                                                                  | Opened Help Center and verified role-filtered articles; opened Detections export menu and selected Export as CSV. Backend log recorded HTTP 200 for `/api/alerts/export?...format=csv`.                                                            | Help accessible and assigned Detections CSV export requested.                                                                                                                                               | No local downloaded file, Blob download event, or parsed file content was observed in the in-app browser; value is not claimed. | Export-file verification remained incomplete; no formal tracker row written.                                                                                                                                            | Blocked                | M-004        |

## G. Operator variant results

| Account | Prepare-next reproducible                                            | Distinct login/role | Assigned export    | File/content result            | Earlier audit evidence preserved                      | Status  | Finding IDs |
| ------- | -------------------------------------------------------------------- | ------------------- | ------------------ | ------------------------------ | ----------------------------------------------------- | ------- | ----------- |
| OP-02   | Not run — B-006 replaced the UAT fixture before variant preparation. | Not run             | Detections PDF     | Not run; no file/content claim | Earlier audit evidence not checked after invalidation | Blocked | B-006       |
| OP-03   | Not run — B-006 replaced the UAT fixture before variant preparation. | Not run             | Dashboard CSV      | Not run; no file/content claim | Earlier audit evidence not checked after invalidation | Blocked | B-006       |
| OP-04   | Not run — B-006 replaced the UAT fixture before variant preparation. | Not run             | Dashboard PDF      | Not run; no file/content claim | Earlier audit evidence not checked after invalidation | Blocked | B-006       |
| OP-05   | Not run — B-006 replaced the UAT fixture before variant preparation. | Not run             | AI Performance CSV | Not run; no file/content claim | Earlier audit evidence not checked after invalidation | Blocked | B-006       |
| OP-06   | Not run — B-006 replaced the UAT fixture before variant preparation. | Not run             | AI Performance PDF | Not run; no file/content claim | Earlier audit evidence not checked after invalidation | Blocked | B-006       |

## H. Core Administrator stage results

| Stage  | Setup/trigger executed                                                   | Written prompt followed | Numbered participant actions actually performed | Expected result | Actual result                                                                             | Timing/click evidence | Intervention/deviation | Status  | Finding IDs |
| ------ | ------------------------------------------------------------------------ | ----------------------- | ----------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------- | --------------------- | ---------------------- | ------- | ----------- |
| AD-J01 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No admin result inferred.                                                                 | Blocked by B-006      | None                   | Blocked | B-006       |
| AD-J02 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No admin result inferred.                                                                 | Blocked by B-006      | None                   | Blocked | B-006       |
| AD-J03 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No replacement-account lifecycle result inferred.                                         | Blocked by B-006      | None                   | Blocked | B-006       |
| AD-J04 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No manual backup/restore result inferred; safety backup was not used as an AD-J04 target. | Blocked by B-006      | None                   | Blocked | B-006       |
| AD-J05 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No post-restore camera/history/positive-alert result inferred.                            | Blocked by B-006      | None                   | Blocked | B-006       |
| AD-J06 | Not run — B-006 replaced the UAT fixture before Administrator execution. | Not run                 | Not run                                         | Not assessed    | No audit filtering/denial/export result inferred.                                         | Blocked by B-006      | None                   | Blocked | B-006       |

## I. Administrator variant results

| Check                                              | Actual result                                                         | Status  | Finding IDs |
| -------------------------------------------------- | --------------------------------------------------------------------- | ------- | ----------- |
| ADM-02 distinct account/role                       | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| Channel 4 condition and healthy reset reproducible | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| `uat_replacement02` lifecycle                      | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| Distinct deactivated-account denied login          | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| AD-J06 retrieves the distinct denial               | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| Earlier audit evidence preserved                   | Not run — B-006 replaced the UAT fixture before variant preparation.  | Blocked | B-006       |
| Backup/restore repetition required?                | No decision — B-006 invalidated the administrator path before ADM-01. | Blocked | B-006       |

## J. Metrics and click measurements

| Metric/stage                                         | Exact tracker start                                                            | Exact tracker stop                                  | Inclusions/exclusions                                                                          | Clock/count method                                                                                  | Observed value         | Requirement/gate | Result | Finding ID |
| ---------------------------------------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ---------------------- | ---------------- | ------ | ---------- |
| OP-J05 NFR-09 collision-visible-to-operator-decision | Collision’s first visible frame on the monitored camera                        | Operator records Confirm or Dismiss                 | Detector accumulation, alert propagation, CCTV/DSS verification, and decision; snooze excluded | Not measured — no participant or controlled timer was anchored to the first visible collision frame | ≤25 seconds target     | Not run          |        |
| OP-J05 click count                                   | First genuine interaction through confirm, excluding snooze, per tracker notes | Exclude global snooze                               | No participant click counter was started                                                       | Not measured                                                                                        | <=3 clicks             | Not run          |        |
| OP-J08 recovery                                      | Pending alert visible through browser refresh/reopen and confirmation          | Recovery action only; no unrelated wait             | Browser reload retained log 22, but no exact tracker timer was started                         | Technical recovery observed; elapsed metric not measured                                            | Per tracker definition | Not run          |        |
| AD-J04 restore                                       | New Valid backup selected through controlled restore completion                | Exact same backup; password/confirmation safeguards | Administrator path was blocked by B-006 before backup creation                                 | Not measured                                                                                        | <=60 seconds           | Blocked          | B-006  |
| SUS overall mean                                     | Ten-item human questionnaire after all participant stages                      | No AI-generated responses permitted                 | No human participants                                                                          | Not available                                                                                       | >=68                   | Not applicable   |        |

## K. Script and flow review

| Area                  | Exact source/location            | What was assessed                                        | Observed result                                                                                                                                                                                            | Severity/Finding ID                               |
| --------------------- | -------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Briefing              | Journey Script/Scripts           | Non-technical first-time orientation; no answer leakage  | Source wording read completely; it withholds controls, alert counts, expected outcomes, and locations. No human briefing was delivered.                                                                    | Pass content review; human evidence not available |
| Tour                  | Journey Script/Scripts           | Teaches location/capability/quirks without solving tasks | Source wording read completely; verbal tour gives capability context without screen/control instruction. No human tour was delivered.                                                                      | Pass content review; human evidence not available |
| Stage transitions     | Journey Script/UAT Journeys      | Natural scenario handoff and trigger cues                | State-only cues were read; OP-01 transition was mechanically executed, but looping profile-2 alerts created extra arrivals and an attribution race.                                                        | M-003                                             |
| Assistance language   | Journey Script/Scripts           | Consistent, logged, validity-preserving                  | Source rule read; no human requested assistance and no assistance log was created.                                                                                                                         | Not applicable to AI dry run                      |
| Consent/privacy/photo | Journey Script/acceptance record | Matches actual collection and evidence                   | Consent/privacy/photo requirements were read; no participant, photo, audio, video, or SUS collection occurred.                                                                                             | Not applicable to AI dry run                      |
| Debrief and SUS       | Journey Script/SUS               | Neutral, understandable, non-leading                     | Wording/formula sources were read; no human debrief or SUS responses were collected.                                                                                                                       | Not applicable; human evidence limitation         |
| Facilitator recovery  | Scripts/UAT Journeys             | Trigger failure, delay, reconnect, unexpected alert      | Real profile restart, RTSP reconnect, browser refresh recovery, and extra-alert handling were observed; MediaMTX Ctrl+C closed the PTY, so the exact command was relaunched in a fresh dedicated terminal. | B-005 resolved; M-003; PTY deviation              |

## L. Tracker formula, validation, and traceability audit

| Check                                | Location/formula or rule inspected                                  | Boundary/consistency test                                                                              | Result | Finding ID |
| ------------------------------------ | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------ | ---------- |
| 66 unique participant-stage units    | `Execution Log!A2:A120`; UAT Results B7                             | Fixed 66 IDs counted; no synthetic row edits                                                           | Pass   |            |
| 54 Operator + 12 Administrator split | `Execution Log` participant IDs                                     | 54 OP stage units plus 12 AD stage units = 66                                                          | Pass   |            |
| One-attempt rule                     | `Execution Log`; no Attempt column or duplicate execution structure | Exactly 66 planned rows; no retest rows added                                                          | Pass   |            |
| Execution status validation          | `Execution Log` Result/status validation                            | Allowed values read as Not Executed/Pass/Fail/Blocked/Retest Required; live rows remained Not Executed | Pass   |            |
| Summary calculations                 | `Summary` formulas and example exclusions                           | Final live summary still showed 66 planned, 0 completed/pass/fail and 66 incomplete                    | Pass   |            |
| UAT Results gates                    | `UAT Results` B7:B17 and eligibility formula                        | Blank-run values correctly produced 0 completed/pass and `NOT YET ELIGIBLE`; no gate was forced        | Pass   |            |
| Blank/error behavior                 | SUS blanks, Usability Results IFERROR/blank formulas, UAT Results   | Blank SUS remains blank; overall gate remains pending/not eligible                                     | Pass   |            |
| SUS forward/reverse scoring          | `SUS Questionnaire!N5:N12` formula                                  | Formula read: forward/reverse 1–5 scoring multiplied by 2.5; no responses written                      | Pass   |            |
| SUS denominator/threshold            | `Summary` SUS count/mean and `UAT Results` B14/B16                  | Eight participant slots and threshold >=68 read; mean remains 0/pending with no human rows             | Pass   |            |
| Six export assignments               | UAT Journeys OP-J09 plus operator variant table                     | OP-01 CSV and OP-02..06 five assigned formats represented exactly once                                 | Pass   |            |
| Timing/click definitions             | UAT Journeys timing columns and Execution Log D/E notes             | Definitions are present; no human values fabricated; dry-run metric rows remain unmeasured             | Pass   |            |
| FR/NFR traceability                  | `UAT Traceability` 45 mapped rows                                   | 20 FR, 22 NFR, and acceptance mappings read; AC-UAT New Addition remains mapped as recorded            | Pass   |            |
| Example-row exclusion                | `Guide & Examples` instructions and Summary formulas                | Example rows visibly excluded from formal formulas; live results unchanged                             | Pass   |            |

## M. Finding ledger

Record a finding here before proposing or making any fix.

| ID    | Time found              | Severity | Source/location                                                               | Evidence/observed behavior                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Validity/participant impact                                                                                                                                                                                            | Dependent path stopped?                                                                                             | Recommended correction                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Status                                                                                                                                          |
| ----- | ----------------------- | -------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| B-001 | 2026-08-30T04:14 +08:00 | Blocker  | Preflight / single authorized `uat` reseed (`backend/scripts/reseed_dev.py`)  | The only reseed attempt exited 1 before deleting/recreating the database: `Could not delete ... adas.db. Stop the backend server or any process using the database`. Read-only follow-up found `127.0.0.1:8000` LISTENING under PID `32676`, with a repository `fastapi` parent PID `31380` started at 03:00:10 +08:00 before this task; the live DB could not be hashed while held. `openfiles /query` returned no owner because local tracking was unavailable.                                                                                                                                                                                                                                                                                                                                               | Without a safe reseed, the required current `uat` fixture could not be established; all dependent UAT execution was stopped.                                                                                           | Yes — UAT reseed, service start, and all dependent journeys/variants.                                               | Stop only the identified pre-existing backend via the repository lifecycle script, verify port/process closure, then retry the existing `uat` reseed once; no code/schema/API change.                                                                                                                                                                                                                                                                                                                                            | Resolved after consent; backend stopped, port 8000 closed, authorized retry succeeded, UAT fixture verified.                                    |
| B-002 | 2026-08-30T04:22 +08:00 | Blocker  | Preflight after reseed / managed runtime metadata                             | The pre-existing managed AI engine remained running (PID chain `34652` → `34352` → `6232`) and the pre-existing restore coordinator remained running (PID chain `34336` → `5796` → `27184`); both started before this task. `var\backups\restore_coordinator_state.json` reported `runtime_ready=false` and `reason=runtime_uncontrolled` after the backend stop. Starting the requested managed backend+AI stack then would either be refused by the launch guard or create duplicate AI/coordinator paths, invalidating real RTSP/AI evidence and AD-J04 restore. AI outbox was empty.                                                                                                                                                                                                                        | A clean, controlled runtime was required before MediaMTX and the browser journey; reusing the stale coordinator could not support the required restore path.                                                           | Yes — controlled service start, real trigger profiles, OP/AD journeys, especially AD-J04/AD-J05 restore.            | Stop only the identified pre-existing ADAS AI/coordinator process trees with the repository lifecycle command `pwsh -File scripts\stop-dev.ps1 -Backend -Ai`; verify the exact trees, ports, and coordinator state are gone, then start the requested managed backend+AI path once and verify readiness before MediaMTX/browser execution. No code/schema/API change.                                                                                                                                                            | Resolved after explicit consent; full ADAS shutdown verified no matching backend/AI/coordinator/MediaMTX/FFmpeg processes or service listeners. |
| M-001 | 2026-08-30T04:33 +08:00 | Minor    | Runtime URL / browser bring-up                                                | `http://127.0.0.1:5173/` returned `ERR_CONNECTION_REFUSED`; netstat showed Vite listening on `[::1]:5173`. A fresh browser tab reached the login screen at `http://localhost:5173/`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | The handoff’s actual browser workflow remains executable through the listening hostname; the operator-facing URL must use `localhost` in this run.                                                                     | No — only the failed first navigation; UAT path continued on the verified URL.                                      | Record the bound hostname in the final run instructions or configure an explicit IPv4 bind before real UAT; no change applied during this dry run.                                                                                                                                                                                                                                                                                                                                                                               | Open — non-blocking                                                                                                                             |
| M-002 | 2026-08-30T04:37 +08:00 | Major    | OP-J03 / live System Health page vs Journey Script condition                  | The authoritative Journey Script says the participant should find one condition not in the expected state. The actual page showed `System memory is 95.1% full (limit: 95%)` plus a separate `Storage getting full — Storage is 86% full` warning, before the seeded Channel 4 Disabled condition was corrected.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | A real participant could reasonably choose either telemetry warning rather than the intended camera condition; a formal OP-J03 result could therefore be misleading. No human decision was fabricated in this dry run. | No — deterministic camera UI check continued; human judgment validity remains qualified.                            | Make the dry-run/UAT fixture produce one unambiguous readiness condition or revise the scenario wording/acceptance rule to distinguish background host warnings; no change applied.                                                                                                                                                                                                                                                                                                                                              | Open — requires mitigation before real UAT                                                                                                      |
| B-003 | 2026-08-30T04:38 +08:00 | Blocker  | OP-J03 / `http://localhost:5173/user/ai` navigation and rendered page         | Clicking the visible `AI Performance` navigation link initially produced URL `/user/ai` while the lazy route had not finished replacing the prior `System Health` content after a 1.2-second wait. A controlled reload followed by a 2.5-second wait rendered the correct AI Performance heading, KPIs, table, filters, and export control; source routing in `frontend/src/App.tsx` and `AiPerformance.tsx` is correct.                                                                                                                                                                                                                                                                                                                                                                                        | The initial snapshot would have invalidated the AI Performance observation if treated as final; after the explicit route-readiness retest, OP-J03 remains executable.                                                  | No — OP-J03 continued after route retest; no dependent stage was invalidated.                                       | Wait for the lazy route to settle or use a route-ready assertion before recording the observation; no code change applied.                                                                                                                                                                                                                                                                                                                                                                                                       | Resolved after retest; retain as a transient dry-run observation.                                                                               |
| B-004 | 2026-08-30T04:48 +08:00 | Blocker  | Runtime bring-up after the user-directed full stop / repeated lifecycle start | The first restart attempt returned the shared `uv` cache access-denied error and exposed no listeners. A second elevated start eventually produced multiple repository ADAS runtime trees at once: two FastAPI backend chains, two AI-engine chains, multiple Vite processes, and a managed restore coordinator; the controlled state reported `runtime_ready=true` while the process inventory was not single-instance. Duplicate inference paths would invalidate real RTSP/AI evidence and restore coordination. The subsequent repository `pwsh -File scripts\stop-dev.ps1 -All` failed closed with `A matching restore coordinator remains outside the terminated process tree` and reported that no managed service was terminated; inspection found the coordinator state PID and PID-file PID disagree. | Continued trigger and restore work was stopped until one controlled stack can be verified; no participant result was recorded from this duplicate runtime.                                                             | Yes — profile-2 continuation was held before the next participant stage.                                            | With explicit consent, resolve only the verified ADAS process trees by exact PID after rechecking each command line (coordinator tree, both backend/AI trees, Vite trees, and MediaMTX/FFmpeg), then run the repository stop command to clear controlled metadata; verify no matching ADAS processes/listeners/state remain; then run one elevated `pwsh -File scripts\start-dev.ps1 -Backend -Frontend -Ai` and wait for a single backend, frontend, AI, and coordinator instance before continuing. No code/schema/API change. | Resolved after exact-PID controlled cleanup and single-instance retest; no code/schema/API change                                               |
| B-005 | 2026-08-30T05:58 +08:00 | Blocker  | OP-J08 / profile-3 recovery trigger                                           | MediaMTX profile 3 loaded the required `red-car-motor.mp4` on Channel 3 and the AI engine established RTSP readers, but no new Channel 3 detection was recorded during a 55-second read-only observation window; the AI log had no Channel 3 alert. The authoritative fixture labels this clip as a positive at approximately 15 seconds. No OP-J08 success was recorded or inferred.                                                                                                                                                                                                                                                                                                                                                                                                                           | The pending-alert/reconnect journey cannot be validly completed until the real Channel 3 trigger is observed.                                                                                                          | Yes — OP-J08 was held; no synthetic alert or tracker result was written.                                            | Restart only the managed AI/backend/coordinator stack while leaving profile-3 MediaMTX running; verify one clean AI tree reconnects to Channel 3, then observe the real clip for at least one full 61-second loop and record the actual result. No code/schema/API change; if no alert after the retest, retain as an execution limitation and continue independent checks.                                                                                                                                                      | Resolved after controlled managed restart; real Channel 3 log 22 observed and recovered                                                         |
| B-006 | 2026-08-30T06:08 +08:00 | Blocker  | Admin DevPanel close attempt during UAT session preparation                   | A forced click intended to close the visible `Dev tools` side panel propagated to the underlying `analytics` profile control; the panel showed `analytics` as `Seeding...`. The request completed and the UI reported 62 detections, 8 cameras, 8 users, 9363 health rows, 5 exports, and 62 snapshots, signed in as admin. Read-only final verification reported 8 users, 8 cameras, 62 detections, 37 audit rows, 8642 raw health rows, 721 hourly rows, and 5 export jobs; database integrity was `ok` and the foreign-key check was empty. No further browser actions or formal tracker writes were made after confirmation.                                                                                                                                                                                | The required current UAT state may have been replaced; subsequent participant execution cannot be treated as valid until the impact is known. No synthetic result or automatic restore/reseed is permitted.            | Yes — all dependent participant work was paused immediately.                                                        | Allow the already-started request to settle; verify the active database profile, row counts, audit preservation, and service state read-only. Preserve the safety backup. Do not run another reseed or restore automatically; if the UAT fixture was replaced, record the run as invalidated/limited rather than fabricate recovery evidence.                                                                                                                                                                                    | Open — impact assessment pending                                                                                                                |
| M-003 | 2026-08-30T05:53 +08:00 | Major    | OP-J04–OP-J07 / continuous profile-2 alert queue                              | After the first profile-2 alerts were handled, resuming cameras while the looping real clips were still running produced additional rows 19, 20, and 21. During the live queue, the DOM showed log 19 while a confirm action completed against log 20; database readback showed log 20 Ongoing and log 19 still Unverified. The sequence was later reconciled through the tray, but action-to-alert attribution was not stable under concurrent arrivals.                                                                                                                                                                                                                                                                                                                                                       | A real participant could act on a different alert than the one just observed, and the one-attempt journey would no longer represent the written true/false sequence.                                                   | Yes — the profile-2-dependent sequence was closed and the next profile was not started until the queue was cleared. | Freeze or gate the multi-alert fixture during participant decisions, or make the selected alert/action identity explicit and invariant through concurrent arrivals; no code change applied in this dry run.                                                                                                                                                                                                                                                                                                                      | Open — requires mitigation before real UAT                                                                                                      |
| M-004 | 2026-08-30T06:03 +08:00 | Minor    | OP-J09 / Detections CSV export evidence                                       | The real browser selected `Export as CSV`; the backend log recorded HTTP 200 and the expected export endpoint. The in-app browser did not emit a download event, no new local export file was observable in the user Downloads folder, and the Blob response could not be parsed through the supported browser inspection surface.                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | The export request behavior was observed, but file existence/format/content/scope could not be verified; no success was claimed.                                                                                       | No — OP-J09 was marked Blocked for this evidence gap; no tracker write or synthetic file was made.                  | Provide a supported artifact-capture path for the in-app browser or verify the downloaded file in the actual browser profile; no change applied.                                                                                                                                                                                                                                                                                                                                                                                 | Open — evidence gap                                                                                                                             |

## N. Consent and approved-fix log

Only Blocker fixes with explicit consent belong here. Quote or tightly summarize the user's decision without exposing secrets.

| Finding ID | Proposed fix and exact targets                                                                                                                                                                                                                                             | Risk                                                                                                                                                                           | Rollback                                                                                                                                                                  | Verification plan                                                                                                                                                                                                                                                                                                                                                         | Consent request time    | User decision/time                                                                                                                                                                                                           | Change applied                                                                                                           | Result                                                                                                                                                                                                                                         |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B-001      | Stop only the identified pre-existing ADAS backend via `pwsh -File scripts\stop-dev.ps1 -Backend` (which resolves the listener on port 8000 and tree-stops that process), then retry the existing `uat` reseed implementation once. No code/schema/API change is proposed. | The command targets the pre-existing backend listener rather than broad process names; it interrupts that running service and any user session attached to it.                 | If the reseed does not proceed cleanly, stop immediately; do not restore/overwrite manually. The verified safety backup remains available for an owner-directed restore.  | Verify port 8000 and the backend process tree are closed, rerun `uv run python backend/scripts/reseed_dev.py --profile uat`, verify seed counts, six cameras, eight coded users, fixture rows, and that the safety backup still verifies.                                                                                                                                 | 2026-08-30T04:18 +08:00 | Explicitly approved by user at 2026-08-30T04:19 +08:00 (“stop that then continue”)                                                                                                                                           | `scripts\stop-dev.ps1 -Backend` applied; one controlled retry of the existing `uat` reseed applied.                      | Pass — port 8000 closed; reseed exit 0; 8 UAT users, 6 cameras, 16 detections, 0 audit rows, Channel 4 disabled, Channel 6 Ongoing, 8,646 raw and 721 hourly health rows verified.                                                             |
| B-002      | Stop only the identified pre-existing managed AI/coordinator trees via `pwsh -File scripts\stop-dev.ps1 -Backend -Ai` (the lifecycle script uses tracked identities and coordinator state; no broad process kill), then start the managed backend+AI path once.            | This interrupts the pre-existing AI inference and restore-coordinator services; no current participant run existed yet, but unrelated use of those ADAS services would stop.   | If controlled stop or startup fails, stop the dependent path and leave the verified safety backup untouched; no manual process/database deletion.                         | Verify no matching AI/coordinator trees or service ports remain; start `pwsh -File scripts\start-dev.ps1 -Backend -Frontend -Ai`; verify controlled PID identities, backend/AI/coordinator readiness and no duplicate processes before MediaMTX.                                                                                                                          | 2026-08-30T04:22 +08:00 | Explicitly approved by user at 2026-08-30T04:29 +08:00 (“stop everything then continue”)                                                                                                                                     | `scripts\stop-dev.ps1 -All` applied; no code/schema/API change.                                                          | Pass — no matching backend/AI/coordinator/MediaMTX/FFmpeg processes or listeners remained; safety backup and UAT DB remained intact.                                                                                                           |
| B-004      | Resolve the exact verified ADAS process-tree/PID mismatch by stopping only the identified coordinator, duplicate backend/AI, Vite, MediaMTX, and FFmpeg trees; then rerun the repository lifecycle stop and one elevated managed start. No code/schema/API change.         | Exact-PID termination interrupts the current duplicate local UAT runtime; it does not target unrelated processes, and it is required before any further real-trigger evidence. | If any PID or command-line verification is ambiguous, stop without terminating it; leave the safety backup untouched and do not continue dependent journeys.              | Recheck command lines immediately before each exact-tree stop; run `scripts\stop-dev.ps1 -All`; verify zero matching ADAS processes, zero listeners on 8000/5173/8554/8555, cleared controlled metadata, then run one elevated `scripts\start-dev.ps1 -Backend -Frontend -Ai` and verify exactly one backend, frontend, AI, and coordinator instance plus readiness logs. | 2026-08-30T04:50 +08:00 | Explicitly approved by user at 2026-08-30T04:52:39+08:00 (“i consent”); standing instruction at 2026-08-30T04:53 to decide subsequent blockers without interruption; credential entry consent reaffirmed at 2026-08-30T04:54 | Exact-PID cleanup applied; stale coordinator metadata cleared; duplicate Vite tree removed; one managed stack started    | Pass — exact-PID cleanup removed the duplicate runtime; stale coordinator state was cleared; verification found one backend tree, one AI tree, one coordinator tree, one Vite tree, listeners on 8000/5173 only, and no duplicate UAT runtime. |
| B-005      | Restart only the managed backend/AI/coordinator stack while leaving the verified profile-3 MediaMTX publishers running; then observe Channel 3 for a complete real clip loop. No code/schema/API change.                                                                   | This interrupts only the current local managed runtime and may discard in-memory AI stream state; the UAT database and safety backup are left untouched.                       | If the controlled restart or readiness verification fails, stop the dependent OP-J08 path, retain the safety backup, and record the limitation without synthetic results. | Stop the managed backend/AI/coordinator through the repository lifecycle command; verify no duplicate trees; start one managed backend/AI/coordinator stack; verify Channel 3 RTSP reader and observe one full 61-second clip loop for an actual detection.                                                                                                               | 2026-08-30T05:58 +08:00 | Standing instruction explicitly authorizes blocker decisions without interruption; applied as the least-scope runtime retest                                                                                                 | Managed AI/backend/coordinator restart applied; one clean tree verified; real Channel 3 log 22 observed after the retest | Pass — restart did not change code/schema/API; B-005 dependency was rechecked                                                                                                                                                                  |

## O. Retest log

| Retest ID | Finding/fix                                                  | Affected stage                   | Dependent checks rerun                                                                                                                                                             | Before                                                                                                               | After                                                                                                                                                                                                                                                                                                                                        | Timestamp                 | Result |
| --------- | ------------------------------------------------------------ | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------ |
| R-001     | B-001 / approved backend stop                                | Pre-seed safety/reseed gate      | Backend listener closure, database readability, single `uat` reseed, UAT fixture query                                                                                             | Delete failed while PID 32676 listened on 8000                                                                       | Backend stopped; port closed; reseed succeeded and fixture verified                                                                                                                                                                                                                                                                          | 2026-08-30T04:20 +08:00   | Pass   |
| R-002     | B-002 / approved full ADAS shutdown                          | Clean runtime gate               | Full lifecycle stop; matching process/port scan; runtime metadata check                                                                                                            | Pre-existing AI/coordinator trees and stale controlled metadata remained after backend-only stop                     | `scripts\stop-dev.ps1 -All` completed; only unrelated Python LSP processes remained; no ADAS listener or matching AI/coordinator/MediaMTX/FFmpeg process; runtime PID metadata cleared                                                                                                                                                       | 2026-08-30T04:30 +08:00   | Pass   |
| R-003     | B-003 / lazy-route rendering                                 | OP-J03 AI Performance navigation | Reload `/user/ai`; wait for DOM route content; verify heading/KPIs/table/filter/export                                                                                             | Initial 1.2-second snapshot showed stale System Health content                                                       | Reloaded route showed AI Performance content; source route/component mapping confirmed; no code change                                                                                                                                                                                                                                       | 2026-08-30T04:39 +08:00   | Pass   |
| R-004     | B-004 / exact-PID runtime cleanup and duplicate Vite removal | Clean managed runtime gate       | Exact command-line recheck; approved exact-tree termination; repository stop; stale coordinator cleanup; one elevated managed start; single-instance process/listener verification | Duplicate backend/AI/Vite/coordinator runtime and mismatched coordinator PID metadata; controlled stop failed closed | Exact verified extra frontend tree rooted at PID 12780 and its children stopped; repository stop then cleared component records; stale coordinator state was removed through `Stop-AdasRestoreCoordinator`; one managed backend, AI, coordinator, and Vite tree verified; port 8000 and 5173 listening; no duplicate extra frontend listener | 2026-08-30T05:41:58+08:00 | Pass   |
| R-005     | B-005 / managed AI/backend/coordinator restart               | OP-J08 recovery trigger          | Stop scoped managed stack; verify clean shutdown; start one managed stack; verify Channel 3 RTSP reader; observe real profile-3 loop                                               | No Channel 3 alert after the initial 55-second observation despite publishers/readers                                | One clean managed stack reconnected while profile-3 MediaMTX remained active; read-only polling captured real Channel 3 log 22 at 06:00:20; browser reload preserved it; confirm left it Ongoing                                                                                                                                             | 2026-08-30T06:02:01+08:00 | Pass   |

## P. Limitations and unperformed evidence

- Human SUS responses: not available from an AI dry run.
- Human usability conclusions: not claimable from an AI dry run.
- Real production CCTV/live context: the UAT is a simulation using configured test clips; record any consequence for wording or validity.
- OP-01 core mechanics were executed through OP-J09, but OP-J09's CSV file existence/content could not be verified through the in-app Blob-download surface; no export success was claimed (M-004).
- OP-J04–OP-J07 used real looping clips and real AI rows, but repeat detections after camera resume created extra alerts and one action-to-visible-alert attribution race; this qualifies the sequence (M-003).
- OP-J08 initially had no Channel 3 alert in the first observed window; after a controlled managed-runtime restart, a real Channel 3 alert was captured, survived browser reload, and was left Ongoing (B-005/R-005).
- The operator-preparation reset was successfully executed by an Administrator, clearing six session detections and preserving 20 audit rows. A later forced overlay click accidentally initiated an `analytics` reseed (B-006), replacing the UAT fixture with the analytics profile. No further UAT execution, automatic restore, or second reseed was performed.
- Because B-006 invalidated the current UAT fixture before variants and Administrator journeys, OP-02–OP-06, ADM-01, ADM-02, AD-J01–AD-J06, AD-J04 restore timing, post-restore positive alert, and administrator audit/export evidence remain unperformed.
- MediaMTX Ctrl+C closed the PTY rather than leaving a reusable command line for the prescribed Up/Enter action; each necessary profile restart was relaunched with the exact same repository-root command in a fresh dedicated terminal, with the deviation recorded in E and K.
- The final database was deliberately left as produced by the accidental analytics reseed: 8 users, 8 cameras, 62 detections, 37 audit rows, 8,642 raw health rows, 721 hourly rows, and 5 export jobs; integrity and foreign-key checks passed. The verified pre-run safety backup remains separate and was not restored.

## Q. Shutdown and final-state record

| Check                                       | Result               | Timestamp/notes                                                                                                                                                                                  |
| ------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Frontend started by task stopped            | Pass                 | Controlled `scripts\stop-dev.ps1 -All`; Vite listener 5173 closed; final verification 2026-08-30T06:09:53+08:00.                                                                                 |
| Backend started by task stopped             | Pass                 | Controlled `scripts\stop-dev.ps1 -All`; backend listener 8000 closed; final verification 2026-08-30T06:09:53+08:00.                                                                              |
| AI engine started by task stopped           | Pass                 | Controlled managed shutdown; no matching `ai_engine/main.py` process remained at final verification.                                                                                             |
| Restore coordinator started by task stopped | Pass                 | Controlled managed shutdown; coordinator state and matching process were absent at final verification.                                                                                           |
| MediaMTX started by task stopped            | Pass                 | Dedicated MediaMTX was stopped by Ctrl+C at 2026-08-30T06:06:52+08:00; no RTSP listener remained.                                                                                                |
| FFmpeg children started by task stopped     | Pass                 | MediaMTX shutdown stopped its five `runOnInit` publishers; final process scan found no task-started FFmpeg.                                                                                      |
| Started ports verified closed               | Pass                 | No listeners on 8000, 5173, 8554, or 8555 at final verification.                                                                                                                                 |
| Current database left in post-run state     | Pass with limitation | Left untouched after the accidental `analytics` reseed: 1,519,616-byte DB, analytics profile counts recorded in P, integrity `ok`, foreign-key check empty; no restore/reseed cleanup performed. |
| Generated artifacts left in post-run state  | Pass with limitation | Generated snapshots/exports and normal backup state left as produced by the analytics reseed; no cleanup or synthetic UAT artifact was added.                                                    |
| Safety backup preserved and restorable      | Pass                 | Separate backup directory and manifest/database remained present; final independent verify returned checksum, quick, integrity, and foreign-key checks true.                                     |
| No commit or push performed                 | Pass                 | No commit, reset, switch, pull, merge, or push performed; handoff/config edits remain uncommitted as required.                                                                                   |

## R. Final readiness verdict

**Verdict:** `Not Ready`

**Core execution summary:** OP-01 OP-J01–OP-J09 was mechanically exercised through real browser/RTSP/AI behavior. OP-J08 recovered a real Channel 3 alert after the controlled AI retest; OP-J09 Help passed and the Detections CSV request returned HTTP 200, but the downloaded file/content could not be verified. The profile-2 sequence has recorded alert-order and repeated-loop deviations.

**Variant summary:** OP-02–OP-06, ADM-01, and ADM-02 were not run. The accidental analytics reseed replaced the UAT fixture before these paths, so no variant result is inferred.

**Artifact/script consistency summary:** All required live source tabs/doc tabs were read completely, including the manually maintained Journey Script; tracker formulas, validations, gates, traceability, and unchanged blank formal results were verified. Script content review passed, with live-flow deviations recorded in M-002/M-003 and export evidence gap M-004.

**Metric/formula summary:** Formula/validation/denominator audits passed mechanically. No human SUS, human usability conclusion, NFR-09 elapsed time, or participant click metric was fabricated; the required human measurements remain unperformed.

**Unresolved Blockers:** B-006 — accidental `analytics` reseed invalidated the current UAT fixture; no automatic restore or second UAT reseed was performed.

**Unresolved Majors:** M-002 — two live System Health warnings conflicted with the single-condition OP-J03 script; M-003 — looping profile-2 alerts created extra arrivals and an action-to-visible-alert attribution race.

**Conditions required before real UAT:** Re-establish an owner-approved UAT fixture without treating this invalidated run as participant evidence; mitigate the ambiguous OP-J03 condition and profile-2 alert-loop/action race; provide verifiable export artifact capture; complete all 66 real participant-stage records, human SUS, consent/privacy evidence, administrator backup/restore, variants, debrief, and formal sign-off. Do not use this run's blank tracker state as a pass.

**Human-evidence caveat:** This dry run cannot provide valid SUS responses or prove actual human usability; those require the planned CDRRMO participant sessions.

**Verdict rationale against Section 14:** `Not Ready` under Section 14 because an unresolved Blocker remains, the current UAT fixture was replaced before the remaining required paths, OP-J09 artifact verification is incomplete, and human participant evidence is absent. The separate safety backup is verified and preserved but was intentionally not restored.
