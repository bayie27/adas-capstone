---
section: Objectives, Definition of Terms, Research Design, NFR-09, and Testing
page/s: "13, 17, 53, 65; TC-S-103 and Operator Training unconfirmed"
required_revision: Replace the superseded 15-second target with the approved 25-second end-to-end CDRRMO verification target.
notes: The 25-second target covers approximately 3 seconds of detector accumulation, 2 seconds of alert propagation, and 20 seconds for CCTV/DSS verification plus Confirm/Dismiss; it supports faster manual dispatch initiation without claiming automatic dispatch or direct DSS integration.
status: In progress
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Objectives of the Study, Objective 3

Page/s: p. 13 per the live document table of contents; native range `15965–16302`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a sub-15-second end-to-end collision-to-operator-decision latency, ensuring effective minimization of the notification gap and facilitating faster emergency intervention to mitigate injury severity and traffic congestion.

#### NEW

To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a 25-second end-to-end collision-to-operator-decision latency, reducing the notification gap and supporting faster initiation of the CDRRMO’s manual dispatch or endorsement procedures to mitigate injury severity and traffic congestion.

#### Evidence

The live paper still carries the superseded sub-15-second objective. The approved operational breakdown is approximately 3 seconds for detector accumulation, 2 seconds for backend/WebSocket/UI alert propagation, and 20 seconds for CCTV/DSS verification plus the operator’s Confirm/Dismiss decision. `ai_engine/accident.py:47-52` states that the event fires a median +3.02 seconds after impact and that `detected_at` approximates the collision timestamp. The 25-second value is an end-to-end target, not a claim that the current proof of concept has already demonstrated the complete production DSS path.

#### Proposed comment (same gate as associated replacement)

Previous: To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a sub-15-second end-to-end collision-to-operator-decision latency, ensuring effective minimization of the notification gap and facilitating faster emergency intervention to mitigate injury severity and traffic congestion.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 2. Defense paper — Definition of Terms, “Notification Gap” definition

Page/s: p. 17 per the live document table of contents; native range `30528–30827`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes, and closing it to under fifteen seconds is the central objective of this study.

#### NEW

The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes. For this study, the operational target is to reduce the measured interval from the accident first becoming visible on camera to a verified operator decision to within twenty-five seconds, supporting faster initiation of manual dispatch or endorsement procedures.

#### Evidence

The live definition still describes the central objective as under fifteen seconds. The revised definition makes the measurement boundary explicit: the operational clock begins when the accident first becomes visible on the monitored camera feed and ends when the operator records Confirm or Dismiss. This matches the approved end-to-end target while retaining the notification-gap rationale.

#### Proposed comment (same gate as associated replacement)

Previous: The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes, and closing it to under fifteen seconds is the central objective of this study.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 3. Defense paper — Research Design, Phase 4: Testing and System Integration

Page/s: p. 53 per the live document table of contents; native range `87543–88765`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system's ability to support the 15-second end-to-end dispatch workflow. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### NEW

In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system’s ability to support the 25-second end-to-end collision-to-operator-decision workflow and faster initiation of manual dispatch or endorsement procedures. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### Evidence

The live Phase 4 paragraph correctly retains the separate 2-second alert-delivery target but still names a 15-second end-to-end dispatch workflow. The proposed text changes only the superseded end-to-end figure and endpoint. The paper’s scope paragraph at native range `17742–18993` states that the proof of concept does not integrate with, modify, or administer Dahua DSS and does not provide automated dispatch; the wording therefore describes support for manual procedures rather than system-initiated dispatch.

#### Proposed comment (same gate as associated replacement)

Previous: In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system's ability to support the 15-second end-to-end dispatch workflow. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 4. Defense paper — Non-Functional Requirements Specification, NFR-09 heading

Page/s: p. 65 per the live document table of contents; native range `101308–101361`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> NFR-09 Operational Efficiency (Detection-to-Dispatch)

#### NEW

NFR-09 Operational Efficiency (Collision-to-Operator Decision)

#### Evidence

The live heading uses “Detection-to-Dispatch,” while the paper’s scope and workflow make the system endpoint the human Confirm/Dismiss decision. Renaming the heading prevents the requirement from implying that ADAS itself executes emergency dispatch.

#### Proposed comment (same gate as associated replacement)

Previous: NFR-09 Operational Efficiency (Detection-to-Dispatch)

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 5. Defense paper — Non-Functional Requirements Specification, NFR-09 body

Page/s: p. 65 per the live document table of contents; native range `101363–101571`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The system shall reduce the notification gap by enabling operators to visually identify, verify, and initiate dispatch protocols for vehicular collisions within 15 seconds of the incident occurring on camera.

#### NEW

The system shall reduce the notification gap by enabling the CDRRMO to receive an accident alert, verify the event through available CCTV/DSS evidence, and record a Confirm or Dismiss decision within 25 seconds of the accident first becoming visible in the monitored camera feed. This shortened time to verified awareness is intended to support faster initiation of the CDRRMO’s manual dispatch or endorsement procedures.

#### Evidence

This is the central target replacement. It incorporates the operator’s verification through the available CCTV/DSS evidence and both possible HITL outcomes. “Support” and “manual” preserve the live paper’s explicit boundary that ADAS does not automatically dispatch responders or directly administer Dahua DSS. The target is the sum of approximately 3 seconds of detector accumulation, 2 seconds of alert propagation, and 20 seconds for verification and decision.

#### Proposed comment (same gate as associated replacement)

Previous: The system shall reduce the notification gap by enabling operators to visually identify, verify, and initiate dispatch protocols for vehicular collisions within 15 seconds of the incident occurring on camera.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 6. Defense paper — Testing and Validation, TC-S-103

Page/s: unconfirmed; native range `234472–234634`, tab `t.y7ms6bhlk4qn`

#### OLD

> The Operator is able to visually identify the UI alert, verify the snapshot, and click "Confirm" in strictly under 15 seconds from the moment of actual detection.

#### NEW

The Operator is able to visually identify the UI alert, verify the snapshot using available CCTV/DSS evidence, and click either "Confirm" or "Dismiss" within 25 seconds from the moment the collision first becomes visible on camera.

#### Evidence

The live test case measures the operator endpoint but still uses the superseded 15-second figure, only the Confirm path, and the ambiguous “actual detection” start. The revised text aligns the test case with NFR-09 and the approved visible-on-camera start while keeping the operator decision as the endpoint.

#### Proposed comment (same gate as associated replacement)

Previous: The Operator is able to visually identify the UI alert, verify the snapshot, and click "Confirm" in strictly under 15 seconds from the moment of actual detection.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 7. Defense paper — Operator Training

Page/s: unconfirmed; native range `247415–247682`, tab `t.y7ms6bhlk4qn`

#### OLD

> Operator Training: Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts to maintain a sub-15-second response time. They are also instructed on generating historical reports and reading system health telemetry.

#### NEW

Operator Training: Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts within the 25-second end-to-end target to reduce the notification gap and support faster initiation of manual dispatch procedures. They are also instructed on generating historical reports and reading system health telemetry.

#### Evidence

The live training paragraph still teaches a sub-15-second response time. The revised sentence carries the approved operational purpose into the training description without changing the training topics or claiming automated dispatch.

#### Proposed comment (same gate as associated replacement)

Previous: Operator Training: Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts to maintain a sub-15-second response time. They are also instructed on generating historical reports and reading system health telemetry.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 8. ADAS_Paper_Audit — §0.4, end-to-end timing recommendation

Page/s: unconfirmed; native range `4413–4694`, tab `t.0`

#### OLD

> Change to: one consistent framing. Recommended: 2 s is the backend→WebSocket→UI budget (NFR-04); 15 s is the end-to-end collision→operator-decision budget (NFR-09); Objective 3 and Phase 4 should cite the 15 s end-to-end figure explicitly as end-to-end, not as "alert propagation".

#### NEW

Decision: use one consistent framing. Approximately 3 s is the detector-accumulation component; 2 s is the backend→WebSocket→UI alert-propagation budget (NFR-04); 25 s is the end-to-end collision-visible-to-operator-decision budget (NFR-09), including CCTV/DSS verification and Confirm/Dismiss. Objective 3 and Phase 4 should cite the 25 s end-to-end figure as supporting faster initiation of manual CDRRMO dispatch or endorsement procedures, not as "alert propagation."

#### Evidence

The live audit recommendation still records the superseded 15-second decision. The local implementation comment at `ai_engine/accident.py:47-52` supports approximately 3 seconds of detector accumulation, while `be_plan/EVIDENCE.md:182-194` measures the backend alert POST-to-WebSocket delivery path at 0.010–0.020 seconds against a 2-second budget. The full LAN numeric NFR-04 capture remains unconfirmed at `be_plan/EVIDENCE.md:196-210`; therefore the component figures are budgets/allocations and do not by themselves prove the complete 25-second target.

#### Proposed comment (same gate as associated replacement)

Previous: Change to: one consistent framing. Recommended: 2 s is the backend→WebSocket→UI budget (NFR-04); 15 s is the end-to-end collision→operator-decision budget (NFR-09); Objective 3 and Phase 4 should cite the 15 s end-to-end figure explicitly as end-to-end, not as "alert propagation".

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 9. ADAS_Paper_Audit — TC-S-103 rewrite guidance

Page/s: unconfirmed; native range `72866–73257`, tab `t.0`

#### OLD

> For the rewrite: "…from the moment of collision." This is the metric supporting the study's central claim of reducing the notification gap from minutes to seconds, so it should honestly include the detector's own latency. After the port, detected_at in the database is the estimated collision time (ai_engine/accident.py:52), so this becomes directly measurable as verified_at − detected_at.

#### NEW

For the rewrite: "…click either 'Confirm' or 'Dismiss' within 25 seconds from the moment the collision first becomes visible on camera." This is the metric supporting the study's central claim of reducing the notification gap from minutes to seconds and enabling faster manual dispatch initiation, so it includes detector accumulation, alert propagation, CCTV/DSS verification, and operator decision time. The UAT logger should use the first visible collision frame as the start event; `detected_at` in the database is an approximate collision timestamp (`ai_engine/accident.py:47-52`) and should not be treated as a substitute when validating this wall-clock target.

#### Evidence

The existing audit guidance correctly identifies TC-S-103 as the end-to-end metric but does not contain the approved 25-second value or the Confirm/Dismiss endpoint. The live UAT script records the genuine collision’s visible onset as the start of OP-J05 and the participant’s manual dispatch/endorsement decision after confirmation as its current endpoint; this package aligns the paper’s test case with the approved end-to-end framing while keeping implementation and UAT evidence distinct.

#### Proposed comment (same gate as associated replacement)

Previous: For the rewrite: "…from the moment of collision." This is the metric supporting the study's central claim of reducing the notification gap from minutes to seconds, so it should honestly include the detector's own latency. After the port, detected_at in the database is the estimated collision time (ai_engine/accident.py:52), so this becomes directly measurable as verified_at − detected_at.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 10. ADAS_Paper_Audit — TC-S-103 budget check

Page/s: unconfirmed; native range `73259–73453`, tab `t.0`

#### OLD

> Budget check before committing to 15 s: ~3 s accumulating + < 2 s plumbing leaves ~10 s of operator time. Achievable, but tighter than the original wording implies — confirm during live testing.

#### NEW

Budget check for 25 s: ~3 s detector accumulation + 2 s alert propagation leaves approximately 20 s for CCTV/DSS verification and the operator’s Confirm/Dismiss decision. The end-to-end target should be timed from the accident’s first visible frame to the operator’s decision and reported per trial, alongside mean and worst-case results.

#### Evidence

The live audit budget check still allocates only approximately 10 seconds to the operator under the superseded 15-second target. The approved 25-second allocation leaves approximately 20 seconds after the detector and alert-propagation components. The current local test plan still says detection-to-dispatch-decision mean ≤15 seconds at `test-execution-validation-plan.md:502`; that companion execution-plan wording is outside the three native Drive write gates in this package and remains a follow-up sync item.

#### Proposed comment (same gate as associated replacement)

Previous: Budget check before committing to 15 s: ~3 s accumulating + < 2 s plumbing leaves ~10 s of operator time. Achievable, but tighter than the original wording implies — confirm during live testing.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 11. ADAS_Paper_Audit_Tracker — `🚩 Action Stream`!A6:H6

Page/s: `🚩 Action Stream`!A6:H6

#### OLD

> Major | Objective 3, NFR-04, Phase 4, NFR-09 | 14, 66, 52, 68 | 0.4 Three different alert-latency figures | Change to: one consistent framing. 2 s is the backend UI budget; 15 s is the end-to-end collision operator-decision budget. | Completed | Paulo | Daniboy

#### NEW

| Change Type | Section / Chapter                                                                     | Page Number                 | Required Revision                                              | Notes                                                                                                                                                                                                                                                   | Status      | Assigned to | Reviewed by |
| ----------- | ------------------------------------------------------------------------------------- | --------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------- | ----------- |
| Major       | Objective 3, Definition of Terms, NFR-04/NFR-09, Phase 4, TC-S-103, Operator Training | 13, 17, 53, 65, unconfirmed | 0.4 Clarify the alert-delivery and end-to-end decision targets | 2 s is the backend/WebSocket/UI alert-propagation budget; 25 s is the collision-visible-to-operator-decision budget, including CCTV/DSS verification and Confirm/Dismiss, to reduce the notification gap and support faster manual dispatch initiation. | In progress | Paulo       | Daniboy     |

#### Evidence

The live tracker row at `🚩 Action Stream` row 6 is the existing record for this finding, so this package updates it rather than creating a duplicate row. The current row is marked Completed but its required revision and notes still encode the superseded 15-second decision. The page values in NEW are the current live table-of-contents hints for the main paper sections; rendered PDF mapping is unconfirmed in this runtime. The `Reviewed by`, owner, validation, formatting, and other manual Sheet state must be preserved.

#### Proposed comment (same gate as associated replacement)

Previous: Major | Objective 3, NFR-04, Phase 4, NFR-09 | 14, 66, 52, 68 | 0.4 Three different alert-latency figures | Change to: one consistent framing. 2 s is the backend UI budget; 15 s is the end-to-end collision operator-decision budget. | Completed | Paulo | Daniboy

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

## No change recommended

- NFR-04 remains a separate technical alert-delivery target of 2 seconds after AI detection; it should not be changed to 25 seconds.
- The paper’s scope and evaluation-boundary passages already state that the proof of concept does not integrate its UI with, modify, or administer Dahua DSS and does not automate emergency dispatch. They remain as written and constrain the interpretation of the new NFR-09 wording.
- The live audit’s quoted OLD values in §0.1 and §0.4 are historical evidence of the inconsistency; this package changes the recommendation and TC-S-103 guidance, not the historical quotations.

## Companion follow-up outside this package

- The local `test-execution-validation-plan.md:502` and the live UAT OP-J05/tracker wording still carry the prior ≤15-second execution criterion. They should be synchronized to the approved 25-second start/end boundary before final UAT reporting, but no changes to those artifacts are proposed under the three native Drive write gates in this paper-sync package.

## Approval / sync ledger

Package ID: `PS-20260903-NFR09-25-SECOND-E2E`

| Target                        | Approved scope                          | Applied/read back                                                                                                                                            | Skipped/pending | Blocked                                                                                                            |
| ----------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- | ------------------------------------------------------------------------------------------------------------------ |
| Defense paper                 | Blocks 1–7 and their attached comments  | Blocks 1–7 and comments `AAACGdvWZuU`, `AAACGdvw4f8`, `AAACGdvw4go`, `AAACGdvyHWE`, `AAACGdvyHWM`, `AAACGdvyHWU`, `AAACGdwBjVE`; anchors verified 2026-09-03 | —               | Block 3 returned a truncated quoted-text preview from the connector; exact comment body and native anchor verified |
| ADAS_Paper_Audit plus tracker | Blocks 8–11 and their attached comments | Blocks 8–10 and comments `AAACGcFzcpM`, `AAACGcFzcpY`, `AAACGcFzcpk`; tracker row `🚩 Action Stream`!A6:G6 read back                                         | —               | Block 11 Sheet comment: connector returned no provider-valid native anchor; comment not created                    |
| Standalone comments           | None proposed                           | —                                                                                                                                                            | None            | —                                                                                                                  |
