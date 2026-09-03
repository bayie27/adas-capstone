---
section: Objectives, Definition of Terms, Research Design, NFR-09, and Testing
page/s: "TOC pp. 13, 17, 53, 65 hints; rendered PDF mapping unconfirmed; TC-S-103 and Operator Training unconfirmed"
required_revision: Replace the superseded 15-second target with the approved 25-second end-to-end CDRRMO verification target.
notes: The 25-second target is evaluated as the observed interval from alert appearance to the operator’s recorded Confirm or Dismiss decision plus approximately 3 seconds of detector accumulation and 2 seconds of alert propagation. It supports faster manual dispatch initiation without claiming automatic dispatch or direct DSS integration. The live test-execution tracker contains OP-J05 entries of 16.0 s, 9.0 s, and 15.0 s (calculated raw mean 13.3 s, raw worst 16.0 s); using the clarified 5-second component allowance gives estimated totals of 21.0 s, 14.0 s, and 20.0 s (mean approximately 18.3 s, worst 21.0 s). The live tracker now records these as raw observations plus a reconstructed allowance rather than a direct first-visible-frame wall-clock measurement. The current tracker content was written/read back on 2026-09-03; one native-anchored replacement comment was also verified, while the remaining proposed Sheet comments remain blocked because no provider-valid native anchors were available. The defense paper and ADAS_Paper_Audit were not changed.
status: In progress
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Objectives of the Study, Objective 3

Page/s: TOC p. 13 hint; native range `15965–16302`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a sub-15-second end-to-end collision-to-operator-decision latency, ensuring effective minimization of the notification gap and facilitating faster emergency intervention to mitigate injury severity and traffic congestion.

#### NEW

To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and an end-to-end interval of no more than 25 seconds from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision, reducing the notification gap and supporting faster initiation of the CDRRMO’s manual dispatch or endorsement procedures to mitigate injury severity and traffic congestion.

#### Evidence

The live paper still carries the superseded sub-15-second objective. The approved operational breakdown is approximately 3 seconds for detector accumulation, 2 seconds for backend/WebSocket/UI alert propagation, and 20 seconds for CCTV/DSS verification plus the operator’s Confirm/Dismiss decision. `ai_engine/accident.py:47-52` states that the event fires a median +3.02 seconds after impact and that `detected_at` approximates the collision timestamp. The 25-second value is an end-to-end target, not a claim that the current proof of concept has already demonstrated the complete production DSS path.

#### Proposed comment (same gate as associated replacement)

Previous: To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a sub-15-second end-to-end collision-to-operator-decision latency, ensuring effective minimization of the notification gap and facilitating faster emergency intervention to mitigate injury severity and traffic congestion.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 2. Defense paper — Definition of Terms, “Notification Gap” definition

Page/s: TOC p. 17 hint; native range `30528–30827`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes, and closing it to under fifteen seconds is the central objective of this study.

#### NEW

The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes. For this study, the operational target is an interval of no more than 25 seconds from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision, supporting faster initiation of manual dispatch or endorsement procedures.

#### Evidence

The live definition still describes the central objective as under fifteen seconds. The revised definition makes the measurement boundary explicit: the operational clock begins at the collision’s first visible frame on the monitored camera and ends at the operator’s recorded Confirm or Dismiss decision. This matches the approved end-to-end target while retaining the notification-gap rationale.

#### Proposed comment (same gate as associated replacement)

Previous: The interval between the physical occurrence of a road accident and the moment the Lipa CDRRMO becomes aware of it. Under the current pipeline of citizen and inter-agency reporting this interval reaches several minutes, and closing it to under fifteen seconds is the central objective of this study.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 3. Defense paper — Research Design, Phase 4: Testing and System Integration

Page/s: TOC p. 53 hint; native range `87543–88765`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system's ability to support the 15-second end-to-end dispatch workflow. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### NEW

In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system’s ability to support an end-to-end interval of no more than 25 seconds from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision, together with faster initiation of manual dispatch or endorsement procedures. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

#### Evidence

The live Phase 4 paragraph correctly retains the separate 2-second alert-delivery target but still names a 15-second end-to-end dispatch workflow. The proposed text changes only the superseded end-to-end figure and endpoint. The paper’s scope paragraph at native range `17742–18993` states that the proof of concept does not integrate with, modify, or administer Dahua DSS and does not provide automated dispatch; the wording therefore describes support for manual procedures rather than system-initiated dispatch.

#### Proposed comment (same gate as associated replacement)

Previous: In this phase, the parallel development lifecycles formally converge for rigorous end-to-end validation. With the YOLO model weights finalized and optimized, it is integrated directly into the AI engine and FastAPI backend. The fully assembled software architecture is then subjected to comprehensive system testing within a simulated LAN environment. Rather than evaluating static datasets, the system processes simulated live RTSP video feeds to validate real-time inference stability, track continuous hardware resource utilization, and ensure that AI detections successfully propagate through the SQLite database to deliver WebSocket alerts to the dashboard within the 2-second target, thereby validating the system's ability to support the 15-second end-to-end dispatch workflow. This quality assurance process also verifies the complete HITL resolution workflow and strictly enforces RBAC routing between Operators and Administrators. Finally, the phase concludes with formal UAT, allowing Lipa CDRRMO dispatchers to interact with the system in a staging environment to validate UI/UX efficiency, operational readiness, and the successful fulfillment of all defined project requirements prior to physical deployment.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 4. Defense paper — Non-Functional Requirements Specification, NFR-09 heading

Page/s: TOC p. 65 hint; native range `101308–101361`, tab `t.y7ms6bhlk4qn`; rendered PDF mapping unconfirmed

#### OLD

> NFR-09 Operational Efficiency (Detection-to-Dispatch)

#### NEW

NFR-09 Operational Efficiency (Collision-Visible-to-Operator Decision)

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

The system shall reduce the notification gap by enabling the CDRRMO to receive an accident alert, verify the event through available CCTV/DSS evidence, and record a Confirm or Dismiss decision within 25 seconds from the collision’s first visible frame on the monitored camera. This shortened time to verified awareness is intended to support faster initiation of the CDRRMO’s manual dispatch or endorsement procedures.

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

The Operator is able to visually identify the UI alert, verify the snapshot using available CCTV/DSS evidence, and produce a recorded Confirm or Dismiss decision within 25 seconds from the collision’s first visible frame on the monitored camera.

#### Evidence

The live test case measures the operator endpoint but still uses the superseded 15-second figure, only the Confirm path, and the ambiguous “actual detection” start. The revised text aligns the test case with NFR-09 and the approved collision’s first visible frame on the monitored camera start and recorded Confirm or Dismiss endpoint.

#### Proposed comment (same gate as associated replacement)

Previous: The Operator is able to visually identify the UI alert, verify the snapshot, and click "Confirm" in strictly under 15 seconds from the moment of actual detection.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 7. Defense paper — Operator Training

Page/s: unconfirmed; native range `247415–247682`, tab `t.y7ms6bhlk4qn`

#### OLD

> Operator Training: Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts to maintain a sub-15-second response time. They are also instructed on generating historical reports and reading system health telemetry.

#### NEW

Operator Training: Dispatchers are trained on the HITL workflow, specifically how to rapidly evaluate, confirm, or dismiss alerts within the 25-second end-to-end target measured from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision. This target is intended to reduce the notification gap and support faster initiation of manual dispatch procedures. They are also instructed on generating historical reports and reading system health telemetry.

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

Decision: use one consistent framing. Approximately 3 s is the detector-accumulation component; 2 s is the backend→WebSocket→UI alert-propagation budget (NFR-04); 25 s is the end-to-end interval from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision (NFR-09), including CCTV/DSS verification. Objective 3 and Phase 4 should cite the 25 s end-to-end figure as supporting faster initiation of manual CDRRMO dispatch or endorsement procedures, not as "alert propagation."

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

For the rewrite: "…click either 'Confirm' or 'Dismiss' within 25 seconds from the collision’s first visible frame on the monitored camera." This is the metric supporting the study's central claim of reducing the notification gap from minutes to seconds and enabling faster manual dispatch initiation, so it includes detector accumulation, alert propagation, CCTV/DSS verification, and operator decision time. The UAT logger should use the first visible collision frame as the start event; `detected_at` in the database is an approximate collision timestamp (`ai_engine/accident.py:47-52`) and should not be treated as a substitute when validating this wall-clock target.

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

Budget check for 25 s: ~3 s detector accumulation + 2 s alert propagation leaves approximately 20 s for CCTV/DSS verification and the operator’s Confirm/Dismiss decision. The end-to-end target should be timed from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision and reported per trial, alongside mean and worst-case results.

#### Evidence

The live audit budget check still allocates only approximately 10 seconds to the operator under the superseded 15-second target. The approved 25-second allocation leaves approximately 20 seconds after the detector and alert-propagation components. The local execution plan and dry-run handoff now use the canonical collision-visible-to-operator-decision boundary; the live audit’s historical 15-second quotation remains as the OLD text above and is not an execution result.

#### Proposed comment (same gate as associated replacement)

Previous: Budget check before committing to 15 s: ~3 s accumulating + < 2 s plumbing leaves ~10 s of operator time. Achievable, but tighter than the original wording implies — confirm during live testing.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 11. ADAS_Paper_Audit_Tracker — `🚩 Action Stream`!A6:H6

Page/s: `🚩 Action Stream`!A6:H6

#### OLD

> Major | Objective 3, NFR-04, Phase 4, NFR-09 | 14, 66, 52, 68 | 0.4 Three different alert-latency figures | Change to: one consistent framing. 2 s is the backend UI budget; 15 s is the end-to-end collision operator-decision budget. | Completed | Paulo | Daniboy

#### NEW

| Change Type | Section / Chapter                                                                     | Page Number                                           | Required Revision                                              | Notes                                                                                                                                                                                                                                                                                                                  | Status      | Assigned to | Reviewed by |
| ----------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------- | ----------- |
| Major       | Objective 3, Definition of Terms, NFR-04/NFR-09, Phase 4, TC-S-103, Operator Training | TOC pp. 13, 17, 53, 65 hints; PDF mapping unconfirmed | 0.4 Clarify the alert-delivery and end-to-end decision targets | 2 s is the backend/WebSocket/UI alert-propagation budget; 25 s is the interval from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision, including CCTV/DSS verification, to reduce the notification gap and support faster manual dispatch initiation. | In progress | Paulo       | Daniboy     |

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
- The `System / E2E Testing` tab has no NFR-09 test case. Leave the human timing measure in UAT rather than adding a duplicate technical case.
- The `Execution Log` OP-J05 elapsed values and the `UAT Results` aggregate are not rewritten in this package. Per the clarified execution method, the elapsed values are raw alert-appearance-to-decision observations; the approximately 3-second accumulation and 2-second propagation components are added when deriving the end-to-end estimate. No displayed result is presented as a direct first-visible-frame wall-clock measurement.

## Test-execution tracker caveat

The live tracker currently reports all 33 participant-stage executions as Pass and the formal acceptance decision as Accepted, but the `UAT Results` eligibility formula does not include the NFR-09 timing criterion. Updating the target text and re-executing the revised boundary are therefore separate from the existing aggregate status. If the 25-second timing is intended to block formal eligibility, that must be added as a separately approved tracker-control change.

### 12. Local test-execution validation plan — operational efficiency criterion

Page/s: `test-execution-validation-plan.md:118-120,473,502,639`

#### OLD

> The end-to-end detection-to-dispatch timing objective is measured during this activity.
>
> | 12 | Operational efficiency (detection to dispatch decision) | Timed observation during UAT: elapsed time from the collision becoming visible in the simulated feed to the operator's verification decision, repeated across all operators and multiple incidents | Timing table with per-operator means, overall mean, and worst case |
>
> | **Operational efficiency** | Detection-to-dispatch-decision mean ≤ 15 seconds across operators; worst case reported alongside the mean. |
>
> | User Acceptance Testing | UAT scenario results; detection-to-dispatch timing table; defect list; **signed acceptance form** |

#### NEW

The end-to-end collision-visible-to-operator-decision timing target is evaluated during this activity using the observed alert-appearance-to-recorded-decision interval plus approximately 3 seconds of detector accumulation and 2 seconds of alert propagation.

| **Operational efficiency** | Collision-visible-to-operator-decision mean ≤ 25 seconds across operators, estimated as the alert-appearance-to-recorded Confirm or Dismiss decision interval plus approximately 5 seconds; worst case reported alongside the mean. |

| 12 | Operational efficiency (collision-visible to operator decision) | Timed observation during UAT: record elapsed time from the alert appearing in the operator dashboard to the operator’s recorded Confirm or Dismiss decision, then add approximately 3 seconds of detector accumulation and 2 seconds of alert propagation when comparing with the 25-second end-to-end target | Timing table with raw alert-to-decision times, the component allowance, per-operator means, overall mean, and worst case |

| User Acceptance Testing | UAT scenario results; alert-to-decision timing table with the 3-second and 2-second allowances; defect list; **signed acceptance form** |

#### Evidence

This local execution plan is the operative acceptance-criteria source for the test team. Its activity definition, acceptance criterion, and evidence inventory now describe the clarified execution method: observe alert appearance to recorded Confirm/Dismiss decision, then account for approximately 3 seconds of detector accumulation and 2 seconds of alert propagation. The resulting value is a reconstructed end-to-end estimate, not a direct first-visible-frame stopwatch measurement.

#### Proposed comment (same gate as associated replacement)

Previous: The end-to-end detection-to-dispatch timing objective is measured during this activity.

Previous: | 12 | Operational efficiency (detection to dispatch decision) | Timed observation during UAT: elapsed time from the collision becoming visible in the simulated feed to the operator's verification decision, repeated across all operators and multiple incidents | Timing table with per-operator means, overall mean, and worst case |

Previous: | **Operational efficiency** | Detection-to-dispatch-decision mean ≤ 15 seconds across operators; worst case reported alongside the mean. |

Previous: | User Acceptance Testing | UAT scenario results; detection-to-dispatch timing table; defect list; **signed acceptance form** |

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 13. UAT dry-run handoff — OP-J05 metric

Page/s: `UAT_READINESS_DRY_RUN_HANDOFF.md:548`

#### OLD

> | OP-J05 NFR-09 detection-to-dispatch | Visible collision/observable alert onset through manual dispatch decision after confirm, per UAT Journeys | Manual dispatch decision included; snooze excluded | No participant and no controlled timer anchored to visible collision | Not measured — browser/DB timestamps are not a valid human NFR-09 measurement | <=15 seconds | Not run |

#### NEW

| OP-J05 NFR-09 collision-visible-to-operator-decision | Alert appearance in the operator dashboard during OP-J04 | Operator records Confirm or Dismiss | Add approximately 3 seconds of detector accumulation and 2 seconds of alert propagation to the observed alert-to-decision interval; snooze excluded | Not measured — no participant timing from the alert-appearance start was captured in this dry run | ≤25 seconds estimated target | Not run |

#### Evidence

The dry-run contains no valid human timing measurement, so the target is recorded without converting the historical `<=15 seconds` placeholder into a result. The clarified live-run method is an alert-appearance-to-decision observation plus approximately 3 seconds of detector accumulation and 2 seconds of alert propagation.

#### Proposed comment (same gate as associated replacement)

Previous: | OP-J05 NFR-09 detection-to-dispatch | Visible collision/observable alert onset through manual dispatch decision after confirm, per UAT Journeys | Manual dispatch decision included; snooze excluded | No participant and no controlled timer anchored to visible collision | Not measured — browser/DB timestamps are not a valid human NFR-09 measurement | <=15 seconds | Not run |

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 14. Local traceability — Evaluation Scope cross-reference

Page/s: `be_plan/TRACEABILITY.md:290-292`

#### OLD

> 5. **Internal numbering**: the Evaluation Scope cites **NFR-03** for the two-second alert target — it is **NFR-04**. It also cites **NFR-06** for the fifteen-second detection-to-dispatch target — it is **NFR-09**.

#### NEW

5. **Internal numbering**: the Evaluation Scope’s alert-delivery target is **NFR-04** (not NFR-03), and its end-to-end collision-visible-to-operator-decision target is **NFR-09** (not NFR-06). The 25-second target is evaluated as the alert-appearance-to-recorded Confirm or Dismiss decision interval plus approximately 3 seconds of detector accumulation and 2 seconds of alert propagation.

#### Evidence

The Evaluation Scope prose is already covered by the historical, applied Block 4 in `paper_sync/findings/2026-08-27-tense-completion.md`; this local traceability mirror was the remaining stale cross-reference. The clarification is recorded as a reconstructed timing method rather than a direct first-visible-frame measurement.

#### Proposed comment (same gate as associated replacement)

Previous: 5. **Internal numbering**: the Evaluation Scope cites **NFR-03** for the two-second alert target — it is **NFR-04**. It also cites **NFR-06** for the fifteen-second detection-to-dispatch target — it is **NFR-09**.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 15. ADAS Test Execution Tracker — `UAT Journeys`, OP-J05

Page/s: `UAT Journeys`!D6, G6, I6

#### OLD

> D6: Facilitator
>
> 1. Continue directly from OP-J04.
> 2. Present the operational need to silence the audible alarm temporarily.
>
> Logger
>
> 1. Use the genuine collision visible-onset timestamp recorded during OP-J04 as the NFR-09 start.
> 2. Stop NFR-09 when the participant states the manual CDRRMO dispatch/endorsement decision after confirmation.
>
> G6: 1. One Snooze Alarm action snoozes all currently active Unverified alerts with a synchronized expiry and silences the alarm. 2. The blocking popup shows the snoozed state but no countdown. 3. Only the suspected genuine alert becomes Ongoing when confirmed; its snooze clears and its camera stays Paused. 4. The other alert remains Unverified and snoozed for independent review in OP-J06. 5. Detection-to-dispatch time is measured from the genuine collision becoming visible in OP-J04 to the participant’s manual dispatch/endorsement decision and is within 15 seconds, or the measured failure/deviation is recorded. 6. ADAS does not automate dispatch, and no unrelated incident changes.
>
> I6: Result; Detection-to-Dispatch Seconds; Assistance; Notes; Evidence

#### NEW

> D6: Facilitator
>
> 1. Continue directly from OP-J04.
> 2. Present the operational need to silence the audible alarm temporarily.
>
> Logger
>
> 1. Start the observed NFR-09 timer when the genuine alert appears in the operator dashboard during OP-J04.
> 2. Stop NFR-09 when the participant records Confirm Accident for the suspected true alert.
> 3. Add approximately 3 seconds for detector accumulation and 2 seconds for alert propagation when deriving the collision-visible-to-operator-decision estimate.
>
> G6: 1. One Snooze Alarm action snoozes all currently active Unverified alerts with a synchronized expiry and silences the alarm. 2. The blocking popup shows the snoozed state but no countdown. 3. Only the suspected genuine alert becomes Ongoing when confirmed; its snooze clears and its camera stays Paused. 4. The other alert remains Unverified and snoozed for independent review in OP-J06. 5. Alert-to-decision time is measured from the genuine alert appearing in OP-J04 to the participant’s recorded Confirm Accident decision. Add approximately 3 seconds of detector accumulation and 2 seconds of alert propagation; the resulting NFR-09 estimate is within 25 seconds, or the measured failure/deviation is recorded. 6. ADAS does not automate dispatch, and no unrelated incident changes.
>
> I6: Result; Alert-to-Decision Seconds (raw); Assistance; Notes; Evidence

#### Evidence

The pre-write `ADAS Test Execution Tracker` readback on 2026-09-03 showed the OP-J05 row using the old visible-onset/post-confirm wording, the 15-second acceptance criterion, and the `Detection-to-Dispatch Seconds` field; a bounded search found no `25 seconds` text. The user clarified that the executed timing started when the alert appeared, with approximately 3 seconds of detector accumulation and 2 seconds of alert propagation then added. The approved tracker write/readback updated `UAT Journeys!D6`, `G6`, and `I6` to that method and the 25-second target. The three existing OP-J05 raw elapsed values remain 16.0 s, 9.0 s, and 15.0 s; the `Usability Results` formulas now apply the 5-second component allowance and resolve to estimated totals of 21.0 s, 14.0 s, and 20.0 s. The tracker does not separately store a first-visible-frame wall-clock timestamp or a separate allowance value on each raw log row.

#### Proposed comment (same gate as associated replacement)

Previous: D6: Facilitator

1. Continue directly from OP-J04.
2. Present the operational need to silence the audible alarm temporarily.

Logger

1. Use the genuine collision visible-onset timestamp recorded during OP-J04 as the NFR-09 start.
2. Stop NFR-09 when the participant states the manual CDRRMO dispatch/endorsement decision after confirmation.

G6: 1. One Snooze Alarm action snoozes all currently active Unverified alerts with a synchronized expiry and silences the alarm. 2. The blocking popup shows the snoozed state but no countdown. 3. Only the suspected genuine alert becomes Ongoing when confirmed; its snooze clears and its camera stays Paused. 4. The other alert remains Unverified and snoozed for independent review in OP-J06. 5. Detection-to-dispatch time is measured from the genuine collision becoming visible in OP-J04 to the participant’s manual dispatch/endorsement decision and is within 15 seconds, or the measured failure/deviation is recorded. 6. ADAS does not automate dispatch, and no unrelated incident changes.

I6: Result; Detection-to-Dispatch Seconds; Assistance; Notes; Evidence

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 16. ADAS Test Execution Tracker — `UAT Traceability`, NFR-09 row

Page/s: `UAT Traceability`!C30, E30, G30

#### OLD

> C30: Operational Efficiency (Detection-to-Dispatch)
>
> G30: Start when the genuine collision becomes visible during OP-J04; stop when the participant states the manual dispatch/endorsement decision after confirmation in OP-J05. Store the cross-stage duration in the OP-J05 row.

#### NEW

> C30: Operational Efficiency (Collision-Visible-to-Operator Decision)
>
> E30: Execution Log; alert-appearance timestamp; 3-second detector-accumulation and 2-second alert-propagation allowance; linked evidence
>
> G30: Measure the observed interval from the genuine alert appearing during OP-J04 to the participant’s recorded Confirm decision for the genuine alert in OP-J05; for a false-alert run, use the corresponding recorded Dismiss decision. Add approximately 3 seconds of detector accumulation and 2 seconds of alert propagation, apply the <=25-second NFR-09 target to the resulting estimate, and store the raw interval plus allowance in the OP-J05 row.

#### Evidence

The pre-write `UAT Traceability` row 30 named NFR-09 as `Detection-to-Dispatch` and pointed to a visible-onset timestamp while the journey text ended at a post-confirm manual dispatch/endorsement statement. The user clarified that the executed timer began at alert appearance and that the approximately 3-second accumulation plus 2-second propagation components were added. The approved write/readback updated `C30`, `E30`, and `G30` to make that reconstruction explicit while preserving the `Mapped` status.

#### Proposed comment (same gate as associated replacement)

Previous: C30: Operational Efficiency (Detection-to-Dispatch)

E30: Execution Log; facilitator visible-onset timestamp; linked evidence

G30: Start when the genuine collision becomes visible during OP-J04; stop when the participant states the manual dispatch/endorsement decision after confirmation in OP-J05. Store the cross-stage duration in the OP-J05 row.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 17. ADAS Test Execution Tracker — `Usability Results`, NFR-09 calculation

Page/s: `Usability Results`!E4, A15:C16

#### OLD

> E4: OP-J05 Decision Seconds
>
> A15: OP-J05 decision-time mean
> B15: =IFERROR(AVERAGEIF('Execution Log'!B:B,"OP-J05",'Execution Log'!D:D),"")
> C15: NFR-09: <=15 seconds
>
> A16: OP-J05 decision-time worst case
> B16: =IFERROR(MAX(FILTER('Execution Log'!D:D,'Execution Log'!B:B="OP-J05",'Execution Log'!D:D<>"")),"")
> C16: Report alongside mean

#### NEW

E4: Alert-to-Decision Seconds (raw)

A15: OP-J05 NFR-09 estimated mean (alert-to-decision + 3 s + 2 s)
B15: =IFERROR(AVERAGEIF('Execution Log'!B:B,"OP-J05",'Execution Log'!D:D)+3+2,"")
C15: NFR-09: <=25 seconds

A16: OP-J05 NFR-09 estimated worst case (alert-to-decision + 3 s + 2 s)
B16: =IFERROR(MAX(FILTER('Execution Log'!D:D,'Execution Log'!B:B="OP-J05",'Execution Log'!D:D<>""))+3+2,"")
C16: Report alongside mean

#### Evidence

The pre-write calculated `Usability Results` row 15 carried the superseded `<=15 seconds` criterion, and its formulas reported the raw mean and worst case from `Execution Log` without the component allowance. The user clarified that the observed values are alert-appearance-to-decision timings, so the approved formulas now add approximately 3 seconds of detector accumulation and 2 seconds of alert propagation while preserving the raw log values. Readback shows estimated values of approximately 18.3 s mean and 21.0 s worst case from the current 16.0 s, 9.0 s, and 15.0 s entries. This remains a reconstructed estimate, not a direct first-visible-frame wall-clock measurement.

#### Proposed comment (same gate as associated replacement)

Previous: E4: OP-J05 Decision Seconds

Previous: A15: OP-J05 decision-time mean
Previous: B15: =IFERROR(AVERAGEIF('Execution Log'!B:B,"OP-J05",'Execution Log'!D:D),"")
Previous: C15: NFR-09: <=15 seconds

Previous: A16: OP-J05 decision-time worst case
Previous: B16: =IFERROR(MAX(FILTER('Execution Log'!D:D,'Execution Log'!B:B="OP-J05",'Execution Log'!D:D<>"")),"")

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 18. ADAS Test Execution Tracker — `Guide & Examples`, Usability Results example

Page/s: `Guide & Examples`!C18

#### OLD

> Example interpretation: OP-J05 mean 12.4 s, worst 14.9 s, compare with NFR-09.

#### NEW

Example interpretation: Compare OP-J05 raw alert-to-decision mean and worst-case values plus approximately 3 seconds of detector accumulation and 2 seconds of alert propagation with NFR-09’s 25-second target.

#### Evidence

The pre-write guide hard-coded an illustrative mean of 12.4 seconds and worst case of 14.9 seconds, while the calculated results showed raw values of 13.3 seconds and 16.0 seconds. The approved write/readback replaced that stale example in `Guide & Examples!C18` with the clarified raw-plus-allowance comparison and aligned the guide with the revised NFR-09 target.

#### Proposed comment (same gate as associated replacement)

Previous: Example interpretation: OP-J05 mean 12.4 s, worst 14.9 s, compare with NFR-09.

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

### 19. ADAS Test Execution Tracker — `Execution Log`, elapsed-time field

Page/s: `Execution Log`!D1

#### OLD

> Elapsed Seconds

#### NEW

Alert-to-Decision Seconds (raw)

#### Evidence

The approved write/readback renamed `Execution Log!D1` from `Elapsed Seconds` to `Alert-to-Decision Seconds (raw)`. The three OP-J05 values in column D remain 16.0 s, 9.0 s, and 15.0 s, preserving the observed alert-appearance-to-decision interval; the approximately 3-second detector-accumulation and 2-second alert-propagation components are handled by the NFR-09 calculation rather than silently folded into the raw log. The existing user comment on D1 already records that those two components were excluded from the raw timing. Replacement comment `AAACAcFCgoA` was created with the verified provider anchor `{"type":"workbook-range","uid":0,"range":"3669484"}` and read back with the exact `Execution Log!D1` quote.

#### Proposed comment (same gate as associated replacement)

Previous: Elapsed Seconds

Codex ID: PS-20260903-NFR09-25-SECOND-E2E

Done by Codex.

## Companion follow-up outside this package

- Live UAT participant execution remains present in the tracker: OP-J05 records raw alert-to-decision values of 16.0 s, 9.0 s, and 15.0 s. The live `Usability Results` formulas now add the approximately 3-second detector-accumulation and 2-second alert-propagation components, giving reconstructed estimates of 21.0 s, 14.0 s, and 20.0 s, with an approximately 18.3 s mean and 21.0 s worst case. The Sheet does not separately store the component allowance on each raw log row or a direct first-visible-frame wall-clock timestamp.
- The local execution plan, dry-run metric, and traceability mirror are synchronized above. Blocks 15–19 were written to and read back from the live tracker on 2026-09-03. Replacement comment `AAACAcFCgoA` for Block 19 was created and its native anchor verified; comments for Blocks 15–18 remain blocked because the connector did not provide provider-valid native anchors. No defense-paper or audit-Doc write was made.

## Approval / sync ledger

Package ID: `PS-20260903-NFR09-25-SECOND-E2E`

| Target                        | Approved scope                           | Applied/read back                                                                                                                                                                                                                                                                           | Skipped/pending                                                                                                          | Blocked                                                                                                         |
| ----------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Defense paper                 | Blocks 1–7 and their attached comments   | Historical live write/readback for Blocks 1–7 and comments `AAACGdvWZuU`, `AAACGdvw4f8`, `AAACGdvw4go`, `AAACGdvyHWE`, `AAACGdvyHWM`, `AAACGdvyHWU`, `AAACGdwBjVE`; anchors verified 2026-09-03; Block 3’s exact body and native anchor were verified despite a truncated connector preview | —                                                                                                                        | —                                                                                                               |
| ADAS_Paper_Audit plus tracker | Blocks 8–11 and their attached comments  | Historical live write/readback for Blocks 8–10 and comments `AAACGcFzcpM`, `AAACGcFzcpY`, `AAACGcFzcpk`; no complete A6:H6 readback is recorded in this package                                                                                                                             | Block 11 tracker range and live Sheet comment remain pending; A6:H6 includes manual `Reviewed by` state                  | Block 11 Sheet comment: connector returned no provider-valid native anchor; comment not created                 |
| Local companion records       | Blocks 12–14                             | Blocks 12–14 applied in this Git commit; live UAT participant results remain unmodified                                                                                                                                                                                                     | —                                                                                                                        | —                                                                                                               |
| ADAS Test Execution Tracker   | Blocks 15–19 and their attached comments | Blocks 15–19 content written/read back on 2026-09-03; existing OP-J05 raw timing values preserved; `Usability Results` resolves to 18.3 s estimated mean and 21.0 s estimated worst case; comment `AAACAcFCgoA` created/read back on `Execution Log!D1` with a non-empty provider anchor    | Attached comments for Blocks 15–18 remain pending; no provider-valid native anchors were returned for those target cells | Blocks 15–18 Sheet comments require provider-valid native-anchor preflight; no unanchored comments were created |
| Standalone comments           | None proposed                            | —                                                                                                                                                                                                                                                                                           | None                                                                                                                     | —                                                                                                               |
