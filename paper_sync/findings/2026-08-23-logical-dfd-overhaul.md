---
section: "Data Flow Diagram (DFD), Figures 5-6"
page/s: "99"
required_revision: "Replace the current DFD narrative and Figures 5-6 with the new logical DFD"
notes: "Two new editable Lucidchart documents: Context Level (0) and Level 1. Supersedes the DFD portions of tracker items 0.11, 2.1, and 2.4 where applicable."
status: "Not started"
assigned_to: "Enjey, Daniboy"
synced: false
---

## WHERE

Live Google Doc: `Group7_Capstone Project Defense Document - ITCAPROJ1`, tab
`__main__`, section `Data Flow Diagram (DFD)`, page 99. The current text and
Figure 5/6 captions were read on 2026-08-24. The replacement diagrams are two
independently created, editable Lucidchart documents:

- [ADAS — Logical DFD — Context Level (0)](https://lucid.app/lucidchart/2411f766-8c85-4f0f-b3c8-c1204e8d03e2/edit)
- [ADAS — Logical DFD — Level 1](https://lucid.app/lucidchart/2b316ba3-9396-4319-ba5d-499dff750ea5/edit)

This finding is a local proposal. A human must apply the replacement text and
figures to the defense document and update the live audit tracker.

## OLD

> Context Level. Figure 5 establishes the operational boundaries of the system by representing the entire platform as a single process interacting with three distinct external entities. The primary data source is the CCTV System, which maintains a continuous input-output relationship with the system by providing live video streams in response to specific stream requests. The HITL architecture is primarily facilitated through the Operator entity, who supplies critical inputs such as login credentials, verification decisions for AI-flagged incidents, camera configuration data, report export filters, and alarm preferences. In return, the system provides the Operator with real-time accident alerts alongside auditory alarms, historical analytics, system health telemetry, and AI performance metrics.

**Figure 5**

**Context Level DFD**

> The Administrator entity serves as the secondary human actor, focusing on higher-level system governance and security. While the Administrator inherits the data outflows provided to the Operator, the diagram highlights the unique administrative data loop where the Administrator provides user management data and receives comprehensive user directories and audit logs. This centralized structure ensures that all localized edge computing tasks, including AI inference and database management, remain isolated within the system process while maintaining clear, secure communication channels with the Lipa CDRRMO’s infrastructure and personnel.

> Level 1. Figure 6 illustrates the internal decomposition of the system, expanding the single process from the context level into six primary sub-processes supported by four localized data stores. This level of detail establishes the functional relationships between the user roles, the AI detection engine, and the underlying database architecture. The Authenticate and Authorize Session (1.0) process serves as the entry point for both Operators and Administrators, validating credentials against the User Data Store (D1) to establish role-based access control (RBAC).

**Figure 6**

**Level 1 DFD**

> The core technical pipeline begins with Ingest Video and Execute AI Inference (2.0), which retrieves live RTSP streams from the external CCTV infrastructure and references the Camera Data Store (D2) for configuration metadata. When a collision is identified, the payload is transmitted to the Manage Incident Alerts (3.0) process. This process serves as the hub for the Human-in-the-Loop (HITL) workflow, recording initial detections in the Detection Log Data Store (D3) and pushing real-time WebSocket alerts and auditory alarms to the Operator. The Operator’s subsequent verification decisions are routed back through this process to update the incident status in the database.

> Parallel to the detection pipeline, Manage Camera Configurations (4.0) allows Operators to update the Camera Data Store (D2), which dynamically informs the stream requests sent to the VMS. For long-term oversight, Process Analytics and Hardware Telemetry (5.0) pulls historical records from the Detection Log (D3) and hardware metrics from the System Health Data Store (D4) to generate the visualizations and reports requested by the Operator. Finally, the Administer User Directory (6.0) process remains isolated for Administrator use, facilitating the management of user account profiles and security credentials within the User Data Store (D1). Together, these processes ensure a balanced flow of information that maintains both real-time responsiveness and administrative integrity.

## NEW

Replace the current DFD narrative and Figures 5-6 with the two new Lucidchart
diagrams. Use the following narrative with exported images of the corresponding
Lucidchart documents.

### Context Level (0)

Figure 5 presents ADAS as one logical process interacting with three external
entities: `CCTV/VMS`, `Operator`, and `Administrator`. `CCTV/VMS` exchanges live
camera video and stream requests with ADAS. The Operator exchanges operational
requests—including credentials, settings, incident decisions, and queries—and
receives operational results, including access results, alerts, analytics,
health information, and help guidance. The Administrator exchanges unique
user-management, audit, and maintenance commands and receives corresponding
administrative results. Administrators also receive all Operator capabilities;
only the unique Administrator exchanges are drawn.

### Level 1 — Logical DFD

Figure 6 decomposes ADAS into seven logical processes:

- 1.0 Manage Identity, Access & Preferences
- 2.0 Manage Camera Configuration & State
- 3.0 Analyze Live Video & Detect Incidents
- 4.0 Coordinate Human Incident Response
- 5.0 Produce Analytics, Reports & Audit
- 6.0 Monitor & Maintain System Reliability
- 7.0 Provide Help & Guidance

The processes use seven logical data stores: D1 Identity & Access Data, D2
Camera State, D3 Incident & Evidence Data, D4 Audit Records, D5 Health &
Performance Data, D6 Reports & Recovery Artifacts, and D7 Help Knowledge Base.
The diagram shows the key loops explicitly: `CCTV/VMS` to and
from 3.0; 3.0 to 4.0 as incident events; 4.0 to 3.0 as incident-control state;
3.0 to 6.0 as telemetry; and both 5.0 and 6.0 to D6. Store arrows represent
logical reads and writes. No direct external-entity-to-store or store-to-store
flows are drawn.

The labels are logical and implementation-neutral. Protocols, vendors,
frameworks, endpoints, and physical deployment details are intentionally
omitted from these DFDs; they belong in the architecture and implementation
sections.

## JUSTIFICATION

The current DFD text is no longer an accurate decomposition of the system. It
describes six processes and four stores, omits the audit, health/performance,
recovery, and help-support responsibilities, uses implementation details such
as RTSP and WebSocket as logical flow labels, and does not show the bidirectional
AI/camera-state and incident-control relationships required by the current
system.

The replacement is grounded in the current repository. `README.md:9-11`
identifies the AI Engine, backend, and operator-facing frontend;
`README.md:38-64` identifies camera, incident, audit, report/export, help,
health, and maintenance/recovery subsystems; and `README.md:471-514` documents
the alert seam, self-blindfold behavior, audit trail, and operator/admin
responsibilities. The implementation evidence includes the bidirectional AI
seam in `backend/app/api/routes/internal.py:93-195`, incident persistence and
self-blindfold state changes in `backend/app/services/incidents.py:124-194`,
health/export/backup scheduling in `backend/app/main.py:180-278`, and the
help, audit, export, health, and maintenance routes under
`backend/app/api/routes/`.

The notation and balancing choices follow the supplied DFD research: a context
diagram has one process and its external exchanges; Level 1 decomposes that
process; processes and stores have meaningful input and output; and the
external exchanges remain balanced across levels. The two Lucidchart diagrams
were visually inspected and validated as follows:

- Context Level (0): 1 process, 3 external entities, 0 internal stores.
- Level 1: 7 processes, 7 stores, 3 external entities.
- Every Level 1 process and store has at least one incoming and one outgoing
  flow.
- There are no direct external-entity-to-store or store-to-store flows.
- The required directional loops and 5.0/6.0-to-D6 flows are present.
- Each Lucidchart document is separately editable and openable for direct
  review and revision in Lucidchart.

## PROPAGATION

- Defense document: replace the current DFD narrative and insert the new
  Lucidchart Context Level (0) diagram as Figure 5 and the new Lucidchart Level
  1 diagram as Figure 6.
- Figure captions and surrounding references: keep the Figure 5/6 numbering,
  but use the new page titles and the replacement narrative above.
- Architecture terminology: keep physical protocols and endpoint details in
  the architecture/implementation sections, not in these logical DFD labels.
- Tracker item 0.11: superseded for the DFD because D4 Audit Records is now
  explicitly present. The live tracker row remains human-maintained.
- Tracker item 2.1: superseded for its Level 1 DFD portion; its ERD and data
  dictionary corrections remain independently applicable.
- Tracker item 2.4: superseded for the old Figure 6 arrow depiction by the
  logical bidirectional/telemetry flows here. The precise
  `/api/internal/alert` and `/api/internal/heartbeat` wording remains applicable
  wherever the paper documents the physical AI/backend seam.
- No application code, API, or database schema changes are required by this
  finding.
- This finding does not edit the Google Doc or live tracker. After review, a
  human should apply the paper changes and record the applicable tracker
  resolutions.
