---
section: Deployment and Implementation
page/s: "pp. 187–191 (live PDF mapping observed 2026-09-16)"
required_revision: Replace completed-deployment claims with the current proof-of-concept state and a conditional adoption-and-procurement plan.
notes: The current three-device demonstration is separate from the unexecuted CDRRMO production target. Existing live tracker row 87 covers the three-device testing-environment correction; no new tracker row is proposed.
status: Applied and verified
assigned_to: Enjey
synced: 2026-09-16
---

## Changes

### 1. Defense paper — Chapter 4, Deployment and Implementation, opening paragraph

Page/s: p. 187; native range `t.y7ms6bhlk4qn:243326–243809`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the opening paragraph immediately after the `Deployment and Implementation` heading
Preserve: the section heading, surrounding Chapter 4 structure, and the distinction between deployment planning and evaluation
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> The deployment phase transitions the system from a controlled development environment into a fully operational edge-computing solution within the Lipa CDRRMO. As established in the system architecture, the deployment is strictly localized; the enterprise-grade inference server (equipped with NVIDIA L4 GPUs) would be physically installed within the command center and integrated directly into the agency's existing CCTV VLAN to ensure zero-latency communication with the Dahua VMS.

#### NEW

If ADAS were adopted by the Lipa CDRRMO and the proposed production hardware were procured, the following would be the proposed deployment and implementation plan. The system would then be deployed as a localized edge-computing solution within the command center, subject to CDRRMO authorization, infrastructure readiness, and completion of the required validation and acceptance activities.

#### Evidence

The live paragraph was re-read at the native range above and mapped to printed p. 187 in the current 239-page PDF export. The repository's deployment decision states that the Linux edge server is what production would be, not a verified deployment (`docs/archive/be_audit/README.md:65-67`). The validation plan identifies the production target as separate from the single-laptop test environment and says the differences do not establish production-scale claims (`docs/validation/test-execution-validation-plan.md:281-296`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): The deployment phase [[transitions the system ... into a fully operational edge-computing solution within the Lipa CDRRMO]]. As established in the system architecture, the deployment is strictly localized; the [[enterprise-grade inference server]] would be [[physically installed within the command center and integrated directly into the agency's existing CCTV VLAN]] to ensure [[zero-latency communication with the Dahua VMS]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 2. Defense paper — Chapter 4, Deployment and Implementation, current evaluation arrangement

Page/s: p. 187; native range `t.y7ms6bhlk4qn:243809–243967`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the paragraph introducing the implementation strategy
Preserve: the section sequence and the transition into Installation and Configuration Procedures
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> To ensure a seamless integration that does not disrupt ongoing emergency monitoring operations, the implementation follows a structured, multi-step strategy.

#### NEW

To support an orderly adoption that does not disrupt ongoing emergency monitoring operations, the implementation would use a controlled, multi-step strategy. The sequence would coordinate network preparation, system installation, integration, validation, training, and handover.

#### Evidence

The three-device topology and port boundary are documented in `docs/operations/VMS_SIMULATOR_SETUP.md:1-45`. The test plan records the researcher-controlled Windows host, separate client, MediaMTX simulation, application stack, and HTTPS/WSS test arrangement (`docs/validation/test-execution-validation-plan.md:130-171`). The live Chapter 4 results also describe the Linux VMS, Windows ADAS host, and browser-only operator laptop at native range `250313–250329`.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): To ensure a [[seamless integration]] that does not disrupt [[ongoing emergency monitoring operations]], the implementation [[follows]] a structured, multi-step strategy.

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 3. Defense paper — Installation and Configuration Procedures, introduction

Page/s: p. 188; native range `t.y7ms6bhlk4qn:244009–244112`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the sentence below `Installation and Configuration Procedures`
Preserve: the subsection heading and the order of the listed procedures
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> The physical and software installation is executed in a strict sequence to guarantee system stability:

#### NEW

The physical and software installation would follow a controlled sequence covering hardware and network preparation, operating-system and GPU-runtime setup, application installation, VMS authorization, validation, and handover:

#### Evidence

The current repository separates the reusable setup procedures from the production target: the remote-VMS guide is a three-device simulator runbook (`docs/operations/VMS_SIMULATOR_SETUP.md:1-18`), while the validation plan labels Linux/rack hardware and the agency VMS as production-target differences (`docs/validation/test-execution-validation-plan.md:281-296`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): The physical and software installation [[is executed]] in a strict sequence to [[guarantee system stability]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 4. Defense paper — Installation and Configuration Procedures, Hardware & Network Initialization

Page/s: p. 188; native range `t.y7ms6bhlk4qn:244112–244443`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Hardware & Network Initialization` paragraph
Preserve: the target-production server concept, the operator-access requirement, and the nearby environment/application paragraphs
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Hardware & Network Initialization. The edge server is rack-mounted and connected to the command center's core aggregation switches. IT administrators assign a static IP address within the restricted CCTV VLAN, establishing the necessary cross-VLAN routing rules to allow standard Operator workstations to access the web dashboard.

#### NEW

The production network design would use agency-approved VLANs and routing policies to separate management, video/VMS, camera, and operations traffic. Before deployment, CDRRMO IT would confirm the as-built topology, VLAN IDs, IP ranges, gateways, switch and uplink capacity, firewall rules, and authorized DSS Pro RTSP endpoint. The system would permit only the required flows between the ADAS server, VMS, and operator workstations. Exact VLAN assignments, ports, addresses, and routing technology would be finalized through an agency network survey and documented in the approved as-built diagram.

#### Evidence

The proposed VLAN names and target segmentation are recorded in the live paper's Deployment Architecture section and the current repository comparison (`docs/validation/test-execution-validation-plan.md:281-296`). The paper's exact VMS/camera placement remains an agency design input; the repository's current runbook records the flat Globe LAN, reserved addresses, and service boundary (`docs/operations/VMS_SIMULATOR_SETUP.md:30-61`). Its flow and restriction are explicit: TCP RTSP 8554 is reachable only from Windows ADAS, while TCP 8000 and 5173 serve the operator (`docs/operations/VMS_SIMULATOR_SETUP.md:33-45`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): [[The edge server is rack-mounted and connected to the command center's core aggregation switches]]. IT administrators [[assign a static IP address within the restricted CCTV VLAN]], establishing the necessary [[cross-VLAN routing rules]] to allow [[standard Operator workstations]] to access the web dashboard.

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 5. Defense paper — Installation and Configuration Procedures, Environment Setup

Page/s: p. 188; native range `t.y7ms6bhlk4qn:244443–244670`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Environment Setup` paragraph
Preserve: the Linux/CUDA target and the application-installation sequence
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Environment Setup. The server is configured with an enterprise Linux distribution (Ubuntu Server LTS), followed by the installation of the NVIDIA CUDA Toolkit and cuDNN drivers necessary for hardware-accelerated deep learning.

#### NEW

Environment Setup. The proposed production server would run a 64-bit enterprise Linux distribution such as Ubuntu Server LTS. IT staff would install and validate the NVIDIA driver, CUDA, cuDNN, and TensorRT runtime for the selected GPU, then confirm that the model and engine operate at the approved production configuration. The deployment profile would use the default OpenCV software reader unless an explicitly validated GPU-resident NVDEC/CUDA path were selected for supported hardware.

#### Evidence

The validation plan records the tested inference/application host as a Windows 11 Lenovo laptop with an RTX 3050 Ti and 4 GB VRAM, while the rack-mounted Linux/eight-GPU system is the production target (`docs/validation/test-execution-validation-plan.md:130-138`, `281-296`). It explicitly qualifies capacity figures as demonstration-hardware-validated (`docs/validation/test-execution-validation-plan.md:617-621`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): [[The server is configured with an enterprise Linux distribution (Ubuntu Server LTS)]], followed by the installation of the [[NVIDIA CUDA Toolkit and cuDNN drivers]] necessary for [[hardware-accelerated deep learning]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 6. Defense paper — Installation and Configuration Procedures, Application Deployment

Page/s: p. 188; native range `t.y7ms6bhlk4qn:244670–244940`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Application Deployment` paragraph
Preserve: the localized stack, SQLite, Alembic, and WAL details
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Application Deployment. The system's software stack (FastAPI backend, React frontend, and AI engine) is deployed. The local SQLite database schema is initialized and version-controlled via Alembic migrations, with WAL enabled to handle high-frequency concurrent writes.

#### NEW

Application Deployment. The FastAPI backend, React/TypeScript frontend, Python AI engine, and local SQLite database would be installed as a localized application stack on the procured edge server. Database creation and upgrades would use Alembic migrations, with WAL enabled for concurrent access. The deployment would configure authenticated REST and WebSocket interfaces, audit logging, export jobs, health telemetry, backup and restore controls, secrets, storage roots, certificates, service ownership, and restart policy in accordance with CDRRMO IT requirements.

#### Evidence

The current application stack and WAL configuration are recorded in the validation plan (`docs/validation/test-execution-validation-plan.md:130-138`). Repository operations document the localized backend/frontend/AI flow and migration-based database setup (`docs/operations/README.md:350-365`). The scheduler wiring covers health sampling, export cleanup, daily backup, and catch-up (`backend/app/main.py:179-281`), while the maintenance routes and controls provide administrator-gated backup/restore operations (`backend/app/api/routes/maintenance.py:73-155`, `423-455`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): The system's software stack ([[FastAPI backend, React frontend, and AI engine]]) [[is deployed]]. The local SQLite database schema is [[initialized and version-controlled via Alembic migrations]], with [[WAL enabled to handle high-frequency concurrent writes]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 7. Defense paper — Installation and Configuration Procedures, VMS Integration

Page/s: p. 188; native range `t.y7ms6bhlk4qn:244940–245129`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `VMS Integration` paragraph
Preserve: the headless-client architecture, Dahua DSS Pro identity, passive RTSP request, and main-feed target
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> VMS Integration. The system is securely authenticated as a headless client to the Dahua DSS Pro server, configuring it to passively request the authorized main RTSP feed for AI processing.

#### NEW

VMS Integration. Following agency authorization, the AI engine would authenticate as a headless client to Dahua DSS Pro and request the authorized main RTSP feed for processing. CDRRMO IT would provide and validate the VMS credentials, connection details, permitted network paths, and camera-to-channel mapping before enabling the selected camera feeds.

#### Evidence

The live paragraph already names the authorized main RTSP feed, but its present-tense wording still implies completed VMS integration. The repository identifies Dahua DSS Pro as production-only configuration (`docs/operations/README.md:34-39`) and describes MediaMTX/prerecorded clips as the current RTSP simulation (`docs/validation/test-execution-validation-plan.md:134-138`, `292-296`). The remote-VMS runbook requires a configured remote template and explicit restart of the backend and AI engine after changing it (`docs/operations/VMS_SIMULATOR_SETUP.md:316-355`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): VMS Integration. The system [[is securely authenticated]] as a headless client to the Dahua DSS Pro server, configuring it to [[passively request the authorized main RTSP feed for AI processing]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 8. Defense paper — Phased Implementation Strategy, introduction

Page/s: p. 189; native range `t.y7ms6bhlk4qn:245129–245302`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the sentence introducing the phased rollout
Preserve: the phased strategy heading and the two phase paragraphs
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> To mitigate risk and prevent overwhelming both the hardware network and the human dispatchers, the system utilizes a Phased Rollout Strategy:

#### NEW

To reduce operational and technical risk, the proposed adoption would proceed in phases rather than immediately enabling the full authorized camera roster. Each phase would have documented entry, exit, rollback, and approval criteria:

#### Evidence

The repository's test plan requires capacity, reliability, security, alert-delivery, and operator-workflow testing before expanding beyond the simulated operating point (`docs/validation/test-execution-validation-plan.md:281-296`, `468-475`). The current lab runbook describes a fixed researcher-controlled three-device arrangement, not an agency rollout (`docs/operations/VMS_SIMULATOR_SETUP.md:1-18`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): To mitigate risk and prevent overwhelming both the [[hardware network]] and the [[human dispatchers]], the system [[utilizes]] a Phased Rollout Strategy.

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 9. Defense paper — Phased Implementation Strategy, Phase 1

Page/s: p. 189; native range `t.y7ms6bhlk4qn:245302–245558`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Phase 1 (Pilot Deployment)` paragraph
Preserve: the pilot-first intent and the requirement to measure performance before expansion
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Phase 1 (Pilot Deployment). The system is initially activated to monitor only 10 to 15 known high-risk intersections in Lipa City. This allows developers to monitor real-world GPU thermal loads, VRAM stability, and inference latency under live conditions.

#### NEW

Phase 1 (Controlled Pilot). After authorization and installation, a limited set of approved cameras would be enabled first. The pilot would verify stream access, per-camera inference rate, alert delivery, camera reconnection, resource usage, backup and restore, security, and operator workflow under the selected production conditions. Expansion would proceed only after the documented pilot acceptance criteria were met.

#### Evidence

The repository records ten simulated RTSP streams as the test operating point, not ten to fifteen live intersections (`docs/validation/test-execution-validation-plan.md:134-138`, `302-307`). The production/test comparison explicitly says the full citywide camera network is not demonstrated by the ten-stream test (`docs/validation/test-execution-validation-plan.md:288-296`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): Phase 1 (Pilot Deployment). The system [[is initially activated]] to monitor only [[10 to 15 known high-risk intersections in Lipa City]]. This allows developers to monitor [[real-world GPU thermal loads, VRAM stability, and inference latency under live conditions]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 10. Defense paper — Phased Implementation Strategy, Phase 2

Page/s: p. 189; native range `t.y7ms6bhlk4qn:245558–245885`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Phase 2 (Gradual Scaling)` paragraph
Preserve: the incremental-expansion concept and the agency camera-network boundary
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Phase 2 (Gradual Scaling). Once the pilot phase demonstrates sustained stability and the dispatchers become comfortable with the alert frequency, the system incrementally ingests additional camera streams until the entirety of the Lipa CDRRMO's 418-camera network is fully integrated and actively monitored by the edge server.

#### NEW

Phase 2 (Measured Expansion). Additional authorized cameras would be enabled in controlled increments after each expansion gate confirmed stable inference, alert delivery, resource use, stream reliability, and recovery readiness. The rollout would continue toward the agency's approved camera roster only when capacity and endurance evidence supported the next increment; any unresolved defect or failed threshold would pause expansion and trigger the agreed rollback or remediation procedure.

#### Evidence

The current validation plan distinguishes the ten-stream demonstration from the full citywide network and states that the citywide figure is not demonstrated by the test hardware (`docs/validation/test-execution-validation-plan.md:288-296`). The deployment decision likewise keeps the Linux edge server and any future rollout in the target-production register (`docs/archive/be_audit/README.md:65-67`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): Once the pilot phase [[demonstrates sustained stability]] and the dispatchers [[become comfortable with the alert frequency]], the system [[incrementally ingests additional camera streams]] until the entirety of the Lipa CDRRMO's [[418-camera network is fully integrated and actively monitored by the edge server]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 11. Defense paper — Data Migration and Initialization

Page/s: p. 189; native range `t.y7ms6bhlk4qn:245919–246383`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete `Data Migration and Initialization` paragraph
Preserve: the absence of legacy AI data and the need for controlled camera initialization
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Because this is a novel system, there is no legacy AI detection data to migrate. However, an initial data seeding process is required. During deployment, the geographical and technical metadata of the city's active cameras (i.e., camera names, channel IDs) are exported from the Dahua VMS and systematically migrated into the system database. This ensures the dashboard's camera management list accurately reflects the city's physical infrastructure from day one.

#### NEW

Before activation, agency IT would provide an authorized camera inventory, including names, locations, channel IDs, and approved VMS connection metadata. The deployment team would review and enter that information through a controlled onboarding procedure, initialize the Alembic-managed schema, validate camera mappings, and confirm the dashboard roster before enabling feeds. No legacy AI detection records would be assumed; any historical data transfer would require a separate approved migration plan.

#### Evidence

The live paragraph was re-read at the native range above and mapped to p. 189. Current operations describe schema provisioning through Alembic and camera records supplied by seed profiles (`docs/operations/README.md:332-365`). The repository contains no documented Dahua export/import onboarding procedure; Dahua values in the operations guide are production-only environment inputs (`docs/operations/README.md:20-39`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): Because this is a novel system, there is no legacy AI detection data to migrate. However, an initial data seeding process is required. During deployment, the geographical and technical metadata of the city's active cameras ([[are exported from the Dahua VMS and systematically migrated into the system database]]). This ensures the dashboard's camera management list accurately reflects the city's physical infrastructure [[from day one]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 12. Defense paper — User Training and Handover, introduction

Page/s: p. 189; native range `t.y7ms6bhlk4qn:246410–246562`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the sentence introducing the training program
Preserve: the User Training and Handover heading and the operator/administrator training roles
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Technical deployment must be paired with operational readiness. The following training program is defined to transition the system to the CDRRMO staff:

#### NEW

Technical deployment would be paired with operational readiness. Before handover, the team and CDRRMO would approve operating procedures, escalation boundaries, support ownership, access responsibilities, acceptance evidence, and the conditions for transferring system responsibility:

#### Evidence

The live UAT narrative says testing was conducted in an isolated local network prepared by system handlers and not on the CDRRMO live production server (`t.y7ms6bhlk4qn:239745–240239`). The repository's deployment decision identifies the target as a proof of concept and says no live handover is claimed (`docs/archive/be_audit/README.md:65-67`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): Technical deployment must be paired with [[operational readiness]]. The following training program is [[defined to transition the system to the CDRRMO staff]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 13. Defense paper — User Training and Handover, Operator Training

Page/s: p. 189; native range `t.y7ms6bhlk4qn:246562–246918`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Operator Training` paragraph
Preserve: the HITL workflow, reporting, telemetry, and 25-second target as a target rather than a guarantee
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Operator Training. Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts within the 25-second end-to-end target to reduce the notification gap and support faster initiation of manual dispatch procedures. They are also instructed on generating historical reports and reading system health telemetry.

#### NEW

Operator Training. Authorized operators would be trained on sign-in, camera and system-health review, alarm preferences, HITL alert confirmation or dismissal, snoozing and clearing, incident history, reporting, dashboard exports, and shift handover. Training would include the approved escalation procedure and use the 25-second end-to-end decision target as a performance objective. Competency would be confirmed through scenario-based acceptance activities before operational access was granted.

#### Evidence

The live UAT narrative records three operator participants and one administrator (`t.y7ms6bhlk4qn:239087–239745`) and says the sessions were conducted in an isolated local network rather than the production server (`t.y7ms6bhlk4qn:239745–240239`). The current paper's results record the 18.3-second estimated mean and 21.0-second estimated longest operator-decision times in that staging evaluation, not a production guarantee (`t.y7ms6bhlk4qn:239087–239461`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): [[Dispatchers are trained]] on the HITL workflow, specifically how to rapidly [[evaluate, confirm, or dismiss alerts within the 25-second end-to-end target]] to reduce the notification gap and support faster initiation of manual dispatch procedures. They are also instructed on [[generating historical reports and reading system health telemetry]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 14. Defense paper — User Training and Handover, Administrator Training

Page/s: p. 190; native range `t.y7ms6bhlk4qn:246918–247131`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Administrator Training` paragraph
Preserve: the administrator access-control responsibilities
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Administrator Training. Command center supervisors are trained exclusively on the secure user management directory, learning how to provision new dispatcher accounts, enforce access control, and manage passwords.

#### NEW

Administrator Training. Authorized administrators would be trained on user and permission management, audit review and export, system health and AI-performance review, backup selection, and the supervised restore workflow. Training would also cover credential handling, maintenance ownership, service restart, protected-storage checks, and recovery escalation. Administrative handover would occur only after the designated personnel completed the acceptance activities.

#### Evidence

The live UAT narrative records one administrator evaluating restricted functions including AI performance, user management, backup/restoration, and audit review (`t.y7ms6bhlk4qn:239461–239745`). It also records that the system handlers prepared the isolated environment and test materials (`t.y7ms6bhlk4qn:238686–239087`), which is not a production handover.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): Command center supervisors [[are trained exclusively]] on the secure user management directory, learning how to [[provision new dispatcher accounts, enforce access control, and manage passwords]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 15. Defense paper — Maintenance and Support Plan, introduction

Page/s: p. 190; native range `t.y7ms6bhlk4qn:247160–247279`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the sentence introducing the maintenance protocol
Preserve: the Maintenance and Support Plan heading and its infrastructure, model-update, and recovery subsections
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> To guarantee the long-term viability of the command center solution, a structured maintenance protocol is established:

#### NEW

To support long-term operation, CDRRMO would approve a maintenance and support plan covering ownership, schedules, external storage, monitoring responsibilities, service supervision, cybersecurity, and model-update governance before production activation:

#### Evidence

The repository documents administrator backup/restore controls, platform-specific maintenance helpers, protected-first/local-degraded storage, and a scheduled daily restart/backup split (`docs/operations/README.md:385-422`). These capabilities are implemented in the prototype but do not establish a CDRRMO production service.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): To guarantee the [[long-term viability of the command center solution]], a structured maintenance protocol [[is established]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 16. Defense paper — Maintenance and Support Plan, Infrastructure Monitoring

Page/s: p. 190; native range `t.y7ms6bhlk4qn:247279–247471`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Infrastructure Monitoring` paragraph
Preserve: hardware/resource monitoring as a production responsibility and the telemetry concept
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Infrastructure Monitoring. Continuous tracking of system-wide hardware telemetry to proactively identify and mitigate performance bottlenecks, resource exhaustion, and critical system errors.

#### NEW

Infrastructure Monitoring. The production deployment would collect and expose periodic host/GPU and AI telemetry, including utilization, uptime, latency, and processing rate, through the System Health surface. Assigned staff would review these indicators, service logs, stream status, disk space, and backup status against agreed thresholds, document incidents, and escalate resource or service failures before expanding the monitored camera roster.

#### Evidence

The application schedules health sampling, raw persistence, rollups, and pruning when the scheduler is enabled (`backend/app/main.py:179-217`). The current operations guide describes System Health as a runtime surface and distinguishes application telemetry from deployment-scale claims (`docs/operations/README.md:332-351`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): [[Continuous tracking of system-wide hardware telemetry]] to proactively identify and mitigate [[performance bottlenecks, resource exhaustion, and critical system errors]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 17. Defense paper — Maintenance and Support Plan, AI Model Retraining

Page/s: p. 190; native range `t.y7ms6bhlk4qn:247471–247936`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `AI Model Retraining (Mitigating Data Drift)` paragraph
Preserve: the data-drift rationale and the need for local evidence in future model work
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> AI Model Retraining (Mitigating Data Drift). As environmental conditions change or new vehicles enter the local roadways, the YOLO model may experience "data drift." A scheduled maintenance plan includes periodically exporting the locally validated incident snapshots (True Positives and False Positives categorized by the Operators) to retrain and refine the model weights, continuously improving the AI's accuracy specifically for Lipa City's traffic conditions.

#### NEW

AI Model Updates. As environmental conditions change or new vehicles enter local roadways, the model could experience data drift. An approved model-update process would require authorized snapshot and label curation, incident-separated retraining and evaluation, review of hard-scene performance and false positives, versioned model and engine deployment, documented acceptance criteria, and rollback procedures before replacing the approved checkpoint or TensorRT engine.

#### Evidence

The current paper and repository contain model/evaluation artifacts and AI-performance review, but no implemented automatic retraining pipeline. The validation plan requires incident-separated interpretation and labels the test data and capacity evidence as bounded to the demonstration environment (`docs/validation/test-execution-validation-plan.md:300-307`, `613-621`). The current model/engine is a selected deployment artifact, not an automatically refreshed production model (`docs/operations/README.md:80-90`).

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): As environmental conditions change or new vehicles enter the local roadways, the YOLO model may experience "data drift." A [[scheduled maintenance plan]] includes [[periodically exporting the locally validated incident snapshots (True Positives and False Positives categorized by the Operators)]] to retrain and refine the model weights, [[continuously improving the AI's accuracy specifically for Lipa City's traffic conditions]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

### 18. Defense paper — Maintenance and Support Plan, Disaster Recovery Protocols

Page/s: pp. 190–191; native range `t.y7ms6bhlk4qn:247936–248874`, observed 2026-09-16.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Disaster Recovery Protocols` paragraph
Preserve: the recovery purpose, protected/local storage distinction, offline restore, rollback, and operational-responsibility boundary
Comment target: the complete replacement paragraph; resolve the native range after replacement

#### OLD

> Disaster Recovery Protocols. To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually retrieving a validated database backup and its associated visual snapshots from the system's generated maintenance archive, preferring the explicitly configured protected external storage when it is available and using the local degraded archive otherwise. Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

#### NEW

Disaster Recovery and Scheduled Maintenance. The deployment would use authenticated backup and restore controls, protected-storage-first backup with a local degraded fallback, an independently supervised offline restore coordinator, and platform-specific restart helpers. CDRRMO IT would configure the daily restart schedule, in-application daily backup and catch-up, protected storage, retention, restore drills, service supervision, and recovery responsibilities. The production acceptance plan would verify readiness, AI-heartbeat recovery, database integrity, and rollback behavior before operational handover.

#### Evidence

The current operations guide states that backup/archive try protected roots first and fall back to local degraded roots, that Windows wraps the backup/restore/restart lifecycle, and that Linux parity is reviewed but unverified on the Windows workstation (`docs/operations/README.md:396-412`). It also identifies the Windows Scheduled Task for daily restart and the in-app scheduler with hourly catch-up for daily backup (`docs/operations/README.md:414-422`). The implementation owns scheduled backup and catch-up in `backend/app/main.py:248-281`; the independently supervised restore coordinator and offline restore boundary are documented in `backend/app/maintenance/restore.py:1-13` and `backend/app/maintenance/coordinator.py:1-7`.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement paragraph

Previous (marked, intentionally non-verbatim): To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual [["Bi-Annual Restore Drill"]]. This proactive maintenance protocol involves [[manually retrieving a validated database backup and its associated visual snapshots from the system's generated maintenance archive]] and requires supervisors to [[deploy this backup into a secure, localized staging environment entirely isolated from the production network]]. This drill [[ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency]].

Codex ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN

Done by Codex.

## Scope notes

- The existing live `ADAS_Paper_Audit_Tracker` row 87 already covers the three-device testing-environment correction for `Testing and Validation` pp. 187–191. This finding does not propose a second tracker row or a tracker write.
- Chapter 3 `Project Development Model`, `Deployment Architecture`, and the Phase 5 timeline table contain separate related sites, including pending overclaim and milestone findings. They are not included in this Chapter 4 section-sized manifest.
- The current live Doc contains six tabs. Only `__main__` / `t.y7ms6bhlk4qn` is in scope; no legacy test-case or appendix tab is changed.

## Application status

The approved blocks were applied to the live `Group7_Capstone Project Defense Document - ITCAPROJ2` in `__main__` / `t.y7ms6bhlk4qn`. The final semantic-readback revision was `ANLCKQkgqM2ZPHwd9a0kn0dQJ21qFxWX-SU8G2Ks5FimhG2sHgh3NG6B5C-yFHSQIkid-TKk4cKGikK-GcM3hdotoD-22NnGXnji50jEyok`.

All 18 NEW passages were re-read and occurred exactly once in the intended tab; all 18 OLD passages were absent. The 18 attached comments were read back as open comments with unique non-empty anchors, the expected package ID, the expected quoted NEW paragraph, and the required `Done by Codex.` ending. Comment IDs and anchors were verified in the live readback.

Verified comment IDs and anchors by block: 1 `AAACAmTG_m4` / `kix.1aptd2fdyrgh`; 2 `AAACAmTG_m8` / `kix.kk5gtmiy1lk`; 3 `AAACAmTG_nA` / `kix.zgjzdw98znj1`; 4 `AAACAmTG_nE` / `kix.esconxu1qtlr`; 5 `AAACAmTG_nI` / `kix.xgj1gek3x2`; 6 `AAACAmTG_nM` / `kix.poveeyltambj`; 7 `AAACAmTG_nQ` / `kix.tim6k49fd0d5`; 8 `AAACAmTG_nU` / `kix.i54tfeh6ir82`; 9 `AAACAmTG_nY` / `kix.ymcxvbtpbjmn`; 10 `AAACAmTG_nc` / `kix.m8m0lnetcpd`; 11 `AAACAmTG_ng` / `kix.e3rn6m94rk6m`; 12 `AAACAmTG_nk` / `kix.s88smhbn12rl`; 13 `AAACAmTG_no` / `kix.lmmydz455lkk`; 14 `AAACAmTG_ns` / `kix.sel6fx6d6hzm`; 15 `AAACAmTG_nw` / `kix.es5o2vh847nt`; 16 `AAACAmTG_n0` / `kix.t3pyp3212yrq`; 17 `AAACAmTG_n4` / `kix.9zpvurijpltk`; 18 `AAACAmTG_n8` / `kix.nzbpz7vvp1mc`.

A post-write PDF export was successfully fetched as a 20,631,461-byte user-scoped file reference, but no local materialized path was returned. Connector semantic verification passed; rendered PDF page re-rasterization and visual inspection after the write remain unavailable in this runtime.

## Approval / sync ledger

Package ID: PS-20260916-DEPLOYMENT-IMPLEMENTATION-PLAN
Approval source: User message "okay apporoved for writing" on 2026-09-16; approves Defense paper blocks 1–18 and their attached `Previous:` comments. Block 4 uses the user-supplied agency network-survey wording.

| Target              | Approved scope                                                           | Applied/read back                                                                           | Skipped/pending             | Blocked |
| ------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | --------------------------- | ------- |
| Defense paper       | blocks 1–18 and their attached comments                                  | Yes — text, old-text absence, exact NEW occurrences, and all 18 anchored comments read back | None                        | —       |
| Tracker Sheet       | Not applicable; existing live row 87 is preserved                        | —                                                                                           | no new tracker row proposed | —       |
| Standalone comments | Not applicable; all proposed comments are attached to paper replacements | —                                                                                           | —                           | —       |
