# 18 — Diagrams: Swimlane, DFD, ERD, and Client–Server

> **One-liner:** The paper’s diagrams show the same ADAS system at different levels: responsibility, user capability, data movement, persistence, and deployment.
> **Panel risk:** high — a panelist can point to any box or arrow and ask whether it is a person, a process, a store, a transport, or an implemented feature.

## 1. What it is

ADAS has six diagram views in this topic.

| View                       | Paper figure | What the view answers                                                                           |
| -------------------------- | ------------ | ----------------------------------------------------------------------------------------------- |
| Client–server architecture | Figure 2     | Where the cameras, server components, database, browser, and user sit, and how they communicate |
| Swimlane                   | Figure 3     | Who performs each step in the accident and administration workflow                              |
| Use case                   | Figure 4     | Which capabilities each actor can request, including included and extended behavior             |
| Context DFD                | Figure 5     | What crosses the ADAS system boundary                                                           |
| Level 1 DFD                | Figure 6     | Which logical processes, stores, and flows make up ADAS                                         |
| ERD                        | Figure 7     | Which durable entities exist and how their foreign-key relationships represent the workflow     |

These are complementary views, not six competing architectures.
The client–server diagram is the deployment and communication view.
The swimlane is the responsibility view.
The use case is the capability view.
The two DFDs are the information-flow view.
The ERD is the persistence view.
The quickest way to orient yourself is to keep three questions separate:

1. **Who acts?** An actor or lane owner is a person or external system.
2. **What does the system do?** A process or use case is work performed by ADAS.
3. **Where is information kept?** A DFD data store or ERD entity is durable or logically grouped data.
   The diagrams use different shapes for those purposes.
   An arrow is a relationship or flow, not automatically an HTTP request.
   For example, the DFD arrow labelled “incident event” is a logical data flow. In code, the event travels from the AI engine through an authenticated HTTP POST, is committed by the backend, and is then broadcast to browsers over WebSocket.
   The paper’s central operational story is:
4. CCTV/VMS supplies a live camera stream.
5. The AI engine analyzes frames and forms an incident event.
6. The backend stores the event and pauses the affected camera’s desired AI state.
7. The frontend receives a live alert.
8. The Operator confirms, dismisses, snoozes, monitors, or clears it.
9. The backend stores the decision and broadcasts the resulting state.
   The Administrator owns restricted account, audit, analytics, and database-maintenance capabilities.
   Final incident verification remains a human decision in the paper’s Human-in-the-Loop framing.

## 2. Where it lives

### In the paper

All six views are in Chapter 3, **System Architecture and Design**.

- Figure 2, **Client-Server Architecture**, is on rendered paper p. 101; Figure 3, **Swimlane Diagram**, is on rendered paper p. 105.
- Figure 4, **Use Case Diagram**, is on rendered paper p. 107; Figure 5, **Context Level DFD**, is on rendered paper p. 112.
- Figure 6, **Level 1 DFD**, is on rendered paper p. 113; Figure 7, **Entity-Relationship Diagram of the Database Architecture**, is on rendered paper p. 117.
  The explanatory paragraphs for these figures run through pp. 100–118.
  The paper describes the system architecture around three software components:
- The AI Engine receives configured RTSP streams, selects the latest frames, invokes YOLO, forms temporal events, captures evidence, and sends events and heartbeats; The Backend runs FastAPI and Uvicorn, owns business rules and database transactions, enforces role checks, and broadcasts live events.
- The Frontend is a React single-page application in the command-center browser.
  The same section identifies SQLite as the relational database on the edge server.
  For the use-case actor wording, use the paper’s terms **Operator/Dispatcher**, **Administrator**, and **CCTV/VMS**.
  For the DFD, use the current paper’s seven logical processes and seven logical data stores.
  For the ERD, use the paper’s ten persistent entities grouped into four domains:
- Core Detection Operations: camera and detection_log; Security and Identity Management: user, auth_session, and alarm_settings.
- System Governance and Async Jobs: audit_log and export_job; Independent Documentation and Telemetry: help_article, sys_health_raw, and sys_health_hourly.
  The paper’s current diagram text is the authority for the labels and conceptual relationships below.

### In the code

The code crosswalk is grouped by the diagram view.
**Client–server and AI-engine side**

- ai_engine/main.py:33–85 wires model loading, the inference pipeline, event handling, and the delivery worker; ai_engine/camera.py:157–245 opens RTSP with OpenCV/FFmpeg, reconnects, and publishes the newest frame.
- ai_engine/pipeline.py:111–147 collects current frames and runs batched inference; ai_engine/pipeline.py:184–225 updates temporal evidence, pauses a camera, and calls the event handler.
- ai_engine/accident.py:46–92 draws the evidence box, writes the snapshot, and queues the event payload; ai_engine/backend_client.py:40–70 sends the heartbeat and reads the authoritative camera snapshot.
- ai_engine/backend_client.py:73–95 sends the alert and classifies HTTP outcomes; ai_engine/outbox.py:58–74 atomically writes pending event files.
- ai_engine/outbox.py:169–219 acknowledges, quarantines, retries, and drains events.
  **Backend seams and browser push**
- backend/app/api/routes/internal.py:30–34 protects the two AI routes with the internal API key; backend/app/api/routes/internal.py:93–136 ingests events and broadcasts after commit.
- backend/app/api/routes/internal.py:139–213 applies heartbeat observations and returns desired camera state; backend/app/main.py:442–529 authenticates /ws/alerts and manages its lifecycle.
- backend/app/services/realtime.py:51–197 owns connection indexes, bounded queues, broadcasts, and sender tasks; backend/app/services/events.py:29–110 builds typed incident and camera event envelopes.
- frontend/src/hooks/useAdasWebSocket.ts:52–130 opens the browser socket and retries recoverable disconnects; frontend/src/components/RealtimeAlertsBridge.tsx:101–139 applies incident, camera, snooze, maintenance, and connection events.
- frontend/src/components/RealtimeAlertsBridge.tsx:235–317 recovers active data after a connection is ready and deduplicates envelopes.
  **Incident and camera workflow**
- backend/app/services/incidents.py:34–42 declares the four legal status transitions; backend/app/services/incidents.py:124–226 inserts an incident, enforces idempotency, and pauses the camera.
- backend/app/services/incidents.py:229–311 performs the conditional transition guard; backend/app/api/routes/alerts.py:222–456 lists incidents, exports them, reads details, and serves snapshots.
- backend/app/api/routes/alerts.py:464–514 confirms an alert; backend/app/api/routes/alerts.py:517–599 dismisses or corrects an alert and applies cooldown behavior.
- backend/app/api/routes/alerts.py:602–662 clears an ongoing incident and resumes the camera; backend/app/api/routes/alerts.py:665–706 snoozes an unverified incident.
- backend/app/services/cameras.py:240–340 derives desired camera state; backend/app/api/routes/cameras.py:151–468 lists, creates, edits, enables, deactivates, and restores cameras.
  **Identity, roles, and use-case capabilities**
- backend/app/api/routes/auth.py:39–138 implements login and logout; backend/app/services/sessions.py:14–105 creates, validates, revokes, and expires server-side sessions.
- backend/app/api/dependencies.py:104–152 authenticates users and supplies the Administrator dependency; backend/app/api/routes/users.py:83–169 implements profile and password changes.
- backend/app/api/routes/users.py:202–561 implements the Administrator user directory and account actions; backend/app/api/routes/settings.py:31–112 reads and updates alarm preferences.
- backend/app/api/routes/analytics.py:266–826 provides dashboard and AI-performance analytics and exports; backend/app/api/routes/exports.py:54–238 creates, lists, downloads, and queues asynchronous exports.
- backend/app/api/routes/audit.py:143–429 lists and exports audit records; backend/app/api/routes/help.py:18–56 serves role-filtered help articles.
- backend/app/api/routes/system_health.py:208–266 serves live and historical health data; backend/app/api/routes/maintenance.py:158–738 serves backup, restore, and maintenance status operations.
  **ERD entities**
- backend/app/models/camera.py:28–107 defines camera state and its detection relationship; backend/app/models/detection.py:21–98 defines detection_log, foreign keys, status checks, and open-incident indexes.
- backend/app/models/user.py:30–78 defines user and its incident and preference relationships; backend/app/models/user.py:81–106 defines auth_session.
- backend/app/models/user.py:108–138 defines alarm_settings; backend/app/models/audit.py:49–117 defines audit_log and append-only triggers.
- backend/app/models/export.py:9–45 defines export_job; backend/app/models/health.py:20–91 defines sys_health_raw and sys_health_hourly.
- backend/app/models/help.py:12–95 defines help_article and the FTS5 synchronization triggers; backend/app/core/db.py:18–34 enables foreign keys, WAL, full synchronous mode, and the busy timeout for SQLite.

## 3. How it works

### Figure 2 — client–server architecture

Read the figure from left to right.
**IP Camera Network**

- IP Camera 1, IP Camera 2, and IP Camera 3 are representative physical camera sources; Each camera sends an RTSP stream to the Network Switch.
- The Network Switch carries the video packets to the NVR and the VMS/Media Gateway; The NVR is the video-recording side of the external camera infrastructure.
- The VMS/Media Gateway is the software-facing stream source that exposes the configured RTSP feeds to ADAS; The RTSPs arrow from the VMS/Media Gateway to the edge server means the AI engine consumes the streams. It does not mean the operator browser consumes raw RTSP.
  **Edge Inference Server**
- **AI Engine (YOLO/OpenCV)** receives the RTSP stream, chooses current frames, preprocesses them, and runs the detector; **Backend (FastAPI)** receives alert and heartbeat HTTP calls, applies domain rules, writes the database, and serves REST routes.
- **Database (SQLite)** is the backend’s local durable store. The backend reads and writes it directly; The engine-to-backend arrow labelled **Idempotent Alert Ingestion (HTTP POST)** is POST /api/internal/alert.
- The engine-to-backend arrow labelled **Telemetry & State Sync (HTTP POST/Response)** is POST /api/internal/heartbeat. The request carries observed metrics; the response carries authoritative desired camera state; The Backend and Database arrow is bidirectional because routes read current records and commit changes.
  **Client**
- The User is the human at the command-center workstation; The Frontend (React) is the browser application.
- The WebSocket arrow from the server toward the Frontend carries push alerts and other typed events; The HTTPS REST API arrow between Frontend and Backend carries page reads and user commands in both directions.
- The user never needs direct access to the database or the raw camera stream for normal operation.
  **Code trace for Figure 2**

1. RTSP connection and newest-frame publication are in ai_engine/camera.py:157–245.
2. Batched YOLO work is in ai_engine/pipeline.py:111–207 and ai_engine/detector.py:167–208.
3. Snapshot and event creation are in ai_engine/accident.py:46–92.
4. HTTP transport and status classification are in ai_engine/backend_client.py:40–95.
5. Backend ingestion and heartbeat are in backend/app/api/routes/internal.py:93–213.
6. The browser REST methods for incident actions are in frontend/src/api/alerts.ts:140–207.
7. The WebSocket handshake is in backend/app/main.py:442–505; browser delivery is in frontend/src/hooks/useAdasWebSocket.ts:52–114 and frontend/src/components/RealtimeAlertsBridge.tsx:292–344.

### Figure 3 — swimlane diagram

The three lanes are **System**, **Operator**, and **Administrator**.
The lane answers “who owns this action?” rather than “which process or table implements it?”
**System lane: detection and evidence**

1. The System receives live CCTV/VMS streams and analyzes frames with the YOLO accident model.
2. It detects a possible vehicle collision.
3. It captures the incident snapshot and metadata.
4. It creates an Unverified incident record.
5. It sends a real-time dashboard alert to the Operator.
   The implementation is the AI pipeline and the internal alert route: ai_engine/pipeline.py:184–225, ai_engine/accident.py:46–92, and backend/app/api/routes/internal.py:93–136.
   **Operator lane: Human-in-the-Loop decision**
6. The Operator reviews the alert, snapshot, and bounding box.
7. The diamond asks **Confirm or Dismiss**.
8. The Operator can snooze the audible alarm while evaluating the evidence.
9. A confirm decision is sent to the backend.
10. A dismiss decision is sent to the backend for a false positive.
    This is where the Operator appears in the swimlane: the Operator owns reviewing, deciding, monitoring, clearing, and reporting. The System performs the database and camera-state effects after the decision.
    The corresponding browser commands are frontend/src/api/alerts.ts:171–207.
    **System lane: decision effects**

- The System validates the Operator session, records the selected action, and updates the incident record; For a confirm path, it changes Unverified to Ongoing. The affected camera is already paused for the open incident.
- The Operator then monitors the ongoing incident; When the scene is clear, the Operator marks the incident as cleared.
- The System changes Ongoing to Cleared, clears incident-linked snooze state, and resumes the affected camera’s AI state; For a dismiss path from Unverified, the System changes the status to Dismissed, applies the cooldown, and later allows detection again.
- For a dismissal correction from Ongoing, the System changes the status to Dismissed and resumes immediately.
  The state effects are in backend/app/services/incidents.py:229–311 and backend/app/api/routes/alerts.py:464–706.
  The camera-state effects are in backend/app/services/cameras.py:240–340.
  **Audit and history**
- The System stores confirmation, dismissal, clearing, historical access, and report-generation actions in the audit trail where the action is state-changing or otherwise covered by the audit catalogue; The Operator searches historical logs and exports reports.
- The audit implementation is backend/app/services/audit.py:63–96; incident transition call sites are backend/app/api/routes/alerts.py:489–660; Incident history and export reads are backend/app/api/routes/alerts.py:222–456 and backend/app/api/routes/exports.py:54–238.
  **Administrator lane**

1. The Administrator logs in with an Administrator role.
2. The System validates Administrator access and exposes the User Management and Audit Trail modules.
3. The Administrator creates, edits, disables, restores, or updates user accounts.
4. The System updates user records and stores account-management actions in the audit trail.
5. The Administrator reviews Operator and Administrator activity records.
6. The System retrieves and displays the audit records.
   The role gate is backend/app/api/dependencies.py:104–152.
   The account actions are backend/app/api/routes/users.py:202–561.
   The audit viewer is backend/app/api/routes/audit.py:143–429.
   The swimlane does not put the Administrator into the day-to-day alert decision diamond.
   The Administrator inherits the Operator capabilities in the paper’s actor model, while the diagram draws the Administrator’s restricted account-management branch separately.

### Figure 4 — use case diagram

The system boundary contains capabilities.
The three actors outside it are:

- **Operator/Dispatcher:** day-to-day monitoring and operational decisions; **Administrator:** the Operator capabilities plus restricted administration and maintenance.
- **CCTV/VMS:** the external source of camera feeds.
  The dotted arrows labelled include mean that the base use case always invokes the included behavior.
  The dotted arrows labelled extend mean that the additional behavior applies only in the extending situation.
  The Figure 4 legend also applies **Record Audit Entry** to state-changing use cases under FR-20, without drawing a separate audit arrow from every oval.
  **Secure access and preferences**
- Log in includes Determine User Role; Determine User Role includes Validate Credentials.
- Failed authentication extends to Display Login Error; Log out includes Revoke Session.
- Edit User Profile and Change Own Password are authenticated self-service capabilities; Configure Alarm Settings writes the user’s alarm preference.
  Code: backend/app/api/routes/auth.py:39–178, backend/app/services/sessions.py:14–105, backend/app/api/routes/users.py:83–169, backend/app/api/routes/settings.py:31–112, and frontend/src/api/auth.ts:34–50.
  **Human-in-the-Loop collision clearance**
- Stream Camera Feed is supplied by CCTV/VMS; Stream Camera Feed feeds Detect Collision.
- Verify Accident Alert includes Detect Collision; Confirm Accident includes Set Ongoing Status.
- Dismiss Accident includes Enforce Cooldown for the false-positive path; Confirm Accident extends to Snooze Audible Alarm when the Operator needs temporary evaluation time.
- Cleared Accident is the terminal operational-clear path after an ongoing incident; Terminal Dismissal is the correction path when an ongoing incident must be dismissed.
  The false-positive path is therefore **Verify Accident Alert → Dismiss Accident → Enforce Cooldown**.
  It is distinct from **Confirm Accident → Set Ongoing Status → Cleared Accident**.
  Code: backend/app/api/routes/alerts.py:464–706, backend/app/services/incidents.py:34–42, and frontend/src/components/GlobalAlerts.tsx:16–19, 181–408.
  **Camera configuration**
- Manage Cameras is the parent capability; It includes Add Camera.
- It includes Edit Camera Config; It includes Enable / Disable Feed.
- It includes Deactivate Camera; It includes Restore Camera.
- It includes View Camera Status.
  Deactivation is soft deactivation, so the camera record and historical incident references remain available for restoration.
  Enabling or disabling a feed is a separate desired-state change and does not remove the camera configuration.
  Code: backend/app/api/routes/cameras.py:151–468 and frontend/src/api/cameras.ts:104–153.
  **Monitoring, analytics, and reports**
- Monitor System Health reads live and historical health information; Analyze Accident Trends reads dashboard aggregations.
- Review Detection Logs reads incident history; Export Reports exports incident or dashboard information.
- Track AI Performance is the Administrator-side performance view; Track AI Performance can export performance information.
- Queue Async Export is the background path for large or heavy report requests.
  Code: backend/app/api/routes/system_health.py:208–266, backend/app/api/routes/analytics.py:266–826, backend/app/api/routes/alerts.py:222–315, backend/app/api/routes/exports.py:54–238, and backend/app/services/reports/jobs.py:583–729.
  **Help Center**
- Access Help Center is available to authenticated users; It retrieves role-filtered article summaries or a selected article.
- The paper’s help data is represented by the Help Knowledge Base in the DFD and help_article in the ERD.
  Code: backend/app/api/routes/help.py:18–56 and backend/app/services/help.py:214–299.
  **Administrator-only capabilities**
- Manage User Accounts includes Add User Account; It includes Edit User Account.
- It includes Deactivate Account; It includes Restore Account.
- It includes Change User Password; Edit User Account includes Prevent Admin Lockout where the final active Administrator must be protected.
- Trigger Database Backup starts a backup; Restore from Backup includes Confirm Identity, Pre-Restore Snapshot, and Verify Integrity.
- Review Audit Log includes Export Audit Records.
  Code: backend/app/api/routes/users.py:202–561, backend/app/api/routes/maintenance.py:158–541, backend/app/maintenance/backup.py:1–180, backend/app/maintenance/restore.py:1–820, and backend/app/api/routes/audit.py:274–429.

### Figure 5 — context-level DFD

The context DFD deliberately compresses all ADAS internals into one process: **ADAS Accident Detection & Alert System**.
It has three external entities.
**CCTV/VMS**

- **Video request:** ADAS asks for the configured stream; **Live camera video:** CCTV/VMS supplies the stream to ADAS.
  In the code, the backend constructs the configured RTSP URL in backend/app/services/cameras.py:44–59, returns it in the heartbeat response at backend/app/api/routes/internal.py:185–201, and the AI engine opens the stream in ai_engine/camera.py:157–190.
  **Operator**
- **Credentials, decisions & queries:** login credentials, alarm preferences, incident decisions, camera configuration, report filters, and operational queries enter ADAS; **Access, alerts & operational information:** access results, real-time alerts, audible-alarm state, analytics, health information, history, and help guidance leave ADAS.
  The main command paths are backend/app/api/routes/auth.py:39–178, backend/app/api/routes/alerts.py:222–706, backend/app/api/routes/cameras.py:151–468, backend/app/api/routes/analytics.py:266–826, backend/app/api/routes/system_health.py:208–266, and backend/app/api/routes/help.py:18–56.
  **Administrator**
- **User, audit & recovery requests:** user-account actions, audit queries/exports, backup requests, restore requests, and performance requests enter ADAS; **User, audit & recovery results:** account results, audit records, export artifacts, backup status, restore status, and performance results leave ADAS.
  The Administrator also receives the Operator capability set; the context drawing highlights only the Administrator-specific exchange.
  The context DFD is not claiming that one Python function performs everything.
  It is a boundary diagram: the internal processes are intentionally hidden at this level.

### Figure 6 — current level 1 DFD

The current levelled DFD decomposes ADAS into seven logical processes and seven logical data stores.

#### Processes

| Label in Figure 6                         | Meaning in the implementation                                                                     |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1.0 Manage Identity, Access & Preferences | Authenticate users, manage sessions, roles, profiles, passwords, and alarm settings               |
| 2.0 Manage Camera Configuration & State   | Maintain camera records, desired state, soft activation, feed enablement, and observed status     |
| 3.0 Analyze Live Video & Detect Incidents | Consume live video, infer collision evidence, form events, and report telemetry                   |
| 4.0 Coordinate Human Incident Response    | Deliver alerts and apply confirm, dismiss, snooze, clear, cooldown, and camera-control decisions  |
| 5.0 Produce Analytics, Reports & Audit    | Query incidents and telemetry, compute analytics, generate reports, and read/write audit activity |
| 6.0 Monitor & Maintain System Reliability | Collect health telemetry, expose health status, and coordinate backup/recovery information        |
| 7.0 Provide Help & Guidance               | Search and serve role-filtered operating guidance                                                 |

Process 1.0 maps to backend/app/api/routes/auth.py, users.py, settings.py, and app/services/sessions.py.
Process 2.0 maps to backend/app/api/routes/cameras.py and app/services/cameras.py.
Process 3.0 maps to ai_engine/main.py, camera.py, pipeline.py, detector.py, accident.py, backend_client.py, and the internal backend route.
Process 4.0 maps to backend/app/api/routes/alerts.py, app/services/incidents.py, app/services/snoozes.py, and app/services/realtime.py.
Process 5.0 maps to backend/app/api/routes/analytics.py, alerts.py, exports.py, audit.py, and app/services/reports/.
Process 6.0 maps to backend/app/api/routes/system.py, system_health.py, maintenance.py, app/core/monitor.py, and app/maintenance/.
Process 7.0 maps to backend/app/api/routes/help.py and app/services/help.py.

#### Data stores

| Store                           | Meaning                                                                                 | Main code entities                                      |
| ------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| D1 Identity & Access Data       | Accounts, sessions, roles, and preferences                                              | User, AuthSession, AlarmSettings                        |
| D2 Camera State                 | Camera configuration and desired/observed status                                        | Camera                                                  |
| D3 Incident & Evidence Data     | Incident lifecycle, confidence, actors, snooze fields, and snapshot key                 | DetectionLog plus snapshot files                        |
| D4 Audit Records                | Append-only accountability records                                                      | AuditLog                                                |
| D5 Health & Performance Data    | Raw and aggregated host and engine telemetry                                            | SysHealthRaw, SysHealthHourly, camera telemetry columns |
| D6 Reports & Recovery Artifacts | Export jobs, generated artifacts, backups, manifests, restore state, and recovery files | ExportJob plus backend maintenance files                |
| D7 Help Knowledge Base          | Role-filtered Markdown operating content and search index                               | HelpArticle plus help_article_fts                       |

The store is logical in the DFD.
For example, D3 contains the incident row in SQLite and the evidence file addressed by snapshot_key; the diagram groups those as one operational data domain.

#### Every external and process flow

- CCTV/VMS sends **Live camera video** to 3.0; 3.0 sends a **Video request** to CCTV/VMS.
- 3.0 sends **Incident event** to 4.0 after temporal event formation; 4.0 sends **Control state** to 3.0 so the engine can pause, resume, or observe cooldown state.
- 3.0 sends **Telemetry** to 6.0 through the heartbeat report; 1.0 exchanges **Credentials & preferences** and **Access/preference result** with the Operator.
- 1.0 exchanges **User administration data** and **User/access result** with the Administrator; 2.0 exchanges **Camera configuration** and **Camera state** with Operator and Administrator.
- 4.0 sends **Alerts/evidence** to the Operator; The Operator sends **Incident decisions** to 4.0.
- 5.0 sends **Dashboards/reports** to the Operator; The Operator sends **Report queries** to 5.0.
- 5.0 exchanges **Audit/report queries** and **Audit reports** with the Administrator; 5.0 reads **Incident data** from D3.
- 5.0 reads **Performance data** from D5; 5.0 exchanges **Audit records** with D4.
- 5.0 writes **Report artifacts** to D6; 6.0 sends **Health status** to the Operator.
- The Operator sends **Health queries** to 6.0; 6.0 exchanges **Maintenance/recovery commands** and **Health/recovery status** with the Administrator.
- 6.0 exchanges **Health/performance data** with D5; 6.0 exchanges **Recovery artifacts** with D6.
- 7.0 exchanges **Help queries** and **Guidance** with the Operator; 7.0 exchanges **Help content** with D7.
- 1.0 reads and writes **Records** in D1; 2.0 reads and writes **State** in D2.
- 3.0 reads and writes **Incident/evidence data** in D3 as the detection event becomes durable.
  The paper calls out the major loops explicitly: CCTV/VMS to and from 3.0; 3.0 to 4.0 as incident events; 4.0 to 3.0 as incident-control state; 3.0 to 6.0 as telemetry; and both 5.0 and 6.0 to D6.
  Store arrows mean logical reads and writes.
  They do not imply that each arrow is a separate table or network connection.

### Figure 7 — entity relationship diagram

The ERD shows ten persistent entities.

#### Security and identity entities

**user**

- Primary key: user_id; Account fields: username, first_name, last_name, password_hash, role, is_active.
- Lifecycle fields: created_at, updated_at, password_changed_at, last_login; Code: backend/app/models/user.py:30–60.
  **auth_session**
- Primary key: session_id; Foreign key: user_id.
- Lifecycle fields: created_at, expires_at, revoked_at, revocation_reason; Device context: user_agent and source_ip.
- Code: backend/app/models/user.py:81–105.
  **alarm_settings**
- Primary key: alarm_settings_id; Foreign key: user_id.
- Preference fields: alarm_sound, volume, snooze_duration; Lifecycle fields: created_at and updated_at.
- Code: backend/app/models/user.py:108–138.

#### Core detection entities

**camera**

- Primary key: camera_id; Source identity: camera_name and channel_id.
- Activation flags: is_active and is_enabled; Desired control: desired_ai_state, desired_state_reason, cooldown_until, config_version.
- Observed engine state: connection_status, ai_status, applied_config_version, last_heartbeat_at, measured_fps, inference_latency_ms, last_error_code, last_error_message; Lifecycle fields: created_at and updated_at.
- Code: backend/app/models/camera.py:28–107.
  **detection_log**
- Primary key: log_id; Event identity: source_event_id, camera_id, detected_at, snapshot_key, confidence_score.
- Lifecycle state: detection_status; Verification fields: verified_by_id and verified_at.
- Closure fields: closed_by_id and closed_at; Snooze fields: snoozed_at, snoozed_until, and snoozed_by_id.
- Lifecycle fields: created_at and updated_at; Code: backend/app/models/detection.py:21–83.

#### Governance and asynchronous jobs

**audit_log**

- Primary key: audit_id; Actor identity: actor_type, user_id, username, and role.
- Action target: action, target_type, target_ref; Result and evidence: result, detail, request_id, source_ip, created_at.
- Code: backend/app/models/audit.py:49–85.
  **export_job**
- Primary key: job_id; Requester: requested_by_id.
- Job request: report_type, format, filters_json, sort_json; Progress: status, progress_current, progress_total.
- Artifact and failure state: artifact_path, artifact_bytes, failure_category; Lifecycle: created_at, started_at, completed_at, expires_at.
- Code: backend/app/models/export.py:9–45.

#### Documentation and telemetry

**help_article**

- Primary key: article_id; Search and presentation: slug, title, category, roles, summary, sort_order, is_faq.
- Content: body_markdown and content_hash; Lifecycle: created_at and updated_at.
- Code: backend/app/models/help.py:12–39.
  **sys_health_raw**
- Primary key: sys_health_id; Time: created_at.
- Paper fields: created_at, cpu_usage, gpu_usage, ram_usage, and gpu_temperature; code metrics: cpu_usage, ram_usage, gpu_usage_avg, gpu_temp_max, cpu_temp, and gpu_mem_pct_max; Code: backend/app/models/health.py:20–47.
  **sys_health_hourly**
- Primary key: hourly_id in the current model; Time key: hour_start.
- Paper fields: hourly_sys_health_id, created_at_hour, avg_cpu_usage, avg_gpu_usage, avg_ram_usage, and peak_gpu_temp; code aggregates: avg_cpu_usage, avg_ram_usage, avg_gpu_usage, avg_cpu_temp, peak_cpu_temp, peak_gpu_temp, avg_gpu_mem_pct, peak_gpu_mem_pct, and sample_count; Code: backend/app/models/health.py:50–91.
  The ERD’s health labels are the paper’s logical names; the code class and field names above identify the current implementation that owns the same data domain.

#### Every ERD relationship

- **user to auth_session:** one user can have many session rows. A session must point to its user so logout, expiry, or revocation can be enforced server-side; **user to alarm_settings:** strict one-to-one. The unique user_id in backend/app/models/user.py:120–122 prevents two preference rows for one account.
- **camera to detection_log:** mandatory one-to-many. One camera can create many incident rows over time; each detection_log has a required camera_id; **user to detection_log, verification:** optional actor link. A newly created AI incident exists before a human acts, so verified_by_id is empty until confirm or immediate dismiss.
- **user to detection_log, closure:** optional actor link. closed_by_id is populated when an ongoing incident is cleared or corrected; **user to detection_log, snooze:** optional actor link. snoozed_by_id records which user applied the incident snooze.
- **user to audit_log:** optional user-to-many. A user action can have many audit rows, while system-generated or unknown-user failures can leave user_id empty; **user to export_job:** one-to-many. One user can request multiple asynchronous exports.
- **help_article to help_article_fts:** the FTS5 virtual table is synchronized from help_article by database triggers in backend/app/models/help.py:42–72. It is a search index, not a second business record; **sys_health_raw and sys_health_hourly:** intentionally independent telemetry tables. They do not need a user or camera foreign key for each sample.

### One end-to-end narration across all views

Use this when a panelist asks you to connect the diagrams.
The client–server diagram starts with CCTV/VMS sending RTSP into the edge server.
The swimlane says the System analyzes it, creates an Unverified incident, and alerts the Operator.
The level-1 DFD names that work as process 3.0, then sends an incident event to process 4.0.
The ERD stores the incident in detection_log and links it to its camera.
The use case gives the Operator Verify Accident Alert, then Confirm Accident or Dismiss Accident.
The backend transition writes the human actor fields, an audit row, and the camera desired state in one transaction.
The WebSocket carries the resulting event to the browser.
The Operator later clears the ongoing incident or dismisses it as a correction.
The ERD then has the closure actor and time, while the DFD sends the updated control state back toward process 3.0.

## 4. Why it was built this way

### Give each diagram one job

A single diagram would either hide important detail or become unreadable.
The context DFD protects the system boundary.
The level-1 DFD explains the internal logical decomposition.
The swimlane makes Human-in-the-Loop ownership obvious.
The use case makes role capabilities reviewable.
The ERD makes durable relationships and optional actor participation explicit.
The client–server diagram connects the logical views to the actual machines and network seams.

### Keep actors, processes, and stores distinct

The Operator is an actor because the person supplies decisions and requests.
Process 4.0 is the response coordinator because the software applies those decisions.
D3 is a store because it holds incident and evidence data across requests and restarts.
Calling D3 a process would confuse stored information with the work that reads or updates it.
Calling process 4.0 a store would hide the state-transition rules and audit transaction.

### Use a context DFD and a levelled DFD

The context view lets the panel see the three external relationships without internal clutter.
The level-1 view makes the current implementation seams visible: detection, response, identity, camera state, reports, reliability, and help.
The current levelled DFD also shows the loops that matter operationally: incident events, control state, telemetry, and recovery/report artifacts.

### Treat CCTV/VMS as external

The physical camera network supplies data but is outside the ADAS software boundary.
ADAS requests a stream and receives video; it does not own the NVR or VMS database.
This boundary lets the same software model apply to the paper’s physical CCTV source and the project’s controlled stream source.

### Keep human decisions in the Operator path

The AI engine proposes an incident.
The Operator supplies the confirmation or dismissal decision.
This protects the paper’s HITL claim and keeps an AI detection from becoming a field-response decision automatically.
The backend still enforces the transition and records the actor, so the human decision is durable and auditable.

### Use relational links for accountability

The incident must point to a camera.
Actor links remain optional until the relevant human action happens.
That is why camera-to-detection_log is mandatory one-to-many, while user-to-detection_log handling links are optional.
The schema can therefore represent both a newly created AI alert and a fully handled incident without placeholder users.

### Use the local edge client–server split

Video and inference stay on the edge host, close to the camera network.
The browser receives alerts and sends commands without handling raw RTSP or database credentials.
The separate HTTP, WebSocket, and REST seams match their traffic patterns and keep each component’s ownership visible.

### Current DFD overhaul

The DFD was overhauled during development. The defense answer should use the current paper’s Figures 5 and 6.
The current context view includes the Administrator as a distinct external entity.
The current level-1 view exposes seven logical processes, seven stores, help, telemetry, reports, recovery artifacts, and the incident-control loop.
That is the version that matches the current system vocabulary and code map in this guide.

## 5. What changed since the 28 April defense

The diagram set now describes the current implementation rather than only the earliest high-level accident path.
The DFD is the clearest change in emphasis:

- The context view now names CCTV/VMS, Operator, and Administrator exchanges; The level-1 view is the current seven-process decomposition.
- It includes identity and preferences, camera state, incident response, analytics and audit, reliability, and help; It shows D6 as the shared logical area for report and recovery artifacts.
- It shows the control-state loop from human response back toward live-video analysis.
  The ERD view also covers the current persistent domains used by the implementation:
- Server-side sessions and per-user alarm settings; Append-only audit records.
- Asynchronous export jobs; Help articles and their search index.
- Raw and hourly health telemetry.
  The current client–server and swimlane narratives also make the post-detection guarantees visible:
- The AI engine writes its snapshot and outbox record before delivery; The backend commits an incident before broadcasting it.
- The browser reconnects and rebuilds active incidents after a missed push; Camera desired state returns through heartbeat reconciliation.
  These are the current code paths in ai_engine/outbox.py:58–74, backend/app/api/routes/internal.py:126–136, backend/app/main.py:442–529, and frontend/src/components/RealtimeAlertsBridge.tsx:235–317.
  When asked what the panel saw before, describe the current views and the current implementation. Do not revive a superseded DFD layout.

## 6. Limits and honest caveats

The diagrams are logical explanations.
They are not packet captures, execution traces, or a promise that every arrow is one network request.
The context DFD intentionally hides internal processes.
The level-1 DFD groups several routes, services, and files under one logical process.
For example, process 5.0 covers analytics, reports, and audit even though those are separate routers and services in code.
The swimlane assigns responsibility, so it does not show every retry, lock, or conditional update.
The use-case diagram expresses capabilities and role relationships, not a complete endpoint matrix.
The “Record Audit Entry” legend is a compact representation of the audit rule; it does not mean every read-only use case writes a row.
Figure 2 is a client–server architecture view.
It shows the edge deployment shape and the local LAN data path; it is not evidence of a measured full production camera capacity.
The paper’s target deployment and the evaluated proof of concept must stay qualified when discussing scale.
The ERD’s independent health tables do not identify a user or camera for every sample.
That is intentional: telemetry is a time series of host observations, while user and camera relations describe operational ownership.
The paper’s ERD displays logical field labels; the current SQLModel classes are the implementation authority for exact Python attribute names.
The database relationship does not replace service rules.
The required camera relationship is reinforced by foreign keys and constraints, while the legal incident transitions are enforced in the service and conditional database update.
The browser’s WebSocket is a notification and synchronization channel.
The client sends incident decisions through REST, and the backend remains the source of truth.

## 7. Likely panel questions

### “Walk me through your data flow diagram.”

Start at CCTV/VMS: it exchanges a stream request and live video with process 3.0. Process 3.0 forms an incident event for process 4.0 and sends telemetry to 6.0; 4.0 sends alerts to the Operator and receives decisions back. Identity, camera state, reports, audit, health, recovery, and help are represented by the other processes and stores.

### “Where does the operator appear in the swimlane?”

The Operator owns the Human-in-the-Loop steps: reviewing the snapshot and bounding box, choosing confirm or dismiss, monitoring an ongoing incident, clearing it, searching history, and exporting reports. The System performs the resulting database, audit, camera-state, and broadcast work after the Operator’s request.

### “Why is that a data store and not a process?”

A data store represents information that persists or is read by more than one logical operation. D3, for example, holds incident and evidence data; process 4.0 is the work that applies a decision to that data. The code reflects this split through SQLModel entities and service functions.

### “Which use case covers the false-positive path?”

The path is Verify Accident Alert, then Dismiss Accident, then Enforce Cooldown. It changes an Unverified incident to Dismissed and applies the configured cooldown before that camera can alert again.

### “Your ERD shows that relationship as one-to-many. Why?”

A camera can produce many incident rows over its lifetime, but each detection_log row has one required camera_id. That is why camera to detection_log is mandatory one-to-many. The foreign key and the Camera.detections relationship implement it.

### “Why do you have both a context DFD and a level-1 DFD?”

The context DFD establishes the system boundary and shows only the three external entities. The level-1 DFD opens the boundary and names the seven logical processes, seven stores, and key loops. The two views answer different questions.

### “Is the Administrator a separate system?”

No. The Administrator is an external actor in the use-case and DFD views because a person outside the software process sends requests. Inside the system, the same backend enforces the Administrator role and returns the administrative results.

### “Why is CCTV/VMS outside the system boundary?”

ADAS consumes the stream but does not own the physical cameras, NVR, or VMS. Treating CCTV/VMS as external makes the software boundary clear: ADAS requests a feed, receives video, and processes it internally.

### “Why does the DFD show a flow back from human response to live-video analysis?”

Human response changes the camera’s desired state: an open incident pauses it, and a clear or eligible cooldown completion allows it to resume. The heartbeat returns that authoritative state to the engine, so the control-state arrow represents a real feedback loop.

### “Does the client–server diagram mean the browser receives RTSP?”

No. RTSP terminates at the AI engine through the VMS/Media Gateway. The browser receives JSON event and status updates over WebSocket and uses REST for reads and actions; it does not need raw video for the alert workflow.

### “Why are help articles and health telemetry disconnected from the user graph?”

Help content is role-filtered through the request, and its FTS5 table is a search index. Health rows are time-series observations of the host. Neither needs a per-row foreign key to a user or camera, so the ERD keeps them as independent domains.

### “What happens if the same alert arrives twice?”

The event carries source_event_id. The backend checks that identifier and has a unique index as a backstop, so a retry returns the existing row without creating a duplicate or broadcasting a second new incident.

## 8. Cram summary

- Figure 2 is **where**: IP cameras/VMS feed the edge AI engine; AI Engine, FastAPI Backend, and SQLite share the edge server; React runs in the client browser; The three technical seams are authenticated HTTP from AI to backend, WebSocket push from backend to frontend, and REST from frontend to backend.
- Figure 3 is **who**: System detects and persists; Operator reviews, decides, monitors, clears, and reports; Administrator manages users and governance; Figure 4 is **what users can request**: login, incident handling, camera management, monitoring, reports, help, user administration, backup, restore, and audit.
- The false-positive use-case path is Verify Accident Alert → Dismiss Accident → Enforce Cooldown; Figure 5 is the boundary: ADAS exchanges video with CCTV/VMS, operational requests/results with Operator, and administrative requests/results with Administrator.
- Figure 6 is the current DFD: seven logical processes and seven logical stores, with incident, control-state, telemetry, report, recovery, and help flows; D1–D7 are logical stores: identity/access, camera state, incident/evidence, audit, health/performance, reports/recovery, and help.
- Figure 7 is the durable graph: ten relational entities, mandatory camera-to-detection_log one-to-many, optional human handling links, user-owned sessions/preferences/audit/exports, and independent help/telemetry; The safest one-sentence defense is: **“The diagrams are different views of one implementation: the camera supplies evidence, the AI proposes, the backend owns durable state, the Operator decides, and every important result is stored and delivered through explicit seams.”**
