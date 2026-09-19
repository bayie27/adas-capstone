# 01 — Objectives

> **One-liner:** The objectives promise an integrated collision-detection pipeline, a dashboard that alerts human operators, and evidence for the model and operator decision targets.
> **Panel risk:** high — Objective 1 changed its subject from the YOLO model to the pipeline, and Objective 3 widened its end-to-end time ceiling while clarifying what the clock covers.

## 1. What it is

The objectives are the study’s top-level promises.
They say what the team set out to build and what it must prove.
They are broader than a feature list.
They connect the CDRRMO notification problem to the system and its evaluation.

The paper has three objectives.
Read them as three linked parts of one service:

- **Objective 1** covers how the system detects collision events across camera streams.
- **Objective 2** covers how operators receive those events in the dashboard.
- **Objective 3** covers the model accuracy target and the elapsed time to an operator decision.

The intended path is:

1. A collision appears in a configured camera feed.
2. The AI engine processes the video and forms a collision event.
3. The application sends a visual and audible dashboard alert.
4. An operator reviews the available evidence.
5. The operator records a Confirm or Dismiss decision.
6. The CDRRMO can then begin its manual dispatch or endorsement procedure.

The first objective is a system development commitment.
It is about the integrated detection path, with the custom-trained YOLO detector at its core.
A detector alone does not collect camera frames, schedule inference across streams, build an event from evidence over time, or deliver that event to the application.

The second objective is an operator notification commitment.
The alert dashboard must present the event visually and audibly.
The wording says the CDRRMO can be notified without relying on an external inter-agency endorsement to learn about the accident.

The third objective is an evaluation commitment.
It contains two distinct measures:
the mAP threshold at the stated IoU threshold, and the collision-to-operator-decision time.
These need separate evidence because a frame-level model metric does not measure a human workflow.

The objectives do not claim that ADAS dispatches emergency vehicles.
They describe detection, notification, operator verification, and support for the next manual procedure.
The human operator remains responsible for the Confirm or Dismiss decision.

### Read the three promises at the right level

| Objective | The promise                                                                                                               | What evidence must support it                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1         | Develop a real-time collision-detection pipeline that uses a custom-trained YOLO detector across multiple camera streams. | Pipeline behavior, event-level detection evidence, and tested stream performance.    |
| 2         | Deliver immediate visual and audible notifications through the operator dashboard.                                        | Dashboard alert presentation, audible notification, and alert-delivery evidence.     |
| 3         | Meet the paper’s mAP and end-to-end operator-decision targets.                                                            | Qualified validation-split mAP evidence and the tracker’s qualified timing evidence. |

The proof is distributed across the guide pack.
Use the objectives guide to explain the promise and the change history.
Use the topic guides for the implementation and result details.

## 2. Where it lives

### In the paper

- **Chapter 1, “Objectives of the Study”** contains all three current objective statements.
  The table of contents points to page 13.
- **Chapter 1, “Scope and Delimitations”** limits the study to a proof-of-concept evaluated on researcher-controlled hardware and simulated or authorized test feeds.
  It excludes production-scale deployment and automated dispatch.
- **Chapter 3, Table 3, “Performance Requirements,” NFR-01** states the mAP and IoU threshold.
- **Chapter 3, Table 3, NFR-04** states the dashboard alert and alarm delivery time.
- **Chapter 3, Table 5, “Usability Requirements,” NFR-09** defines the collision-visible-to-operator-decision boundary and the 25-second limit.
- The full wording for the prior Objective 1 appears in the historical “OLD” block of paper_sync/findings/2026-09-02-objective-1-detection-pipeline.md.
- The prior sub-15-second Objective 3 wording appears in the historical “OLD” block of paper_sync/findings/2026-09-03-nfr09-25-second-end-to-end.md.
  Those records are used for the before-and-after wording.
  The current paper supplies the current objectives.

The paper is the authority for what the objectives mean.
The test plan and execution tracker are the authority for how their measurable claims were evaluated.
The guide catalogue identifies where to study each proof.

### In the code

| Part of the promise                                                    | Code location                                                                                 |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Select the newest frame from each eligible camera and prepare a batch. | ai_engine/pipeline.py:111 and ai_engine/pipeline.py:149                                       |
| Run batched YOLO inference.                                            | ai_engine/detector.py:162 and ai_engine/detector.py:188                                       |
| Accumulate detections into collision events over time.                 | ai_engine/accumulate.py:77                                                                    |
| Handle a fired event and persist it through the durable outbox.        | ai_engine/accident.py:46                                                                      |
| Receive an AI event in the backend.                                    | backend/app/api/routes/internal.py:94                                                         |
| Handle the browser’s NEW_DETECTION event.                              | frontend/src/components/RealtimeAlertsBridge.tsx:103                                          |
| Play the audible notification.                                         | frontend/src/utils/detectionSound.ts:55                                                       |
| Present Confirm and Dismiss actions to the operator.                   | frontend/src/components/GlobalAlerts.tsx:401 and frontend/src/components/GlobalAlerts.tsx:408 |
| Record the operator’s confirmation or dismissal request.               | backend/app/api/routes/alerts.py:465 and backend/app/api/routes/alerts.py:518                 |

The objective is a study claim, not a source-code symbol.
The code locations explain the mechanism.
The paper and tracker establish the target and the result.

### In the test record

- The test plan’s operational-efficiency method measures alert-appearance-to-decision time during UAT.
- It adds an approximately 3-second detector-accumulation allowance and an approximately 2-second alert-propagation allowance to reconstruct the collision-visible-to-decision estimate.
- The tracker stores the objective’s model evidence in AI Model Validation, AI-VAL-001.
- The tracker stores the UAT timing instructions in UAT Journeys, OP-J05.
- The raw UAT timing observations are in Execution Log, OP-J05.
- Dashboard response evidence is in Performance & Load Testing, TC-PERF-003 and TC-PERF-004.

## 3. How it works

### The service path in plain language

The system watches configured video streams.
The AI engine looks for collision evidence and creates an event.
The application carries the event to an operator dashboard.
The operator reviews it and records a decision.

Objective 1 covers the detection path through event creation.
Objective 2 covers the dashboard notification.
Objective 3 evaluates the model metric and the time from visible collision to human decision.

### The event path step by step

1. The AI engine collects the newest available frame from each eligible camera.
   This makes the detector part of a multi-camera pipeline rather than an isolated model call.

2. The detector analyzes the collected frames in a batch.
   It returns frame-level candidate detections.

3. The temporal accumulator uses detections over time to form an event.
   A single candidate frame is not itself the operator alert.

4. When an event fires, the AI engine handles it and creates the event payload and visual evidence.
   The camera’s ingestion behavior is also updated as part of event handling.

5. The backend receives the event at its internal alert route.
   The application records the alert and makes it available to clients.

6. The browser receives a NEW_DETECTION message through the realtime alert bridge.
   That message updates the dashboard’s alert state.

7. The dashboard presents the alert and invokes the configured audible notification.
   The operator can inspect the incident image and the information displayed with it.

8. The operator selects Confirm Accident or Dismiss Accident.
   The backend records the operator action through the corresponding alert route.

9. The test plan compares the decision time with the Objective 3 ceiling.
   The UAT observation begins when the genuine alert appears in the dashboard.
   The plan then adds the detector and propagation allowances to estimate the full collision-visible interval.

### What each objective asks you to prove

**Objective 1 asks for a working pipeline.**

Show that the system can take configured camera streams through inference and event creation.
Explain the roles of stream collection, YOLO inference, temporal evidence accumulation, event handling, and backend delivery.
For performance, use the recorded stream tests and their stated hardware and stream-count qualifications.
For detection quality, use the event-level corpus results as well as the frame-level metric where relevant.

A mAP figure alone does not prove Objective 1.
The mAP calculation describes frame-level detection on a validation split.
It does not prove that the whole pipeline raises a useful event on every operational collision clip.

**Objective 2 asks for a working alert experience.**

Show that a generated event is displayed to the operator.
Show that the alert includes its captured image and that the audible alarm path is exercised.
Explain how the operator reviews and records Confirm or Dismiss.
Use the alert-response result with its simulation and audio-test qualifications.

“Without reliance on external inter-agency endorsements” means the CDRRMO can receive the system alert directly.
It does not mean ADAS sends dispatch instructions to another agency.
It does not mean the system takes over the operator’s decision.

**Objective 3 asks for two independent forms of evidence.**

For accuracy, report mAP at the paper’s IoU threshold and identify the dataset split and its limitations.
For workflow time, report the raw alert-to-decision observations separately from the reconstructed estimate.
Keep both measures attached to their own proof.

The 25-second clock is defined by NFR-09.
It starts when the collision first becomes visible in the monitored camera feed.
It ends when the operator records Confirm or Dismiss.
The test record reconstructs that clock from a measured dashboard-alert segment plus the stated allowances.

## 4. Why it was built this way

### Earlier wording and current wording

The current paper is authoritative for the current wording.
The earlier wording below is reproduced from the revision records so the team can explain the change.
Objective 2 has no separate replacement recorded; its current wording is treated as carried forward.

| Objective | Earlier wording                                                                                                                                                                                                                                                                                                                                   | Current paper wording                                                                                                                                                                                                                                                                                                                                                              |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | To develop a custom-trained YOLO model capable of detecting vehicle-to-vehicle accidents in real-time across multiple camera streams, automating the surveillance process to overcome the limitations of manual monitoring.                                                                                                                       | To develop a real-time vehicle-to-vehicle collision detection pipeline, with a custom-trained YOLO detector at its core, capable of identifying collision events across multiple camera streams, thereby reducing reliance on manual monitoring.                                                                                                                                   |
| 2         | No replacement wording is recorded. The dashboard-notification commitment is carried forward.                                                                                                                                                                                                                                                     | To develop a real-time alert dashboard that delivers immediate visual and audible notifications to operators, enabling Lipa CDRRMO to be notified of accidents without reliance on external inter-agency endorsements.                                                                                                                                                             |
| 3         | To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50) and a sub-15-second end-to-end collision-to-operator-decision latency, ensuring effective minimization of the notification gap and facilitating faster emergency intervention to mitigate injury severity and traffic congestion. | To validate the system’s performance by achieving a minimum Mean Average Precision (mAP) of 85% (at Intersection over Union [IoU] ≥ 0.50) and a 25-second end-to-end collision-to-operator-decision latency, reducing the notification gap and supporting faster initiation of the CDRRMO’s dispatch or endorsement procedures to mitigate injury severity and traffic congestion. |

The previous Objective 1 wording is from the recorded revision history.
The current Objective 1 wording is in Chapter 1, “Objectives of the Study.”
The previous Objective 3 wording is from the recorded revision history.
The current Objective 3 wording is in the same paper section.
The paper’s NFR-09 row supplies the precise start and end events used for the current time measure.

### Why Objective 1 names the pipeline

The earlier wording makes the model the subject of the objective.
That wording can sound as if YOLO alone performs continuous surveillance and produces a collision event.

The implemented system has several stages around the detector.
It collects frames from camera streams.
It schedules and batches inference.
It accumulates evidence over time.
It creates an event and passes it to the backend.

The current wording keeps the custom-trained YOLO detector at the center of the work.
It names the pipeline as the unit the study develops.
That matches the team’s actual proof obligation: the components must work together across multiple streams.

The phrase “reducing reliance on manual monitoring” describes the intended operational benefit.
It does not claim to remove operators from the workflow.
Objective 2 separately promises the operator alert surface.
The operator still verifies the event and makes the Confirm or Dismiss decision.

### Why Objective 2 stays distinct

Objective 2 describes what operators receive.
Objective 1 describes how a collision event is produced.
Keeping the statements separate makes the handoff visible.

The visual alert, captured image, and audible alarm are user-facing outcomes.
The test plan evaluates the alert within the NFR-04 response limit.
The UAT journey then evaluates what the operator does after the alert arrives.

The notification can reduce dependence on delayed external reports.
It does not replace inter-agency coordination after the operator reviews the event.
It does not promise automated emergency dispatch.

### Why Objective 3 moved from under 15 seconds to 25 seconds

The earlier target was a strict sub-15-second total.
The current target is a 25-second collision-visible-to-operator-decision ceiling.
The revised boundary accounts for the pipeline before the operator decision.

The current measurement begins at the first visible collision frame.
It ends at the operator’s recorded Confirm or Dismiss decision.
That boundary includes the time needed to form and deliver the alert and the time needed for human review.

The test plan explicitly records two allowances:

| Component                              | Allowance                                          | How the plan uses it                                                                                              |
| -------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Detector accumulation                  | Approximately 3 seconds                            | Added because evidence must accumulate before an alert fires.                                                     |
| Alert propagation                      | Approximately 2 seconds                            | Added for backend, WebSocket, and dashboard delivery.                                                             |
| Alert appearance to operator decision  | Up to approximately 20 seconds of remaining budget | Derived from the 25-second ceiling after the two stated allowances; the tracker measures this segment during UAT. |
| Collision visible to operator decision | 25 seconds maximum                                 | The end-to-end acceptance boundary stated in the paper and test plan.                                             |

The 20-second remainder is arithmetic: 25 seconds minus approximately 3 seconds and approximately 2 seconds.
It is a budget for the measured operator segment.
It is not a separate raw 20-second measurement in the tracker.

The test plan says to report the raw alert-to-decision observations separately.
It says to add the two allowances only when deriving the collision-visible estimate.
It does not claim automatic dispatch timing or direct DSS timing.

### What the UAT observations show

The tracker records three Operator OP-J05 raw alert-to-decision observations:

| UAT entry | Raw alert-to-decision time | Reconstructed estimate after adding 5 seconds |
| --------- | -------------------------: | --------------------------------------------: |
| OP-01     |               16.0 seconds |                                  21.0 seconds |
| OP-02     |                9.0 seconds |                                  14.0 seconds |
| OP-03     |               15.0 seconds |                                  20.0 seconds |

The raw values are in ADAS Test Execution.xlsx, Execution Log, cells D6, D15, and D24.
The OP-J05 instructions in UAT Journeys cell G6 specify the timing boundary and the two allowances.
The reconstructed values are calculated by adding the stated 3-second and 2-second allowances to each raw observation.

All three reconstructed estimates are within the 25-second target.
These estimates are not three direct wall-clock measurements beginning at the collision’s first visible frame.
Use the tracker’s wording: raw observations plus a reconstructed allowance.

### Why the change is defensible

The numeric ceiling is wider than the former sub-15-second target.
Say so plainly if asked.

The revised target also covers a more complete and observable workflow.
It has a defined start event, a defined operator decision, and a component budget.
The test plan keeps measured human response separate from the detector and alert allowances.

The change does not mean that a 25-second result is presented as automatic dispatch.
The paper says the target supports faster initiation of manual dispatch or endorsement procedures.
The operator’s recorded decision remains the measured endpoint.

Objective 3 also keeps the mAP threshold.
The paper’s target remains 85% mAP at IoU ≥ 0.50.
The test tracker reports a qualified validation-split result for that measure.
The event-level test evidence remains separate from that frame-level result.

## 5. What changed since the 28 April defense

The earlier wording recorded for the objectives made the YOLO model the subject of Objective 1.
The current paper names the real-time collision-detection pipeline and retains YOLO as its core detector.

Objective 2 keeps the dashboard promise.
It remains the separate commitment to visual and audible operator notifications.

The earlier Objective 3 wording required a sub-15-second end-to-end interval.
The current paper sets a 25-second collision-to-operator-decision interval.
NFR-09 makes the boundary specific: first visible collision frame to recorded Confirm or Dismiss decision.

The mAP threshold stayed in Objective 3.
The time target changed.
The test plan now separates the UAT alert-to-decision measurement from the detector-accumulation and alert-propagation allowances.

The practical defense shift is this:

- Describe a multi-stage pipeline when asked how collisions become alerts.
- Describe the dashboard and the human decision separately from detection.
- Treat the 25-second result as a reconstructed end-to-end estimate.
- State that the numeric ceiling widened and explain the clarified measurement boundary.

## 6. Limits and honest caveats

**The model metric is qualified.**
The tracker reports accident mAP@0.50 of 0.956 for epoch50.pt.
The original validation split was not available for a fresh rerun.
The tracker discloses frame-level incident leakage and does not present the figure as independent operational detection accuracy.
See AI Model Validation cells H2 and K2.

**Event-level detection has a separate limitation.**
The tracker’s frozen-corpus run records 8 hits among 16 crash clips.
It records 8 hits among 10 standard clips and 0 among 6 hard clips.
Those results are descriptive; the tracker records no approved event-recall threshold.
See AI Model Validation cells H3 and H4.

**The UAT timing is reconstructed.**
The raw clock starts when the genuine alert appears in the dashboard.
The collision-visible estimate adds approximately 3 seconds for accumulation and 2 seconds for propagation.
Do not say the three UAT timings were directly timed from the first visible collision frame.

**The alert-response result has a qualification.**
TC-PERF-003 used controlled browser simulation for the visual alert and snapshot.
The alarm path used component-level instrumentation.
Report the result with that qualification.

**The proof-of-concept has a bounded scope.**
The paper says testing used researcher-controlled hardware and simulated or authorized feeds.
The objective does not establish production-scale performance across Lipa’s camera network.
The scope excludes automated dispatch and direct workflow support for field responders.

**Objective 2 is about operator awareness.**
The dashboard can make the operator aware of a generated alert without waiting for an external endorsement.
The objective does not say another agency receives a dispatch command from ADAS.

**The paper and tracker do not name an individual approver for the wording change.**
If the panel asks who approved it, identify the person only from the team’s signed or recorded approval evidence.
Do not infer formal approval from a tracker result or a paper edit.

## 7. Likely panel questions

**“Did you weaken your objectives to make them easier to hit?”**

The 25-second ceiling is numerically wider than the previous sub-15-second target.
We revised it to cover the actual path from a visible collision through detector accumulation, alert delivery, and a recorded operator decision.
We report the human timing raw and show the added system allowances separately.

**“Who approved the change?”**

The current paper and test plan use the revised wording and acceptance boundary.
The cited study and test records do not identify an individual approver.
We would name the approver only from the signed or recorded approval evidence.

**“Which objective was hardest to meet?”**

Objective 1 was hardest to substantiate at event level because it depends on the full stream-to-alert pipeline.
The frozen-corpus tracker records 8 of 16 crash clips detected and 0 of 6 hard clips detected.
We report those limits directly instead of treating the mAP score as an operational recall result.

**“Why did Objective 1 move from a YOLO model to a pipeline?”**

YOLO produces frame-level candidates.
The system also has to collect and schedule camera frames, accumulate evidence, create an event, and deliver it to the backend.
The revised wording keeps YOLO at the core and describes the full unit the team developed.

**“What exactly does Objective 2 guarantee?”**

It commits the team to a dashboard that presents visual and audible alerts to operators.
The test plan measures dashboard alert delivery under NFR-04 and the tracker qualifies the simulation used.
The objective supports operator awareness; it does not claim that ADAS dispatches responders.

**“Does the 25-second target mean dispatch happens in 25 seconds?”**

No.
The clock ends when the operator records Confirm or Dismiss.
The result supports faster initiation of manual dispatch or endorsement procedures, which remain outside the measured endpoint.

**“Did you time 25 seconds from the first visible collision frame?”**

The UAT raw observations begin when the genuine alert appears in the dashboard.
The plan adds approximately 3 seconds for detector accumulation and 2 seconds for alert propagation to reconstruct the collision-visible interval.
We present the result as an estimate, not a direct full-path stopwatch reading.

**“Did you meet the 85% accuracy target?”**

The tracker records 0.956 accident mAP at IoU 0.50, above the 0.85 threshold.
It is a qualified validation-split result because the original split was not rerun and frame-level incident leakage is disclosed.
We do not call it independent operational detection accuracy.

## 8. Cram summary

- Objective 1 promises a real-time collision-detection pipeline with a custom-trained YOLO detector at its core.
- Objective 2 promises visual and audible dashboard alerts so operators can receive events directly.
- Objective 3 keeps the 85% mAP target at IoU ≥ 0.50 and sets the 25-second collision-visible-to-operator-decision target.
- The 25-second test estimate adds approximately 3 seconds for detector accumulation and approximately 2 seconds for alert propagation to the measured alert-to-decision time.
- The three OP-J05 raw times are 16.0, 9.0, and 15.0 seconds; the reconstructed estimates are 21.0, 14.0, and 20.0 seconds.
- mAP 0.956 is qualified validation-split evidence; event-level recall is 8 of 16 overall and 0 of 6 hard clips.
- Study the pipeline in guide 24, operator alerts in guides 20 and 21, accuracy in guide 26, performance timing in guide 27, and consolidated results in guide 05.
