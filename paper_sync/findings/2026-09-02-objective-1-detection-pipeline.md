---
section: Objectives of the Study
page/s: "13 (live TOC; native range 15501–15720)"
required_revision: Reframe Objective 1 around the integrated AI detection pipeline rather than the YOLO model alone.
notes: The selected wording makes YOLO the core detector within a broader multi-camera detection pipeline. Objective 2 separately covers dashboard alerts.
status: Not started
assigned_to: Daniboy
synced: 2026-09-02
---

## Changes

### 1. Defense paper — Objectives of the Study, Objective 1

Page/s: 13 per the live document table of contents; native range `15501–15720`, tab `t.y7ms6bhlk4qn`

#### OLD

> To develop a custom-trained YOLO model capable of detecting vehicle-to-vehicle accidents in real-time across multiple camera streams, automating the surveillance process to overcome the limitations of manual monitoring.

#### NEW

To develop a real-time vehicle-to-vehicle collision detection pipeline, with a custom-trained YOLO detector at its core, capable of identifying collision events across multiple camera streams, thereby reducing reliance on manual monitoring.

#### Evidence

The live paper's Objective 1 is the OLD text above. The implementation treats YOLO as the core model within a broader engine: `ai_engine/detector.py:90-105` performs batched inference, while `ai_engine/pipeline.py:84-87,111-127,167-206` schedules the newest frames from eligible cameras and routes detected events onward. The live tracker already contains an open Objective 1 item at `🚩 Action Stream` row 74; this finding does not create a duplicate tracker row.

#### Proposed comment (same gate as associated replacement)

Previous: To develop a custom-trained YOLO model capable of detecting vehicle-to-vehicle accidents in real-time across multiple camera streams, automating the surveillance process to overcome the limitations of manual monitoring.

Codex ID: PS-20260902-OBJECTIVE-1-DETECTION-PIPELINE

Done by Codex.

### 2. Defense paper — Definition of Terms, “YOLO (You Only Look Once)”

Page/s: 17 per the live document table of contents; native range `35150–35345`, tab `t.y7ms6bhlk4qn`

#### OLD

> The custom-trained AI computer vision model utilized by the edge server to passively process standard optical video feeds and autonomously detect vehicle-to-vehicle collisions in real time.

#### NEW

The custom-trained AI computer vision model at the core of the edge server’s collision-detection pipeline, used to process standard optical video frames and produce frame-level candidate detections in real time.

#### Evidence

The live definition assigns autonomous collision detection directly to the YOLO model. The implementation separates model inference from the broader detection engine: `ai_engine/detector.py:70-105` owns the YOLO model and returns per-frame detections, while the pipeline and event-processing layers determine when a collision event is emitted. This is a direct consistency edit with the revised Objective 1; it does not change the model’s role as the pipeline’s core detector.

#### Proposed comment (same gate as associated replacement)

Previous: The custom-trained AI computer vision model utilized by the edge server to passively process standard optical video feeds and autonomously detect vehicle-to-vehicle collisions in real time.

Codex ID: PS-20260902-OBJECTIVE-1-DETECTION-PIPELINE

Done by Codex.

### 3. Defense paper — System Architecture and Design, opening paragraph

Page/s: 89 per the live document table of contents; native range `134518–134886`, tab `t.y7ms6bhlk4qn`

#### OLD

> The system is a localized edge-computing solution that automates continuous traffic camera monitoring. It ingests CCTV network streams and employs a custom-trained YOLO object detection model to identify vehicle-to-vehicle collisions in real time. Upon detection, the system captures visual evidence and transmits an immediate alert to a centralized command dashboard.

#### NEW

The system is a localized edge-computing solution that supports continuous traffic-camera monitoring through an integrated collision-detection pipeline. It ingests CCTV network streams and uses a custom-trained YOLO detector at the core of the pipeline to identify vehicle-to-vehicle collision events in real time. Upon detection, the system captures visual evidence and transmits an immediate alert to a centralized command dashboard.

#### Evidence

The live architecture opening currently attributes continuous monitoring and collision identification directly to the YOLO model. The implemented AI engine has separate stream scheduling and inference responsibilities in `ai_engine/pipeline.py:84-127` and `ai_engine/detector.py:70-105`; the proposed wording preserves YOLO as the core while describing the pipeline as the system-level unit.

#### Proposed comment (same gate as associated replacement)

Previous: The system is a localized edge-computing solution that automates continuous traffic camera monitoring. It ingests CCTV network streams and employs a custom-trained YOLO object detection model to identify vehicle-to-vehicle collisions in real time. Upon detection, the system captures visual evidence and transmits an immediate alert to a centralized command dashboard.

Codex ID: PS-20260902-OBJECTIVE-1-DETECTION-PIPELINE

Done by Codex.

### 4. Defense paper — System Architecture and Design, Operations and Warning Division paragraph

Page/s: 89 per the live document table of contents; native range `134887–135362`, tab `t.y7ms6bhlk4qn`

#### OLD

> The Operations and Warning Division of the Lipa CDRRMO serves as the primary user of the system. Automating the surveillance detection phase enables the system to overcome the limitations of manual monitoring of a large-scale citywide camera network, which has previously led to missed or delayed incident identification. The integration of AI-driven automation reduces dependence on delayed inter-agency endorsements and effectively addresses the emergency notification gap.

#### NEW

The Operations and Warning Division of the Lipa CDRRMO serves as the primary user of the system. Real-time collision detection reduces reliance on manual monitoring of a large-scale citywide camera network, which has previously led to missed or delayed incident identification. The integration of AI-assisted detection reduces dependence on delayed inter-agency endorsements and effectively addresses the emergency notification gap.

#### Evidence

This paragraph repeats the broader “automating the surveillance” framing removed from Objective 1. The revised wording retains the operational benefit—less dependence on manual monitoring and delayed endorsements—without implying that the entire surveillance function is autonomous. The adjacent swimlane narrative already states that AI detection assists the command center and that final verification remains under human supervision (`134887–135362` and `141388–141902`).

#### Proposed comment (same gate as associated replacement)

Previous: The Operations and Warning Division of the Lipa CDRRMO serves as the primary user of the system. Automating the surveillance detection phase enables the system to overcome the limitations of manual monitoring of a large-scale citywide camera network, which has previously led to missed or delayed incident identification. The integration of AI-driven automation reduces dependence on delayed inter-agency endorsements and effectively addresses the emergency notification gap.

Codex ID: PS-20260902-OBJECTIVE-1-DETECTION-PIPELINE

Done by Codex.

## No change recommended

- Project Scope and Boundaries already describes the AI engine, RTSP feeds, event-level evaluation, and operator HITL review at native range `16306–17720`.
- The AI Engine architecture narrative already distinguishes batched YOLO inference from temporal event processing at native range `136385–137299`.
- FR-05, NFR-01, the data dictionary, and the swimlane narrative describe system-level detection or model-level metrics at the appropriate abstraction level.
- Chapter 2 passages about autonomous surveillance describe the literature or the problem context, not ADAS’s internal implementation, and should remain unless separately revised for another reason.
- Testing passages that say “the YOLO model” and carry mAP/IoU or false-positive claims are separate accuracy/acceptance issues already present in the audit trail; they should not be silently changed as part of this objective wording package.

## Approval / sync ledger

| Target                        | Approved scope                                                                         | Applied/read back                                       | Skipped/pending | Blocked |
| ----------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------- | ------- |
| Defense paper                 | Blocks 1–4 and their attached comments                                                 | Blocks 1–4 and 4 anchored comments, verified 2026-09-02 | —               | —       |
| ADAS_Paper_Audit plus tracker | No live write proposed; existing Action Stream row 74 remains the live tracking record | —                                                       | —               | —       |
| Standalone comments           | None; every comment is attached to its corresponding defense-paper replacement         | —                                                       | —               | —       |
