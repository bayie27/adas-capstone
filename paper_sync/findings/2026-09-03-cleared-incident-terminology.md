---
section: Definition of Terms, FR/NFR, Use Cases, Data Dictionary, Wireframes
page/s: "unconfirmed; native ranges recorded below and rendered PDF mapping remains unavailable"
required_revision: Replace active Resolved/Resolve incident terminology with Cleared/Clear.
notes: "Breaking cross-stack rename: Cleared is the only true-positive terminal status; /clear and ALERT_CLEAR are the active contracts. The old terms in this finding remain only as quoted historical text or migration input."
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Definition of Terms, “Detection Status”

Page/s: TOC p. 17 hint; native range `24525–24835`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The verification state attached to every incident record, progressing through Unverified upon automated detection, Ongoing once an operator confirms a genuine collision, Resolved once the scene has been cleared, and Dismissed where the detection is judged a false positive or a confirmation is later corrected.

#### NEW

The verification state attached to every incident record, progressing through Unverified upon automated detection, Ongoing once an operator confirms a genuine collision, Cleared once the scene has been cleared, and Dismissed where the detection is judged a false positive or a confirmation is later corrected.

#### Evidence

The live paper paragraph at native range `24525–24835` still names the old terminal status. The active enum is `DetectionStatus.CLEARED = "Cleared"` (`backend/app/models/enums.py:41–45`), and the model CHECK permits `Cleared` (`backend/app/models/detection.py:25–31`).

#### Proposed comment (same gate as associated replacement)

Previous: Resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 2. Defense paper — Definition of Terms, “Human-in-the-Loop (HITL)”

Page/s: TOC p. 19 hint; native range `28067–28309`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The operational framework in which the AI performs detection and triage while a human operator retains sole authority to confirm, dismiss, or resolve every incident, ensuring that no emergency dispatch proceeds on unverified machine judgment.

#### NEW

The operational framework in which the AI performs detection and triage while a human operator retains sole authority to confirm, dismiss, or clear every incident, ensuring that no emergency dispatch proceeds on unverified machine judgment.

#### Evidence

The live definition uses the old action verb at native range `28067–28309`. The backend exposes the transition as `POST /api/alerts/{log_id}/clear` (`backend/app/api/routes/alerts.py:611–627`) and maps it to `ALERT_CLEAR` (`backend/app/services/incidents.py:36–41`).

#### Proposed comment (same gate as associated replacement)

Previous: resolve

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 3. Defense paper — FR-11 True Positive Handling

Page/s: native range `95353–95808`, tab `t.y7ms6bhlk4qn`; TOC NFR/FR section hint p. 58; rendered PDF mapping unconfirmed

#### OLD

> If the user selects Confirm, the system shall update the incident database record to reflect an Ongoing status. The system must keep the AI detection for the camera paused throughout the incident. AI detection shall resume for that feed only after an operator manually updates the record as Resolved (indicating a cleared emergency) or Dismissed (indicating an aborted or misidentified event), thereby preventing duplicate alerts for the ongoing incident.

#### NEW

If the user selects Confirm, the system shall update the incident database record to reflect an Ongoing status. The system must keep the AI detection for the camera paused throughout the incident. AI detection shall resume for that feed only after an operator manually updates the record as Cleared (indicating a cleared emergency) or Dismissed (indicating an aborted or misidentified event), thereby preventing duplicate alerts for the ongoing incident.

#### Evidence

The paper’s FR-11 paragraph still names `Resolved`. The implementation’s legal transition is `Ongoing → Cleared` and the camera resumes only after the clear route commits (`backend/app/services/incidents.py:36–41`; `backend/app/api/routes/alerts.py:611–677`).

#### Proposed comment (same gate as associated replacement)

Previous: Resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 4. Defense paper — Use Case 5, step 8 / snooze outcome

Page/s: native range `114639–114844`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> The system maintains the camera's AI detection in a Paused state to prevent redundant alerts during the emergency. The snooze re-alarm is suppressed as the alert has been resolved within the snooze window.

#### NEW

The system maintains the camera's AI detection in a Paused state to prevent redundant alerts during the emergency. The snooze re-alarm is suppressed because the alert has already been handled within the snooze window.

#### Evidence

The sentence uses `resolved` for a general handled-state outcome rather than naming the active terminal status. The backend’s snooze path remains separate from `Cleared`; terminal transitions clear snooze fields in the same transaction (`backend/app/services/incidents.py:242–264`).

#### Proposed comment (same gate as associated replacement)

Previous: has been resolved within the snooze window

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 5. Defense paper — Use Case 5, step 9

Page/s: native range `114845–114950`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> Once the physical emergency is cleared, the user manually updates the ongoing accident log to “Resolved”.

#### NEW

Once the physical emergency is cleared, the user manually updates the ongoing accident log to “Cleared”.

#### Evidence

The live Use Case 5 step contains the old stored/API status. The current response model emits the stored status after `POST /api/alerts/{log_id}/clear` (`backend/app/api/routes/alerts.py:611–677`).

#### Proposed comment (same gate as associated replacement)

Previous: “Resolved”

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 6. Defense paper — Use Case 5, step 10

Page/s: native range `114951–115176`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> The system updates the database record with the status changed to “Resolved,” the user’s name as “Closed by,” and the exact “Time Resolve” timestamp, then immediately resumes active AI detection for that specific camera feed.

#### NEW

The system updates the database record with the status changed to “Cleared,” the user’s name as “Closed by,” and the exact “Time Cleared” timestamp, then immediately resumes active AI detection for that specific camera feed.

#### Evidence

The live step has both the old status and the old action-specific timestamp label. The implementation retains generic `closed_by`/`closed_at` fields but emits `Cleared`; the shared modal labels the terminal timestamp `TIME CLEARED` (`frontend/src/pages/detections/IncidentDetailModal.tsx:83–93`).

#### Proposed comments (same gate as associated replacements)

Previous: “Resolved,”

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: “Time Resolve”

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 7. Defense paper — Use Case 5, alternative flow 4a

Page/s: native range `115196–115393`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> 4a. User Proceeds Without Snoozing: If the user does not click "Snooze" and proceeds directly to review, the audible alarm continues to sound until the alert is resolved via "Confirm" or "Dismiss."

#### NEW

4a. User Proceeds Without Snoozing: If the user does not click "Snooze" and proceeds directly to review, the audible alarm continues to sound until the alert is handled via "Confirm" or "Dismiss."

#### Evidence

Confirm and dismiss are the actions that end the unverified alarm path; `Resolved`/`Cleared` is not an action available before confirmation. The frontend keeps this distinction in `Detections.tsx` and `IncidentDetailModal.tsx`.

#### Proposed comment (same gate as associated replacement)

Previous: the alert is resolved via

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 8. Defense paper — Use Case 5, alternative flow 4b

Page/s: native range `115394–115694`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> 4b. Snooze Timer Expires Before Resolution: If the configured snooze duration elapses and the alert has not been confirmed or dismissed, the system re-triggers the audible alarm for that specific camera's alert to prompt the user to act. The user may snooze again, after which a new countdown begins.

#### NEW

4b. Snooze Timer Expires Before an Operator Decision: If the configured snooze duration elapses and the alert has not been confirmed or dismissed, the system re-triggers the audible alarm for that specific camera's alert to prompt the user to act. The user may snooze again, after which a new countdown begins.

#### Evidence

The alternative flow describes an unverified snooze deadline, not the true-positive terminal status. Renaming the heading removes the old incident-resolution vocabulary while preserving the snooze behavior implemented in `backend/app/services/snoozes.py`.

#### Proposed comment (same gate as associated replacement)

Previous: Before Resolution:

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 9. Defense paper — Use Case 5, alternative flow 6a

Page/s: native range `115695–116064`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 78; rendered PDF mapping unconfirmed

#### OLD

> 6a. Immediate False Positive: The user identifies the alert as a false positive and clicks "Dismiss." The system updates the record status to "Dismissed," logs the user's name, clears the user interface alert, enforces a 1-minute AI detection cooldown on that specific camera before resuming detection, and suppresses the snooze re-alarm as the alert has been resolved.

#### NEW

6a. Immediate False Positive: The user identifies the alert as a false positive and clicks "Dismiss." The system updates the record status to "Dismissed," logs the user's name, clears the user interface alert, enforces a 1-minute AI detection cooldown on that specific camera before resuming detection, and suppresses the snooze re-alarm because the alert has been handled.

#### Evidence

This is the immediate false-positive path, which ends in `Dismissed`, not `Cleared`. The backend’s dismiss transition and cooldown ordering are unchanged by P28 (`backend/app/api/routes/alerts.py:551–609`).

#### Proposed comment (same gate as associated replacement)

Previous: has been resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 10. Defense paper — Use Case 8, analytics status population

Page/s: native range `121215–121358`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 83; rendered PDF mapping unconfirmed

#### OLD

> The system queries the database to aggregate historical records of verified accidents (specifically those with “Ongoing” or "Resolved” status).

#### NEW

The system queries the database to aggregate historical records of verified accidents (specifically those with “Ongoing” or "Cleared” status).

#### Evidence

Analytics now counts `DetectionStatus.ONGOING` and `DetectionStatus.CLEARED` in `_ACCIDENT_STATUSES` (`backend/app/api/routes/analytics.py:55–56`).

#### Proposed comment (same gate as associated replacement)

Previous: "Resolved” status

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 11. Defense paper — Use Case 8, dashboard KPI labels

Page/s: native range `121359–121461`, tab `t.y7ms6bhlk4qn`; TOC Use Cases hint p. 83; rendered PDF mapping unconfirmed

#### OLD

> The system then calculates and displays the global KPIs: Pending, Total Accidents, and Total Resolved.

#### NEW

The system then calculates and displays the global KPIs: Ongoing, Total Accidents, and Total Cleared.

#### Evidence

The live paper says `Pending` and `Total Resolved`, while the API response and dashboard use `ongoing`, `total_accidents`, and `total_cleared` (`backend/app/schemas/analytics.py:6–18`; `frontend/src/pages/Dashboard.tsx:257–266`).

#### Proposed comment (same gate as associated replacement)

Previous: Pending, Total Accidents, and Total Resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 12. Defense paper — Figure 3, Swimlane Diagram narrative

Page/s: native range `141166–141920`, tab `t.y7ms6bhlk4qn`; TOC Figure 3 hint p. 92; rendered PDF mapping unconfirmed

#### OLD

> Figure 3 illustrates how ADAS distributes tasks among the System, Operator, and Administrator during accident detection and verification. The System lane covers the automated flow, beginning with the reception of CCTV/VMS streams, AI-based frame analysis, possible collision detection, incident record creation, and dashboard alert delivery. The Operator lane represents the Human-in-the-Loop portion of the workflow, where the dispatcher reviews the alert snapshot, decides whether to confirm or dismiss the detection, monitors confirmed incidents, marks cleared incidents as resolved, and generates historical reports when needed. The Administrator lane shows the restricted account-management responsibilities assigned to authorized supervisory users.

#### NEW

Figure 3 illustrates how ADAS distributes tasks among the System, Operator, and Administrator during accident detection and verification. The System lane covers the automated flow, beginning with the reception of CCTV/VMS streams, AI-based frame analysis, possible collision detection, incident record creation, and dashboard alert delivery. The Operator lane represents the Human-in-the-Loop portion of the workflow, where the dispatcher reviews the alert snapshot, decides whether to confirm or dismiss the detection, monitors confirmed incidents, marks incidents as cleared, and generates historical reports when needed. The Administrator lane shows the restricted account-management responsibilities assigned to authorized supervisory users.

#### Evidence

The Figure 3 narrative still says that cleared incidents are “resolved.” The active UI and route use the terminal label `Cleared`, while the generic `closed_by` metadata remains intentionally unchanged.

#### Proposed comment (same gate as associated replacement)

Previous: marks cleared incidents as resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 13. Defense paper — Figure 4, Use Case Diagram overview

Page/s: native range `142483–142945`, tab `t.y7ms6bhlk4qn`; TOC Figure 4 hint p. 94; rendered PDF mapping unconfirmed

#### OLD

> Figure 4 defines the daily operational workflows of ADAS, demonstrating the interactions among dispatchers, system administrators, and the city’s physical camera infrastructure to facilitate real-time incident resolution, manage camera configurations, analyze data, and maintain secure access control. This operational structure is designed to maximize efficiency, mitigate operator cognitive load, and accelerate the Human-in-the-Loop (HITL) emergency response.

#### NEW

Figure 4 defines the daily operational workflows of ADAS, demonstrating the interactions among dispatchers, system administrators, and the city’s physical camera infrastructure to facilitate real-time incident clearance, manage camera configurations, analyze data, and maintain secure access control. This operational structure is designed to maximize efficiency, mitigate operator cognitive load, and accelerate the Human-in-the-Loop (HITL) emergency response.

#### Evidence

Figure 4 is the use-case surface for the incident action label. The implementation calls the true-positive terminal action `Clear` and the visible button `Cleared`; the figure itself therefore needs the separate redraw recorded below.

#### Proposed comment (same gate as associated replacement)

Previous: real-time incident resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 14. Defense paper — Figure 4, Human-in-the-Loop Collision Resolution narrative

Page/s: native range `144400–145612`, tab `t.y7ms6bhlk4qn`; TOC Figure 4 hint p. 94; rendered PDF mapping unconfirmed

#### OLD

> Human-in-the-Loop Collision Resolution. The central operational workflow begins with the external CCTV/VMS, which continuously Streams Camera Feed to the system. ADAS processes the incoming video and performs Detect Collision to identify potential vehicle collisions. When a potential collision is detected, the Operator performs Verify Accident Alert to determine whether the detection represents a genuine incident. The Operator may temporarily Snooze Audible Alarm when additional time is required to evaluate the alert. If the alert is confirmed, the system performs Confirm Accident and Set Ongoing Status, allowing the incident to remain actively monitored while preventing redundant alerts from the same camera. If the detection is determined to be a false positive, the Operator may Dismiss Accident, after which the system applies the appropriate cooldown behavior. Once the incident has been addressed, the Operator may Resolve Accident, with the system enforcing the required cooldown and supporting a Terminal Dismissal when an ongoing incident must be dismissed. These workflows ensure that AI detections are subject to human verification and that incident decisions are recorded for accountability.

#### NEW

Human-in-the-Loop Collision Clearance. The central operational workflow begins with the external CCTV/VMS, which continuously Streams Camera Feed to the system. ADAS processes the incoming video and performs Detect Collision to identify potential vehicle collisions. When a potential collision is detected, the Operator performs Verify Accident Alert to determine whether the detection represents a genuine incident. The Operator may temporarily Snooze Audible Alarm when additional time is required to evaluate the alert. If the alert is confirmed, the system performs Confirm Accident and Set Ongoing Status, allowing the incident to remain actively monitored while preventing redundant alerts from the same camera. If the detection is determined to be a false positive, the Operator may Dismiss Accident, after which the system applies the appropriate cooldown behavior. Once the incident has been addressed, the Operator may Clear Accident, with the system resuming the camera immediately and supporting a Terminal Dismissal when an ongoing incident must be dismissed. These workflows ensure that AI detections are subject to human verification and that incident decisions are recorded for accountability.

#### Evidence

The live Figure 4 narrative contains the old `Resolve Accident` use-case label. The route is now `/api/alerts/{log_id}/clear`, the audit action is `ALERT_CLEAR`, and a successful clear resumes an enabled camera immediately (`backend/app/api/routes/alerts.py:611–677`).

#### Proposed comments (same gate as associated replacements)

Previous: Human-in-the-Loop Collision Resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: may Resolve Accident

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: with the system enforcing the required cooldown

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 15. Defense paper — Table 11, `closed_by_id` description

Page/s: native range `152224–152344`, tab `t.y7ms6bhlk4qn`; TOC Data Dictionary/Table 11 hint p. 109; rendered PDF mapping unconfirmed

#### OLD

> Closure (closed_by_id): Populated only when the scene of an ongoing accident was officially cleared and marked resolved.

#### NEW

Closure (closed_by_id): Populated only when the scene of an ongoing accident was officially cleared and marked Cleared.

#### Evidence

The paper’s data-dictionary text uses the old terminal label. `closed_by_id` is intentionally retained for both `Ongoing → Cleared` and `Ongoing → Dismissed` correction transitions (`backend/app/services/incidents.py:242–264`).

#### Proposed comment (same gate as associated replacement)

Previous: officially cleared and marked resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 16. Defense paper — Table 11, `closed_by_id` foreign-key description

Page/s: native range `162939–163043`, tab `t.y7ms6bhlk4qn`; TOC Data Dictionary/Table 11 hint p. 109; rendered PDF mapping unconfirmed

#### OLD

> Foreign key linking the incident to the operator who officially closed or resolved the ongoing accident.

#### NEW

Foreign key linking the incident to the operator who officially closed or cleared the ongoing accident.

#### Evidence

The live data-dictionary description uses `resolved` as an action verb. The schema keeps the generic `closed_by_id` name by explicit P28 contract, while the clear action is recorded as `ALERT_CLEAR`.

#### Proposed comment (same gate as associated replacement)

Previous: closed or resolved the ongoing accident

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 17. Defense paper — Table 11, `closed_at` description

Page/s: native range `163126–163202`, tab `t.y7ms6bhlk4qn`; TOC Data Dictionary/Table 11 hint p. 109; rendered PDF mapping unconfirmed

#### OLD

> UTC timestamp when the incident was officially marked resolved or dismissed.

#### NEW

UTC timestamp when the incident was officially marked cleared or dismissed.

#### Evidence

The live description names the old terminal status. The implementation continues storing `closed_at` for both terminal paths, but the true-positive status is now `Cleared` (`backend/app/models/enums.py:41–45`).

#### Proposed comment (same gate as associated replacement)

Previous: officially marked resolved or dismissed

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 18. Defense paper — Dashboard wireframe narrative

Page/s: native range `175991–176584`, tab `t.y7ms6bhlk4qn`; TOC Dashboard/Wireframes hint p. 112; rendered PDF mapping unconfirmed

#### OLD

> The core data presentation consists of graphical reports and numerical summaries. A horizontal bar graph displays "Accident Frequency by Location," while a time-series line graph tracks "Peak Accident Times (24H)." Adjacent to these charts, three KPI cards summarize critical operational metrics. The "Ongoing" incidents card is emphasized with a darker visual weight to draw user attention, as unresolved emergencies require monitoring and immediate human verification to resume the AI detection for affected camera feeds. The remaining cards track cumulative accident and resolution volumes.

#### NEW

The core data presentation consists of graphical reports and numerical summaries. A horizontal bar graph displays "Accident Frequency by Location," while a time-series line graph tracks "Peak Accident Times (24H)." Adjacent to these charts, three KPI cards summarize critical operational metrics. The "Ongoing" incidents card is emphasized with a darker visual weight to draw user attention, as uncleared emergencies require monitoring and immediate human verification to resume the AI detection for affected camera feeds. The remaining cards track cumulative accident and clearance volumes.

#### Evidence

The live Dashboard narrative uses `unresolved` and `resolution` wording, and the associated Figure 10 screenshot must change its KPI label from `Total Resolved` to `Total Cleared`. The frontend renders `Total Cleared` and reads `total_cleared` (`frontend/src/pages/Dashboard.tsx:257–266`).

#### Proposed comments (same gate as associated replacements)

Previous: unresolved emergencies

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: resolution volumes

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 19. Defense paper — Figure 16, Detections tab purpose

Page/s: native range `182009–182348`, tab `t.y7ms6bhlk4qn`; TOC Figure 16 hint p. 117; rendered PDF mapping unconfirmed

#### OLD

> Figure 16 illustrates the detections interface, focusing on the Ongoing accidents view, which is accessed by selecting the "Detections" module from the left navigation sidebar. The primary purpose is to enable operators and administrators to continuously monitor actively verified collisions requiring scene clearance and final resolution.

#### NEW

Figure 16 illustrates the detections interface, focusing on the Ongoing accidents view, which is accessed by selecting the "Detections" module from the left navigation sidebar. The primary purpose is to enable operators and administrators to continuously monitor actively verified collisions requiring scene clearance and final clearing.

#### Evidence

The live Figure 16 narrative describes the true-positive terminal outcome as `final resolution`. The active Detections UI labels the corresponding action `Cleared` and the backend route is `/clear` (`frontend/src/pages/Detections.tsx:230–237`; `backend/app/api/routes/alerts.py:611–627`).

#### Proposed comment (same gate as associated replacement)

Previous: final resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 20. Defense paper — Figure 16, Ongoing tab narrative

Page/s: native range `182386–182778`, tab `t.y7ms6bhlk4qn`; TOC Figure 16 hint p. 117; rendered PDF mapping unconfirmed

#### OLD

> Aligned with the system's design language, the layout features a prominent page title and a descriptive subtitle for immediate functional context. Below the header, a tabbed navigation structure separates current emergencies ("Ongoing") from historical data ("Logs"). The "Ongoing" tab is set as the default view, ensuring users see critical, unresolved accidents when they access the module.

#### NEW

Aligned with the system's design language, the layout features a prominent page title and a descriptive subtitle for immediate functional context. Below the header, a tabbed navigation structure separates current emergencies ("Ongoing") from historical data ("Logs"). The "Ongoing" tab is set as the default view, ensuring users see critical, uncleared accidents when they access the module.

#### Evidence

The live narrative uses `unresolved` for the active Ongoing queue. The shared store treats `Dismissed` and `Cleared` as terminal and removes either from the active queue (`frontend/src/store/useAlertStore.ts:163–176`).

#### Proposed comment (same gate as associated replacement)

Previous: unresolved accidents

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 21. Defense paper — Figure 17, Ongoing Accident Details Modal narrative

Page/s: native range `184364–184647`, tab `t.y7ms6bhlk4qn`; TOC Figure 17 hint p. 118; rendered PDF mapping unconfirmed

#### OLD

> The interface features two large action buttons at the bottom, "Dismiss" and "Resolve", to ensure quick target acquisition. The "Resolve" button uses a high-contrast background to emphasize its role as the primary action required to resume automated AI detection for the camera feed.

#### NEW

The interface features two large action buttons at the bottom, "Dismiss" and "Cleared", to ensure quick target acquisition. The "Cleared" button uses a high-contrast background to emphasize its role as the immediate primary action required to resume automated AI detection for the camera feed.

#### Evidence

The shared `IncidentDetailModal` now renders a single immediate `Cleared` button for an Ongoing incident and calls `onClear` directly (`frontend/src/pages/detections/IncidentDetailModal.tsx:315–336`). No confirmation or warning UI was added.

#### Proposed comments (same gate as associated replacements)

Previous: "Dismiss" and "Resolve"

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: "Resolve" button

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

Previous: emphasize its role as the primary action required to resume

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 22. Defense paper — AI Pause Signal Handover narrative

Page/s: native range `221817–221962`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The backend successfully passes the "Pause" boolean flag to the isolated AI worker thread, which instantly ceases frame ingestion until resolved.

#### NEW

The backend successfully passes the "Pause" boolean flag to the isolated AI worker thread, which instantly ceases frame ingestion until the incident is cleared or dismissed.

#### Evidence

The paper’s handover text uses the old generic terminal verb. The backend’s self-blindfold remains active until a legal terminal transition; both `Cleared` and `Dismissed` resume an enabled camera according to the existing state machine.

#### Proposed comment (same gate as associated replacement)

Previous: until resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 23. Defense paper — Incident Action Audit test narrative

Page/s: native range `238633–238774`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The system records the Operator’s confirm, dismiss, resolve, or correction action with the user ID, affected incident, timestamp, and result.

#### NEW

The system records the Operator’s confirm, dismiss, clear, or correction action with the user ID, affected incident, timestamp, and result.

#### Evidence

The audit catalog now contains `ALERT_CLEAR` (`backend/app/models/audit.py:10–27`), and every successful incident transition records the catalog action in the same transaction (`backend/app/api/routes/alerts.py:488–677`).

#### Proposed comment (same gate as associated replacement)

Previous: resolve

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

## Readback follow-up — additional Defense paper sites

The 2026-09-04 post-write sweep found these additional active incident-terminology sites in
the Defense paper. They are part of the same approved Defense-paper scope and use the same
exact-span replacement/comment treatment. Generic technical uses of `resolve`, `resolved`, or
`resolution` remain intentionally unchanged.

### 24a. Defense paper — Table 11, `detection_status` description

Page/s: native range `162479–162560`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Incident lifecycle verification state (Unverified, Ongoing, Dismissed, Resolved).

#### NEW

Incident lifecycle verification state (Unverified, Ongoing, Dismissed, Cleared).

#### Evidence

The live Table 11 data-dictionary text still listed `Resolved`. The active enum and database
CHECK now use `Cleared` (`backend/app/models/enums.py:41–45`; `backend/app/models/detection.py:25–31`).

#### Proposed comment (same gate as associated replacement)

Previous: Resolved

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24b. Defense paper — Scope boundary incident actions

Page/s: native range `79322–79766`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The emergency-response boundary ends at alert presentation and operator decision-making, including the confirmation, dismissal, resolution, and review of incidents. Automated emergency-vehicle dispatch, routing, and inter-agency response coordination are explicitly excluded, as the CDRRMO’s established emergency response procedures for these activities are already operational and effective and therefore fall outside the scope of this study.

#### NEW

The emergency-response boundary ends at alert presentation and operator decision-making, including the confirmation, dismissal, clearance, and review of incidents. Automated emergency-vehicle dispatch, routing, and inter-agency response coordination are explicitly excluded, as the CDRRMO’s established emergency response procedures for these activities are already operational and effective and therefore fall outside the scope of this study.

#### Evidence

This sentence enumerates the operator incident actions. The active transition catalog uses clear/`ALERT_CLEAR` for the true-positive terminal action.

#### Proposed comment (same gate as associated replacement)

Previous: resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24c. Defense paper — System-testing workflow

Page/s: native range `87737–89048`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system’s ability to support the 25-second end-to-end collision-to-operator-decision workflow and faster initiation of manual dispatch or endorsement procedures. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### NEW

In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system’s ability to support the 25-second end-to-end collision-to-operator-decision workflow and faster initiation of manual dispatch or endorsement procedures. This quality assurance process also verifies the complete HITL incident-handling workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### Evidence

The live testing narrative uses `resolution` as the name of the HITL action workflow. The
implementation’s workflow is confirm, dismiss, clear, snooze, and their corresponding audit/event paths.

#### Proposed comment (same gate as associated replacement)

Previous: HITL resolution workflow

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24d. Defense paper — Dashboard requirement, resolution status

Page/s: native range `97716–97998`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The system shall provide a dashboard that summarizes past accident data. It shall display overall figures for the number of accidents and their resolution status, together with charts showing when and where accidents occur, and shall allow the user to filter and sort what is shown.

#### NEW

The system shall provide a dashboard that summarizes past accident data. It shall display overall figures for the number of accidents and their clearance status, together with charts showing when and where accidents occur, and shall allow the user to filter and sort what is shown.

#### Evidence

The dashboard now exposes `total_cleared` and `total_cleared_delta_pct`, with `Cleared` as the
true-positive terminal status (`backend/app/schemas/analytics.py:7–17`).

#### Proposed comment (same gate as associated replacement)

Previous: resolution status

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24e. Defense paper — Help Center requirement

Page/s: native range `98305–98672`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident resolution, general dashboard navigation guides, and frequently asked questions (FAQs).

#### NEW

The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident handling, general dashboard navigation guides, and frequently asked questions (FAQs).

#### Evidence

The help content now describes the `Cleared` action and the renamed clearing article/slugs, while
the module remains a general documentation surface.

#### Proposed comment (same gate as associated replacement)

Previous: incident resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24f. Defense paper — Audit-trail incident actions

Page/s: native range `98703–99476`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The system shall maintain an activity audit trail for critical user actions that affect incident verification, camera availability, official reporting, and account management. For Operators, the system shall record accident confirmation, dismissal, resolution, terminal dismissal correction, camera addition, camera editing, camera enabling or disabling, camera removal, report generation, and incident record export. For Administrators, the system shall record user account creation, account editing, account disabling or restoration, role changes, and password updates. The system shall also record successful and failed login attempts for both user roles. Each audit record must include the user ID, role, action performed, affected record, timestamp, and action result.

#### NEW

The system shall maintain an activity audit trail for critical user actions that affect incident verification, camera availability, official reporting, and account management. For Operators, the system shall record accident confirmation, dismissal, clearance, terminal dismissal correction, camera addition, camera editing, camera enabling or disabling, camera removal, report generation, and incident record export. For Administrators, the system shall record user account creation, account editing, account disabling or restoration, role changes, and password updates. The system shall also record successful and failed login attempts for both user roles. Each audit record must include the user ID, role, action performed, affected record, timestamp, and action result.

#### Evidence

The audit catalog now records `ALERT_CLEAR` for the Ongoing-to-Cleared transition. The generic
closure columns remain unchanged.

#### Proposed comment (same gate as associated replacement)

Previous: accident confirmation, dismissal, resolution, terminal dismissal correction

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24g. Defense paper — Snooze test wording

Page/s: native range `163365–163452`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Expiration UTC timestamp after which an unresolved snooze reactivates dashboard alerts.

#### NEW

Expiration UTC timestamp after which an active snooze reactivates dashboard alerts.

#### Evidence

The sentence describes the snooze lifecycle, not a persisted incident status. `active snooze`
keeps that meaning without using the retired incident terminology.

#### Proposed comment (same gate as associated replacement)

Previous: unresolved snooze

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24h. Defense paper — Snooze scenario alert state

Page/s: native range `224723–224812`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Snooze is active on an unresolved Camera A alert. The configured snooze duration expires.

#### NEW

Snooze is active on an uncleared Camera A alert. The configured snooze duration expires.

#### Evidence

The scenario refers to an open incident while snoozed. The active terminal vocabulary uses
`Cleared`, so an uncleared alert is the accurate state description.

#### Proposed comment (same gate as associated replacement)

Previous: unresolved Camera A alert

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24i. Defense paper — Operator incident-clearance verification heading

Page/s: native range `225087–225128`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Operator Incident Resolution Verification

#### NEW

Operator Incident Clearance Verification

#### Evidence

This is a test-narrative heading for the true-positive incident path; the active route and audit
action are `/clear` and `ALERT_CLEAR`.

#### Proposed comment (same gate as associated replacement)

Previous: Operator Incident Resolution Verification

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24j. Defense paper — Full true-positive verification heading

Page/s: native range `233862–233891`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Full True Positive Resolution

#### NEW

Full True Positive Clearance

#### Evidence

The heading names the Ongoing-to-Cleared true-positive path and should use the same vocabulary
as the state machine and event catalog.

#### Proposed comment (same gate as associated replacement)

Previous: Full True Positive Resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24k. Defense paper — Three-click verification action

Page/s: native range `235627–235772`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The Operator can successfully review a snapshot and execute a resolution ("Confirm" or "Dismiss") using a maximum of 3 mouse clicks per incident.

#### NEW

The Operator can successfully review a snapshot and execute a decision ("Confirm" or "Dismiss") using a maximum of 3 mouse clicks per incident.

#### Evidence

The cited actions in this sentence are Confirm and Dismiss, so `decision` is more precise than
the retired true-positive action noun.

#### Proposed comment (same gate as associated replacement)

Previous: execute a resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24l. Defense paper — Operator testing scope

Page/s: native range `240356–240608`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> Operators: Personnel responsible for monitoring the command center’s video wall. This group tested real-time HITL alert resolution, camera stream configuration, and historical data export functions, as operators are the primary users of these features.

#### NEW

Operators: Personnel responsible for monitoring the command center’s video wall. This group tested real-time HITL alert handling, camera stream configuration, and historical data export functions, as operators are the primary users of these features.

#### Evidence

The operator test scope covers the whole confirm/dismiss/clear handling path, not a separate
`resolution` action name.

#### Proposed comment (same gate as associated replacement)

Previous: real-time HITL alert resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24m. Defense paper — System-testing UI alert workflow

Page/s: native range `213768–214288`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> System Testing. System testing assessed the fully integrated application as a single cohesive entity. The objective was to validate the complete operational lifecycle and technical workflows from end to end prior to user deployment. This phase emphasized the execution of the uninterrupted HITL pipeline (from network video ingestion to UI alert resolution), the enforcement of RBAC routing protocols, and the validation of system-wide utility functions (e.g., historical data filtering and formatted report generation).

#### NEW

System Testing. System testing assessed the fully integrated application as a single cohesive entity. The objective was to validate the complete operational lifecycle and technical workflows from end to end prior to user deployment. This phase emphasized the execution of the uninterrupted HITL pipeline (from network video ingestion to UI alert handling), the enforcement of RBAC routing protocols, and the validation of system-wide utility functions (e.g., historical data filtering and formatted report generation).

#### Evidence

The system-testing paragraph names the user-facing HITL workflow. The implementation uses confirm, dismiss, and clear actions; `handling` accurately describes the whole pipeline.

#### Proposed comment (same gate as associated replacement)

Previous: UI alert resolution

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 24. ADAS_Paper_Audit — §0.3, Use Case 5 status note

Page/s: native range `t.0:3522–4071`; rendered PDF mapping unconfirmed

#### OLD

> Change to: status Resolved throughout. Table 11 enumerates exactly four statuses — Unverified, Ongoing, Dismissed, Resolved — and the database CHECK constraint agrees (backend/app/models/detection.py:24-31). The column names closed_by_id / closed_at are correct and should stay; it is only the status value that is wrong.

#### NEW

Change to: status Cleared throughout. Table 11 enumerates exactly four statuses — Unverified, Ongoing, Dismissed, Cleared — and the database CHECK constraint agrees (backend/app/models/detection.py:25-31). The column names closed_by_id / closed_at are correct and should stay; it is only the status value that is wrong.

#### Evidence

The live audit Doc still carries its earlier recommendation using the old status. P28’s model CHECK and enum now use `Cleared`; the reviewed migration rewrites existing `Resolved` rows.

#### Proposed comment (same gate as associated replacement)

Previous: Change to: status Resolved throughout. Table 11 enumerates exactly four statuses — Unverified, Ongoing, Dismissed, Resolved — and the database CHECK constraint agrees (backend/app/models/detection.py:24-31). The column names closed_by_id / closed_at are correct and should stay; it is only the status value that is wrong.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 25. ADAS_Paper_Audit — UC-9 step 3 status chip note

Page/s: native range `t.0:52089–52331`; rendered PDF mapping unconfirmed

#### OLD

> UC-9 step 3 offers filters by Status and by Operator. In the Logs tab, status is a static decorative chip reading "Dismissed & Resolved" — not interactive — and the operator select is rendered only for Administrators (Detections.tsx:298-321).

#### NEW

UC-9 step 3 offers filters by Status and by Operator. In the Logs tab, status is a static decorative chip reading "Dismissed & Cleared" — not interactive — and the operator select is rendered only for Administrators (Detections.tsx:298-321).

#### Evidence

The audit note’s status text is stale. The active status filter options are `Unverified`, `Ongoing`, `Cleared`, and `Dismissed` (`frontend/src/pages/Detections.tsx:72–79`).

#### Proposed comment (same gate as associated replacement)

Previous: UC-9 step 3 offers filters by Status and by Operator. In the Logs tab, status is a static decorative chip reading "Dismissed & Resolved" — not interactive — and the operator select is rendered only for Administrators (Detections.tsx:298-321).

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 26. ADAS_Paper_Audit — NFR-10 immediate-action note

Page/s: native range `t.0:52793–53025`; rendered PDF mapping unconfirmed

#### OLD

> NFR-10 promises three clicks; the alarm modal takes one. handleConfirm / handleDismiss / handleResolve each POST directly with no secondary confirmation, no reason field, no notes box (GlobalAlerts.tsx:32-72). State the real figure.

#### NEW

NFR-10 promises three clicks; the alarm modal takes one. Confirm, dismiss, and clear each POST directly with no secondary confirmation, no reason field, no notes box (Detections.tsx and the shared IncidentDetailModal). State the real figure.

#### Evidence

The old audit note names a stale handler and component. The current shared modal exposes `onClear` and immediately invokes it from the `Cleared` button; there is no confirmation layer (`frontend/src/pages/detections/IncidentDetailModal.tsx:315–336`).

#### Proposed comment (same gate as associated replacement)

Previous: NFR-10 promises three clicks; the alarm modal takes one. handleConfirm / handleDismiss / handleResolve each POST directly with no secondary confirmation, no reason field, no notes box (GlobalAlerts.tsx:32-72). State the real figure.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 27. ADAS_Paper_Audit — verified-correct HITL state-machine note

Page/s: native range `t.0:75286–75498`; rendered PDF mapping unconfirmed

#### OLD

> The HITL state machine Unverified → Ongoing → Resolved / → Dismissed, and the self-blindfold pause ordering — matches the code and the CHECK constraints. Exactly four legal transitions, each a conditional UPDATE.

#### NEW

The HITL state machine Unverified → Ongoing → Cleared / → Dismissed, and the self-blindfold pause ordering — matches the code and the CHECK constraints. Exactly four legal transitions, each a conditional UPDATE.

#### Evidence

The live audit note explicitly records the old terminal status. The current transition map has the four legal transitions and `ALERT_CLEAR` (`backend/app/services/incidents.py:36–41`).

#### Proposed comment (same gate as associated replacement)

Previous: The HITL state machine Unverified → Ongoing → Resolved / → Dismissed, and the self-blindfold pause ordering — matches the code and the CHECK constraints. Exactly four legal transitions, each a conditional UPDATE.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### 28. ADAS_Paper_Audit_Tracker — `🚩 Action Stream`!A82:H82

Page/s: `🚩 Action Stream`!A82:H82; first fully blank row confirmed from `userEnteredValue` read on 2026-09-03

#### OLD

> No existing row. The live `🚩 Action Stream` row A82:H82 is fully blank by `userEnteredValue`; rows 1–81 are occupied.

#### NEW

Major | Definition of Terms, FR/NFR, Use Cases, Data Dictionary, Figures 4/10/16/17 | unconfirmed | Replace active Resolved/Resolve incident terminology with Cleared/Clear across the paper and audit notes. | Ongoing → Cleared via POST /api/alerts/{log_id}/clear; audit ALERT_CLEAR; KPI fields use total_cleared*. Verify rendered figure redraws before applying paper edits. | Not started | Daniboy | [preserve blank]

#### Evidence

The live tracker metadata reports the exact `🚩 Action Stream` tab and row capacity. A `userEnteredValue` preflight found rows 1–81 occupied and row 82 fully blank. No row was written.

#### Proposed comment (same gate as associated replacement)

Previous: No existing row. The live `🚩 Action Stream` row A82:H82 is fully blank by `userEnteredValue`; rows 1–81 are occupied.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

## Redraw required

### Figure 4 — Use Case Diagram

Page/s: TOC p. 94 hint; Figure 4 caption native range `142949–142958`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### Current issue

The live Figure 4 use-case visual contains the old incident action vocabulary represented by the `Resolve Accident` use case and the surrounding resolution wording.

#### Required redraw

Replace the `Resolve Accident` use-case label with `Clear Accident` and keep the existing operator-to-system relationship and audit-recording relationship. Do not add a confirmation step or alter unrelated use cases.

#### Proposed standalone comment

Comment scope: exact Figure 4 caption span `142948–142956` in tab `t.y7ms6bhlk4qn`.

Figure 4 requires a redraw to replace the `Resolve Accident` use-case label with `Clear Accident` so the diagram matches the active `/clear` and `ALERT_CLEAR` contracts.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### Figure 10 — Dashboard

Page/s: TOC p. 112 hint; Figure 10 caption native range `175569–175579`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### Current issue

The live dashboard visual is described as carrying the old `Total Resolved` KPI label.

#### Required redraw

Replace the KPI card label `Total Resolved` with `Total Cleared`. Preserve the card’s placement, success tone, and the other dashboard metrics.

#### Proposed standalone comment

Comment scope: exact Figure 10 caption span `175557–175566` in tab `t.y7ms6bhlk4qn`.

Figure 10 requires a redraw so its dashboard KPI label reads `Total Cleared`, matching the `total_cleared` response field.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

### Figure 17 — Ongoing Accident Details Modal

Page/s: TOC p. 118 hint; Figure 17 caption native range `183598–183608`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### Current issue

The live Figure 17 visual shows the Ongoing modal’s primary action as `Resolve`.

#### Required redraw

Change the primary action’s visible label to exactly `Cleared`. Keep `Dismiss` as the correction action, keep the button immediate, and do not add a confirmation modal, warning copy, or an explanatory UI step.

#### Proposed standalone comment

Comment scope: exact Figure 17 caption span `183583–183592` in tab `t.y7ms6bhlk4qn`.

Figure 17 requires a redraw so the Ongoing incident modal’s immediate primary action reads exactly `Cleared` and matches the shared `IncidentDetailModal`.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.

## ADAS Test Execution Tracker — separate approval manifest (no writes performed)

The live Test Execution Tracker was read on 2026-09-03. These are proposed terminology/evidence updates only; no tracker cells, links, validation, formulas, formatting, or comments were changed. Existing evidence must not be relabeled as proof of the renamed build. The rows should be rerun on the completed P28 build before any approved execution-cell replacement; if rerun evidence is not available, preserve the old evidence and set the relevant result state to `Retest Required`.

### Target 1 — `Unit Testing`!A23:J24

Current rows:

- `A23:J23`: `TC-UNIT-022` describes “An Ongoing incident can be resolved by an operator,” points to `test_resolve_ongoing_alert`, and says the incident moves to `Resolved`.
- `A24:J24`: `TC-UNIT-023` describes “Resolving an incident reactivates an enabled camera,” points to `test_resolve_ongoing_reactivates_enabled_camera_and_broadcasts`, and uses resolved wording in the acceptance text.

Proposed changes after rerun: update the two descriptions, selectors, and expected-result text to `Cleared`, `clear`, and the renamed `test_clear_*` functions; preserve the existing date/link/manual columns; use the new P28 run evidence and do not copy the old 2026-08-29 evidence forward as proof.

### Target 2 — `Integration Testing`!A9:J9

Current row: `TC-INT-008` describes resolving an incident, points to `test_resolve_alert_broadcasts_camera_status_update_over_websocket`, and says the resolved incident is shown.

Proposed changes after rerun: update the workflow, selector, and expected event payload to `Cleared`, `clear`, and `ALERT_CLEAR`; preserve the existing evidence link and manual fields until the P28 rerun is recorded.

### Target 3 — `System / E2E Testing`!A3:J3

Current row: `TC-SYS-002` says the browser workflow confirms and then resolves an incident, instructs the participant to select Resolve and verify Resolved, and describes the resulting incident as resolved.

Proposed changes after real system/E2E rerun: replace those action/status terms with `Cleared`/`clear`, preserve the no-result status until execution, and do not claim a P28 system result from the backend/frontend automated suites.

### Target 4 — `UAT Journeys`!A8:J8

Current row: `OP-J07` uses “after it is resolved,” “Review & Resolve,” “resolve it,” and says the participant-confirmed incident becomes Resolved.

Proposed changes: replace those journey instructions and expected-result terms with “cleared,” `Review Incident`, `Cleared`, and the clear action; preserve the participant result, assistance, notes, and evidence columns until a fresh UAT execution is performed.

### Target 5 — terminology half of `UAT Journeys`!A10:J10

Current row: `OP-J09` uses “resolved and dismissed records” in the handover instruction and “resolved” in the terminal-record expectation. The export and Help Center execution scope is otherwise unchanged.

Proposed terminology-only changes: replace those two handover/expectation phrases with “cleared and dismissed records” and “cleared,” while preserving all export, Help Center, participant, and evidence content. Do not rewrite the existing execution result as a P28 result.

### Target 6 — `Guide & Examples`!A8:E8

Current row: the `System / E2E Testing` example says `Collision stream → alert → confirm → resolve`.

Proposed change: update only the example workflow label to `Collision stream → alert → confirm → clear`; preserve the guide instruction and the warning that a technical end-to-end result must be executed and recorded.

### Approved tracker comment plan

Each comment below uses logical-row scope: one comment covers the changed cells in that test record, with the exact prior values preserved in `Previous:`. The comments are created only after the corresponding row readback and only if the Sheet connector returns a provider-valid native anchor.

#### Target 1 — `Unit Testing`!C23:H23

Comment scope: one logical test row, changed cells `C23:H23`.

```text
Previous:
C23: An Ongoing incident can be resolved by an operator.
D23: uv run pytest backend/tests/test_alerts.py::TestAlertTransitions::test_resolve_ongoing_alert
E23: The incident moves to Resolved with the closer's identity and timestamp.
F23: 2026-08-29
G23: Pass
H23: Pass — full backend fast suite: 939 passed, 2 skipped, 12 deselected.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 1 — `Unit Testing`!C24:H24

Comment scope: one logical test row, changed cells `C24:H24`.

```text
Previous:
C24: Resolving an incident reactivates an enabled camera.
D24: uv run pytest backend/tests/test_alerts.py::TestAlertCameraStatusSideEffects::test_resolve_ongoing_reactivates_enabled_camera_and_broadcasts
F24: 2026-08-29
G24: Pass
H24: Pass — full backend fast suite: 939 passed, 2 skipped, 12 deselected.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 2 — `Integration Testing`!C9:H9

Comment scope: one logical test row, changed cells `C9:H9`.

```text
Previous:
C9: Resolving an incident resumes the camera and notifies operators of both state changes.
D9: pytest selector: backend/tests/test_websocket.py::test_resolve_alert_broadcasts_camera_status_update_over_websocket
E9: Client receives CAMERA_STATUS_UPDATE then ALERT_STATUS_UPDATE showing the resolved incident.
F9: 2026-08-29
G9: Pass
H9: 4 selected tests passed in 0.80s.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 3 — `System / E2E Testing`!C3:H3

Comment scope: one logical test row, changed cells `C3:E3` and `G3:H3`.

```text
Previous:
C3: A live collision feed becomes a confirmed and then resolved incident in the operator browser.
D3: Entry gate: all 10 streams ingesting; identify a documented collision replay and its camera. 1. Sign in from the client workstation at https://adas.local. 2. Allow the replayed collision to reach the live engine. 3. Observe the alert, audible alarm, and snapshot. 4. Select Confirm and verify Ongoing status and the camera's paused state. 5. Select Resolve and verify Resolved status and the camera's return to Active. 6. Capture the alert, status transitions, incident record, and audit evidence.
E3: One incident is created with snapshot and Unverified status; Confirm records Ongoing and keeps the camera paused; Resolve records the user and completion time, resumes the camera, and leaves an auditable history.
G3: Not Executed
H3: Awaiting the required two-node walkthrough with a live replay; no System/E2E result is claimed.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 4 — `UAT Journeys`!D8:G8

Comment scope: one logical UAT journey row, changed cells `D8:G8`.

```text
Previous:
D8: Facilitator
1. Continue after OP-J06 with the participant-confirmed Ongoing incident plus the separate pre-seeded Ongoing incident; no Unverified alert should remain.
2. Declare the participant-confirmed incident cleared.
3. After it is resolved, tell the participant that the remaining pre-seeded Ongoing incident was later determined to have been misidentified.

Logger
1. Record tray badge counts: 2 before the first action, 1 after resolution, and 0 after the correction.
E8: Use the Ongoing Incidents tray to resolve the genuine incident and correct one misidentified Ongoing incident
F8: 1. Open the bottom-right Ongoing Incidents tray.
2. Verify the initial badge/count and distinguish the two cards.
3. Select Review & Resolve on the participant-confirmed incident and resolve it.
4. Reopen the tray and review the remaining pre-seeded incident.
5. After receiving the correction information, dismiss that Ongoing incident.
6. Use Detections date/status filters to retrieve both terminal records.
G8: 1. The tray initially shows 2 correct Ongoing cards.
2. The participant-confirmed incident becomes Resolved and its camera resumes monitoring.
3. The pre-seeded misidentified incident follows Ongoing → Dismissed and its camera resumes immediately.
4. Only the selected incident changes at each action.
5. Both terminal records are attributable and retrievable from history.
6. The tray count changes 2 → 1 → 0.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 5 — `UAT Journeys`!F10

Comment scope: one logical terminology change in the OP-J09 handover cell `F10`, exact old span `resolved and dismissed records`.

```text
Previous: resolved and dismissed records

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

#### Target 6 — `Guide & Examples`!C8

Comment scope: one logical example cell, changed cell `C8`.

```text
Previous: TC-SYS-001 | Collision stream → alert → confirm → resolve | Pass | video/log bundle.

Codex ID: PS-20260903-CLEARED-INCIDENT-TERMINOLOGY

Done by Codex.
```

## Approval / sync ledger

Package ID: `PS-20260903-CLEARED-INCIDENT-TERMINOLOGY`

| Target                        | Approved scope                                                                                                     | Applied/read back                                                                                                                                                                     | Skipped/pending                                                            | Blocked                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Defense paper                 | blocks 1–23 and readback follow-up blocks 24a–24m plus their attached `Previous:` comments                         | blocks 1–23 and 24a–24m; 42 exact-span comments                                                                                                                                       | Figure 4, Figure 10, Figure 17 redraws (separate standalone-comments gate) | —                                                                                               |
| ADAS_Paper_Audit plus tracker | none yet; blocks 24–28 are proposed                                                                                | —                                                                                                                                                                                     | blocks 24–28                                                               | —                                                                                               |
| Standalone comments           | `FIGURE-4`, `FIGURE-10`, `FIGURE-17`                                                                               | comments `AAACGhHS_Gk`, `AAACGhHS_Go`, `AAACGhHS_Gs`; exact caption quotes and native anchors verified open                                                                           | —                                                                          | —                                                                                               |
| ADAS Test Execution Tracker   | Targets 1–6: Unit A23:J24; Integration A9:J9; System / E2E A3:J3; UAT A8:J8; terminology half UAT F10; Guide A8:E8 | all approved row/cell updates read back; comments `AAACGg5qXio`, `AAACGg5qXis`, `AAACGg5qXiw`, `AAACGg5qXi0`, `AAACGg5qXi4`, `AAACGhDoCn4`, `AAACGhDoCn8` created with `anchor: null` | —                                                                          | seven Sheet comments are blocked as unanchored; deletion is pending and no comment was resolved |

## Drive-read evidence and gated-write status

- The live defense Doc `Group7_Capstone Project Defense Document - ITCAPROJ1` was read on 2026-09-03 through Google Drive, and a fresh revision/anchor read was completed on 2026-09-04 immediately before the approved exact-range edits. The OLD text in blocks 1–23 was verified against native paragraph ranges.
- The live `ADAS_Paper_Audit` Doc was read on 2026-09-03 through Google Drive. Its current revision was read before this finding; the OLD text in blocks 24–27 was verified against native paragraph ranges.
- The live `ADAS_Paper_Audit_Tracker` Sheet was read on 2026-09-03. `🚩 Action Stream` rows 1–81 have `userEnteredValue`; A82:H82 is the first fully blank candidate. No row was written.
- The live ADAS Test Execution Tracker ranges were read for the approved Targets 1–6. The approved row/cell updates were written and read back on 2026-09-04 with the existing manual/evidence columns preserved. The seven associated comment attempts returned `anchor: null` and are blocked as unanchored pending deletion; they must not be resolved or retried through the same generic route.
- The four initial broad paper comments created during the first attempt were resolved on 2026-09-04 after review. They were replaced by 42 exact-span comments whose `Previous:` value is only the changed old word/phrase; every returned native anchor and quote was verified.
- No `ADAS_Paper_Audit` or audit tracker write has been approved or attempted. Defense-paper blocks 1–23 and follow-up blocks 24a–24m plus their exact-span comments were applied and read back; only the figure redraws remain pending, so `synced: false` remains correct.
- On 2026-09-04 the user approved all six Test Execution Tracker target groups, standalone figure comments `FIGURE-4`, `FIGURE-10`, and `FIGURE-17`, and the associated retesting. The approved retest passed the three renamed backend clear-action selectors and all 275 frontend tests across 47 files. No live System / E2E two-node walkthrough or human UAT rerun was completed, so those result states must not be marked passed.
- A fresh live read on 2026-09-04 found that `UAT Journeys` cell `F10` for `OP-J09` still contains `resolved and dismissed records`, but its expected-result text already says `terminal records` rather than `resolved`; only the stale handover phrase in `F10` is an approved textual replacement.
- Standalone figure comments were created and read back on 2026-09-04: `AAACGhHS_Gk` on `Figure 4`, `AAACGhHS_Go` on `Figure 10`, and `AAACGhHS_Gs` on `Figure 17`; each has a non-empty native anchor, the exact caption quote, the package ID, and final `Done by Codex.` attribution.
- The approved Test Execution Tracker rows were written/read back on 2026-09-04: Unit `A23:J24`, Integration `A9:J9`, System / E2E `A3:J3`, UAT `A8:J8` plus `F10`, and Guide `C8`. Seven row-level comments were then created by the Sheet connector, but every returned anchor was `null`; the IDs are recorded above for deletion. The Drive connector exposes no comment-deletion operation, and none of these comments was resolved.
