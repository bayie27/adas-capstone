# 07 — Definition of Terms

> **One-liner:** A speaking glossary for the paper’s technical vocabulary, with the ADAS meaning and the follow-up that a panelist is likely to ask.
> **Panel risk:** High — several familiar terms have a system-specific meaning, and the panel can easily confuse model metrics, event outcomes, and operator judgments.

## 1. What it is

The paper’s Chapter 1 Definition of Terms is the authority for the definitions below. Each item gives that paper definition first, then a plain explanation for a follow-up, and finally why it matters in this system.

The glossary follows the paper’s list, then adds event-level recall, false positives per minute, and the System Usability Scale because the test evidence uses them and the panel can reasonably ask for their meaning.

### Administrator

- **Paper definition:** A high-level role with all operational capabilities and exclusive authority over user accounts, the user directory, and security management. (Paper: Ch. 1, “Definition of Terms,” “Administrator.”)
- **If they push:** Administrators can do operator work as well as the restricted account and security tasks. Role checks determine which actions are available.
- **Why ADAS cares:** The distinction limits sensitive administration to authorized users while keeping incident review available to operators. (Paper: Ch. 3, Figures 3 and 20.)

### Alert Fatigue

- **Paper definition:** Desensitization caused by a continuous stream of notifications, which can make critical incidents easier to overlook. The paper identifies this as the risk addressed by the confidence threshold, dismissal cooldown, and snooze controls. (Paper: Ch. 1, “Definition of Terms,” “Alert Fatigue.”)
- **If they push:** Too many weak or repeated alarms can teach an operator to ignore the alarm channel. Reducing avoidable repetition helps the operator focus on alerts that still need a decision.
- **Why ADAS cares:** The system combines a low frame-level confidence floor with temporal evidence and operator controls so one noisy frame does not immediately become an alarm. (Paper: Ch. 3, “Inference and Temporal Event Formation”; Figure 4.)

### Asynchronous Server Gateway Interface (ASGI)

- **Paper definition:** The Python server interface used through Uvicorn so one backend worker can keep operator WebSocket connections open while processing alert ingestion, heartbeats, and REST requests. (Paper: Ch. 1, “Definition of Terms,” “Asynchronous Server Gateway Interface.”)
- **If they push:** ASGI is the server interface that supports asynchronous connections and requests. An open alert socket does not need to occupy a thread that blocks the other application work.
- **Why ADAS cares:** The backend serves both normal API calls and live dashboard alert connections on the edge server. (Paper: Ch. 3, “Technical Scope”; code: backend/app/main.py:442, backend/app/main.py:535.)

### Audit Trail

- **Paper definition:** An append-only record of state-changing actions, committed in the same database transaction as the action, with the responsible user, role, action, affected record, timestamp, and result. (Paper: Ch. 1, “Definition of Terms,” “Audit Trail.”)
- **If they push:** The record gives an accountable history of who changed what. Committing it with the action prevents a successful state change from being stored without its audit row.
- **Why ADAS cares:** Incident decisions and administrative changes need to be traceable after the live alert is gone. (Paper: Ch. 3, Figure 3 and Table 11; code: backend/app/services/audit.py:51.)

### Automation Bias

- **Paper definition:** The tendency to over-trust algorithmic output and stop looking for evidence that confirms or contradicts it. The paper uses this as the reason every detection needs human verification. (Paper: Ch. 1, “Definition of Terms,” “Automation Bias.”)
- **If they push:** A correct-looking AI alert can still be wrong; the interface must support a human decision rather than treat the model score as authorization.
- **Why ADAS cares:** Operators review the snapshot and choose whether the incident is Unverified, Ongoing, Dismissed, or Cleared through the incident workflow. (Paper: Ch. 3, Figure 3; FR-09.)

### Batched Inference

- **Paper definition:** Frames from active cameras are grouped into one detector call per scheduling tick instead of running one separate model pass for every stream. The paper reports prototype-hardware latency of 16.5 ms at batch size 1 and 114.1 ms at batch size 16. (Paper: Ch. 1, “Definition of Terms,” “Batched Inference.”)
- **If they push:** Batching shares the model-call overhead across cameras, but a larger batch takes longer to finish. Those two reported timings describe the paper’s prototype measurement, not a promise for every device or stream profile.
- **Why ADAS cares:** A shared edge server processes multiple configured feeds, so the cost of a batch matters to each camera’s detection cadence. (Paper: Ch. 3, “AI Engine Layer”; code: ai_engine/detector.py:188, ai_engine/main.py:33.)

### Bounding Box

- **Paper definition:** A rectangular overlay on the incident snapshot that marks the region the AI identified as a vehicle-to-vehicle collision. (Paper: Ch. 1, “Definition of Terms,” “Bounding Box.”)
- **If they push:** The rectangle is the model’s spatial estimate. Comparing it with a labeled rectangle is how IoU-based localization is evaluated.
- **Why ADAS cares:** The operator sees the highlighted region when reviewing an alert snapshot, and box overlap also links evidence across frames. (Paper: Ch. 3, “AI Engine Layer”; code: ai_engine/accident.py:21, ai_engine/accumulate.py:27.)

### Cognitive Overload

- **Paper definition:** A condition where simultaneous video feeds exceed an operator’s attention capacity, narrowing the area they effectively monitor. (Paper: Ch. 1, “Definition of Terms,” “Cognitive Overload.”)
- **If they push:** The problem is not that the operator is careless; attention is limited, and events can happen outside the currently watched part of a video wall.
- **Why ADAS cares:** Automated screening is intended to draw attention to possible collisions while leaving verification to the operator. (Paper: Ch. 2, “Manual Surveillance Limitations and Emergency Response Latency”; Figure 3.)

### Confidence Score

- **Paper definition:** A probability metric from YOLO indicating its mathematical certainty that a visual anomaly is a vehicle collision. (Paper: Ch. 1, “Definition of Terms,” “Confidence Score.”)
- **If they push:** It is the model’s score for a frame-level candidate, not an operator’s confirmation and not a guarantee that the scene is a real collision.
- **Why ADAS cares:** The detector keeps weak candidates available for temporal evidence; the human workflow decides whether the resulting incident is genuine. (Paper: Ch. 3, “Inference and Temporal Event Formation”; Table 11.)

### Cooldown Timer

- **Paper definition:** A one-minute pause on AI detection for the specific camera after an operator dismisses a false-positive alert, intended to prevent repeat notices from persistent environmental noise. (Paper: Ch. 1, “Definition of Terms,” “Cooldown Timer.”)
- **If they push:** It is camera-specific and follows a dismissal; it is different from snoozing an audible alarm while an operator examines an alert.
- **Why ADAS cares:** The cooldown reduces repeated nuisance alerts from the same camera scene while preserving the incident decision and camera state in the backend. (Paper: Ch. 3, Figure 4; code: backend/app/api/routes/alerts.py:518.)

### Data Drift

- **Paper definition:** A gradual loss of model accuracy as local road conditions or vehicle populations change from the training data. The maintenance plan uses operator-categorized true- and false-positive snapshots for future retraining. (Paper: Ch. 1, “Definition of Terms,” “Data Drift”; Ch. 3, “Maintenance and Support Plan.”)
- **If they push:** Drift is a reason to keep collecting reviewed examples and reevaluate the model. Exporting examples does not itself retrain or redeploy model weights.
- **Why ADAS cares:** Local vehicles, lighting, camera views, and road conditions can change, so the paper’s maintenance plan includes a feedback path for later model updates. (Paper: Ch. 3, “Maintenance and Support Plan.”)

### Desired State Reconciliation

- **Paper definition:** The backend holds the authoritative camera configuration and sends it to the AI engine on each heartbeat; a restart is corrected on the first heartbeat because the engine stores no local configuration. (Paper: Ch. 1, “Definition of Terms,” “Desired State Reconciliation.”)
- **If they push:** The backend tells the engine what should be active; the engine reports what it observes. On restart, the engine asks for a fresh full view instead of trusting stale local settings.
- **Why ADAS cares:** Camera enablement, pauses, cooldown expiry, stream addresses, and configuration versions must converge after a process restart. (Paper: Ch. 3, “State Reconciliation & Heartbeat”; code: backend/app/api/routes/internal.py:140.)

### Detection Status

- **Paper definition:** The incident verification state begins as Unverified, changes to Ongoing when an operator confirms a genuine collision, becomes Cleared when the scene is clear, or becomes Dismissed for a false alarm or a corrected confirmation. (Paper: Ch. 1, “Definition of Terms,” “Detection Status.”)
- **If they push:** The states separate machine detection from human judgment and closure. Cleared is the paper’s term for a handled incident; Dismissed means the alert was judged false or corrected.
- **Why ADAS cares:** The status drives the operator’s incident queue, camera pause behavior, and the record of who verified or closed the incident. (Paper: Ch. 3, Figure 3 and Table 11; code: backend/app/services/incidents.py:229.)

### Discriminative Foil

- **Paper definition:** The ordinary-vehicle class in training that helps the model distinguish normal traffic from a collision; it is capped at an 8:1 ratio against accident boxes and never triggers alerts. (Paper: Ch. 1, “Definition of Terms,” “Discriminative Foil.”)
- **If they push:** The vehicle class teaches a boundary. It is not a second event class that operators are alerted about.
- **Why ADAS cares:** Without examples of ordinary vehicles, a model could confuse a moving car with an accident and generate unnecessary alerts. (Paper: Ch. 3, “Deep Learning Implementation and Training Protocol”; code: ai_engine/config.py:105.)

### Durable Outbox

- **Paper definition:** A detected event and its snapshot are written atomically to an on-disk queue before network transmission; pending items retry with exponential backoff, and invalid payloads are quarantined. (Paper: Ch. 1, “Definition of Terms,” “Durable Outbox.”)
- **If they push:** The event is kept locally while the backend is unreachable, then delivery can resume. A retry repeats the same event identity so it can be handled idempotently.
- **Why ADAS cares:** A temporary network or backend outage should not erase the event between detection and database ingestion. (Paper: Ch. 3, “AI Engine Layer”; code: ai_engine/outbox.py:58, ai_engine/outbox.py:138.)

### Edge Inference Server

- **Paper definition:** A localized computer architecture intended to host the database, web application, and AI processes within the target network without depending on remote cloud computing. (Paper: Ch. 1, “Definition of Terms,” “Edge Inference Server.”)
- **If they push:** “Edge” means processing near the video source and operator network. It describes the intended local architecture; the study evaluated a proof of concept on researcher-controlled hardware.
- **Why ADAS cares:** Local video processing and local alert delivery support the paper’s on-premises design. The study does not claim a production-scale CDRRMO deployment. (Paper: Ch. 1, “Scope and Delimitations”; Ch. 3, “Deployment Architecture”; Figure 2.)

### Export Job

- **Paper definition:** A background report task used when an export exceeds the synchronous limit of 10,000 PDF rows or 50,000 CSV rows; the artifact is retained for 72 hours. (Paper: Ch. 1, “Definition of Terms,” “Export Job.”)
- **If they push:** The API accepts the request and the dashboard checks progress instead of holding one request open while a very large file is built.
- **Why ADAS cares:** Historical incident and administrative reports can grow, and background jobs keep large exports from exhausting edge-server memory. (Paper: Ch. 3, “System Architecture and Design”; code: backend/app/api/routes/exports.py:55, backend/app/core/config.py:108.)

### False Positive

- **Paper definition:** An alert where the model labels environmental noise or ordinary traffic as a vehicle collision, which an operator must dismiss. (Paper: Ch. 1, “Definition of Terms,” “False Positive.”)
- **If they push:** A false positive is one incorrect event alert. It is not the same as a false negative, where a real collision receives no alert.
- **Why ADAS cares:** Dismissal records the operator’s judgment and informs per-camera performance review and later retraining examples. (Paper: Ch. 3, Figure 4 and Table 11.)

### “Flag and Restart” Restoration

- **Paper definition:** A recovery lifecycle where the backend records a restore request rather than replacing the live database itself; an external orchestrator stops services, creates a safety copy, replaces the database, removes sidecars, verifies integrity, then restarts or rolls back. (Paper: Ch. 1, “Definition of Terms,” “Flag and Restart Restoration.”)
- **If they push:** The running application coordinates and records the request, but the offline database replacement happens after service shutdown. Verification decides whether to proceed or restore the safety copy.
- **Why ADAS cares:** SQLite files and their sidecars must not be swapped underneath a running backend. The paper separates request handling from offline restoration. (Paper: Ch. 3, “System Maintenance and Database Restoration Architecture”; code: backend/app/maintenance/restore.py:291, backend/app/maintenance/restore.py:495.)

### Golden Hour

- **Paper definition:** The critical period after traumatic injury when rapid medical intervention can improve survival and reduce severe complications. (Paper: Ch. 1, “Definition of Terms,” “Golden Hour.”)
- **If they push:** In this project it motivates reducing time before the command center is aware of a collision. It is not a measured ADAS outcome or a promise of medical treatment.
- **Why ADAS cares:** The system supports operator verification and faster manual dispatch or endorsement procedures; it does not dispatch emergency responders itself. (Paper: Ch. 1, “Objectives of the Study” and “Scope and Delimitations.”)

### Grayscale Normalization

- **Paper definition:** Each frame is converted to grayscale and replicated into three channels for both training and inference, preventing image color from becoming a shortcut feature. (Paper: Ch. 1, “Definition of Terms,” “Grayscale Normalization.”)
- **If they push:** The model still receives the three-channel shape expected by its input pipeline, but all three channels carry grayscale image information.
- **Why ADAS cares:** The paper notes that the accident and ordinary-vehicle source images differ in color, so normalization reduces a spurious color cue that could fail on live color video. (Paper: Ch. 3, “Deep Learning Implementation and Training Protocol”; code: ai_engine/detector.py:28.)

### Heartbeat

- **Paper definition:** A periodic AI-engine report of observed frame rate, inference latency, stream status, and diagnostic errors that also receives the backend’s desired configuration. (Paper: Ch. 1, “Definition of Terms,” “Heartbeat.”)
- **If they push:** It carries telemetry in one direction and current camera instructions in the other. It is both a health report and a synchronization point.
- **Why ADAS cares:** The dashboard can show what the engine observes while camera control remains authoritative in the backend. (Paper: Ch. 3, “State Reconciliation & Heartbeat”; code: backend/app/api/routes/internal.py:140.)

### Held-Out Evaluation Corpus

- **Paper definition:** Seventeen archival Lipa CDRRMO CCTV clips excluded from training and validation and used to measure event-level behavior on authentic local footage. (Paper: Ch. 1, “Definition of Terms,” “Held-Out Evaluation Corpus.”)
- **If they push:** “Held out” here means the clips were kept out of training and validation. Use the tracker’s qualification too: it does not claim an untouched post-selection test set, and incident independence is uncertain.
- **Why ADAS cares:** Local clips provide evidence about collision events and conditions the model did not see in its training and validation material, within the limits recorded by the tracker. (Paper: Ch. 3, “Checkpoint Selection”; tracker: AI Model Validation, AI-VAL-002 and AI-VAL-007.)

### Human-in-the-Loop (HITL)

- **Paper definition:** The AI detects and triages possible incidents, while an operator alone confirms, dismisses, or clears them; dispatch does not proceed on unverified machine judgment. (Paper: Ch. 1, “Definition of Terms,” “Human-in-the-Loop”; Ch. 3, Figure 3.)
- **If they push:** The AI raises a candidate and presents evidence. An authorized person makes the incident decision; the software supports that workflow rather than making the dispatch decision.
- **Why ADAS cares:** HITL addresses automation bias and keeps human judgment in the high-consequence decision path. (Paper: Ch. 2, “HITL Approaches in Automated Surveillance”; FR-09.)

### Hybrid Dual-Track Development Framework

- **Paper definition:** The project’s custom method runs an iterative Machine Learning Development Life Cycle alongside a predictive Software Development Life Cycle. (Paper: Ch. 1, “Definition of Terms,” “Hybrid Dual-Track Development Framework.”)
- **If they push:** Model work needs repeated data, training, and evaluation cycles; application work needs planned requirements, design, implementation, and integration. The tracks converge for end-to-end validation.
- **Why ADAS cares:** The approach lets the team refine the detector while building the backend and dashboard needed to deliver and review its alerts. (Paper: Ch. 3, “Project Development Model,” Figures 2–4.)

### Idempotency

- **Paper definition:** A unique AI-generated event identifier makes repeated transmissions of the same collision create only one incident record; a retry is acknowledged without adding a duplicate row. (Paper: Ch. 1, “Definition of Terms,” “Idempotency.”)
- **If they push:** The event identifier is created once and reused by retries. The backend checks that identity and returns the existing incident rather than inserting and broadcasting a second incident.
- **Why ADAS cares:** The durable outbox can retry after a network failure without turning one detected collision into duplicate rows or duplicate alerts. (Paper: Ch. 3, Table 11; code: ai_engine/events.py:10, backend/app/services/incidents.py:124, backend/app/models/detection.py:32.)

### Inference Latency

- **Paper definition:** The milliseconds the edge AI engine needs to process one live frame and generate bounding boxes. (Paper: Ch. 1, “Definition of Terms,” “Inference Latency.”)
- **If they push:** This is a detector processing measure. It is not the full time from a collision becoming visible to an operator decision, and it does not include the entire human workflow.
- **Why ADAS cares:** The engine reports inference latency as telemetry, while the paper separately sets an end-to-end objective for collision visibility to verified operator decision. (Paper: Ch. 1, “Objectives of the Study”; Ch. 3, “Performance and Load Testing.”)

### Intersection over Union (IoU)

- **Paper definition:** A spatial metric that measures overlap between the AI’s generated box and the labeled location of the crashed vehicles. (Paper: Ch. 1, “Definition of Terms,” “Intersection over Union.”)
- **If they push:** IoU is intersection area divided by the total area covered by either box. A higher value means the predicted box overlaps the reference more closely.
- **Why ADAS cares:** Model validation uses IoU 0.50 for the paper’s mAP target; the temporal accumulator has a separate IoU 0.30 setting to link boxes over adjacent frames. Those thresholds answer different questions. (Paper: Ch. 1, “Objectives of the Study”; Ch. 3, “Inference and Temporal Event Formation”; code: ai_engine/accumulate.py:27.)

### JSON Web Token (JWT)

- **Paper definition:** A signed authentication token carried in an HttpOnly, Secure cookie and backed by a server-side auth_session row, used to manage sessions, enforce role access, and revoke individual sessions. (Paper: Ch. 1, “Definition of Terms,” “JSON Web Token.”)
- **If they push:** The browser sends the cookie with requests; the backend checks the token and its server-side session. The cookie is not JavaScript-readable storage, and the session record supports early revocation.
- **Why ADAS cares:** The same authenticated identity controls dashboard access and the authority to verify incidents or administer accounts. (Paper: Ch. 3, “Technical Scope”; code: backend/app/core/security.py:36, backend/app/api/dependencies.py:48.)

### Mean Average Precision (mAP)

- **Paper definition:** The standard object-detection accuracy metric, adopted as an 85% validation threshold at IoU of at least 0.50; the paper treats it as a benchmark, not a field guarantee. (Paper: Ch. 1, “Definition of Terms,” “Mean Average Precision”; “Objectives of the Study.”)
- **If they push:** Average Precision summarizes precision across recall levels for a class; mAP averages that value across classes at a chosen IoU criterion. It scores frame-level detections and box matches, not distinct collision events over time.
- **Why ADAS cares:** The objective uses mAP@0.50, while the tracker separately reports event recall and false positives per minute. Do not use one metric as a substitute for another. (Paper: Ch. 3, “Checkpoint Selection”; tracker: AI Model Validation, AI-VAL-001–004.)

### MediaMTX

- **Paper definition:** The open-source RTSP gateway used in the isolated test environment to imitate the VMS media-gateway behavior and make the engine ingest network streams instead of local video files. (Paper: Ch. 1, “Definition of Terms,” “MediaMTX.”)
- **If they push:** It simulates the stream delivery path for testing. It is not the Lipa CDRRMO Dahua DSS Pro server.
- **Why ADAS cares:** It lets the team test RTSP ingest and the end-to-end alert path without changing live agency operations. (Paper: Ch. 3, “Test Environment” and “Testing Strategy Overview”; Figure 2.)

### Model Checkpoint

- **Paper definition:** Saved model weights retained every ten training epochs over runs of up to sixty epochs; the epoch-50 checkpoint was chosen after comparing event-level recall and false-positive behavior on local clips. (Paper: Ch. 1, “Definition of Terms,” “Model Checkpoint.”)
- **If they push:** A checkpoint is one saved set of weights from training. The team compared candidates on the event-level local-footage harness instead of choosing solely by the model framework’s default best checkpoint label.
- **Why ADAS cares:** The selected weights are the detector artifact integrated into the inference pipeline. The tracker records the checkpoint selection evidence as archival, not a fresh sweep. (Paper: Ch. 3, “Checkpoint Selection”; tracker: AI Model Validation, AI-VAL-005.)

### Notification Gap

- **Paper definition:** The time from a road accident happening until the Lipa CDRRMO becomes aware of it; the study’s target is from the accident becoming visible on camera to a verified operator decision within 25 seconds. (Paper: Ch. 1, “Definition of Terms,” “Notification Gap”; “Objectives of the Study.”)
- **If they push:** The end point is the operator’s verified decision, not the arrival of responders or the completion of dispatch.
- **Why ADAS cares:** The system aims to shorten awareness and verification time so staff can begin their manual dispatch or endorsement procedure sooner. (Paper: Ch. 1, “Objectives of the Study” and “Scope and Delimitations.”)

### Operator (Dispatcher)

- **Paper definition:** Frontline command-center personnel who monitor the dashboard, verify AI alerts, configure camera feeds, and create analytical reports. (Paper: Ch. 1, “Definition of Terms,” “Operator.”)
- **If they push:** Operators are the incident-review users. They inspect the snapshot and select the applicable incident action; they do not administer the user directory.
- **Why ADAS cares:** The dashboard and alert workflow are designed around their live monitoring and decision tasks. (Paper: Ch. 3, Figures 3–4.)

### Precision Score

- **Paper definition:** The proportion of AI-generated alerts that operators later confirm rather than dismiss, shown globally and by camera in the AI Performance module. (Paper: Ch. 1, “Definition of Terms,” “Precision Score.”)
- **If they push:** In this dashboard the term means an operator-disposition measure. Do not confuse it with class precision used in a model’s precision–recall curve.
- **Why ADAS cares:** Per-camera scores help administrators find concentrations of dismissed alerts and investigate their scene conditions. (Paper: Ch. 3, Figure 24.)

### Quantization

- **Paper definition:** Exporting model weights from 32-bit to 16-bit floating point, reducing VRAM use and accelerating inference without a mathematically significant loss against the target accuracy. (Paper: Ch. 1, “Definition of Terms,” “Quantization.”)
- **If they push:** The weights use a lower-precision numeric representation. The deployment comparison still needs to check event outcomes and not rely on smaller artifact size alone.
- **Why ADAS cares:** The model must fit the available edge-inference budget while processing camera frames. (Paper: Ch. 3, “Deep Learning Implementation and Training Protocol”; tracker: AI Model Validation, AI-VAL-008.)

### Real-Time Streaming Protocol (RTSP)

- **Paper definition:** The network protocol used to send live localized video from the CDRRMO’s enterprise infrastructure to the edge server for AI analysis. (Paper: Ch. 1, “Definition of Terms,” “Real-Time Streaming Protocol.”)
- **If they push:** RTSP is the incoming video path to the AI engine. The paper’s test setup uses simulated or authorized feeds; its scope excludes changing or administering Dahua DSS Pro.
- **Why ADAS cares:** RTSP carries the camera images that the engine batches and analyzes; MediaMTX simulates the gateway during the isolated LAN tests. (Paper: Ch. 1, “Scope and Delimitations”; Ch. 3, “Test Environment.”)

### Sim-to-Real Gap

- **Paper definition:** The loss in detection performance that may appear when a model trained on curated data meets unfiltered field conditions such as glare, weather, compressed video, or local vehicles missing from training data. (Paper: Ch. 1, “Definition of Terms,” “Sim-to-Real Gap.”)
- **If they push:** A good score on curated data does not automatically cover every camera angle, lighting condition, or vehicle population in operation.
- **Why ADAS cares:** Local CCTV clips and condition-level results provide a more relevant check, but the tested corpus still limits what can be generalized. (Paper: Ch. 3, “Checkpoint Selection”; tracker: AI Model Validation, AI-VAL-006–007.)

### Single Page Application (SPA)

- **Paper definition:** A React web application that updates the current page with new server data rather than loading a completely new page for each change. (Paper: Ch. 1, “Definition of Terms,” “Single Page Application.”)
- **If they push:** The browser keeps the dashboard shell loaded while its components refresh alert, camera, and report state.
- **Why ADAS cares:** Operators can work from one dashboard while real-time alerts and current system data update in place. (Paper: Ch. 3, “Technical Scope”; code: frontend/src/main.tsx:16, frontend/src/App.tsx:1.)

### Soft Delete

- **Paper definition:** Marking a user or camera inactive instead of permanently deleting the row, preserving links from historical records and audit trails. (Paper: Ch. 1, “Definition of Terms,” “Soft Delete.”)
- **If they push:** The current operational view can hide inactive records while old incidents still refer to the original camera or user.
- **Why ADAS cares:** Historical incident and audit records remain interpretable after an account or camera is deactivated. (Paper: Ch. 3, Tables 10–11 and Figure 7.)

### Temporal Accumulation

- **Paper definition:** Overlapping frame detections build confidence-weighted evidence across successive frames, and an alert is raised only when that evidence persists past a threshold. The paper says this compensates for a low confidence floor and adds roughly three seconds of alert delay. (Paper: Ch. 1, “Definition of Terms,” “Temporal Accumulation.”)
- **If they push:** The engine links boxes spatially by IoU, adds confidence multiplied by elapsed time, lets unsupported evidence decay, smooths box coordinates, and fires when evidence reaches its threshold. This is not a dedicated identity tracker.
- **Why ADAS cares:** The paper says some measured false positives scored above genuine detections, so raising a single confidence cutoff could lose useful evidence. The chosen configuration uses confidence 0.15, IoU link 0.30, threshold 1.0 confidence-seconds, decay 0.30 per second, and EMA smoothing 0.50; persistence helps reject isolated noise. (Paper: Ch. 1, “Definition of Terms”; Ch. 3, “Inference and Temporal Event Formation”; code: ai_engine/accumulate.py:27, ai_engine/accumulate.py:59.)

### Thermal Throttling

- **Paper definition:** Automatic reduction in processing speed and power when sustained inference pushes hardware beyond safe temperatures; the paper cites literature reporting around 87°C for consumer devices. (Paper: Ch. 1, “Definition of Terms,” “Thermal Throttling”; Ch. 2, “Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision.”)
- **If they push:** The temperature is a literature example, not an ADAS measured trip point. Sustained load can affect inference timing even if a brief test run looks fast.
- **Why ADAS cares:** Continuous camera processing makes thermal and resource monitoring relevant to selecting and qualifying deployment hardware. (Paper: Ch. 3, “Performance and Load Testing” and Figure 25.)

### Third Normal Form (3NF)

- **Paper definition:** A relational schema standard applied to SQLite to reduce duplicated data and prevent update anomalies in historical incident records. (Paper: Ch. 1, “Definition of Terms,” “Third Normal Form.”)
- **If they push:** Descriptive facts such as a camera’s stream configuration live with the camera row; incident rows refer to that entity rather than copying every value.
- **Why ADAS cares:** Normalized camera, user, and incident records preserve consistent history as names and settings change. (Paper: Ch. 3, Figure 7 and Table 11.)

### User Acceptance Testing (UAT)

- **Paper definition:** The final evaluation where Lipa CDRRMO personnel use the integrated system in isolated staging to assess readiness, interface intuitiveness, and fit with established response workflows before live deployment. (Paper: Ch. 1, “Definition of Terms,” “User Acceptance Testing”; Ch. 3, “User Acceptance Testing.”)
- **If they push:** UAT is a structured user evaluation in staging. It is not evidence that the system was deployed in the command center.
- **Why ADAS cares:** The intended operators and administrators need to validate their workflows, not just the software tests. (Paper: Ch. 3, “Testing and Validation”; tracker: UAT Journeys and UAT Results.)

### Video Management System (VMS)

- **Paper definition:** The CDRRMO’s enterprise-level Dahua DSS Pro software, acting as a media gateway that provides the authorized main RTSP feed to the AI edge server. (Paper: Ch. 1, “Definition of Terms,” “Video Management System.”)
- **If they push:** The VMS owns video management; ADAS consumes a configured stream. The paper’s scope says ADAS does not modify or administer the VMS.
- **Why ADAS cares:** It describes the intended source of authorized camera video, while MediaMTX simulates that stream path in tests. (Paper: Ch. 1, “Scope and Delimitations”; Ch. 3, “Deployment Architecture” and Figure 33.)

### Vigilance Decrement

- **Paper definition:** A gradual, involuntary loss of sustained attention during a long monitoring shift, described in the literature as operators fixating on a small area and missing the rest of the video wall. (Paper: Ch. 1, “Definition of Terms,” “Vigilance Decrement.”)
- **If they push:** It is a human-factors concept from the literature, not a measured ADAS participant outcome.
- **Why ADAS cares:** It helps explain why automated screening can assist with many feeds while operators remain responsible for verifying incidents. (Paper: Ch. 2, “Manual Surveillance Limitations and Emergency Response Latency”; Ch. 2, “HITL Approaches in Automated Surveillance.”)

### Virtual Local Area Network (VLAN)

- **Paper definition:** Logical network segmentation into separate broadcast domains for management, video archival, edge surveillance, and operations, routed between segments through a router-on-a-stick configuration. (Paper: Ch. 1, “Definition of Terms,” “Virtual Local Area Network”; Ch. 3, Figure 33.)
- **If they push:** A VLAN separates network traffic logically even where devices share physical switching hardware. The paper presents a target topology, not a claim that the test used the CDRRMO’s live network.
- **Why ADAS cares:** The proposed layout isolates AI stream processing from video archiving and operator traffic. (Paper: Ch. 3, “Deployment Architecture,” Figure 33.)

### WebSocket Secure (WSS)

- **Paper definition:** A secure, full-duplex connection used by the backend to push collision alerts, camera state, and snooze lifecycle notifications to the dashboard in real time. (Paper: Ch. 1, “Definition of Terms,” “WebSocket Secure.”)
- **If they push:** The backend can send an event over an already-open connection instead of waiting for the browser’s next poll. HTTPS protects the WebSocket connection in transit.
- **Why ADAS cares:** WSS is the live alert delivery seam from the backend to operator browsers; REST handles the other dashboard requests. (Paper: Ch. 3, Figure 2 and “Technical Scope”; code: backend/app/main.py:442, frontend/src/hooks/useAdasWebSocket.ts:57.)

### Write-Ahead Logging (WAL)

- **Paper definition:** A SQLite mode that supports concurrent dashboard reads and high-frequency AI-engine writes while preventing database locking errors. (Paper: Ch. 1, “Definition of Terms,” “Write-Ahead Logging”; Ch. 3, “The Database.”)
- **If they push:** A change is recorded in the write-ahead log before it is checkpointed into the main database file. Readers can use a consistent view while committed changes are appended to the log.
- **Why ADAS cares:** The local database receives incident and telemetry writes while the dashboard reads incidents, analytics, and system status. (Paper: Ch. 3, “The Database”; code: backend/app/core/db.py:18.)

### YOLO (You Only Look Once)

- **Paper definition:** The custom-trained computer-vision model at the center of the edge collision pipeline; it processes optical frames and returns candidate detections in real time. (Paper: Ch. 1, “Definition of Terms,” “YOLO.”)
- **If they push:** YOLO supplies frame-level candidate boxes and confidence scores. Temporal accumulation turns suitable accident-class candidates over time into a possible collision event.
- **Why ADAS cares:** The paper selects a lightweight YOLO26n model for the prototype’s edge budget and batched RTSP processing; this is a deployment choice, not a claim that it is the most accurate architecture. (Paper: Ch. 3, “Model Architecture and Training Configuration,” Table 22.)

### Event-Level Recall

- **Paper definition:** The paper’s Definition of Terms does not give a separate entry; the tracker measures whether a labeled collision receives an event alert in the fixed scoring window. A hit window begins 2 seconds before labeled onset and ends 15 seconds after the labeled event. (Tracker: AI Model Validation, AI-VAL-002–003.)
- **If they push:** It counts collision events, not the number of matching video frames. One event is a hit if the system emits an alert within its scoring window.
- **Why ADAS cares:** It checks whether the pipeline detects actual collision events in local clips, complementing the frame-level mAP metric. (Tracker: AI Model Validation, AI-VAL-002; code: ai_engine/eval/run_one_clip.py:119.)

### False Positives per Minute (FP/min)

- **Paper definition:** The paper’s Definition of Terms does not list FP/min; the tracker reports the count of false event alerts divided by clean-footage minutes. The current reference run records 3 false positives over 11.0 clean minutes, or 0.27 FP/min. (Tracker: AI Model Validation, AI-VAL-004; code: ai_engine/eval/score.py:167.)
- **If they push:** The denominator is non-crash footage time, not the number of frames and not the total duration including collision windows. The result is descriptive; no FP/min acceptance threshold was approved.
- **Why ADAS cares:** It expresses nuisance alerts relative to the amount of clean footage tested, while remaining limited to that tested corpus. (Tracker: AI Model Validation, AI-VAL-004.)

### System Usability Scale (SUS)

- **Paper definition:** The paper’s Definition of Terms does not give a separate entry; the tracker uses the 10-item SUS questionnaire with the listed alternating-item scoring rule and a 0–100 score. (Tracker: SUS Questionnaire, rows 1–4.)
- **If they push:** SUS summarizes participants’ perceived ease of use after completing the role-based task journey. For scoring, subtract 1 from odd-item ratings, subtract each even-item rating from 5, add the adjusted values, and multiply by 2.5; it does not measure detection accuracy.
- **Why ADAS cares:** The tracker records 4 responses, a mean score of 89.375, and an acceptance criterion of 68. These describe the tested participants, not every future operator. (Tracker: SUS Questionnaire, rows 11–19; Usability Results, rows 11–18.)

## 2. Where it lives

### In the paper

- **Chapter 1, Definition of Terms:** the authoritative short definitions above, starting on page 17. The associated context is Scope and Delimitations, Objectives of the Study, and the three role definitions.
- **Chapter 2:** “Manual Surveillance Limitations and Emergency Response Latency” (p. 28), “Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision” (p. 36), and “HITL Approaches in Automated Surveillance” (p. 42) ground the human-factors and metric terms.
- **Chapter 3, Project Development Model:** pages 54–59 explain the hybrid development framework and how the model and software tracks converge.
- **Chapter 3, System Architecture and Design:** page 101 onward; Figure 2 shows the client-server system, Figures 3–4 show the operator and administrator workflow, Figure 7 shows the database relationships, and Tables 10–11 describe camera and incident records.
- **Chapter 3, System Maintenance and Database Restoration Architecture:** page 160 onward describes “Flag and Restart” recovery. “Deployment Architecture” begins on page 162; Figure 33 shows the proposed VLAN topology.
- **Chapter 3, Deep Learning Implementation and Training Protocol:** page 174 onward describes input normalization, model configuration, checkpoint choice, and temporal event formation; Table 22 lists YOLO26n training configuration.
- **Chapter 3, Testing and Validation:** page 187 onward describes the isolated test environment and UAT. The tracker supplies the qualified current AI results and SUS evidence used in this guide.

### In the code

- **Stream and model path:** ai_engine/camera.py:157 opens the RTSP reader; ai_engine/main.py:33 schedules multi-camera inference; ai_engine/detector.py:28 normalizes frames and ai_engine/detector.py:188 runs batched detection; ai_engine/config.py:105 identifies the alertable class and ai_engine/config.py:111 sets the detector confidence floor.
- **Event formation and delivery:** ai_engine/accumulate.py:27 computes box IoU and ai_engine/accumulate.py:59 accumulates temporal evidence; ai_engine/accident.py:46 turns an event into a snapshot and payload; ai_engine/outbox.py:58 persists the payload, ai_engine/outbox.py:121 quarantines invalid items, and ai_engine/outbox.py:138 computes retry backoff.
- **Backend incident flow:** backend/app/api/routes/internal.py:94 accepts AI alerts and backend/app/services/incidents.py:124 ingests them; backend/app/models/detection.py:32 enforces a unique source event; backend/app/services/incidents.py:229 owns status transitions; backend/app/api/routes/alerts.py:518 handles dismissals and cooldowns.
- **Live delivery and persistence:** backend/app/main.py:442 serves the alert WebSocket; frontend/src/hooks/useAdasWebSocket.ts:57 opens the browser connection; backend/app/core/db.py:18 installs SQLite settings; backend/app/services/audit.py:51 records audited actions.
- **Administration and recovery:** backend/app/core/security.py:36 creates session tokens; backend/app/api/routes/exports.py:55 queues large exports; backend/app/maintenance/restore.py:291 writes restore requests and backend/app/maintenance/restore.py:495 performs offline restoration.
- **Evaluation evidence:** ai_engine/eval/run_one_clip.py:119 builds event detections; ai_engine/eval/score.py:167 calculates FP/min. SUS is recorded in the ADAS Test Execution tracker, not in application code.

## 3. How it works

1. A configured RTSP feed reaches a camera reader. The inference loop selects current frames and batches them for the detector. (Paper: Ch. 3, “AI Engine Layer”; code: ai_engine/camera.py:157, ai_engine/main.py:33, ai_engine/detector.py:188.)
2. The detector normalizes the input, runs YOLO, and returns frame-level boxes and confidence scores. Only the accident class can contribute to alert formation; the ordinary-vehicle class is a discriminative foil. (Paper: Ch. 3, “Inference and Temporal Event Formation”; code: ai_engine/detector.py:28, ai_engine/detector.py:330, ai_engine/config.py:105.)
3. For each camera, the temporal accumulator links spatially overlapping accident boxes. It adds confidence-weighted evidence across elapsed time, decays unsupported evidence, smooths boxes, and emits an event when its evidence threshold is reached. (Paper: Ch. 3, “Inference and Temporal Event Formation”; code: ai_engine/accumulate.py:59.)
4. The event path pauses the camera for review, writes an annotated snapshot, creates a source event identifier, and puts the payload in the durable outbox before network delivery. (Paper: Ch. 3, “AI Engine Layer”; code: ai_engine/accident.py:46, ai_engine/outbox.py:58.)
5. The backend checks the event identity and stores one incident record. A repeated delivery with the same identity returns the existing incident instead of creating another. (Paper: Ch. 3, Table 11; code: backend/app/services/incidents.py:124, backend/app/models/detection.py:32.)
6. After the incident is committed, the backend pushes a typed event over WSS. The dashboard presents the alert snapshot and status, and the operator confirms, dismisses, or later marks a confirmed incident Cleared. (Paper: Ch. 3, Figures 2–4; code: backend/app/api/routes/internal.py:130, backend/app/main.py:442.)
7. Heartbeats report engine observations and receive the backend’s desired camera configuration. SQLite WAL supports the mixed local read and write workload, and audit rows accompany state-changing actions. (Paper: Ch. 3, “State Reconciliation & Heartbeat” and “The Database”; code: backend/app/api/routes/internal.py:140, backend/app/core/db.py:18, backend/app/services/audit.py:51.)
8. The team evaluates different questions with different measures: mAP and IoU for frame-level box validation, event recall and FP/min for local collision clips, inference latency for detector processing, and SUS for participant-perceived usability. (Paper: Ch. 1, “Objectives of the Study”; tracker: AI Model Validation and SUS Questionnaire.)

## 4. Why it was built this way

- **Keep evidence and decisions separate.** YOLO proposes candidate detections; accumulation adds persistence; a person makes the incident decision. This responds to the paper’s automation-bias and alert-fatigue concerns. (Paper: Ch. 2, “HITL Approaches in Automated Surveillance”; Ch. 3, Figure 3.)
- **Use metrics that answer different questions.** mAP evaluates frame-level detections and box matching; event recall asks whether labeled collisions were surfaced; FP/min describes nuisance alerts over clean time. None is a replacement for the others. (Paper: Ch. 1, “Objectives of the Study”; tracker: AI Model Validation, AI-VAL-001–004.)
- **Tolerate short delivery failures.** A durable outbox and stable event identity let the engine retry without losing its queued item or duplicating the backend incident. (Paper: Ch. 3, “AI Engine Layer” and Table 11.)
- **Keep the backend responsive on the local machine.** ASGI and WSS support persistent alert connections, while SQLite WAL fits local dashboard reads alongside event and telemetry writes. (Paper: Ch. 3, “Technical Scope” and “The Database.”)
- **Test without touching live agency operations.** MediaMTX reproduces a network stream path in isolated staging; the paper keeps actual VMS administration and live citywide deployment outside study scope. (Paper: Ch. 1, “Scope and Delimitations”; Ch. 3, “Test Environment.”)
- **Measure usability after real tasks.** SUS gives a consistent perception measure, and task observation and timing add evidence about how the operator journey went. (Paper: Ch. 3, “Usability Testing”; tracker: SUS Questionnaire and Usability Results.)

## 5. What changed since the 28 April defense

The current implementation has several mechanisms that this guide now names explicitly: a temporal evidence accumulator, idempotent AI event ingestion, a durable outbox, authenticated WebSocket delivery, SQLite WAL configuration, and a flag-and-restart restoration coordinator. The repository history records the accumulator port in 7d09a34, idempotent v2 ingest in 783bd74, durable outbox in 50372dc, authenticated WebSocket setup in dda00d4, SQLite connection policy in e0ac8b8, and the restore coordinator in d990815.

Use the current paper’s definitions and current tracker qualifications when explaining these terms. The current local source set does not establish a term-by-term wording comparison with the version shown on 28 April, so avoid inventing an older definition or result.

## 6. Limits and honest caveats

- **mAP is qualified evidence.** The tracker records mAP@0.50 = 0.956 as an archival validation-split result for epoch50; the original split was not rerun, and frame-level incident leakage is disclosed. It is not independent operational detection accuracy. (Tracker: AI Model Validation, AI-VAL-001.)
- **Event evidence is descriptive.** The current run records overall event recall 8/16, standard 8/10, hard 0/6, and 3 false positives over 11.0 clean minutes (0.27 FP/min). The tracker marks these as descriptive and does not set an event-recall or FP/min acceptance threshold. (Tracker: AI Model Validation, AI-VAL-002–004.)
- **The corpus is limited.** Seventeen clips were evaluated, but the tracker does not claim an untouched post-selection test set and notes uncertainty about incident independence. One negative clip does not establish a deployment-wide false-alarm rate. (Paper: Ch. 1, “Definition of Terms”; tracker: AI Model Validation, AI-VAL-004 and AI-VAL-007.)
- **Latency terms have different endpoints.** Inference latency is a model-processing measure. The 25-second objective ends at a verified operator decision, not dispatch or arrival of emergency services. (Paper: Ch. 1, “Objectives of the Study” and “Scope and Delimitations.”)
- **Usability evidence has a small participant set.** The tracker records 4 SUS responses, a mean of 89.375, and a criterion of 68; this describes those test participants and does not establish the experience of every operator. (Tracker: SUS Questionnaire, rows 11–19.)
- **Some terms describe a target or literature, not a measured deployment.** The 87°C thermal-throttling value is literature context; Figure 33 is the proposed VLAN topology; MediaMTX simulates the VMS stream path; and the project evaluation used an isolated staging setup. (Paper: Ch. 2, “Performance Metrics and Hardware Trade-offs”; Ch. 3, Figure 33 and “Test Environment.”)
- **ADAS supports, but does not perform, dispatch.** The paper limits the system to operator review and decision support. It does not claim emergency dispatch, response-time improvement, or production-scale citywide readiness as measured outcomes. (Paper: Ch. 1, “Scope and Delimitations”; Ch. 5, “Recommendations.”)

## 7. Likely panel questions

**“If your mAP was 95.6%, why are you still reporting misses?”**

The tracker’s 0.956 mAP@0.50 is an archival validation-split result with frame-level incident leakage disclosed. Event-level scoring is separate: the current local-clip run records 8 of 16 collision events, and the tracker does not present that as an independent post-selection test estimate. (Tracker: AI Model Validation, AI-VAL-001–003.)

**“Why is your accumulator’s IoU 0.30 when the paper says IoU 0.50?”**

They serve different purposes. IoU 0.50 is the box-matching criterion for model validation; IoU 0.30 links neighboring candidate boxes so evidence can accumulate across frames. (Paper: Ch. 3, “Inference and Temporal Event Formation.”)

**“How is RTSP different from WSS?”**

RTSP carries incoming video from a configured source to the AI engine; MediaMTX simulated that network-stream path in isolated testing. WSS carries backend alert and camera-state events to the dashboard after the engine has produced them. (Paper: Ch. 3, Figure 2 and “Test Environment.”)

**“What happens if the same alert is sent twice?”**

The AI engine reuses the same source event identifier when it retries a queued event. The backend recognizes that identifier and returns the existing incident, so it does not insert or broadcast a duplicate. (Paper: Ch. 1, “Idempotency”; code: backend/app/services/incidents.py:124.)

**“Why not let the AI decide whether an accident happened?”**

The model raises a candidate; the operator reviews the snapshot and confirms or dismisses it. This keeps an authorized person responsible for the incident decision and addresses automation bias. (Paper: Ch. 2, “HITL Approaches in Automated Surveillance”; Ch. 3, Figure 3.)

**“Does the 0.27 FP/min result mean operators will get that many false alerts in service?”**

It means 3 false events across 11.0 minutes of clean footage in the recorded run. The tracker marks the rate descriptive, with no FP/min threshold, so it should not be presented as a deployment-wide alert rate. (Tracker: AI Model Validation, AI-VAL-004.)

**“What does an SUS mean of 89.375 prove?”**

It is the mean perceived-usability score from 4 participants after their test journeys, above the tracker’s criterion of 68. It supports the usability finding for that staging evaluation, not a claim about every future user. (Tracker: SUS Questionnaire, rows 11–19.)

**“Is 25 seconds your inference latency?”**

No. Inference latency measures the detector’s processing time for a frame; the 25-second objective runs from when a collision is visible on camera to a verified operator decision. (Paper: Ch. 1, “Objectives of the Study”; “Inference Latency.”)

## 8. Cram summary

- **mAP and IoU:** mAP@0.50 is frame-level detection evidence; IoU measures box overlap. The tracker qualifies the validation result and reports event behavior separately.
- **The two network directions:** RTSP brings video into the AI engine; WSS delivers backend events to the dashboard.
- **The detection path:** YOLO proposes boxes; the per-camera temporal accumulator requires persistent spatial evidence before it raises an event.
- **Human authority:** Operators verify, dismiss, and clear. The system does not dispatch responders.
- **Retry safety:** The durable outbox preserves events; idempotency prevents the same retried event becoming duplicate incidents.
- **Local persistence:** SQLite WAL supports the dashboard and event-write workload; audited changes keep an accountable trail.
- **Know the limits:** mAP is not event recall, FP/min is descriptive for the tested clips, and SUS describes the small participant set.
- **Test framing:** MediaMTX and the VLAN drawing are part of isolated or target topology explanations; neither is evidence of a live citywide deployment.
