# 05 — Chapter 4: Results and Discussion

> **One-liner:** Chapter 4 presents the prototype test results; the test tracker supplies the case-by-case evidence and keeps each measured result attached to its actual scope.
> **Panel risk:** high — the tracker records every planned technical case as Pass, but several results are archival, simulated, duration-accelerated, or limited to a small demonstration setup.

## 1. What it is

Chapter 4 is the evidence story for the completed ADAS prototype. It asks whether the system behaved as planned across software checks, AI evaluation, load and recovery exercises, security checks, operator tasks, and formal acceptance.

The results come from three distinct evidence layers:

- Technical test cases check a defined behaviour or requirement.
- Participant-stage executions show whether the intended operator and administrator journeys were completed.
- SUS responses and the signed decision record user experience and organizational acceptance.

Keep those layers separate when speaking.

A technical case marked Pass means the recorded case outcome met its stated disposition. It does not mean every underlying deployment condition was reproduced, that the AI detected every collision, or that the system is certified for live citywide operation.

The exact test record is in the ADAS Test Execution tracker. The approved test plan defines the activity criteria and says that a simulated, accelerated, archival, or otherwise qualified result is not treated as unqualified proof.

**Evidence:** Test Plan, Purpose and Acceptance Criteria; Tracker, Summary!A1:G32.

## 2. Where it lives

### In the paper

- Chapter 4, Results and Discussion, especially System Overview, frames the completed system whose results are being discussed.
- Chapter 3, Testing and Validation, describes the bottom-up testing strategy, the simulated environment, and all ten testing activities.
- Chapter 3, Table 23, Test Environment Summary, is the paper’s environment reference.
- Chapter 1, Table 3, Performance Requirements, contains NFR-01 through NFR-06.
- Chapter 1, Table 4, Scalability Requirements, contains NFR-07 and NFR-08.
- Chapter 1, Table 5, Usability Requirements, contains NFR-09 through NFR-12.
- Chapter 1, Table 6, Reliability Requirements, contains NFR-13 through NFR-18.
- Chapter 1, Table 7, Security Requirements, contains the security criteria.
- Chapter 5, Recommendations, says to treat this as a proof-of-concept and calls for pilot and further capacity, endurance, backup, security, and alert-delivery evaluation.

The paper locations explain the system and its intended criteria.

The test plan and tracker are the sources for the executed results, denominators, measured figures, and qualifications.

### In the code

The test cases and mechanisms that produced or support this evidence are grouped here by role.

- Authentication test: backend/tests/test_auth.py:27.
- AI temporal evidence test: ai_engine/tests/test_accumulate.py:150.
- Audit transaction rollback test: backend/tests/test_audit.py:54.
- Alert WebSocket integration test: backend/tests/test_websocket.py:53.
- Camera and alert ingestion integration cases: backend/tests/test_internal.py:47.
- Backup during concurrent writes: backend/tests/test_maintenance.py:170.
- Offline database replacement and sidecar cleanup: backend/tests/test_maintenance.py:511.
- AI evaluation clip selection and scoring: ai_engine/eval/run_clips.py:45 and ai_engine/eval/score.py:39.
- Alert delivery isolation test: backend/tests/perf/test_alert_latency.py:69.
- Unauthenticated WebSocket rejection test: backend/tests/test_realtime.py:38.
- Operator incident decisions are routed through backend/app/api/routes/alerts.py:465.

These files explain the implementation and test seams.

Use the tracker, not code coverage or a source-code reading, when stating test outcomes.

## 3. How it works

### Test setting and sequence

The test plan records the execution period as August 27–31, 2026; technical tests were completed before participant sessions.

The environment used a private three-device LAN:

- A Linux VMS simulator published prerecorded traffic clips over RTSP.
- A Windows laptop hosted the ADAS application and AI engine.
- An operator laptop used a browser for the dashboard and API.

This exercises a real network path and browser workflow while keeping the video source simulated; the application and AI engine ran on demonstration hardware, not a production edge server.

The current plan allows up to ten concurrent streams as the immediate prototype target; fifteen-camera qualification is deferred.

**Evidence:** Test Plan, Project Information, Test Environment, Network Configuration, and Testing Schedule; Paper, Chapter 3, Testing and Validation, Table 23.

### The headline denominators

The tracker contains eight technical activities.

| Technical activity           | Tracked cases | Recorded Pass | Source                   |
| ---------------------------- | ------------: | ------------: | ------------------------ |
| Unit testing                 |            68 |            68 | Tracker, Summary!A5:G5   |
| Integration testing          |            23 |            23 | Tracker, Summary!A6:G6   |
| System / end-to-end testing  |            21 |            21 | Tracker, Summary!A7:G7   |
| AI model validation          |             9 |             9 | Tracker, Summary!A8:G8   |
| Performance and load testing |            15 |            15 | Tracker, Summary!A9:G9   |
| Reliability and endurance    |            15 |            15 | Tracker, Summary!A10:G10 |
| Backup and recovery          |            16 |            16 | Tracker, Summary!A11:G11 |
| Security testing             |            27 |            27 | Tracker, Summary!A12:G12 |
| **All technical activities** |       **194** |       **194** | Tracker, Summary!A16:G16 |

The tracker separately records 33 participant-stage executions: 27 Operator stages and 6 Administrator stages. Those are stages completed by four participants, not 33 people; the same four participants completed the ten-item SUS questionnaire.

The tracker records a SUS mean of 89.375 against the plan’s acceptance criterion of at least 68, all nine readiness items as Ready, and the formal decision as Accepted in the UAT Results sheet.

**Evidence:** Tracker, Summary!A13:G32; Execution Log!A1:H34; SUS Questionnaire!A4:O19; UAT Results!A3:D14; Session Control!A20:D29.

### Activity 1 — Unit testing

- **Acceptance criterion:** All executed unit cases must pass.
- Any failed unit case is a build defect that blocks later activities.
- The paper describes module-level tests for backend services, AI components, and frontend utilities.

- **What was executed:** The tracker contains 68 unit cases across authentication, role checks, camera handling, AI detection and accumulation, alerts, and application utilities.
- Automated selectors were run against backend, AI-engine, and frontend code.
- The execution notes also record a full backend fast-suite result of 939 passed, 2 skipped, and 12 deselected.
- The AI-engine fast suite is recorded as 127 passed and 7 skipped.

- **Recorded outcome:** All 68 tracked unit cases are Pass.
- No unit defect remains in the recorded activity.
- The full-suite counts are supporting run evidence; they are not the tracker’s 68-case denominator.

- **Qualification:** This is automated component-level evidence.
- It does not prove that all components work together; that is why integration and system testing follow.

**Sources:** Test Plan, Acceptance Criteria → Unit Testing; Tracker, Unit Testing!A1:J69 and Summary!A5:G5; Paper, Chapter 3, Types of Testing Conducted → Unit Testing.

### Activity 2 — Integration testing

- **Acceptance criterion:** All executed integration cases must pass.
- The paper identifies the engine-to-backend webhook, backend-to-browser WebSocket, backend-to-database, audit coupling, and camera-state reconciliation as integration seams.

- **What was executed:** The tracker records 23 integration cases across the component boundaries.
- The cases check authenticated alert ingestion, broadcast payloads, persisted state, audit behavior, and camera status reconciliation.
- Automated tests exercise the actual application services and interfaces.

- **Recorded outcome:** All 23 tracked cases are Pass.
- The activity meets its 100% executed-case criterion.

- **Qualification:** These cases verify component boundaries and transactions.
- They are not a substitute for the later live-browser workflow checks.

**Sources:** Test Plan, Acceptance Criteria → Integration Testing; Tracker, Integration Testing!A1:J24 and Summary!A6:G6; Paper, Chapter 3, Types of Testing Conducted → Integration Testing.

### Activity 3 — System and end-to-end testing

- **Acceptance criterion:** At least 95% of system cases must pass.
- No Critical or Major defect may remain open.

- **What was executed:** The team walked complete operator and administrator flows over the three-device LAN in a real browser.
- The flows covered collision ingestion, dashboard alerts and snapshots, confirm/dismiss/clear actions, alarm snooze, camera configuration, logs and exports, health views, administration, audit, and restore.
- One recorded flow used a genuine live detection from a replayed 2K collision clip and followed it through the operator decision.

- **Recorded outcome:** All 21 system/E2E cases are Pass.
- That exceeds the case-percentage criterion; the UAT acceptance record later confirms zero open Critical or Major defects.

- **Qualification:** The browser, TLS connection, LAN route, dashboard, and application services were real.
- RTSP video was replayed from the VMS simulator; this was not a live CDRRMO camera deployment.
- Some alert-path tests used development-injected events, while TC-SYS-004 recorded a genuine detection path.
- Do not describe every E2E event as a natural live-camera detection.

**Sources:** Test Plan, Acceptance Criteria → System / End-to-End Testing; Tracker, System E2E Testing!A1:J22 and Summary!A7:G7; Paper, Chapter 3, Types of Testing Conducted → System / End-to-End Testing.

### Activity 4 — AI model validation

- **Acceptance criterion:** The primary criterion is mAP at IoU 0.50 of at least 0.85 on the validation split.
- Supporting evidence reports event-level recall and false positives with denominators, clip strata, artifact, cadence, and source-resolution qualifications.
- The plan makes no independent post-selection held-out test-set claim.

**What was executed**

The AI Model Validation sheet contains nine cases:

- AI-VAL-001 records the frame-level validation metric for epoch50.pt.
- AI-VAL-002 runs the frozen checkpoint on the labelled Lipa clip corpus.
- AI-VAL-003 reports standard and hard-event strata separately.
- AI-VAL-004 records false positives and the clean-footage denominator.
- AI-VAL-005 records checkpoint-selection evidence.
- AI-VAL-006 records the night-condition analysis.
- AI-VAL-007 checks that the complete clip corpus and subsets are accounted for.
- AI-VAL-008 compares TensorRT event outcomes with the checkpoint.
- AI-VAL-009 compares cadence and source-resolution profiles.

- **Recorded outcome:** The recorded validation-split mAP@0.50 is 0.956 at epoch 50.
- The original validation split was unavailable for a fresh rerun.
- Its frame-level split has incident leakage; treat the value as a qualified validation-split result, not independent operational accuracy.
- The 17-clip operational corpus contains 16 crash-labelled clips and 1 negative clip.
- Frozen-checkpoint crash recall is 8/16 overall: 8/10 standard and 0/6 hard.
- There were 3 false positives over 11.0 clean minutes, or 0.27 FP/minute; the negative airbase clip produced no events.
- All six hard clips were missed, so the hard-case limitation must be stated with the aggregate.
- The night analysis classified 8 of 17 clips as night; all three residual false positives occurred at night and involved nearby vehicles.
- The exact per-clip night numerator is not recoverable from the machine-readable labels, so the tracker does not claim universal night robustness.
- Archival TensorRT parity matched the checkpoint’s hit/miss outcome on all 17 clips; the engine had 4 false positives at native rate versus 3 for the checkpoint, and 3 at 10 FPS.
- Archival profile testing found that 720p source footage reduced recall from 8/16 to 6/16.

**Interpretation**

- The tracker marks all nine validation cases Pass because their stated evidence and reporting checks were completed.
- That 9/9 case status is not a 100% detection rate.
- The actual event-level result remains 8/16, including 0/6 hard clips.
- No event-recall minimum was approved before the result, so do not invent one after seeing the misses.

- **Qualification:** mAP, checkpoint selection, night analysis, TensorRT parity, and cadence/resolution sensitivity are archival evidence.
- The event-level clip run was executed on the frozen checkpoint, but its small project corpus is descriptive and is not an independent held-out estimate.
- The hard-case result and 720p loss are limitations, not details to bury under the mAP figure.

**Sources:** Test Plan, Acceptance Criteria → AI Model Validation; Tracker, AI Model Validation!A1:K10 and Summary!A8:G8; Paper, Chapter 1, Table 3, NFR-01; Paper, Chapter 3, Types of Testing Conducted → AI Model Validation.

### Activity 5 — Performance and load testing

- **Acceptance criteria:** Per-frame analysis target: mean and p95 at or below 100 ms on the declared artifact and stream profile.
- Per-stream cadence: 5–15 FPS, with 15 FPS as target and 5 FPS as the warning floor.
- Alert and snapshot presentation: within 2 seconds after detection.
- Normal single-user dashboard requests: within 3 seconds.
- Under 20 concurrent authenticated requests: p95 within 10 seconds, with valid-request errors reported.
- A standard 30-day report must begin downloading within 5 seconds.
- Fifteen-camera qualification is deferred.

- **What was executed:** The 15 tracked cases cover inference timing, per-stream frame rate, alert delivery, exports, API/database load, burst handling, and resource behavior.
- A sustained cadence run used 8 simultaneous simulated streams and sampled health every 15 seconds.
- Separate load steps exercised 9 streams and a ten-camera scheduled-backup overlap.
- API queries ran against 100,000 incident rows; a later asynchronous export exercised 600,006 rows.
- Alert rendering was repeated using development-injected events through the real dashboard path.

- **Recorded outcome:** The inference case is marked Pass; its notes say the TensorRT artifact was present and the measured health and batch results stayed within the 100 ms target.
- In the 15-minute 8-stream cadence run, 61 samples were collected; the minimum was 5.15 FPS, the mean was 6.778 FPS, and no sample fell below 5 FPS.
- At 8 streams, measured per-camera rates were 11.4–14.8 FPS with 20–31 ms AI analysis delay.
- The 9-stream simulated step held about 12–13.6 FPS with 20–24 ms latency.
- Thirty development-injected alert events rendered with a mean of 668.2 ms, p95 of 887 ms, and maximum of 1,395 ms; all were below 2 seconds.
- That browser simulation used component-level instrumentation for audio and does not measure the full camera-to-alert path.
- Two independent dashboard clients received a status update 24 ms after the operator decision; only two clients were exercised, fewer than the intended command-center count.
- For a 300-row, 30-day dataset, CSV took 0.190 seconds and PDF took 2.104 seconds, both under the 5-second target.
- A 600,006-row CSV export returned 202 Accepted, progressed to completion, and produced the matching row count.
- On 20 concurrent authenticated API requests against 100,000 rows, all 20 returned HTTP 200; aggregate p95 was 5.986 seconds and maximum was 5.991 seconds.
- A combined CPU/RAM/VRAM run lasted 34.7 continuous minutes, not the planned one hour.

- **Qualification:** Stream counts are stated per test. The cadence run proves the 8-stream profile and a separate case records the 9-stream step; it does not establish a 15-camera result.
- The alert test validates the post-injection dashboard path. It is not an end-to-end measurement from collision visibility through human decision.
- The load database was populated for testing; report the row count and profile with every query or export number.
- TC-PERF-013 is marked Pass, but its notes say WAL file size/checkpoint behavior was not separately inspected in that pass. Do not claim that sub-check was measured.

**Sources:** Test Plan, Acceptance Criteria → Inference latency, Frame rate, Alert delivery, Dashboard query response, and Report export; Tracker, Performance & Load Testing!A1:J16 and Summary!A9:G9; Paper, Chapter 1, Tables 3–4, NFR-02–NFR-08.

### Activity 6 — Reliability and endurance testing

- **Acceptance criteria:** Reconnection is attempted within 10 seconds after a lost stream.
- A single camera failure must not bring down the server, dashboard, or other cameras.
- Report backend readiness, AI heartbeat, and camera ingestion separately after restart.
- State recovery must return pending Unverified alerts after reload or reconnection.
- Report availability only for the active observation window; a short soak does not prove annual 99.9% availability.
- A multi-hour or 24-hour endurance claim requires a run of that duration.

- **What was executed:** The 15 cases covered stream loss, engine and backend restart, alert recovery, process isolation, availability sampling, export resume, memory, and thermal behavior.
- Faults were injected or represented by lifecycle simulations for several branches.
- The team also invoked the registered scheduled restart while the simulated camera feeds were live.

- **Recorded outcome:** During actively monitored, non-maintenance periods, no unplanned outage was observed.
- Planned maintenance and periods with no service running were excluded from that active-window observation.
- The 24-hour memory case used a direct accelerated buffer probe: after 1,000 warmup frames and 10,000 frame replacements, the latest-frame buffer still held one frame.
- The combined real performance/thermal harness ran for 34.7 minutes, not 24 hours.
- During that window, GPU temperature was 59–63 °C and memory use was about 13–14%; no sustained thermal decline or stream loss was observed.
- An on-demand scheduled restart returned backend readiness in 5.11 seconds and a fresh AI heartbeat in 12.672 seconds; all 10 enabled cameras later returned Connected and Active.
- Backend readiness met the 10-second sub-measure, but the 12.672-second heartbeat means the full stack must not be called an unqualified under-10-second recovery.

- **Qualification:** Reconnect loops, process failures, network partitions, pending-alert recovery, and interrupted-job behavior are recorded as simulated or injected cases.
- The memory probe is accelerated and does not substitute for a continuous 24-hour operation.
- The thermal run is real on the test host but shorter than its one-hour and 24-hour criteria.
- Availability is an observed short test window, not an annual uptime estimate.

**Sources:** Test Plan, Evaluation Methods and Acceptance Criteria → Network fault tolerance, Process isolation, Restart recovery, State recovery, Availability; Tracker, Reliability & Endurance!A1:J16 and Summary!A10:G10; Paper, Chapter 1, Table 6, NFR-13–NFR-17.

### Activity 7 — Backup and recovery testing

- **Acceptance criteria:** Automated backup must not interrupt inference or produce database-lock errors.
- Restore and resumed automated alerting must fit within the 60-second operational window.
- Backup integrity, protected and degraded storage, concurrent writes, rollback, database replacement, and service resumption are recorded by phase.

- **What was executed:** The 16 tracked cases covered manual and scheduled backups, audit records, protected storage, degraded fallback, restore initiation, offline replacement, integrity failure, rollback, and post-restore alerting.
- The team performed live UI backup and restore actions and ran automated concurrency and fault-branch cases.
- The restore workflow used a real isolated test database and the host recovery process.

- **Recorded outcome:** All 16 cases are marked Pass.
- A manual backup request returned control in 0.31–0.43 seconds; the protected artifact became Valid in 5.14–5.20 seconds while all 10 of 10 cameras remained connected and active.
- A scheduled protected backup ran for 4.686 seconds during active detection; a detection during the backup reached the dashboard in 1.986 seconds.
- A successful restore returned the database to its recorded pre-backup state and passed integrity checks with 0 foreign-key violations.
- The first fresh post-restore alert appeared 57.04 seconds after restore completion and rendered in 0.67 seconds, within the 60-second recovery window but with little margin.
- Protected-storage loss, read-only/full targets, and rollback branches were exercised; some branch outcomes used disposable fixtures.
- The interrupted-restore case is explicitly recorded as a simulated drill; no physical power cut was performed.

- **Qualification:** The successful backup and restore lifecycle was exercised on the isolated deployment, not on the CDRRMO production database.
- A simulated power interruption and fixture-based rollback demonstrate the recovery logic, not physical-host power-loss behavior.
- State the 57.04-second result together with its 60-second target; do not round away the narrow margin.

**Sources:** Test Plan, Acceptance Criteria → Backup and Recovery; Tracker, Backup & Recovery!A1:J17 and Summary!A11:G11; Paper, Chapter 1, Table 6, NFR-18.

### Activity 8 — Security testing

- **Acceptance criterion:** All security checklist items pass.
- There must be zero Critical findings.
- Role-based denials and failed authentication attempts must appear in the audit trail.

- **What was executed:** The 27 checklist cases combine automated tests, live checks on the isolated application, audit inspection, and artifact/header review.
- They cover authentication and session revocation, role boundaries, WebSocket authorization, injection handling, export inputs, backup/restore controls, cross-site request protections, data localization, and audit integrity.
- The team verified failed logins and denied requests against the audit records.

- **Recorded outcome:** All 27 security cases are Pass.
- Wrong-password, unknown-user, and deactivated-user sign-ins returned the same generic denial and were logged as LOGIN_FAILURE.
- An Operator’s requests to restricted Administrator endpoints were denied.
- The tested audit entries retained actor, action, target, result, and time while hiding passwords and confirmation strings.
- Direct attempts to edit or delete an audit record found no such route; the tested audit-row count was unchanged.
- The localization case observed only loopback connections during a controlled health/operations simulation.

- **Qualification:** That localization result is scope-limited: a packet capture across every workflow and backup activity was outside the run.
- One script-rendering case confirmed literal text through an API path; the tracker does not present it as a full browser-rendering audit.
- The 27/27 result is evidence against the defined checklist, not a claim that every possible attack was tested.

**Sources:** Test Plan, Acceptance Criteria → Security; Tracker, Security Testing!A1:K28 and Summary!A12:G12; Paper, Chapter 1, Table 7.

### Activity 9 — Usability testing

- **Acceptance criteria:** The mean SUS score must be at least 68.
- Each first-time participant must complete the defined learnability task within 15 minutes after the standard briefing.
- Assistance is recorded separately; timing is not described as unaided.
- The operational-efficiency target is at most 25 seconds from collision becoming visible to the operator decision.

- **What was executed:** Three coded Operators and one coded Administrator each completed one role-based journey, then gave an individual SUS response and debrief.
- All four participants were marked first-time ADAS users.
- The tracker records 27 Operator stages and 6 Administrator stages.
- Operators handled alerts, settings, cameras, history, exports, and handover; the Administrator handled restricted administration, audit, backup, and restore tasks.
- UAT collision clips were replayed through the simulator. Participants used the alert snapshot and metadata for the scored decision; live-video review was not scored.

- **Recorded outcome:** Individual SUS scores were 85, 95, 77.5, and 100.
- The mean is 89.375, above the 68 acceptance threshold.
- Each participant’s learnability time was 5 minutes, under the 15-minute threshold.
- Assistance and verbal prompts were recorded, so present the timing as briefed, assisted task completion rather than unaided learning.
- The raw alert-to-decision observations were 16, 9, and 15 seconds for the three Operators.
- The tracker adds approximately 3 seconds for detector accumulation and 2 seconds for alert propagation to estimate collision-visible-to-decision time.
- The resulting mean estimate is 18.333 seconds and the worst case is 21 seconds, both within 25 seconds.
- No automatic dispatch time was measured.

- **Qualification:** Four participants support a role-based usability and acceptance judgment, not a population-level statistical estimate.
- Simulated clips and snapshot/metadata review do not reproduce every live-video decision condition.
- The 25-second figure is a reconstructed estimate; the raw observation begins when the alert appears in the browser.

**Sources:** Test Plan, Test Participants, Evaluation Methods, and Acceptance Criteria → Usability, Learnability, Operational efficiency; Tracker, Session Control!A14:H18; Execution Log!A1:H34; SUS Questionnaire!A4:O19; Usability Results!A4:H18; Paper, Chapter 1, Table 5; Paper, Chapter 3, User Acceptance Testing.

### Activity 10 — User Acceptance Testing

**Acceptance criterion**

All 33 planned participant-stage executions must have a final Pass or Fail result, at least 95% must pass, and there must be:

- Zero open Critical or Major defects.
- An overall SUS mean of at least 68.
- All nine readiness items marked Ready.
- A signed decision from an authorized CDRRMO representative.

Not Executed, Blocked, and Retest Required are incomplete or unresolved.

- **What was executed:** Each of the three Operators completed nine journey stages.
- The Administrator completed six role-specific stages.
- The sessions used coded accounts, a frozen build, prepared fixtures, and an isolated simulated VMS setup.
- The readiness checklist covered the frozen build, technical gates, defect review, participant accounts and fixtures, rehearsed stream profiles, restore target and coordinator, briefing and privacy materials, evidence capture, and facilitator script.
- The authorized representative’s acceptance decision was recorded separately from task-level results.

- **Recorded outcome:** Planned stages: 33.
- Completed final stages: 33.
- Passed stages: 33.
- Incomplete or unresolved stages: 0.
- Failed completed stages: 0.
- Participant-stage pass rate: 100%.
- Open Critical or Major defects: 0.
- SUS mean: 89.375.
- Readiness items Ready: 9 of 9.
- Eligibility: Eligible for formal sign-off.
- Formal UAT decision: Accepted.
- The Session Control sheet identifies the signatory as the authorized Lipa CDRRMO Operations and Warning Division head.

- **Qualification:** Accepted means the defined prototype UAT gates were met and the authorized representative recorded acceptance.
- It does not mean the prototype was deployed to live CDRRMO operations or proven at citywide scale.
- The test plan’s own rule is that simulated, accelerated, archival, and scope-limited rows keep their qualifications after a Pass decision.

**Sources:** Test Plan, Acceptance Criteria → User Acceptance Testing; Tracker, UAT Journeys!A1:I16; Execution Log!A1:H34; SUS Questionnaire!A4:O19; UAT Results!A1:D16; Session Control!A9:D29; Defect Log!A1:G1; Paper, Chapter 3, User Acceptance Testing; Paper, Chapter 5, Recommendations.

## 4. Why it was built this way

The sequence isolates errors before combining the full stack: unit tests check small contracts, integration tests check whether service boundaries exchange and persist the right state, and system testing checks the real browser and network path.

Separate AI and load tests prevent a model metric or speed measurement from being mistaken for workflow correctness. Reliability, backup, and security tests cover failure cases that a happy-path demonstration would miss; usability and UAT test how people use the system and whether an authorized representative accepts the defined workflow.

The test plan makes qualifications explicit because the evaluation used demonstration hardware, prerecorded RTSP streams, model artifacts from earlier runs, and controlled fault injection. That framing protects the result from overclaiming while preserving evidence useful for the next pilot.

The test record also keeps case pass status, participant completion, SUS, readiness, defects, and the manual acceptance decision on separate sheets.

**Sources:** Test Plan, Purpose, Evaluation Methods, Acceptance Criteria, and Deliverables; Paper, Chapter 3, Testing Strategy Overview and Types of Testing Conducted.

## 5. What changed since the 28 April defense

The current results come from a later execution campaign recorded for August 27–31, 2026. The tracker identifies the build used for participant testing and records individual case evidence, rather than relying on the April demonstration as test evidence.

The current summary records 194 tracked technical cases, 33 participant-stage executions, four SUS responses, nine readiness items, and a separate formal acceptance decision. Do not describe these as a measured improvement over April unless you can cite a comparable April baseline.

What changed for the defense is the strength and shape of the evidence: the team can now name the denominator, the observed result, and the qualification for each claim. The paper’s Chapter 5 recommendations still frame the prototype as needing controlled adoption and more operational evaluation.

**Sources:** Test Plan, Project Information and Testing Schedule; Tracker, Summary!A5:G32, Session Control!B7:B12, UAT Results!A3:D14; Paper, Chapter 5, Recommendations.

## 6. Limits and honest caveats

- **No production deployment claim.** The tests ran on the three-device private LAN with prerecorded clips from a VMS simulator; the operator laptop did not host RTSP or the AI engine. Cite Test Plan, Test Environment and Network Configuration; Paper, Chapter 3, Table 23.
- **No 15-camera qualification.** The sustained tracker profile exercised eight streams and a separate case stepped to nine; other ten-camera checks do not establish a 15-camera capacity result. Cite Tracker, Performance & Load Testing!A3:H11 and Backup & Recovery!A11:H11; Test Plan, Model and Inference Configuration.
- **No independent operational accuracy claim.** The 0.956 mAP value is an archival validation-split result with frame-level incident leakage; the project event corpus reports 8/16 crash recall and 0/6 hard recall. Cite Tracker, AI Model Validation!A2:K4.
- **No 24-hour endurance claim.** The observed combined thermal run lasted 34.7 minutes; the memory case used accelerated frame replacement. Cite Tracker, Reliability & Endurance!A6:J7 and Performance & Load Testing!A10:H16.
- **No full-stack under-10-second restart claim.** Backend readiness was 5.11 seconds, while the new AI heartbeat was 12.672 seconds. Cite Tracker, Reliability & Endurance!A13:H13; Test Plan, Acceptance Criteria → Restart recovery.
- **No annual uptime conclusion.** Availability reflects actively monitored non-maintenance periods; the plan expressly says a short soak is not annual 99.9% evidence. Cite Tracker, Reliability & Endurance!A5:H5; Test Plan, Acceptance Criteria → Availability; Paper, Chapter 1, Table 6.
- **No unaided-learnability claim.** All four participants finished the timed task in five minutes, but prompts were recorded and the approved method separates assistance from time. Cite Tracker, Session Control!A14:H18 and Execution Log!A1:H34; Test Plan, Acceptance Criteria → Learnability.
- **No population-level SUS estimate.** Four SUS respondents provide a small role-based sample; their 89.375 mean describes those respondents and is not a statistical claim about every operator. Cite Tracker, SUS Questionnaire!A4:O19; Test Plan, Test Participants.
- **No direct dispatch-time measurement.** The 18.333-second mean and 21-second worst-case values add estimated detector and alert allowances to browser-observed decisions; no dispatch action was timed. Cite Tracker, Usability Results!A15:C16; Test Plan, Evaluation Methods → Operational efficiency.
- **Security evidence has scope limits.** The localization check observed loopback connections in a controlled simulation; a packet capture over every workflow and backup was outside scope. Cite Tracker, Security Testing!A26:H26.
- **Restore fault evidence is mixed.** The successful restore and protected-storage workflow ran in the isolated environment, while the interrupted-restore case is a simulated drill and some rollback branches used disposable fixtures. Cite Tracker, Backup & Recovery!A5:H16.
- **A 100% recorded pass rate is not a 100% detection rate.** The denominator is the predeclared tracker case set; the AI clip result remains 8/16 crash events. Cite Tracker, Summary!A5:G16 and AI Model Validation!A3:H4.
- **A Pass does not erase qualification.** The test plan explicitly says that simulated, accelerated, archival, or otherwise qualified rows are not considered unqualified proof. Cite Test Plan, Acceptance Criteria introduction.

When asked what to do next, the defensible answer is a limited pilot with the intended hardware, authorized RTSP path, longer endurance and capacity runs, broader local evaluation clips, and further recovery and security evidence.

**Source:** Paper, Chapter 5, Recommendations.

## 7. Likely panel questions

**“Which criteria did you not fully prove, and why is that acceptable?”**

We did not prove 24-hour endurance, fifteen-camera capacity, independent post-selection accuracy, or annual availability. The plan keeps those results qualified, and Chapter 5 recommends a controlled pilot with more capacity, endurance, and operational evidence. We accept the prototype decision within the tested scope; we do not present it as production certification.

**“A 100% pass rate — why should we believe that?”**

The 100% figure applies to the 194 tracked technical cases and, separately, the 33 planned participant-stage executions. Each has a fixed row, expected result, actual result, and evidence reference. It is not 100% model recall: the event corpus result is 8/16, with 0/6 hard cases detected, and qualified rows stay qualified.

**“Four participants — is that enough?”**

It is enough to record a small role-based usability and UAT sample: three Operators across shifts and one Administrator completed the defined journeys. It is not enough for a population-level statistical claim. We report the mean and the participant count together.

**“What does ‘qualified’ mean here?”**

It means the number is valid for the stated setup and evidence, with a condition that narrows what it proves. For example, 34.7 minutes is a real measured run, but it is not a 24-hour endurance result. We state the condition in the same breath as the figure.

**“Does 0.956 mAP mean the system detects 95.6% of accidents?”**

No. It is an archival frame-level mAP result on the validation split, with frame-level incident leakage disclosed. The operational clip result is event recall of 8/16, including 0/6 hard cases, so those are different measures with different evidence.

**“Why did AI validation pass with 0/6 hard cases?”**

The tracker’s nine Pass results mean the validation cases and reporting requirements were completed; they do not mean every model-quality result cleared a hard-recall target. No hard-recall threshold was approved before the run. We report the 0/6 result as a limitation.

**“Did you actually test fifteen cameras?”**

No. The sustained cadence run covered eight streams, and a separate load step covered nine. The plan defers fifteen-camera qualification, so we do not extrapolate beyond the measured profiles.

**“Why is 34.7 minutes evidence for a 24-hour system?”**

It is not evidence of 24-hour operation. It is a real short-window performance and thermal observation, paired with a separate accelerated memory probe. A full-duration run remains a deployment-evidence task.

**“Was this tested on live CDRRMO cameras?”**

No. We used prerecorded clips published as RTSP by a VMS simulator on a private LAN. The browser and application path were real, but the feed was simulated and the evaluation was not run on live production cameras.

**“Can you claim the 25-second decision target if you added time after the test?”**

We report the raw browser alert-to-decision observations separately from the reconstructed estimate. The estimate adds about three seconds for detector accumulation and two for alert propagation; its mean was 18.333 seconds and worst case 21 seconds. It does not measure automatic dispatch.

**“If participants needed prompts, can you say the system was easy to learn?”**

We can say all four first-time users completed the timed task in five minutes after the standardized briefing. Prompts were recorded, so we do not call the timing unaided. The SUS mean of 89.375 is reported with its four-person denominator.

**“What does ‘Accepted’ authorize?”**

It records the authorized representative’s decision for the defined UAT and prototype scope. It does not authorize a citywide deployment or prove untested operating conditions. The paper recommends a limited pilot and further capacity, endurance, security, and recovery checks.

## 8. Cram summary

- Chapter 4 is the results narrative; the tracker is the detailed evidence record. Cite paper Chapter 4, System Overview, and the named tracker sheets.
- The technical denominator is 194 cases across eight activities: 68 unit, 23 integration, 21 system/E2E, 9 AI, 15 performance/load, 15 reliability/endurance, 16 backup/recovery, and 27 security; all are recorded Pass. Cite Tracker, Summary!A5:G16.
- Participant evidence is separate: 33/33 stages passed, 27 Operator and 6 Administrator stages, completed by four people. Cite Tracker, UAT Results!A4:D10 and Execution Log!A1:H34.
- SUS mean is 89.375 against 68; all four first-time users took five minutes on the learnability task, with assistance recorded. Cite Tracker, SUS Questionnaire!A4:O19 and Session Control!A14:H18.
- UAT readiness is 9/9 Ready and the formal decision is Accepted by the authorized representative. Cite Tracker, Session Control!A20:D29 and UAT Results!A11:D14.
- AI: mAP@0.50 is 0.956, archival validation-split evidence with incident leakage; event recall is 8/16, standard 8/10, hard 0/6, with 0.27 false positives/minute over 11.0 clean minutes. Cite Tracker, AI Model Validation!A2:K5.
- Performance: the 8-stream 15-minute cadence run ranged from 5.15 FPS minimum to 6.778 mean; 30 injected alert tests rendered within 2 seconds; 20 concurrent API requests had 5.986-second p95. Keep simulation and dataset scope attached. Cite Tracker, Performance & Load Testing!A3:H13.
- Reliability: the combined host run lasted 34.7 minutes, not 24 hours; scheduled restart had 5.11-second backend readiness and a 12.672-second AI heartbeat. Cite Tracker, Reliability & Endurance!A7:H13.
- Recovery: after restore, a fresh alert appeared 57.04 seconds after restore completion and rendered in 0.67 seconds; some failure branches were simulated. Cite Tracker, Backup & Recovery!A14:H16.
- The short answer to every challenge is: give the denominator, give the measured value, state the qualification, then name the next evidence needed for a pilot.
