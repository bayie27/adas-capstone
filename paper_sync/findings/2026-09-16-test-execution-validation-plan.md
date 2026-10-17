---
section: Testing and Validation
page/s: "pending fresh PDF mapping; native ranges recorded below from the live document read on 2026-09-16"
required_revision: Convert the stale pre-execution plan into an evidence-qualified record aligned with the current tracker, adopted model profile, three-device technical topology, single-laptop UAT environment, revised performance criteria, and UAT evidence
notes: "The live Doc is Capstone Test Execution and Validation, one tab, 283 paragraphs, 10 tables. Native ranges are verified; PDF export succeeded but the signed connector file could not be materialized in this environment, so rendered page mapping remains pending."
status: Not started
assigned_to: Daniboy
synced: false
---

## Audit result

The live document is materially stale. Its project identity, testing dates, participant count, core accumulator values, 17-clip corpus, SUS threshold, backup-recovery window, and 33-execution UAT denominator are still supported. The stale or incomplete parts are the execution status, physical topology, model/export profile, FPS and end-to-end timing criteria, endurance wording, evidence qualifications, and deliverable list.

The current live test tracker is ADAS Test Execution (ID 16GSpVeXcGAxx_1lp9vKSG6QKB9CG_xGc816KWf5dyhw), not the older ADAS Test Execution Tracker (v2). Its Summary reports 194/194 technical cases passed, 33/33 participant-stage executions passed, four SUS responses with an overall mean of 89.375, nine of nine readiness items Ready, and eligibility for formal sign-off. Those figures are qualified below where the underlying rows record simulation, duration, or artifact limitations.

## Changes

### 1. Live Doc — Purpose paragraph

Native range: t.gu7j5a4nobzi:601–1391; current paragraph 19.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Purpose paragraph
Preserve: the document's testing scope, organizational context, and proof-of-concept boundary
Comment target: the complete revised paragraph

#### OLD

> This document defines the planned testing and validation activities for ADAS before its final evaluation, organizational acceptance, and any future production deployment. It identifies the testing scope, environments, participants, schedule, evaluation methods, success criteria, and documentary evidence required to determine whether the system correctly implements its specified functional requirements; meets its defined detection-accuracy, latency, and performance targets under simulated multi-camera load; sustains reliable operation and recovers from fault and data-loss conditions; enforces its access-control and audit requirements; and is judged usable and acceptable by Lipa CDRRMO operators and administrators — within the constraints of a single-node demonstration environment.

#### NEW

This document records the testing and validation activities completed for ADAS and the evidence used to assess readiness for final evaluation and organizational acceptance. It identifies the tested scope, environments, participants, schedule, evaluation methods, success criteria, and documentary evidence used to assess functional correctness, detection behavior, latency, performance, fault recovery, backup and restore safety, access control, auditability, usability, and organizational acceptance. Results are qualified where they use demonstration hardware, simulated fault injection, accelerated endurance windows, archival model evidence, or reconstructed timing. For technical/system network testing, the application and AI components ran on one Windows ADAS host within a private three-device LAN. Participant-facing UAT used a single-laptop evaluation environment. The record does not establish production-scale capacity or a completed live CDRRMO deployment.

#### Evidence

The live Doc still uses pre-execution language even though the current tracker contains dated results through 2026-09-16. `docs/operations/VMS_SIMULATOR_SETUP.md:1-45` establishes the three-device technical topology. `paper_sync/findings/2026-09-16-chapter4-results-framing.md:318-320` records the user-confirmed single-laptop participant-facing UAT environment. The current tracker Summary records the completed technical and participant-stage counts, while its detailed rows retain explicit qualifications.

#### Proposed comment

Comment scope: logical paragraph; the complete Purpose paragraph

Previous: This document defines the planned testing and validation activities for ADAS before its final evaluation, organizational acceptance, and any future production deployment. It identifies the testing scope, environments, participants, schedule, evaluation methods, success criteria, and documentary evidence required to determine whether the system correctly implements its specified functional requirements; meets its defined detection-accuracy, latency, and performance targets under simulated multi-camera load; sustains reliable operation and recovers from fault and data-loss conditions; enforces its access-control and audit requirements; and is judged usable and acceptable by Lipa CDRRMO operators and administrators — within the constraints of a single-node demonstration environment.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 2. Live Doc — Test Environment, Application Stack cell

Native range: t.gu7j5a4nobzi:2132–2283; Table 2, row 4, column 2.

#### Change metadata

Operation: replace
Scope: cell
Changed target: the Application Stack description cell
Preserve: React, TypeScript, FastAPI, SQLite, WAL, and Ultralytics YOLO
Comment target: the complete new cell value

#### OLD

> React and TypeScript frontend; FastAPI backend; SQLite database configured with Write-Ahead Logging; Python AI engine using Ultralytics YOLO and OpenCV

#### NEW

React and TypeScript frontend; FastAPI backend; SQLite database configured with Write-Ahead Logging; Python AI engine using Ultralytics YOLO and TensorRT for the adopted inference artifact, with OpenCV as the default RTSP software reader and an optional NVIDIA GPU-resident input path for supported hardware

#### Evidence

ai_engine/config.py:119-162 records the active inference constants and opt-in GPU-resident path. pyproject.toml declares the TensorRT and additive ai-gpu dependencies. The current tracker and engine logs identify epoch50.engine as the adopted artifact and the software OpenCV/FFmpeg reader as the current performance-test reader.

#### Proposed comment

Comment scope: span; OLD using Ultralytics YOLO and OpenCV; NEW using Ultralytics YOLO and TensorRT for the adopted inference artifact, with OpenCV as the default RTSP software reader and an optional NVIDIA GPU-resident input path for supported hardware

Previous: using Ultralytics YOLO and OpenCV

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 3. Live Doc — Test Environment, RTSP Simulation cell

Native range: t.gu7j5a4nobzi:2303–2493; Table 2, row 5, column 2.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete RTSP Simulation description cell
Preserve: prerecorded-video simulation and active inference purpose
Comment target: the complete new cell value

#### OLD

> MediaMTX will locally rebroadcast fifteen distinct prerecorded traffic and collision videos as ten simultaneous RTSP streams. All fifteen streams will run active AI inference simultaneously.

#### NEW

For technical remote-VMS LAN tests, a Linux VMS laptop running MediaMTX and FFmpeg rebroadcast the selected prerecorded traffic and collision clips as RTSP streams to the Windows ADAS server. Stream count varied by technical test case; local performance runs exercised the configured 8-, 9-, and 10-stream profiles, while the separate browser-only operator laptop never accessed RTSP. Participant-facing UAT used a single-laptop evaluation environment. The setup does not claim that fifteen videos or fifteen cameras were active simultaneously.

#### Evidence

`docs/operations/VMS_SIMULATOR_SETUP.md:1-45,154-260` places MediaMTX and FFmpeg on Linux and restricts RTSP to the Windows server. `paper_sync/findings/2026-09-16-chapter4-results-framing.md:318-320` records single-laptop participant-facing UAT, distinct from tri-device technical tests. `mediamtx-vms.yml:1-37` defines five remote VMS channels. The current tracker records an 8-stream performance run, a 9-stream degradation run, and 10-channel backup-overlap sampling; it does not support the old all-fifteen-streams wording.

#### Proposed comment

Comment scope: logical paragraph; the complete revised RTSP Simulation cell

Previous: MediaMTX will locally rebroadcast fifteen distinct prerecorded traffic and collision videos as ten simultaneous RTSP streams. All fifteen streams will run active AI inference simultaneously.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 4. Live Doc — Test Environment, Browser and client-device description

Native ranges: browser t.gu7j5a4nobzi:2505–2551; client hardware t.gu7j5a4nobzi:1992–2110.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the Browser and Client Device descriptions
Preserve: use of a supported desktop browser for operator access
Comment target: the complete new Client Device description

#### OLD

> Client Device: Acer Nitro 5 AN515-57; Intel Core i5-11400H; NVIDIA GeForce RTX 3050 with 4 GB VRAM; 16 GB RAM; 512 GB SSD; Windows 11

#### NEW

Operator laptop: browser-only client running a supported desktop version of Google Chrome or Microsoft Edge; it does not host the repository, AI engine, MediaMTX, FFmpeg, model weights, or RTSP access.

#### Evidence

docs/operations/VMS_SIMULATOR_SETUP.md:368-430 defines the operator laptop as browser-only and explicitly says it needs no repository, FFmpeg, MediaMTX, AI weights, or RTSP access. The current tracker does not record the Acer hardware as the operator device. The browser version is also not frozen in the current Session Control tab, so latest stable is not reproducible.

#### Proposed comment

Comment scope: logical paragraph; the Client Device description

Previous: Client Device: Acer Nitro 5 AN515-57; Intel Core i5-11400H; NVIDIA GeForce RTX 3050 with 4 GB VRAM; 16 GB RAM; 512 GB SSD; Windows 11

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 5. Live Doc — Test Environment, topology row

Native range: t.gu7j5a4nobzi:2563–2630; Table 2, row 7, column 2.

#### Change metadata

Operation: replace
Scope: span
Changed target: the Network description cell
Preserve: private, isolated-network qualification
Comment target: the complete new cell value

#### OLD

> Two-node wired Ethernet segment. See "Network Configuration" below.

#### NEW

Three-device private LAN: Linux VMS simulator → Windows ADAS server over TCP RTSP; browser-only operator laptop → Windows ADAS server over HTTPS/WSS. See "Network Configuration" below.

#### Evidence

docs/operations/VMS_SIMULATOR_SETUP.md:26-45 defines the directional three-device topology and ports. The existing paper-sync row at ADAS_Paper_Audit_Tracker A87:H87 is a separate defense-paper target; this block is the corresponding live validation-plan site.

#### Proposed comment

Comment scope: span; OLD Two-node wired Ethernet segment; NEW Three-device private LAN: Linux VMS simulator → Windows ADAS server over TCP RTSP; browser-only operator laptop → Windows ADAS server over HTTPS/WSS

Previous: Two-node wired Ethernet segment

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 6. Live Doc — Network Configuration table

Native Table 3 ranges: t.gu7j5a4nobzi:2883–3277.

#### Change metadata

Operation: replace
Scope: row
Changed target: the complete seven-row Network Configuration table
Preserve: private-network, hostname, and transport-security intent; retain the separate Transport Security table
Comment target: each changed new topology row

#### OLD

> Server and Client columns; single direct Cat5e cable; addresses 192.168.50.1 and 192.168.50.2; blank gateways; server-local RTSP.

#### NEW

| Item               | Linux VMS simulator                          | Windows ADAS server                                          | Operator laptop                             |
| ------------------ | -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------- |
| Connection         | Same private Globe LAN                       | Same private Globe LAN                                       | Same private Globe LAN                      |
| RTSP path          | Publishes TCP 8554                           | Reads TCP 8554 from Linux VMS                                | No RTSP access                              |
| Dashboard/API path | No dashboard access                          | Serves HTTPS/WSS on TCP 8000 and HTTPS dashboard on TCP 5173 | Reaches Windows server on TCP 8000 and 5173 |
| Addressing         | DHCP-reserved venue address                  | DHCP-reserved venue address                                  | DHCP-reserved venue address                 |
| Hostname           | —                                            | Serves as adas.local                                         | Resolves adas.local to the Windows server   |
| Gateway            | Router-provided                              | Router-provided                                              | Router-provided                             |
| Network isolation  | RTSP firewall allows only the Windows server | Private firewall rules expose only the dashboard/API ports   | Operator cannot reach RTSP                  |

#### Evidence

docs/operations/VMS_SIMULATOR_SETUP.md:28-45,53-64,71-81,220-233,273-328,368-449 documents the current three-device Globe topology, DHCP-reserved role addresses, router gateway, RTSP restriction, HTTPS/WSS path, and browser-only operator. The old 192.168.50.1/192.168.50.2 direct-cable plan and blank gateways are no longer the established test topology.

#### Proposed comment

Comment scope: logical paragraph; the complete replacement Network Configuration table

Previous: Server and Client columns; single direct Cat5e cable; addresses 192.168.50.1 and 192.168.50.2; blank gateways; server-local RTSP.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 7. Live Doc — Transport Security table, certificate and RTSP exposure

Native ranges: certificate t.gu7j5a4nobzi:3376–3588; ports t.gu7j5a4nobzi:3712–3776.

#### Change metadata

Operation: replace
Scope: cell
Changed target: Certificate and Ports crossing the link / RTSP cells
Preserve: HTTPS/WSS, adas.local, and self-signed demonstration-grade qualification
Comment target: each changed cell

#### OLD

> Self-signed, issued to the hostname adas.local, with subject alternative names covering adas.local, localhost, 192.168.50.1, and 127.0.0.1; installed into the client's Trusted Root Certification Authorities store
>
> TCP 8000 and TCP 5173 only
>
> Port 8554, server-local only.

#### NEW

Self-signed certificate for adas.local, with the current LAN profile covering adas.local, localhost, and 127.0.0.1; the public certificate is installed in the operator laptop's trusted root store and the private key remains on the Windows ADAS server.

TCP 8554 between the Windows ADAS server and Linux VMS simulator; TCP 8000 and 5173 between the Windows ADAS server and browser-only operator laptop. The operator laptop does not access RTSP.

TCP 8554, VMS-to-server only; not reachable from the operator laptop.

#### Evidence

docs/operations/VMS_SIMULATOR_SETUP.md:297-328,400-430 defines the current certificate and client trust route. Its network table at 38-45 makes RTSP a Windows-to-Linux path, not server-local. The old 192.168.50.1 SAN and server-local RTSP wording belong to the superseded direct-cable setup.

#### Proposed comment

Comment scope: logical paragraph; the Certificate and port cells

Previous: Self-signed, issued to the hostname adas.local, with subject alternative names covering adas.local, localhost, 192.168.50.1, and 127.0.0.1; installed into the client's Trusted Root Certification Authorities store

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 8. Live Doc — AI batch-size description

Native range: t.gu7j5a4nobzi:2648–2858; Table 2, row 8, column 2.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete AI Batch Size description cell
Preserve: the 10-stream immediate target only as a target, not as a qualification result
Comment target: the complete new cell value

#### OLD

> TensorRT engine exported with dynamic shapes at batch 15, supporting an operating range of 1–15 cameras. Tested operating point is 10 concurrent streams at 15 FPS. See "Model and Inference Configuration" below.

#### NEW

TensorRT engine exported with a dynamic profile whose adopted maximum and optimum batch are 10. The immediate target is up to 10 concurrent streams; fifteen-camera qualification is deferred. The current performance record reports the actual stream count and measured cadence for each test case. See "Model and Inference Configuration" below.

#### Evidence

ai_engine/docs/AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md:15-41 records the new epoch50.engine profile as maximum/optimum batch 10, preserves the old batch-32 artifact separately, and explicitly defers batch 15. The current TC-PERF-002 record is an 8-channel, 15-minute run with minimum average FPS 5.15 and mean 6.778; it does not establish ten cameras at 15 FPS.

#### Proposed comment

Comment scope: logical paragraph; the complete AI Batch Size cell

Previous: TensorRT engine exported with dynamic shapes at batch 15, supporting an operating range of 1–15 cameras. Tested operating point is 10 concurrent streams at 15 FPS. See "Model and Inference Configuration" below.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 9. Live Doc — Deployed build cell

Native range: t.gu7j5a4nobzi:4057–4215; Table 5, row 4, column 2.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Deployed build cell
Preserve: source checkpoint, dynamic export, FP16, GPU-specific qualification
Comment target: the complete new cell value

#### OLD

> TensorRT engine exported from epoch50.pt with dynamic=True, batch=32, half=True (FP16). Built on the demo laptop itself; engines are not portable across GPUs.

#### NEW

TensorRT engine exported from epoch50.pt with dynamic=True, batch=10, and half=True (FP16). The adopted epoch50.engine was built on the demonstration GPU host; engines are not portable across GPUs and fifteen-camera qualification is deferred.

#### Evidence

The current .env selects ai_engine/epoch50.engine. ai_engine/docs/AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md:15-41 records the new artifact profile and hash. The old batch-32 artifact is historical context, not the adopted deployed profile.

#### Proposed comment

Comment scope: span; OLD batch=32; NEW batch=10

Previous: batch=32

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 10. Live Doc — Participant paragraph

Native range: t.gu7j5a4nobzi:4845–5181; current paragraph 103.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Test Participants paragraph
Preserve: three operator shifts and one administrator
Comment target: the complete new paragraph

#### OLD

> For the participant sessions, one operator per shift was tested across the three shifts, for a total of three operators, plus one administrator. Each shift's second designated operator received the information shared by the tested operator, so the testing still covered one operator from each shift without duplicating the same session.

#### NEW

Participant sessions used three coded Operators, one assigned to each shift, plus one coded Administrator. Each participant completed one standardized continuous role-based journey followed by an individual SUS response and debrief. The current tracker records 33 participant-stage executions: 27 Operator stages and 6 Administrator stages.

#### Evidence

ADAS Test Execution, Session Control A14:H18 records OP-01, OP-02, OP-03, and ADM-01; Summary A13:B14 records 33 participant-stage executions and four SUS responses. The current tracker does not evidence the sentence about each shift's second designated operator receiving shared information, so it is removed from the current record.

#### Proposed comment

Comment scope: logical paragraph; the complete Test Participants paragraph

Previous: For the participant sessions, one operator per shift was tested across the three shifts, for a total of three operators, plus one administrator. Each shift's second designated operator received the information shared by the tested operator, so the testing still covered one operator from each shift without duplicating the same session.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 11. Live Doc — Testing Schedule narrative and status cells

Native ranges: narrative t.gu7j5a4nobzi:6123–6517; schedule activity cells t.gu7j5a4nobzi:6702–6792 and 6817–6984; status cells are the blank fourth-column cells in the five schedule rows.

#### Change metadata

Operation: replace/insert
Scope: logical paragraph and cell
Changed target: schedule narrative, Day 2 and Day 3 activity descriptions, and the five blank Status cells
Preserve: Aug 27–31 date sequence and participant-session dates
Comment target: each changed paragraph/cell

#### OLD

> Testing runs across five days, August 27–31, 2026. Researcher-executed technical activities are scheduled before the CDRRMO participant sessions so the system has already undergone functional, performance, reliability, backup/recovery, and security testing. The endurance soak run is limited to one day, and no separate defect re-test, data-analysis, or evidence-consolidation day is scheduled.
>
> System / End-to-End Testing (two-node walkthrough in a real browser); AI Model Validation.
>
> Performance & Load Testing; Security Testing; Backup & Recovery Testing; Reliability & Endurance Testing, including the one-day endurance soak run and results capture.
>
> Status cells: blank.

#### NEW

The five-day testing schedule was followed as planned from August 27–31, 2026. Days 1–3 covered final deployment and build freeze, technical testing, performance and load testing, security testing, backup and recovery testing, and reliability and endurance testing. Days 4–5 covered the participant sessions for usability testing and User Acceptance Testing. The detailed tracker records the results and retains any applicable model, profile, duration, or simulation qualification.

>

System / End-to-End Testing (three-device LAN walkthrough in a real browser); AI Model Validation.

>

Performance & Load Testing; Security Testing; Backup & Recovery Testing; Reliability & Endurance Testing, including the qualified accelerated endurance/thermal window and results capture.

>

Status cells: Completed; Completed; Completed with documented profile or duration qualifications; Completed; Completed.

#### Evidence

The current tracker dates its technical cases to August 27–29 and UAT to August 30–31. TC-REL-006 records a 34.7-minute thermal window in place of 24 hours; TC-PERF-009 and TC-PERF-015 record 34.7-minute windows in place of one hour. TC-REL-012 and TC-PERF-012 have later re-tests. The live schedule's empty Status column does not describe the current state.

#### Proposed comment

Comment scope: logical paragraph; schedule narrative and changed table cells

Previous: Testing runs across five days, August 27–31, 2026. Researcher-executed technical activities are scheduled before the CDRRMO participant sessions so the system has already undergone functional, performance, reliability, backup/recovery, and security testing. The endurance soak run is limited to one day, and no separate defect re-test, data-analysis, or evidence-consolidation day is scheduled.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 12. Live Doc — Testing Schedule placeholder

Native range: t.gu7j5a4nobzi:5759–6121; current paragraph 146.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete angle-bracketed schedule placeholder
Preserve: the heading and the actual schedule table
Comment target: the replacement paragraph

#### OLD

> <With the final defense scheduled 1 month from now, this table should help you plan the testing activities that you will need to perform to be ready for the final defense. This section will also be submitted regularly so that your progress can be monitored. The activities listed in the table would depend on the different types of tests that you will execute.>

#### NEW

The table below records the five-day execution schedule that was followed. Detailed case results, evidence links, and any applicable qualifications are maintained in the current ADAS Test Execution tracker.

#### Evidence

The angle-bracketed text is a template instruction left in the live document. The current tracker is a result record, not a recurring progress submission.

#### Proposed comment

Comment scope: logical paragraph; the complete schedule placeholder

Previous: <With the final defense scheduled 1 month from now, this table should help you plan the testing activities that you will need to perform to be ready for the final defense. This section will also be submitted regularly so that your progress can be monitored. The activities listed in the table would depend on the different types of tests that you will execute.>

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 13. Live Doc — Evaluation Methods placeholder

Native range: t.gu7j5a4nobzi:7352–7659; current paragraph 168.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete angle-bracketed evaluation-method placeholder
Preserve: the Evaluation Methods heading and table
Comment target: the replacement paragraph

#### OLD

> <This section identifies how the tests will be conducted and what methods will be used for testing. For example, Ease of Use will be evaluated using a SUS usability questionnaire. Functional correctness will be using the execution of test cases and measuring the number of test cases with “Passed” status.>

#### NEW

Evaluation methods and evidence are recorded in the current ADAS Test Execution tracker. Technical cases were executed before the participant sessions, and each result records its denominator, evidence location, model artifact or hardware condition where relevant, and any simulation, duration, or scope qualification. Participant-stage results, SUS responses, readiness, defects, and formal acceptance are tracked separately so incomplete evidence cannot be hidden by a single aggregate pass rate.

#### Evidence

The angle-bracketed text is an unremoved template instruction. The current tracker has separate technical tabs, participant-stage Execution Log, SUS Questionnaire, Usability Results, UAT Results, Defect Log, and UAT Traceability tabs.

#### Proposed comment

Comment scope: logical paragraph; the complete Evaluation Methods placeholder

Previous: <This section identifies how the tests will be conducted and what methods will be used for testing. For example, Ease of Use will be evaluated using a SUS usability questionnaire. Functional correctness will be using the execution of test cases and measuring the number of test cases with “Passed” status.>

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 14. Live Doc — Evaluation Methods table, stale or under-qualified rows

Native ranges: system t.gu7j5a4nobzi:8139–8290; AI t.gu7j5a4nobzi:8391–8984; inference t.gu7j5a4nobzi:9151–9332; query/export t.gu7j5a4nobzi:9450–9544; fault/endurance t.gu7j5a4nobzi:9607–9807; backup t.gu7j5a4nobzi:9945–10125; learnability t.gu7j5a4nobzi:10780–10903; efficiency t.gu7j5a4nobzi:11009–11203; organizational acceptance t.gu7j5a4nobzi:11301–11466.

#### Change metadata

Operation: replace
Scope: row
Changed target: the listed Evaluation Methods table rows
Preserve: the table's objective/evidence structure and all correctly described measures
Comment target: each changed row

#### OLD

> System testing: Execution of system test cases over the two-node network in a real browser, combining automated end-to-end scripts with a structured manual walkthrough
>
> AI detection accuracy: Supporting event-level scoring of the deployed engine against the 17 hand-labelled clips
>
> Inference and delivery latency: Timed measurement under the full 10-stream load
>
> Query and export performance: Timed dashboard queries and report exports executed against the 100,000-record seeded database
>
> Fault tolerance and endurance: Fault injection (...) plus a continuous multi-hour run
>
> Backup and recovery: Timed execution of an automated backup against a live system with active inference and concurrent database writes, followed by a timed administrative restore and service resumption
>
> Learnability: Timed observation of a participant with no prior exposure processing an alert unaided
>
> Operational efficiency: Timed observation during UAT: elapsed time from the collision becoming visible in the simulated feed to the operator's verification decision
>
> Organizational acceptance: Scenario-based UAT covering the operational workflows the agency actually performs, concluding in a formal acceptance decision by an authorized CDRRMO representative

#### NEW

> System testing: Execution of system test cases over the established three-device LAN in a real browser, combining automated system checks with a structured walkthrough from the Linux VMS simulator through the Windows ADAS server to the operator browser.
>
> AI detection accuracy: Primary reporting of the qualified validation-split mAP@0.50 for epoch50.pt; supporting event-level scoring of the 17-clip corpus with standard and hard strata, false alarms per minute, and TensorRT-versus-checkpoint differences reported separately. No independent held-out post-selection test-set claim is made.
>
> Inference and delivery latency: Timed measurement at the declared model artifact and actual configured stream count, with batch inference, alert delivery, and hardware conditions recorded separately. A capacity diagnostic is not treated as a production scheduler result.
>
> Query and export performance: Single-request and 20-request concurrent API measurements against the 100,000-row database, plus operational 30-day synchronous exports and larger asynchronous export jobs reported separately.
>
> Fault tolerance and endurance: Fault injection and recovery checks, with simulated cases clearly labelled, plus a qualified 34.7-minute combined performance/thermal window; no multi-hour or 24-hour endurance result is claimed.
>
> Backup and recovery: Timed manual and scheduled backup/restore drills covering protected and degraded storage tiers, concurrent-write safety, integrity verification, rollback, database replacement, and service resumption.
>
> Learnability: Timed observation of first-time participants after the standardized briefing, with assistance events recorded separately from the learnability timing.
>
> Operational efficiency: Raw alert-appearance-to-operator-decision timings during UAT, with an approximately 3-second detector-accumulation and 2-second alert-propagation allowance added only when deriving the 25-second collision-visible-to-decision estimate; no automatic dispatch timing is claimed.
>
> Organizational acceptance: Scenario-based UAT covering the defined operator and administrator journeys; record tracker eligibility and the authorized representative's signed decision separately. A tracker-level Accepted value is not a substitute for a completed signed record.

#### Evidence

The current tracker records AI-VAL-001 as a qualified archival mAP result and AI-VAL-002 as an epoch50.pt event-level run: standard 8/10, hard 0/6, overall 8/16, 0.27 false positives/minute over 11.0 clean minutes. AI-VAL-008 keeps the TensorRT parity result separate and records native-rate false-positive drift. TC-PERF-002 is an 8-channel run; TC-PERF-012 defines the concurrent profile; TC-REL-005/006/012 explicitly qualify accelerated durations; and Usability Results records raw OP-J05 values plus the reconstructed 25-second estimate.

#### Proposed comment

Comment scope: logical paragraph; one comment per changed Evaluation Methods row

Previous: The exact OLD row text is the corresponding row quoted above.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 15. Live Doc — Acceptance Criteria placeholder

Native range: t.gu7j5a4nobzi:11549–11718; current paragraph 212.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete angle-bracketed acceptance-criteria placeholder
Preserve: the heading and criteria table
Comment target: the replacement paragraph

#### OLD

> <This section identifies the criteria that will be used to determine if the test results are acceptable or not, and can help determine if you have met your objectives.>

#### NEW

The criteria below are the approved acceptance rules used to interpret the recorded results. A criterion is not considered proven when the underlying row is only simulated, duration-accelerated, archival, or otherwise qualified; those limitations remain part of the result.

#### Evidence

The live document still contains a template instruction. The current tracker records qualifications in the Actual Result / Notes and Defect / Retest Note columns.

#### Proposed comment

Comment scope: logical paragraph; the complete acceptance-criteria placeholder

Previous: <This section identifies the criteria that will be used to determine if the test results are acceptable or not, and can help determine if you have met your objectives.>

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 16. Live Doc — Acceptance Criteria table, revised performance and evidence rules

Native ranges: inference latency t.gu7j5a4nobzi:12480–12499; AI supporting 12204–12458; frame rate 12514–12576; query 12714–12762; restart 13235–13346; availability 13493–13624; learnability 14053–14138; efficiency 14165–14271; UAT 14299–14834.

#### Change metadata

Operation: replace
Scope: row
Changed target: the listed Acceptance Criteria table rows
Preserve: unit/integration, system, alert-delivery, backup, recovery, security, and SUS thresholds where still supported
Comment target: each changed row

#### OLD

> AI supporting: Event-level recall on standard-difficulty clips and false alarms per minute reported against the frozen reference baseline, with no regression from that baseline. Hard-difficulty recall reported separately and never blended into a single headline figure.
>
> Inference latency: ≤ 100 ms per frame.
>
> Frame rate: Sustained 10–15 FPS on every one of the 10 concurrent streams.
>
> Dashboard query response: ≤ 3 seconds against the 100,000-record database.
>
> Restart recovery: Memory flush and return to service completed in under 10 seconds; camera ingestion confirmed resumed afterward.
>
> Availability: ≥ 99.9% of readiness probes successful across the continuous soak window, with no unplanned service interruption. (See note below.)
>
> Learnability: A new operator processes and verifies an alert unaided within 15 minutes of briefing.
>
> Operational efficiency: Detection-to-dispatch-decision mean ≤ 15 seconds across operators; worst case reported alongside the mean.
>
> User Acceptance Testing: NEW ADDITION — Clarified UAT acceptance denominator: all 33 planned applicable participant-stage executions (27 Operator + 6 Administrator) must have a final Pass or Fail result; at least 95% of those 33 executions must pass; zero Critical or Major defects may remain open; overall mean SUS must be at least 68; all nine UAT readiness items must be Ready; and formal sign-off must be obtained from an authorized CDRRMO representative. Not Executed, Blocked, and Retest Required are incomplete or unresolved and prevent full completion.

#### NEW

> AI supporting: Event-level recall and false alarms per minute are reported separately for standard and hard clips against the frozen checkpoint baseline, with TensorRT artifact, cadence, and source-resolution differences disclosed. The current reference run records standard recall 8/10, hard recall 0/6, overall 8/16, and 0.27 false positives/minute over 11.0 clean minutes; this is descriptive, project-specific evidence rather than an independent held-out test-set estimate.
>
> Inference latency: The ≤100 ms per-frame target is measured against the declared model artifact and actual stream profile, with the timing definition and hardware recorded. A missing-artifact or capacity-only measurement is supporting evidence, not a deployed TensorRT result.
>
> Frame rate: The accepted operating band is 5–15 FPS per connected stream, with 15 FPS as the target and rates below 5 FPS as the warning floor. Each result states the actual stream count, artifact, hardware, duration, and whether the measurement is a clean qualification or a qualified deviation; fifteen-camera qualification is deferred.
>
> Dashboard query response: Normal single-user dashboard requests remain within 3 seconds; under the defined 20-request concurrent authenticated-use profile, the 95th-percentile response remains within 10 seconds against the 100,000-row database, with valid-request error rate reported separately.
>
> Restart recovery: Report backend readiness, AI heartbeat, and camera-ingestion recovery separately. The latest scheduled-restart record returned backend readiness in 5.11 seconds and a fresh AI heartbeat in 12.672 seconds, so full-stack recovery is reported with that qualification rather than as an unqualified under-10-second result.
>
> Availability: Report readiness-probe success over a stated active observation window and identify planned maintenance or inactive periods. A short soak is not evidence of annual 99.9% availability; the current tracker marks the full-duration case as qualified/not fully run.
>
> Learnability: Each first-time participant completes the defined learnability task within 15 minutes after the standardized briefing. Assistance events are recorded and interpreted separately; the timing is not described as an unaided measure.
>
> Operational efficiency: Collision-visible-to-operator-decision target ≤25 seconds. Report raw alert-to-decision observations separately from the reconstructed estimate that adds approximately 3 seconds of detector accumulation and 2 seconds of alert propagation; no automatic dispatch or direct DSS timing is claimed.
>
> User Acceptance Testing: All 33 planned applicable participant-stage executions (27 Operator and 6 Administrator) must have a final Pass or Fail result; at least 95% must pass; zero Critical or Major defects may remain open; overall mean SUS must be at least 68; all nine readiness items must be Ready; and a signed decision must be obtained from an authorized CDRRMO representative. Not Executed, Blocked, and Retest Required remain incomplete or unresolved.

#### Evidence

ai_engine/config.py:124-127 records the 5–15 FPS band and 15 FPS target. paper_sync/findings/2026-09-14-nfr03-five-to-fifteen-fps.md records the approved requirement wording. ADAS Test Execution, Performance & Load Testing A13:J13 records the 20-request p95 5.986-second result against the revised 10-second concurrent budget. Usability Results A15:C16 records the reconstructed NFR-09 mean 18.3 seconds and worst case 21.0 seconds. Reliability & Endurance A13:J13 records the latest restart qualification. UAT Results A4:D14 records 33/33, SUS 89.375, readiness 9/9, and the tracker-level Accepted value.

#### Proposed comment

Comment scope: logical paragraph; one comment per changed Acceptance Criteria row

Previous: The exact OLD row text is the corresponding row quoted above.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

### 17. Live Doc — Deliverables placeholder and output rows

Native ranges: placeholder t.gu7j5a4nobzi:14852–15347; system output 15606–15722; reliability output 16136–16280; UAT output 16735–16828; Deliverables table t.gu7j5a4nobzi:15349–16830.

#### Change metadata

Operation: replace/insert
Scope: logical paragraph and row
Changed target: the placeholder, topology-sensitive output rows, and missing cross-cutting deliverables
Preserve: the activity names and evidence-oriented structure
Comment target: each changed paragraph/row

#### OLD

> <This section identifies what will be the documentary evidence that will prove that you have completed the specific test activities. These documents may be attached as appendices and supporting evidence in your final paper. For example, in the case of Functional Testing, there are 10 functions and features of your application that need to be tested, then you need to show the results of the testing that was done. Similarly, for Usability, you will need to present the results of the survey.>
>
> System test case results table; automated end-to-end run report; annotated two-node walkthrough log with screenshots
>
> Endurance run log: memory, VRAM, thermal, and availability sampling across the soak window; fault injection results table; restart drill records
>
> UAT scenario results; detection-to-dispatch timing table; defect list; signed acceptance form

#### NEW

> The deliverables below are the evidence artifacts used for the completed test record. The current ADAS Test Execution tracker is the index for technical results, participant-stage execution, SUS, readiness, defects, traceability, and formal acceptance. Each result retains its evidence link and any simulation, duration, artifact, or scope qualification.
>
> System test case results table; automated system-test report; annotated three-device LAN walkthrough log with screenshots
>
> Qualified endurance/performance run log: memory, VRAM, thermal, availability sampling, fault-injection results, restart drill records, and explicit duration qualifications
>
> UAT scenario results; raw alert-to-decision and reconstructed collision-visible-to-operator-decision timing table; defect log; UAT acceptance and sign-off record
>
> Requirements Traceability Matrix | Every FR/NFR mapped to a technical source or participant-stage journey, evidence location, and coverage status
>
> Defect Log | All recorded defects with severity, status, resolution, and retest notes
>
> Test Summary Report | Consolidated activity counts, pass rates, acceptance gates, evidence qualifications, and limitations

#### Evidence

The placeholder is still present. The current tracker has the missing cross-cutting artifacts as UAT Traceability, Defect Log, Summary, and UAT Results. The current UAT timing fields are raw alert-appearance-to-decision values with a reconstructed allowance, not a direct first-visible-frame measurement. The current reliability rows explicitly record accelerated durations.

#### Proposed comment

Comment scope: logical paragraph; placeholder and changed deliverable rows

Previous: The exact OLD deliverable text is quoted above.

Codex ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN

Done by Codex.

## Blocking evidence and limitations

1. The tracker-level UAT decision is Accepted, but the linked native ADAS User Acceptance Testing (UAT) Acceptance and Sign-Off Record (ID 1d2nSnoi95E_QJikl9Hp93zW18MHXJaUi3lDJlhqWKWQ) still shows Decision: ☐ Accepted ☐ Accepted with Conditions ☐ Rejected, blank conditions, and a blank date in its front page. The plan must not describe formal sign-off as evidenced until that record is actually completed and signed. The same file retains a stale 66-execution template appendix and old Resolved terminology; that related-artifact cleanup is outside this target Doc and needs a separate approval.

2. Fresh PDF export of the target Doc succeeded through Google Drive, but the returned authenticated file reference could not be materialized from this Windows session (SEC_E_NO_CREDENTIALS). Native indexes and table locations are verified; rendered page mapping and visual QA remain pending and block approval-ready page numbers.

3. Current code and evidence confirm these values as still current: confidence floor 0.15, input size 640, accumulator threshold 1.0 conf-seconds, decay 0.30, IoU link 0.30, EMA 0.5, reset gap 0.5 seconds, 17 labelled clips, four participants, SUS criterion 68, and 60-second post-restore alerting window.

4. This finding does not propose changing the separate defense-paper Doc or the sign-off Doc. It owns the linked Capstone Test Execution and Validation Doc and records a proposed tracker row below.

### 18. Tracker Sheet — ADAS_Paper_Audit_Tracker, 🚩 Action Stream!A89:H89

#### Change metadata

Operation: insert
Scope: row
Changed target: the first fully blank row in the named 🚩 Action Stream tab; current A1 range A89:H89
Preserve: occupied rows 1–88, existing formatting, validation, notes, and the manual Reviewed by cell H89
Comment target: exact newly inserted text colored orange (#E67E22); no Sheet comment

#### OLD

> The live bounded userEnteredValue read of 🚩 Action Stream!A1:H99 returned occupied rows through row 88; row 89 is the first fully blank append candidate.

#### NEW

A89: Major
B89: Testing and Validation
C89: pending PDF mapping
D89: Reconcile the live Test Execution and Validation Plan with the completed tracker, adopted batch-10 profile, three-device technical topology, single-laptop UAT environment, revised performance criteria, qualified endurance evidence, and formal UAT-sign-off state
E89: Current tracker reports 194/194 technical cases and 33/33 participant stages, but the live plan still carries two-node, batch-15/batch-32, 10–15 FPS, 15-second, multi-hour, template-placeholder, and incomplete-deliverable wording; formal sign-off record remains unsigned.
F89: Not started
G89: Daniboy
H89: preserve blank

#### Evidence

Live tracker identity: ADAS_Paper_Audit_Tracker, spreadsheet 1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ. The fresh userEnteredValue scan established occupied rows through 88 and the first fully blank append target as row 89. No Sheet write was attempted.

#### Formatting fallback

Color the newly inserted text in A89:G89 orange (#E67E22) using rich-text textFormatRuns; preserve H89 blank, existing row formatting, validation, and notes.

## Approval / sync ledger

Package ID: PS-20260916-TEST-EXECUTION-VALIDATION-PLAN
Approval source: user approval in chat on 2026-09-16; approved scope is all remaining listed blocks after removal of the former execution-summary Block 18

| Target                                   | Approved scope                                                | Applied/read back                 | Skipped/pending    | Blocked                                                                                   |
| ---------------------------------------- | ------------------------------------------------------------- | --------------------------------- | ------------------ | ----------------------------------------------------------------------------------------- |
| Linked Test Execution and Validation Doc | blocks 1–17 and their attached replacement comments           | blocks 1–17; 48 anchored comments | —                  | —                                                                                         |
| ADAS_Paper_Audit_Tracker                 | block 18 and its exact orange text-format fallback            | —                                 | —                  | fresh PDF mapping unavailable; tracker write held under the procedure's page-mapping gate |
| Related UAT sign-off record              | Not part of this target                                       | —                                 | separate follow-up | unsigned decision/date and stale appendix                                                 |
| Standalone comments                      | Not applicable; all Doc comments are bundled with blocks 1–17 | 48 anchored replacement comments  | —                  | —                                                                                         |
