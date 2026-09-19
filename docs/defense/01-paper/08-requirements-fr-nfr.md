# 08 — Functional and Non-Functional Requirements

> **One-liner:** The FRs define what ADAS lets an operator or administrator do; the NFRs set the measurable operating, usability, reliability, security, and maintenance conditions.
> **Panel risk:** High — the requirements include ambitious real-world claims, while the tracker records a mix of direct, simulated, accelerated, archival, and reconstructed evidence.

## 1. What it is

Functional requirements (FRs) describe visible system capabilities: signing in, configuring cameras, reviewing incidents, viewing analytics, exporting reports, and consulting the Help Center. Non-functional requirements (NFRs) set conditions such as accuracy, latency, uptime, access security, retention, and learnability.

The defense paper is the source for the exact requirement wording. The test tracker is the source for how each item was exercised and what result was recorded. The code references below show where the behavior lives; they do not replace the paper's requirement or the tracker's qualification.

The tracker distinguishes technical test cases from participant-stage UAT. Its UAT Traceability sheet maps each user-facing FR and most NFRs to the appropriate journey or technical activity. A mapped row means the requirement has a planned evidence path; the recorded outcome is in the named test cases, Execution Log, or UAT Results sheet.

## 2. Where it lives

### In the paper

All requirement text below comes from **Chapter 3, Requirements Analysis** of the defense paper:

- **Table 2 — Functional Requirements:** FR-01 through FR-20.
- **Table 3 — Performance Requirements:** NFR-01 through NFR-06.
- **Table 4 — Scalability Requirements:** NFR-07 and NFR-08.
- **Table 5 — Usability Requirements:** NFR-09 through NFR-12.
- **Table 6 — Reliability Requirements:** NFR-13 through NFR-18.
- **Table 7 — Security Requirements:** NFR-19 through NFR-21.
- **Table 8 — Maintainability Requirements:** NFR-22.

### In the code

The requirement-by-requirement matrix below cites the implementation points. Read it by subsystem:

- **Sign-in, authorization, accounts:** `backend/app/api/routes/auth.py:39`, `backend/app/api/dependencies.py:104`, `backend/app/api/dependencies.py:118`, `backend/app/api/routes/users.py:83`, `backend/app/api/routes/users.py:254`.
- **Camera and AI path:** `backend/app/api/routes/cameras.py:151`, `backend/app/services/cameras.py:44`, `ai_engine/camera.py:165`, `ai_engine/pipeline.py:84`, `ai_engine/detector.py:188`, `ai_engine/accident.py:38`.
- **Alert, snapshot, incident lifecycle:** `backend/app/api/routes/internal.py:93`, `backend/app/api/routes/alerts.py:464`, `backend/app/services/incidents.py:229`, `backend/app/services/snoozes.py:30`, `frontend/src/components/GlobalAlerts.tsx:401`.
- **Logs, analytics, exports, help, audit:** `backend/app/api/routes/alerts.py:222`, `backend/app/api/routes/analytics.py:266`, `backend/app/api/routes/exports.py:54`, `backend/app/api/routes/help.py:18`, `backend/app/services/audit.py:51`.
- **Health and maintenance:** `backend/app/core/monitor.py:153`, `backend/app/api/routes/system_health.py:208`, `backend/app/api/routes/maintenance.py:192`, `backend/app/services/maintenance_schedule.py:231`.
- **Session and local-data controls:** `backend/app/services/sessions.py:14`, `backend/app/core/security.py:69`, `backend/app/core/config.py:52`, `scripts/register-maintenance-task.ps1:68`.

## 3. How it works

The operator-facing requirements follow one connected path:

1. An authorized user signs in; the backend checks the session and role before returning protected data or enabling a role-specific action.
2. The AI engine opens configured camera streams, keeps the newest frame available, analyzes frames on a fixed cadence, and accumulates evidence before emitting an event.
3. A fired event produces an annotated snapshot and a durable event payload. The backend persists it as an Unverified incident and publishes an alert for connected dashboards.
4. The operator reviews the alert and chooses Confirm or Dismiss. Confirmation keeps the camera paused while the incident is Ongoing; dismissal records a one-minute camera cooldown. The operator later records Cleared or corrects an Ongoing incident to Dismissed.
5. The same records feed historical search, analytics, AI-performance views, exports, and the append-only audit trail. Separate health and maintenance paths sample host/AI status, retain trends, back up data, and restore it.

The test tracker records **194/194 technical test cases as Pass** across its eight technical activities and **33/33 participant-stage executions as Pass** in UAT Results. UAT Results also records a SUS mean of **89.375**, **9/9** readiness items marked Ready, and the tracker-level acceptance decision **Accepted**. These are tracker summaries; individual requirements still carry their own evidence and qualifications in the matrices.

### Functional requirements — paper Table 2

The UAT Traceability sheet maps the stage IDs shown in the result column. The overall participant-stage result is 33/33 Pass; technical results name the exact tracker case IDs.

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>FR-01 — User Authentication</strong><br>The system shall require all users to securely log in using a valid username and password before accessing the web dashboard.</td>
<td><code>backend/app/api/routes/auth.py:39</code>; <code>frontend/src/pages/Login.tsx:25</code></td>
<td><code>TC-UNIT-001/002</code> and <code>TC-SEC-001</code>: Pass. UAT maps <code>OP-J01</code> and <code>AD-J01</code>; participant-stage results are 33/33 Pass.</td>
</tr>
<tr>
<td><strong>FR-02 — Role-Based Access Control (RBAC)</strong><br>The system shall enforce two distinct access levels. Operators shall have operational access to the analytics dashboard, active camera status lists and configurations, detection logs, and system health metrics. Administrators shall inherit all Operator privileges and have exclusive access to AI performance monitoring, AI performance exports, and User Account Management.</td>
<td><code>backend/app/api/dependencies.py:118</code>; <code>backend/app/api/routes/users.py:202</code>; <code>frontend/src/components/layouts/Sidebar.tsx:68</code></td>
<td><code>TC-UNIT-003</code>, <code>TC-SEC-003/005</code>: Pass. UAT maps <code>OP-J01</code>, <code>AD-J01</code>, and <code>AD-J03</code>; participant-stage results are 33/33 Pass.</td>
</tr>
<tr>
<td><strong>FR-03 — User Account Management</strong><br>The system shall provide account management appropriate to each access level. Administrators shall be able to create, edit, deactivate, and restore user accounts, assign roles, change user passwords, and search the list of users. Operators shall be able to update only their own account details and their own password.</td>
<td><code>backend/app/api/routes/users.py:83</code>; <code>backend/app/api/routes/users.py:254</code>; <code>frontend/src/pages/Users.tsx:53</code></td>
<td><code>TC-UNIT-004–007</code>, <code>TC-SEC-009/010</code>, and <code>TC-SYS-003</code>: Pass. UAT maps <code>AD-J03</code>; participant-stage results are 33/33 Pass.</td>
</tr>
<tr>
<td><strong>FR-04 — Video Stream Ingestion</strong><br>The system shall connect to and retrieve video feeds from the agency’s CCTV network.</td>
<td><code>ai_engine/camera.py:165</code>; <code>backend/app/services/cameras.py:44</code></td>
<td><code>TC-UNIT-008–010</code> and <code>TC-INT-001</code>: Pass. Integration used a live RTSP stream published by the MediaMTX VMS simulator. UAT maps <code>OP-J04</code>; UAT video was simulated.</td>
</tr>
<tr>
<td><strong>FR-05 — Automated Collision Detection</strong><br>The system shall continuously analyze active video feeds using an AI computer vision model to detect vehicle-to-vehicle collisions within each camera’s field of view.</td>
<td><code>ai_engine/pipeline.py:84</code>; <code>ai_engine/detector.py:188</code>; <code>ai_engine/accumulate.py:59</code></td>
<td><code>TC-UNIT-011–017</code>: Pass. <code>AI-VAL-002</code>: Pass with event-level recall 8/16 overall and 0/6 hard clips. UAT maps <code>OP-J04</code>.</td>
</tr>
<tr>
<td><strong>FR-06 — Alert Generation and Snapshot Capture</strong><br>Upon detecting a collision, the system shall automatically capture a visual snapshot with a bounding box around the incident, store the event record in the local database with an Unverified status, display the active alert on the web dashboard, and trigger an audible alarm to notify the operator.</td>
<td><code>ai_engine/accident.py:21</code>; <code>ai_engine/accident.py:38</code>; <code>backend/app/api/routes/internal.py:93</code></td>
<td><code>TC-UNIT-018–020</code> and <code>TC-INT-002–005</code>: Pass. UAT maps <code>OP-J04</code>; the tracker records the snapshot, alert, and alarm in the simulated stream journey.</td>
</tr>
<tr>
<td><strong>FR-07 — Audible Alert Timeout and Escalation</strong><br>Along with the visual alert, the system shall include a 'Mute/Snooze' button to give the operator a quiet moment to verify the incident. However, if the alert is left 'Unverified' for too long (e.g., 30 seconds), the alarm automatically sounds again to ensure no emergency is missed.</td>
<td><code>backend/app/services/snoozes.py:30</code>; <code>backend/app/services/snoozes.py:126</code>; <code>frontend/src/components/GlobalAlerts.tsx:330</code></td>
<td><code>TC-UNIT-021/022</code> and <code>TC-REL-001</code>: Pass; the restart case is an accelerated simulation. UAT maps <code>OP-J02</code>, <code>OP-J05</code>, and <code>OP-J06</code>; deterministic timeout proof is technical.</td>
</tr>
<tr>
<td><strong>FR-08 — Alarm Configuration Module</strong><br>The system shall provide a settings interface allowing users to select distinct auditory alert tones, control system volume, and define the temporal duration (in seconds/minutes) for the alert suppression (snooze) feature.</td>
<td><code>backend/app/api/routes/settings.py:31</code>; <code>backend/app/api/routes/settings.py:52</code>; <code>frontend/src/pages/profile/AlarmSettingsCard.tsx:106</code></td>
<td><code>TC-UNIT-023–026</code>: Pass, including snooze and volume boundary checks. UAT maps <code>OP-J02</code>; participant-stage results are 33/33 Pass.</td>
</tr>
<tr>
<td><strong>FR-09 — Human-in-the-Loop (HITL) Verification Workflow</strong><br>The system shall present the captured incident snapshot to the user, requiring selection of either Confirm (to verify a true accident) or Dismiss (to indicate a false positive) before clearing the alert from the primary dashboard.</td>
<td><code>backend/app/api/routes/alerts.py:464</code>; <code>frontend/src/components/GlobalAlerts.tsx:401</code>; <code>frontend/src/components/GlobalAlerts.tsx:408</code></td>
<td><code>TC-UNIT-027/028</code> and <code>TC-SYS-009</code>: Pass. UAT maps <code>OP-J05</code> and <code>OP-J06</code>; the UI decision path was also checked without intermediate navigation.</td>
</tr>
<tr>
<td><strong>FR-10 — False Positive Handling</strong><br>If the user selects Dismiss, the system shall update the incident database record to reflect a Dismissed status and clear the notification from the dashboard. To prevent redundant alerts from the same environmental noise, the system shall enforce a one-minute AI detection cooldown on the specific camera feed before resuming active monitoring.</td>
<td><code>backend/app/services/incidents.py:284</code>; <code>backend/app/services/cameras.py:413</code></td>
<td><code>TC-UNIT-029–031</code> and <code>TC-INT-006</code>: Pass. UAT maps <code>OP-J06</code>; the technical result verified the cooldown expiry and resume behavior.</td>
</tr>
<tr>
<td><strong>FR-11 — True Positive Handling</strong><br>If the user selects Confirm, the system shall update the incident database record to reflect an Ongoing status. The system must keep the AI detection for the camera paused throughout the incident. AI detection shall resume for that feed only after an operator manually updates the record as Cleared (indicating a cleared emergency) or Dismissed (indicating an aborted or misidentified event), thereby preventing duplicate alerts for the ongoing incident.</td>
<td><code>backend/app/services/incidents.py:229</code>; <code>backend/app/services/cameras.py:326</code>; <code>ai_engine/supervisor.py:172</code></td>
<td><code>TC-UNIT-032–034</code> and <code>TC-INT-007/008</code>: Pass. UAT maps <code>OP-J05</code> and <code>OP-J07</code>; tracker terminology for a true positive's final status is Cleared.</td>
</tr>
<tr>
<td><strong>FR-12 — Incident Logging</strong><br>The system shall keep a separate, uniquely numbered record for every detected incident. Each record shall include the captured image, the camera, the time of detection, and the AI's confidence in the detection, and shall be updated as the incident progresses. The record shall show the full history of the incident: every change of status, who made it, and when.</td>
<td><code>backend/app/models/detection.py:12</code>; <code>backend/app/services/incidents.py:124</code>; <code>backend/app/services/audit.py:51</code></td>
<td><code>TC-UNIT-035</code>, <code>TC-INT-002/009</code>, and <code>TC-SYS-012</code>: Pass. UAT maps <code>OP-J05</code>, <code>OP-J07</code>, and <code>AD-J05</code>.</td>
</tr>
<tr>
<td><strong>FR-13 — Historical Logs Search and Filtering</strong><br>The system shall allow users to search past incident records and to filter and sort them by date range, camera, status, and the operator who handled them.</td>
<td><code>backend/app/api/routes/alerts.py:124</code>; <code>backend/app/api/routes/alerts.py:222</code>; <code>frontend/src/pages/Detections.tsx:113</code></td>
<td><code>TC-UNIT-036/037</code> and <code>TC-SEC-002</code>: Pass. UAT maps <code>OP-J07</code>, <code>OP-J09</code>, and <code>AD-J05</code>.</td>
</tr>
<tr>
<td><strong>FR-14 — Camera Configuration Management</strong><br>The system shall provide a camera screen showing, for each feed, whether the camera is currently reachable over the network (Connected, Disconnected, Connecting, or Unresponsive) and whether AI detection on it is running (Active, Inactive, Paused, or Unresponsive). From this screen, users shall be able to add, edit, or remove cameras, switch a camera off entirely so that both its video and its detection stop, and search or filter the camera list by status.</td>
<td><code>backend/app/api/routes/cameras.py:151</code>; <code>backend/app/api/routes/cameras.py:259</code>; <code>backend/app/api/routes/cameras.py:305</code>; <code>frontend/src/pages/Cameras.tsx:93</code></td>
<td><code>TC-UNIT-038–045</code>, <code>TC-INT-010–013</code>, and <code>TC-SYS-013/014</code>: Pass. UAT maps <code>OP-J03</code> and <code>AD-J02</code>.</td>
</tr>
<tr>
<td><strong>FR-15 — System Health and Hardware Telemetry</strong><br>The system shall provide a screen showing how heavily the server is being used and how steadily the AI is running. It shall display how long the server has been running, how much of its processing, graphics, memory, and storage capacity is in use, and how quickly video is being analyzed. Users shall be able to view these figures over past periods to see how they change over time.</td>
<td><code>backend/app/core/monitor.py:153</code>; <code>backend/app/api/routes/system_health.py:208</code>; <code>frontend/src/pages/SystemHealth.tsx:522</code></td>
<td><code>TC-UNIT-046/047</code>, <code>TC-INT-014/015</code>, and <code>TC-SYS-015</code>: Pass. UAT maps <code>OP-J03</code> and <code>AD-J02</code>.</td>
</tr>
<tr>
<td><strong>FR-16 — AI Performance</strong><br>The system shall provide a screen showing how well the AI has been performing. It shall display, for the whole system and for each camera, how many incidents were detected, how many turned out to be real, and the AI's average confidence, so that problem cameras and conditions can be identified and the model improved.</td>
<td><code>backend/app/api/routes/analytics.py:673</code>; <code>frontend/src/pages/AiPerformance.tsx:46</code></td>
<td><code>TC-UNIT-048/049</code> and <code>TC-SYS-016</code>: Pass. UAT maps <code>AD-J02</code>; the role-restricted performance view and export were checked.</td>
</tr>
<tr>
<td><strong>FR-17 — Accident Analytics and Visualization</strong><br>The system shall provide a dashboard that summarizes past accident data. It shall display overall figures for the number of accidents and their clearance status, together with charts showing when and where accidents occur, and shall allow the user to filter and sort what is shown.</td>
<td><code>backend/app/api/routes/analytics.py:266</code>; <code>frontend/src/pages/Dashboard.tsx:80</code></td>
<td><code>TC-UNIT-050/051</code>, <code>TC-INT-017</code>, and <code>TC-SYS-017</code>: Pass. UAT maps <code>OP-J09</code>.</td>
</tr>
<tr>
<td><strong>FR-18 — Report Generation and Data Export</strong><br>The system shall allow users to export incident records, summary figures, and shall allow Administrators to export AI performance data as files in common formats such as CSV and PDF, for sharing with other agencies, for official record-keeping, and for improving the AI model.</td>
<td><code>backend/app/api/routes/analytics.py:341</code>; <code>backend/app/api/routes/exports.py:54</code>; <code>backend/app/services/reports/jobs.py:616</code></td>
<td><code>TC-UNIT-052</code>, <code>TC-SEC-012/013</code>, and <code>TC-SYS-016/017</code>: Pass. UAT maps <code>OP-J09</code> and <code>AD-J02</code>.</td>
</tr>
<tr>
<td><strong>FR-19 — Help Center</strong><br>The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident handling, general dashboard navigation guides, and frequently asked questions (FAQs).</td>
<td><code>backend/app/api/routes/help.py:18</code>; <code>backend/app/services/help.py:194</code>; <code>frontend/src/pages/HelpCenter.tsx:39</code></td>
<td><code>TC-UNIT-053–056</code> and <code>TC-SYS-018</code>: Pass. UAT maps <code>OP-J09</code> and <code>AD-J04</code>; the tracker checked role filtering, search, and article display.</td>
</tr>
<tr>
<td><strong>FR-20 — Activity Audit Trail</strong><br>The system shall maintain an activity audit trail for critical user actions that affect incident verification, camera availability, official reporting, and account management. For Operators, the system shall record accident confirmation, dismissal, clearance, terminal dismissal correction, camera addition, camera editing, camera enabling or disabling, camera removal, report generation, and incident record export. For Administrators, the system shall record user account creation, account editing, account disabling or restoration, role changes, and password updates. The system shall also record successful and failed login attempts for both user roles. Each audit record must include the user ID, role, action performed, affected record, timestamp, and action result.</td>
<td><code>backend/app/services/audit.py:51</code>; <code>backend/app/api/routes/audit.py:143</code>; <code>backend/app/models/audit.py:49</code></td>
<td><code>TC-UNIT-057</code>, <code>TC-SYS-019/020</code>, and <code>TC-BR-002</code>: Pass. UAT maps <code>AD-J06</code>; the tracker inspected both audit coverage and backup/restore attribution.</td>
</tr>
</tbody>
</table>

### Performance NFRs — paper Table 3

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-01 — Algorithmic Accuracy</strong><br>The AI inference engine shall maintain a minimum Mean Average Precision (mAP) of 85% and an Intersection over Union (IoU) threshold of ≥ 0.50 for detecting vehicle-to-vehicle collisions in real-world environmental conditions.</td>
<td><code>ai_engine/detector.py:162</code>; <code>ai_engine/detector.py:188</code>; <code>ai_engine/config.py:111</code></td>
<td><code>AI-VAL-001</code>: Pass; accident mAP@0.50 = 0.956 at epoch 50, retained as a qualified validation-split result because the original split was unavailable for rerun and frame-level incident leakage is disclosed. <code>AI-VAL-002</code>: Pass; event recall 8/16 overall, 8/10 standard, 0/6 hard. These are distinct measures.</td>
</tr>
<tr>
<td><strong>NFR-02 — Inference Latency</strong><br>The system shall finish analyzing video frames and marking any detected collision within 100 milliseconds per frame.</td>
<td><code>ai_engine/pipeline.py:193</code>; <code>ai_engine/pipeline.py:197</code></td>
<td><code>TC-PERF-001</code>: Pass on the tested TensorRT demonstration configuration; the tracker records the measured samples within the 100 ms per-frame criterion.</td>
</tr>
<tr>
<td><strong>NFR-03 — Frame Rate Maintenance</strong><br>The system shall analyze each connected camera feed at a minimum of 5 to 15 frames per second which is enough to catch collisions as they happen without overloading the server.</td>
<td><code>ai_engine/config.py:124</code>; <code>ai_engine/config.py:126</code>; <code>ai_engine/pipeline.py:95</code></td>
<td><code>TC-PERF-002</code>: Pass; 15-minute run with eight MediaMTX channels and 61 authenticated health samples, all in the configured 5–15 FPS band. Cadence-sensitivity evidence in <code>AI-VAL-009</code> is archival.</td>
</tr>
<tr>
<td><strong>NFR-04 — Alert Response Time</strong><br>The system shall display the alert and its captured image on the dashboard, and sound the alarm, within 2 seconds of the AI detecting a collision.</td>
<td><code>backend/app/api/routes/internal.py:93</code>; <code>backend/app/api/routes/internal.py:132</code>; <code>frontend/src/hooks/useAdasWebSocket.ts:30</code></td>
<td><code>TC-PERF-003/004</code>: Pass. In the controlled browser run, 30 injected detections rendered in a mean 668.2 ms, p95 887 ms, maximum 1,395 ms; all 30 were below 2 seconds. Multi-client delivery was also checked.</td>
</tr>
<tr>
<td><strong>NFR-05 — Telemetry Refresh Rate</strong><br>The system shall refresh the live system health figures every 5 seconds. Detailed readings shall be stored every 5 minutes and kept for 48 hours, and hourly summaries shall be kept for 30 days, so that long-term trends remain available without the stored data growing without limit.</td>
<td><code>backend/app/core/config.py:98</code>; <code>backend/app/core/monitor.py:153</code>; <code>frontend/src/pages/SystemHealth.tsx:529</code></td>
<td><code>TC-UNIT-058/059</code>, <code>TC-INT-018</code>, and <code>TC-SYS-015</code>: Pass. Tracker verified roll-up arithmetic, raw/hourly pruning boundaries, and live/history refresh behavior.</td>
</tr>
<tr>
<td><strong>NFR-06 — Report Generation Speed &amp; Export Scalability</strong><br>The system shall begin downloading a standard 30-day report within 5 seconds. For larger requests, above 10,000 rows for PDF or 50,000 rows for CSV, the system shall prepare the file in the background while showing the user its progress, keep the finished file available for 72 hours, and resume the task if it is interrupted.</td>
<td><code>backend/app/api/routes/exports.py:54</code>; <code>backend/app/services/reports/jobs.py:616</code>; <code>backend/app/services/reports/jobs.py:744</code></td>
<td><code>TC-UNIT-060/061</code>, <code>TC-PERF-005/006</code>: Pass; the 300-row 30-day export completed in 0.190 s for CSV and 2.104 s for PDF; a 600,006-row CSV used the background path. <code>TC-REL-003</code> passed under accelerated export-restart simulation.</td>
</tr>
</tbody>
</table>

### Scalability NFRs — paper Table 4

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-07 — Hardware Scalability</strong><br>The system shall be able to handle more cameras at the same time by upgrading the server hardware, without any change to the system's program code.</td>
<td><code>ai_engine/pipeline.py:84</code>; <code>ai_engine/pipeline.py:95</code>; <code>ai_engine/supervisor.py:151</code></td>
<td><code>TC-PERF-007–010</code>: Pass at the tested prototype scale. The tracker records eight concurrent 2K streams, a nine-stream simulation, and a duration deviation for the combined run; it does not establish a 15-camera qualification.</td>
</tr>
<tr>
<td><strong>NFR-08 — Database Performance</strong><br>The system’s database shall remain responsive with up to 100,000 stored incident records and monitoring data points, with dashboard screens loading within 3 seconds.</td>
<td><code>backend/app/models/detection.py:39</code>; <code>backend/app/models/detection.py:40</code>; <code>backend/app/api/routes/alerts.py:213</code></td>
<td><code>TC-PERF-011</code>: Pass; filtered incident queries were exercised at 100,000 rows and later 600,006 rows. The combined filtered first-page query took 1.28–1.41 seconds across three trials.</td>
</tr>
</tbody>
</table>

### Usability NFRs — paper Table 5

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-09 — Operational Efficiency (Collision-to-Operator Decision)</strong><br>The system shall reduce the notification gap by enabling the CDRRMO to receive an accident alert, verify the event through available CCTV/DSS evidence, and record a Confirm or Dismiss decision within 25 seconds of the accident first becoming visible in the monitored camera feed. This shortened time to verified awareness is intended to support faster initiation of the CDRRMO’s manual dispatch or endorsement procedures.</td>
<td><code>ai_engine/pipeline.py:84</code>; <code>backend/app/api/routes/internal.py:132</code>; <code>frontend/src/components/GlobalAlerts.tsx:401</code></td>
<td>UAT <code>OP-J05</code> records raw alert-to-decision times of 16, 9, and 15 seconds, then adds the instructed approximately 3-second accumulation and 2-second propagation allowance. <code>Usability Results</code> records an estimated mean of 18.33 seconds and worst case 21.0 seconds: within the 25-second target. This is a reconstructed estimate from simulated UAT, not a direct first-visible-frame measurement.</td>
</tr>
<tr>
<td><strong>NFR-10 — Workflow Efficiency</strong><br>The web dashboard shall enable users to verify an incident and select either "Confirm" or "Dismiss" in one click.</td>
<td><code>frontend/src/components/GlobalAlerts.tsx:401</code>; <code>frontend/src/components/GlobalAlerts.tsx:408</code></td>
<td><code>TC-SYS-009</code>: Pass; the alert dialog's control inventory showed Confirm and Dismiss reachable in one action. **Traceability gap:** the UAT Traceability sheet has no NFR-10 row. The separate System E2E case directly names NFR-10 and records the one-action result.</td>
</tr>
<tr>
<td><strong>NFR-11 — Alert Distinctiveness</strong><br>The system shall generate an audible notification for new incidents that is clearly distinguishable from ambient noise in a standard emergency command center.</td>
<td><code>frontend/src/utils/detectionSound.ts:34</code>; <code>frontend/src/components/GlobalAlerts.tsx:48</code>; <code>frontend/src/pages/profile/AlarmSettingsCard.tsx:106</code></td>
<td><code>TC-UNIT-062</code> and <code>TC-SYS-007</code>: Pass; distinct sound assets were checked and the selected tone/volume was used by the next alert. UAT maps <code>OP-J02</code> and <code>OP-J04</code>; the tracker records participant observation, not a calibrated ambient-noise measurement.</td>
</tr>
<tr>
<td><strong>NFR-12 — Learnability</strong><br>The dashboard user interface shall be sufficiently intuitive to allow a new operator with basic computer literacy to learn to process and verify an alert within a 15-minute training session.</td>
<td><code>frontend/src/pages/HelpCenter.tsx:39</code>; <code>backend/app/services/help.py:283</code>; <code>frontend/src/components/GlobalAlerts.tsx:408</code></td>
<td>UAT maps <code>OP-J05</code> and Session Control. <code>Usability Results</code> records four first-time users assessed and four meeting learnability; each recorded five minutes. The associated UAT stages passed.</td>
</tr>
</tbody>
</table>

### Reliability NFRs — paper Table 6

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-13 — System Availability</strong><br>The system, including the AI engine and web dashboard shall maintain 99.9% uptime, excluding planned maintenance.</td>
<td><code>backend/app/api/routes/system.py:14</code>; <code>backend/app/api/routes/system.py:20</code>; <code>scripts/register-maintenance-task.ps1:68</code></td>
<td><code>TC-REL-004</code>: Pass; availability during the actively monitored, non-maintenance window was recorded as effectively 100%, with no unplanned outage. The endurance and thermal cases carry accelerated or duration-deviation qualifications; this is not a year-long uptime record.</td>
</tr>
<tr>
<td><strong>NFR-14 — Network Fault Tolerance</strong><br>If a camera stream disconnects due to network instability or power loss, the system shall automatically attempt to reconnect to the feed every 10 seconds.</td>
<td><code>ai_engine/config.py:37</code>; <code>ai_engine/camera.py:165</code>; <code>ai_engine/camera.py:183</code></td>
<td><code>TC-REL-007–010</code>: Pass under injected, accelerated, restart, and partition simulations. The tracker verifies the 10-second retry interval and recovery behavior.</td>
</tr>
<tr>
<td><strong>NFR-15 — Process Isolation</strong><br>If detection on one camera fails, freezes, or is stopped, the problem shall be confined to that camera and shall not affect the server, the dashboard, or detection on any other camera.</td>
<td><code>ai_engine/pipeline.py:152</code>; <code>ai_engine/supervisor.py:172</code></td>
<td><code>TC-REL-011</code>: Pass under fatal-inference fault simulation; the failed camera was excluded while healthy cameras continued. <code>TC-PERF-015</code>: Pass with duration deviation during the combined load run.</td>
</tr>
<tr>
<td><strong>NFR-16 — Daily System Restart</strong><br>The system shall restart itself once every 24 hours at a configurable quiet hour, such as 3:00 AM, and shall be fully back in service within 10 seconds, so that performance does not degrade over long periods of continuous operation.</td>
<td><code>scripts/register-maintenance-task.ps1:68</code>; <code>scripts/adas-maintenance.ps1:263</code>; <code>backend/app/api/routes/system.py:20</code></td>
<td><code>TC-REL-012</code>: Pass in the tracker. Its actual-result note separates recovery points: backend readiness at 5.11 seconds, fresh AI heartbeat at 12.672 seconds, and all 10 enabled cameras Connected/Active after the reconnect window. Report those values together.</td>
</tr>
<tr>
<td><strong>NFR-17 — Asynchronous Alert Recovery</strong><br>Whenever the dashboard is opened or reconnects after a network interruption, it shall immediately retrieve and display all incidents that are still Unverified, so that no pending emergency is lost from view.</td>
<td><code>backend/app/api/routes/alerts.py:222</code>; <code>frontend/src/components/RealtimeAlertsBridge.tsx:246</code>; <code>frontend/src/hooks/useAdasWebSocket.ts:30</code></td>
<td><code>TC-UNIT-063/064</code>, <code>TC-INT-019</code>, and <code>TC-REL-013/014</code>: Pass; restart and reconnect evidence is simulated or browser-lifecycle based. UAT maps <code>OP-J08</code>.</td>
</tr>
<tr>
<td><strong>NFR-18 — Data Redundancy &amp; Recovery</strong><br>The system shall back up its data automatically every day without interrupting detection. An Administrator shall be able to restore the system from a backup and have alerts working again within 60 seconds.</td>
<td><code>backend/app/services/maintenance_schedule.py:231</code>; <code>backend/app/api/routes/maintenance.py:192</code>; <code>backend/app/api/routes/maintenance.py:238</code></td>
<td><code>TC-BR-001–016</code>: Pass. The tracker includes a live scheduled backup while detections continued and a successful restore whose fresh alert appeared 57.04 seconds after the restore request. UAT maps <code>AD-J04</code> and <code>AD-J05</code>.</td>
</tr>
</tbody>
</table>

### Security NFRs — paper Table 7

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-19 — Session Security</strong><br>A user's login session shall last no longer than 8 hours and shall be protected so that it cannot be read or reused by anything other than the user's own browser session. The system shall be able to end a session immediately when the user logs out, when their password is changed, or when an Administrator revokes their access.</td>
<td><code>backend/app/services/sessions.py:14</code>; <code>backend/app/services/sessions.py:52</code>; <code>backend/app/core/security.py:69</code></td>
<td><code>TC-UNIT-065</code>, <code>TC-SEC-016–024</code>, and <code>TC-SYS-021</code>: Pass. Tracker verified the 8-hour lifetime, protected cookie, logout revocation, password-change revocation, administrator revocation, and WebSocket closure after logout.</td>
</tr>
<tr>
<td><strong>NFR-20 — Data Localization</strong><br>To ensure data privacy and compliance with government security standards, all data shall be stored and processed exclusively on the edge server's physical drives and shall not be transmitted to external cloud services.</td>
<td><code>backend/app/core/config.py:52</code>; <code>backend/app/core/config.py:160</code>; <code>backend/app/core/config.py:60</code></td>
<td><code>TC-SEC-014/017/018/025</code>: Pass. The controlled network run observed only loopback process connections; the tracker explicitly says full packet capture across every workflow and backup activity was outside that run's scope.</td>
</tr>
<tr>
<td><strong>NFR-21 — Audit Trail Integrity</strong><br>Every action that changes system data shall be recorded at the same time as the change itself, so that no action can go unrecorded. Failed or unauthorized attempts shall also be recorded, with sensitive values hidden. No user, including an Administrator, shall be able to edit or delete these records.</td>
<td><code>backend/app/services/audit.py:51</code>; <code>backend/app/models/audit.py:49</code>; <code>backend/app/api/routes/audit.py:143</code></td>
<td><code>TC-UNIT-066/067</code>, <code>TC-INT-021/022</code>, <code>TC-SEC-026/027</code>, and <code>TC-SYS-020</code>: Pass. Tracker checked same-transaction rollback, hidden sensitive values, denied/failure entries, and absence of edit/delete interfaces.</td>
</tr>
</tbody>
</table>

### Maintainability NFR — paper Table 8

<table>
<thead>
<tr>
<th>Requirement and paper text</th>
<th>Implemented in code</th>
<th>Verification and recorded tracker result</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>NFR-22 — Modular AI Upgrades</strong><br>Developers shall be able to update or replace the AI model without having to change the dashboard or the rest of the system.</td>
<td><code>ai_engine/config.py:63</code>; <code>ai_engine/config.py:85</code>; <code>ai_engine/detector.py:162</code></td>
<td><code>TC-UNIT-068</code>: Pass; a missing configured model fails closed. <code>TC-INT-023</code>: Pass as a qualified artifact-level check; a compatible ONNX replacement loaded through the existing integration boundary without source changes.</td>
</tr>
</tbody>
</table>

## 4. Why it was built this way

The paper says the requirements came from an initial interview with the Lipa CDRRMO operations and warning division, internal brainstorming, and follow-up interviews to clarify functions and align scope with emergency-response procedures (Chapter 3, Requirements Analysis). That is why the set pairs operator workflow requirements with measurable conditions for AI, reliability, and security.

Human verification is central: the AI raises an Unverified incident with its evidence, then the operator determines whether it is a true accident. The tracker tests each part of that path at the appropriate layer: unit tests for validators and state changes, integration and E2E cases for data crossing component boundaries, and UAT journeys for role-specific work.

Quantitative claims use separate evidence paths. For example, mAP is reported separately from event recall; alert-to-decision UAT timing is separated from the detector and propagation allowance; and server readiness, AI heartbeat, and camera reconnection are recorded as distinct restart observations. Those distinctions keep the spoken answer faithful to the measured result.

## 5. What changed since the 28 April defense

The current paper provides a finalized requirement set in Chapter 3, Tables 2–8, but the paper and test tracker do not mark any one of the 42 FR/NFR items as newly added after the earlier defense. Do not guess an ID when asked which was added late.

The current **NFR-09** is an end-to-end collision-visible-to-operator-decision target of 25 seconds. Its tracker method records alert-appearance-to-decision time and adds the stated approximately 3-second detector-accumulation and 2-second alert-propagation allowance when deriving the estimate.

The test tracker separately records a new UAT acceptance criterion, **AC-UAT**. It uses all 33 planned participant-stage executions in the denominator so an incomplete stage cannot be omitted from the acceptance calculation. AC-UAT is a tracker-level acceptance rule, not an FR or NFR in the paper.

## 6. Limits and honest caveats

- **NFR-01 is the clearest accuracy limitation.** The tracker marks the qualified mAP case Pass at 0.956, but event-level recall on the local labelled clips is 8/16 overall and 0/6 on hard clips. State both measures and do not present mAP as a claim that 95.6% of real collisions are detected.
- **NFR-09 is reconstructed.** The tracker adds the 3-second and 2-second allowances to observed alert-to-decision intervals. The UAT stream was simulated, and live CCTV review was not scored in that participant exercise.
- **NFR-10 has a traceability gap.** The UAT Traceability sheet has no NFR-10 row. The separate System E2E case TC-SYS-009 names NFR-10 and records Pass for Confirm and Dismiss being reachable in one action; cite that case and acknowledge the missing trace row.
- **NFR-13 is an observation-window result.** TC-REL-004 records effectively 100% availability while the stack was actively monitored, excluding planned/non-active windows. The tracker also labels the endurance and thermal cases accelerated or duration-deviation results.
- **NFR-16 records separate recovery points.** TC-REL-012 is marked Pass; its note says the backend was ready at 5.11 seconds, the fresh AI heartbeat arrived at 12.672 seconds, and all 10 enabled cameras were active after the reconnect window. Do not compress these into a single unqualified under-10-second statement.
- **NFR-20 has a scoped network observation.** The controlled test saw loopback process connections. Full packet capture across all workflows and backup activity was outside its scope.
- **NFR-07 is qualified to tested scale.** The tracker records eight concurrent streams and a nine-stream simulation, not a 15-camera qualification.
- **FR-04 uses simulated VMS feeds in the tracker.** The evidence verifies RTSP ingestion through MediaMTX; it does not say that the current test ran on the agency’s production CCTV network.

## 7. Likely panel questions

**“Show me a requirement you only partly met.”**

NFR-16 is marked Pass in the tracker, but its restart note reports backend readiness at 5.11 seconds and a fresh AI heartbeat at 12.672 seconds. We would present both measurements and say the tracker verified restart and camera recovery, while the recorded full-stack timing is qualified against the 10-second wording.

**“Which requirement was added late, and why?”**

The current paper and tracker do not identify any FR/NFR as a late addition, so I would not guess an ID. The tracker does identify AC-UAT as a new acceptance rule: all 33 planned participant-stage executions count, which prevents an incomplete stage from being dropped from the denominator.

**“How do you know FR-10 actually works?”**

TC-UNIT-029 through TC-UNIT-031 are marked Pass for dismissal, status recording, and the one-minute cooldown. TC-INT-006 is also Pass for propagating that cooldown to the AI engine, and UAT maps FR-10 to OP-J06.

**“Which requirement was hardest?”**

NFR-01 is the hardest to defend because frame-level mAP and operational event recall answer different questions. The tracker reports a qualified mAP of 0.956, while event-level recall is 8/16 overall and 0/6 on hard clips; those hard cases are the clearest limitation.

**“Does 95.6% mAP mean you detect 95.6% of accidents?”**

No. The 0.956 figure is mAP@0.50 on a recorded validation split and is qualified because the original split could not be rerun and frame-level incident leakage is disclosed. The local event-level run reports 8 of 16 labelled crashes detected, including none of the six hard clips.

**“Was FR-04 tested on actual CDRRMO cameras?”**

The tracker verifies a live RTSP stream from the MediaMTX VMS simulator, and the UAT footage was simulated. That proves the stream-ingestion path under the tested setup; it is not evidence of a production CDRRMO CCTV installation.

**“How did you get the 25-second NFR-09 result?”**

UAT timed from the alert appearing on the dashboard to the participant’s Confirm decision, then added about 3 seconds for detector accumulation and 2 seconds for alert propagation. The recorded estimated mean is 18.33 seconds and the worst case is 21 seconds, within the 25-second target; it is a reconstructed estimate.

**“NFR-10 is missing from your traceability sheet. How do you know it works?”**

That is a real traceability gap. TC-SYS-009 separately names NFR-10 and passes: the alert dialog exposes Confirm and Dismiss as one-action choices without intermediate navigation.

**“Have you proven 99.9% uptime?”**

The tracker records effectively 100% availability in its actively monitored, non-maintenance observation window and no unplanned outage in that window. Its accelerated endurance and shorter thermal runs are qualified evidence, not a year-long availability measurement.

**“Did the daily restart bring every component back within 10 seconds?”**

The tracker’s Pass entry reports backend readiness at 5.11 seconds and a fresh AI heartbeat at 12.672 seconds, followed by all 10 enabled cameras returning Connected/Active after the reconnect window. We should report those separate timings rather than claim every component was back under 10 seconds.

## 8. Cram summary

- The paper is authoritative for requirement text: Chapter 3, Tables 2–8 contain 20 FRs and 22 NFRs.
- The tracker records 194/194 technical cases and 33/33 UAT participant stages as Pass.
- Functional flow: RTSP ingest → accumulated AI evidence → snapshot and Unverified record → dashboard alert → operator Confirm/Dismiss → lifecycle log and audit.
- Strongly qualify AI accuracy: mAP@0.50 = 0.956 is a validation-split result; event recall is 8/16 overall and 0/6 hard.
- NFR-09's estimated mean/worst are 18.33/21 seconds, derived from UAT timing plus the 3+2 second allowance.
- NFR-10's UAT Traceability row is missing; TC-SYS-009 independently passes the one-action decision path.
- State simulation, acceleration, archival results, and duration deviations whenever the tracker records them.
