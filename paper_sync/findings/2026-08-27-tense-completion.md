---
section: Whole paper — completion-oriented tense
page/s: "unconfirmed rendered pages; TOC pp. 22, 30, 41, 45, 48, 58, 92, 94, 105, 129, 142"
required_revision: Replace future/proposal wording with completed-study or present-system wording while retaining the documented proof-of-concept and target-production boundary.
notes: This package supersedes the wording scope of live tracker item 0.13. It does not claim a production CDRRMO deployment; it reports the user-confirmed completed TensorRT export at batch size 32.
status: Not started
assigned_to: Enjey
synced: 2026-08-27
---

## Changes

### 1. Defense paper — Chapter 2, Review of Related Literature and Studies

Page/s: unconfirmed rendered page (TOC: 22)

#### OLD

> This chapter provides a comprehensive review of the theoretical and technical literature underpinning the proposed system. It examines the intersection of human cognitive limitations in continuous CCTV monitoring, advancements in deep learning architectures for high-speed object detection, and the hardware constraints associated with deploying artificial intelligence in provincial local government units. By integrating current research across multiple disciplines, including the physiological limitations of manual surveillance and the computational demands of edge-based computer vision, this review identifies the specific operational gap addressed by the proposed system. Additionally, it establishes the academic and technical justification for utilizing a localized, single-stage YOLO architecture coupled with an HITL framework, thereby supporting both high accuracy in complex local traffic scenarios and practical feasibility for the Lipa CDRRMO.

#### NEW

This chapter provides a comprehensive review of the theoretical and technical literature underpinning ADAS. It examines the intersection of human cognitive limitations in continuous CCTV monitoring, advancements in deep learning architectures for high-speed object detection, and the hardware constraints associated with deploying artificial intelligence in provincial local government units. By integrating current research across multiple disciplines, including the physiological limitations of manual surveillance and the computational demands of edge-based computer vision, this review identifies the specific operational gap addressed by ADAS. Additionally, it establishes the academic and technical justification for utilizing a localized, single-stage YOLO architecture coupled with an HITL framework, thereby supporting both high accuracy in complex local traffic scenarios and practical feasibility for the Lipa CDRRMO.

#### Evidence

Current native paragraph range `35399–36357`, verified 2026-08-27. This is terminology-only; it removes proposal language without changing the literature review's present-tense analysis.

#### Proposed comment (same gate as associated replacement)

Previous: This chapter provides a comprehensive review of the theoretical and technical literature underpinning the proposed system. It examines the intersection of human cognitive limitations in continuous CCTV monitoring, advancements in deep learning architectures for high-speed object detection, and the hardware constraints associated with deploying artificial intelligence in provincial local government units. By integrating current research across multiple disciplines, including the physiological limitations of manual surveillance and the computational demands of edge-based computer vision, this review identifies the specific operational gap addressed by the proposed system. Additionally, it establishes the academic and technical justification for utilizing a localized, single-stage YOLO architecture coupled with an HITL framework, thereby supporting both high accuracy in complex local traffic scenarios and practical feasibility for the Lipa CDRRMO.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 2. Defense paper — Chapter 2, Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision

Page/s: unconfirmed rendered page (TOC: 30)

#### OLD

> Synthesizing these findings, the architecture of the proposed system requires processing multiple simultaneous RTSP streams via multiprocessing on localized edge hardware. Prioritizing a lightweight model targeting an 85% mAP prevents the severe latency bottlenecks identified in the literature. Furthermore, because the system implements a strict "Human-in-the-Loop" workflow, where human operators ultimately verify generated snapshots prior to dispatching emergency responders, this performance threshold guarantees rapid early-warning detection. This approach minimizes the critical notification gap without demanding the prohibitive computational resources that a near-perfect mAP model would otherwise dictate.

#### NEW

Synthesizing these findings, the architecture of ADAS requires processing multiple simultaneous RTSP streams via multiprocessing on localized edge hardware. Prioritizing a lightweight model targeting an 85% mAP prevents the severe latency bottlenecks identified in the literature. Furthermore, because the system implements a strict "Human-in-the-Loop" workflow, where human operators ultimately verify generated snapshots prior to dispatching emergency responders, this performance threshold guarantees rapid early-warning detection. This approach minimizes the critical notification gap without demanding the prohibitive computational resources that a near-perfect mAP model would otherwise dictate.

#### Evidence

Current native paragraph range `52868–53584`, verified 2026-08-27. Terminology-only change.

#### Proposed comment (same gate as associated replacement)

Previous: Synthesizing these findings, the architecture of the proposed system requires processing multiple simultaneous RTSP streams via multiprocessing on localized edge hardware. Prioritizing a lightweight model targeting an 85% mAP prevents the severe latency bottlenecks identified in the literature. Furthermore, because the system implements a strict "Human-in-the-Loop" workflow, where human operators ultimately verify generated snapshots prior to dispatching emergency responders, this performance threshold guarantees rapid early-warning detection. This approach minimizes the critical notification gap without demanding the prohibitive computational resources that a near-perfect mAP model would otherwise dictate.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 3. Defense paper — Chapter 2, Synthesis

Page/s: unconfirmed rendered page (TOC: 41)

#### OLD

> Finally, the literature explicitly warns against deploying fully autonomous AI in public safety contexts due to the psychological risks of automation bias and a lack of accountability. As a result, integrating a HITL framework is both an operational and ethical requirement. By employing edge-deployed AI to filter routine traffic and rapidly escalate verified collisions to a specialized dashboard, the system reduces operator alert fatigue. This approach forms the foundation of the proposed study: a resource-efficient, locally trained AI that functions as a high-speed detection model, transforming the local command center from a reactive monitoring station into a proactive, highly responsive emergency dispatch hub.

#### NEW

Finally, the literature explicitly warns against deploying fully autonomous AI in public safety contexts due to the psychological risks of automation bias and a lack of accountability. As a result, integrating a HITL framework is both an operational and ethical requirement. By employing edge-deployed AI to filter routine traffic and rapidly escalate verified collisions to a specialized dashboard, the system reduces operator alert fatigue. This approach formed the foundation of this study: a resource-efficient, locally trained AI that functions as a high-speed detection model, transforming the local command center from a reactive monitoring station into a proactive, highly responsive emergency dispatch hub.

#### Evidence

Current native paragraph range `72518–73241`, verified 2026-08-27. The change preserves the literature conclusion while referring to the completed study.

#### Proposed comment (same gate as associated replacement)

Previous: Finally, the literature explicitly warns against deploying fully autonomous AI in public safety contexts due to the psychological risks of automation bias and a lack of accountability. As a result, integrating a HITL framework is both an operational and ethical requirement. By employing edge-deployed AI to filter routine traffic and rapidly escalate verified collisions to a specialized dashboard, the system reduces operator alert fatigue. This approach forms the foundation of the proposed study: a resource-efficient, locally trained AI that functions as a high-speed detection model, transforming the local command center from a reactive monitoring station into a proactive, highly responsive emergency dispatch hub.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 4. Defense paper — Chapter 3, Project Scope and Boundaries, Evaluation Scope

Page/s: unconfirmed rendered page (TOC: 45)

#### OLD

> Evaluation Scope: System performance will be evaluated against the model-validation objectives for mAP and IoU. Event-level detection results from held-out Lipa CDRRMO CCTV clips will provide additional evidence of field relevance and model behaviour. The evaluation will also assess inference cadence and latency, alert-delivery performance, and operator workflow efficiency. The alerting workflow supports operator decision-making and incident lifecycle management; it does not automate or measure emergency dispatch. Any reported mAP, IoU, alert-delivery, or workflow-time result will be supported by the corresponding final evidence.

#### NEW

Evaluation Scope: System performance was evaluated against the model-validation objectives for mAP and IoU. Event-level detection results from held-out Lipa CDRRMO CCTV clips provided additional evidence of field relevance and model behaviour. The evaluation also assessed inference cadence and latency, alert-delivery performance, and operator workflow efficiency. The alerting workflow supports operator decision-making and incident lifecycle management; it does not automate or measure emergency dispatch. Any reported mAP, IoU, alert-delivery, or workflow-time result was supported by the corresponding final evidence.

#### Evidence

Current native paragraph range `76218–76855`, verified 2026-08-27. The paper's Testing Strategy Overview states that all testing was conducted in a controlled LAN staging environment (native range `209723–210783`).

#### Proposed comment (same gate as associated replacement)

Previous: Evaluation Scope: System performance will be evaluated against the model-validation objectives for mAP and IoU. Event-level detection results from held-out Lipa CDRRMO CCTV clips will provide additional evidence of field relevance and model behaviour. The evaluation will also assess inference cadence and latency, alert-delivery performance, and operator workflow efficiency. The alerting workflow supports operator decision-making and incident lifecycle management; it does not automate or measure emergency dispatch. Any reported mAP, IoU, alert-delivery, or workflow-time result will be supported by the corresponding final evidence.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 5. Defense paper — Chapter 3, Project Scope and Boundaries, What Is Excluded

Page/s: unconfirmed rendered page (TOC: 45)

#### OLD

> The AI detection is limited to vehicle-to-vehicle collision events. The detection of pedestrian accidents, traffic rule violations, theft, fires, infrastructure damage, or any other event category is explicitly outside the scope of the current AI detection and will not be addressed in this study.

#### NEW

The AI detection is limited to vehicle-to-vehicle collision events. The detection of pedestrian accidents, traffic rule violations, theft, fires, infrastructure damage, or any other event category is explicitly outside the scope of the current AI detection and was not addressed in this study.

#### Evidence

Current native paragraph range `78247–78544`, verified 2026-08-27. This retains the system limitation but makes the completed study boundary explicit.

#### Proposed comment (same gate as associated replacement)

Previous: The AI detection is limited to vehicle-to-vehicle collision events. The detection of pedestrian accidents, traffic rule violations, theft, fires, infrastructure damage, or any other event category is explicitly outside the scope of the current AI detection and will not be addressed in this study.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 6. Defense paper — Chapter 3, Project Scope and Boundaries, What Is Excluded

Page/s: unconfirmed rendered page (TOC: 45)

#### OLD

> All performance evaluations and testing procedures will be conducted on researcher-controlled hardware to simulate the live deployment environment without disrupting the CDRRMO’s active monitoring operations.

#### NEW

All performance evaluations and testing procedures were conducted on researcher-controlled hardware to simulate the live deployment environment without disrupting the CDRRMO’s active monitoring operations.

#### Evidence

Current native paragraph range `79602–79810`, verified 2026-08-27. Consistent with the completed-testing statement in Testing Strategy Overview.

#### Proposed comment (same gate as associated replacement)

Previous: All performance evaluations and testing procedures will be conducted on researcher-controlled hardware to simulate the live deployment environment without disrupting the CDRRMO’s active monitoring operations.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 7. Defense paper — Chapter 3, Project Scope and Boundaries, What Is Excluded

Page/s: unconfirmed rendered page (TOC: 45)

#### OLD

> The web application, including the dashboard, alert workflow, camera and user management, historical detections, analytics, system-health and AI-performance monitoring, Help Center, audit-log review, maintenance, and export functions, will be accessible only to authenticated, authorized users on the CDRRMO’s localized command center LAN. Incident records, snapshots, audit data, backups, and generated export artifacts are stored locally; the system does not transmit or store operational data on external cloud services.

#### NEW

The web application, including the dashboard, alert workflow, camera and user management, historical detections, analytics, system-health and AI-performance monitoring, Help Center, audit-log review, maintenance, and export functions, is accessible only to authenticated, authorized users on the CDRRMO’s localized command center LAN. Incident records, snapshots, audit data, backups, and generated export artifacts are stored locally; the system does not transmit or store operational data on external cloud services.

#### Evidence

Current native paragraph range `79811–80334`, verified 2026-08-27. A finished system's access boundary is a present-state behavior, not a future promise.

#### Proposed comment (same gate as associated replacement)

Previous: The web application, including the dashboard, alert workflow, camera and user management, historical detections, analytics, system-health and AI-performance monitoring, Help Center, audit-log review, maintenance, and export functions, will be accessible only to authenticated, authorized users on the CDRRMO’s localized command center LAN. Incident records, snapshots, audit data, backups, and generated export artifacts are stored locally; the system does not transmit or store operational data on external cloud services.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 8. Defense paper — Chapter 3, Project Development Model

Page/s: unconfirmed rendered page (TOC: 48)

#### OLD

> Therefore, the Hybrid Dual-Track Development Framework best fits the proposed system because it balances fixed requirements with controlled iteration. The framework preserved the finalized operational scope of the Lipa CDRRMO while allowing both the AI detection engine and the web-based command center application to be refined through testing and integration. This approach supports the development of a reliable, secure, and real-time AI-assisted accident detection system.

#### NEW

Therefore, the Hybrid Dual-Track Development Framework was selected for ADAS because it balanced fixed requirements with controlled iteration. The framework preserved the finalized operational scope of the Lipa CDRRMO while allowing both the AI detection engine and the web-based command center application to be refined through testing and integration. This approach supported the development of a reliable, secure, and real-time AI-assisted accident detection system.

#### Evidence

Current native paragraph range `82557–83033`, verified 2026-08-27. The preceding paragraph already states that the framework was selected and that development iterations occurred.

#### Proposed comment (same gate as associated replacement)

Previous: Therefore, the Hybrid Dual-Track Development Framework best fits the proposed system because it balances fixed requirements with controlled iteration. The framework preserved the finalized operational scope of the Lipa CDRRMO while allowing both the AI detection engine and the web-based command center application to be refined through testing and integration. This approach supports the development of a reliable, secure, and real-time AI-assisted accident detection system.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 9. Defense paper — Chapter 3, Functional Requirements Specification, FR-07 row

Page/s: unconfirmed rendered page (TOC: 58)

#### OLD

> Along with the visual alert, the system shall include a 'Mute/Snooze' button to give the operator a quiet moment to verify the incident. However, if the alert is left 'Unverified' for too long (e.g., 30 seconds), the alarm will automatically sound again to ensure no emergency is missed.

#### NEW

Along with the visual alert, the system shall include a 'Mute/Snooze' button to give the operator a quiet moment to verify the incident. However, if the alert is left 'Unverified' for too long (e.g., 30 seconds), the alarm automatically sounds again to ensure no emergency is missed.

#### Evidence

Current native table paragraph range `94174–94461`, verified 2026-08-27. The normative `shall` remains; only the runtime behavior is stated in present tense.

#### Proposed comment (same gate as associated replacement)

Previous: Along with the visual alert, the system shall include a 'Mute/Snooze' button to give the operator a quiet moment to verify the incident. However, if the alert is left 'Unverified' for too long (e.g., 30 seconds), the alarm will automatically sound again to ensure no emergency is missed.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 10. Defense paper — Chapter 3, Figure 3 narrative

Page/s: unconfirmed rendered page (TOC: 92)

#### OLD

> Figure 3 illustrates how the proposed system distributes tasks among the System, Operator, and Administrator during accident detection and verification. The System lane covers the automated flow, beginning with the reception of CCTV/VMS streams, AI-based frame analysis, possible collision detection, incident record creation, and dashboard alert delivery. The Operator lane represents the Human-in-the-Loop portion of the workflow, where the dispatcher reviews the alert snapshot, decides whether to confirm or dismiss the detection, monitors confirmed incidents, marks cleared incidents as resolved, and generates historical reports when needed. The Administrator lane shows the restricted account-management responsibilities assigned to authorized supervisory users.

#### NEW

Figure 3 illustrates how ADAS distributes tasks among the System, Operator, and Administrator during accident detection and verification. The System lane covers the automated flow, beginning with the reception of CCTV/VMS streams, AI-based frame analysis, possible collision detection, incident record creation, and dashboard alert delivery. The Operator lane represents the Human-in-the-Loop portion of the workflow, where the dispatcher reviews the alert snapshot, decides whether to confirm or dismiss the detection, monitors confirmed incidents, marks cleared incidents as resolved, and generates historical reports when needed. The Administrator lane shows the restricted account-management responsibilities assigned to authorized supervisory users.

#### Evidence

Current native paragraph range `140998–141767`, verified 2026-08-27. Terminology-only change.

#### Proposed comment (same gate as associated replacement)

Previous: Figure 3 illustrates how the proposed system distributes tasks among the System, Operator, and Administrator during accident detection and verification. The System lane covers the automated flow, beginning with the reception of CCTV/VMS streams, AI-based frame analysis, possible collision detection, incident record creation, and dashboard alert delivery. The Operator lane represents the Human-in-the-Loop portion of the workflow, where the dispatcher reviews the alert snapshot, decides whether to confirm or dismiss the detection, monitors confirmed incidents, marks cleared incidents as resolved, and generates historical reports when needed. The Administrator lane shows the restricted account-management responsibilities assigned to authorized supervisory users.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 11. Defense paper — Chapter 3, Figure 4 narrative

Page/s: unconfirmed rendered page (TOC: 94)

#### OLD

> Figure 4 defines the daily operational workflows of the proposed system, demonstrating the interactions among dispatchers, system administrators, and the city’s physical camera infrastructure to facilitate real-time incident resolution, manage camera configurations, analyze data, and maintain secure access control. This operational structure is designed to maximize efficiency, mitigate operator cognitive load, and accelerate the Human-in-the-Loop (HITL) emergency response.

#### NEW

Figure 4 defines the daily operational workflows of ADAS, demonstrating the interactions among dispatchers, system administrators, and the city’s physical camera infrastructure to facilitate real-time incident resolution, manage camera configurations, analyze data, and maintain secure access control. This operational structure is designed to maximize efficiency, mitigate operator cognitive load, and accelerate the Human-in-the-Loop (HITL) emergency response.

#### Evidence

Current native paragraph range `142330–142807`, verified 2026-08-27. Terminology-only change.

#### Proposed comment (same gate as associated replacement)

Previous: Figure 4 defines the daily operational workflows of the proposed system, demonstrating the interactions among dispatchers, system administrators, and the city’s physical camera infrastructure to facilitate real-time incident resolution, manage camera configurations, analyze data, and maintain secure access control. This operational structure is designed to maximize efficiency, mitigate operator cognitive load, and accelerate the Human-in-the-Loop (HITL) emergency response.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 12. Defense paper — Chapter 3, Data Dictionary, snooze expiration description

Page/s: unconfirmed rendered page (TOC: 105)

#### OLD

> Expiration UTC timestamp after which an unresolved snooze will reactivate dashboard alerts.

#### NEW

Expiration UTC timestamp after which an unresolved snooze reactivates dashboard alerts.

#### Evidence

Current native table paragraph range `162401–162492`, verified 2026-08-27. A data-dictionary definition should describe the runtime behavior in present tense.

#### Proposed comment (same gate as associated replacement)

Previous: Expiration UTC timestamp after which an unresolved snooze will reactivate dashboard alerts.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 13. Defense paper — Chapter 3, Deployment Architecture

Page/s: unconfirmed rendered page (TOC: 129)

#### OLD

> Under this proposed design, cross-VLAN communication would be executed via a Router-on-a-Stick topology. This configuration would enable the edge server (VLAN 50) to securely transmit real-time WebSocket alerts to the operator terminals (VLAN 60). The server would connect via a Gigabit copper port (8GT) to the command center's core aggregation switches and interface directly with the Dahua DSS Pro server. This setup would place the server on the same subnetwork as the VMS, enabling zero-latency intranet communication without traversing external firewalls.

#### NEW

The target production deployment was designed around a Router-on-a-Stick topology for cross-VLAN communication. In this planned topology, the edge server (VLAN 50) would securely transmit real-time WebSocket alerts to the operator terminals (VLAN 60). The server would connect via a Gigabit copper port (8GT) to the command center's core aggregation switches and interface directly with the Dahua DSS Pro server. This design would place the server on the same subnetwork as the VMS, enabling zero-latency intranet communication without traversing external firewalls.

#### Evidence

Current native paragraph range `187446–188007`, verified 2026-08-27. This avoids presenting a designed production topology as an actual deployment, consistent with live tracker item 0.13.

#### Proposed comment (same gate as associated replacement)

Previous: Under this proposed design, cross-VLAN communication would be executed via a Router-on-a-Stick topology. This configuration would enable the edge server (VLAN 50) to securely transmit real-time WebSocket alerts to the operator terminals (VLAN 60). The server would connect via a Gigabit copper port (8GT) to the command center's core aggregation switches and interface directly with the Dahua DSS Pro server. This setup would place the server on the same subnetwork as the VMS, enabling zero-latency intranet communication without traversing external firewalls.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 14. Defense paper — Chapter 3, Deep Learning Implementation and Training Protocol, TensorRT export

Page/s: unconfirmed rendered page (TOC: 142)

#### OLD

> The following parameters configure the TensorRT export. Batching itself is already real and load-bearing in the deployed PyTorch pipeline, all active cameras are grouped into a single inference call per scheduling tick, with per-batch latency measured directly on the prototype hardware. The TensorRT export adds a compiled, fixed-batch path intended to reduce that latency further once complete.

#### NEW

The following parameters configure the TensorRT export. Batching is already real and load-bearing in the deployed PyTorch pipeline: all active cameras are grouped into a single inference call per scheduling tick, with per-batch latency measured directly on the prototype hardware.

#### Evidence

Current native paragraph range `208050–208446`, verified 2026-08-27. This removes the unfinished `once complete` wording. The completed batch-32 export is stated only in the dedicated Batch Sizing item below, avoiding duplication.

#### Proposed comment (same gate as associated replacement)

Previous: The following parameters configure the TensorRT export. Batching itself is already real and load-bearing in the deployed PyTorch pipeline, all active cameras are grouped into a single inference call per scheduling tick, with per-batch latency measured directly on the prototype hardware. The TensorRT export adds a compiled, fixed-batch path intended to reduce that latency further once complete.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

### 15. Defense paper — Chapter 3, Deep Learning Implementation and Training Protocol, Batch Sizing

Page/s: unconfirmed rendered page (TOC: 142)

#### OLD

> Batch Sizing (batch=10): Set to ten, matching the camera count planned for the system's live demonstration, this ties the figure to a concrete near-term scenario rather than an assumption about eventual citywide scale. Extending toward the full 418-camera network would require a larger export batch.

#### NEW

Batch Sizing (batch=32): The TensorRT export was completed at a batch size of 32. This establishes the batch size used for the optimized inference configuration without assuming eventual citywide scale. Extending toward the full 418-camera network would require a larger export batch.

#### Evidence

Current native paragraph range `208885–209185`, verified 2026-08-27. The user confirmed on 2026-08-27 that the TensorRT export was completed at batch size 32. This removes the unfinished demonstration wording while retaining the stated conditional scalability limitation.

#### Proposed comment (same gate as associated replacement)

Previous: Batch Sizing (batch=10): Set to ten, matching the camera count planned for the system's live demonstration, this ties the figure to a concrete near-term scenario rather than an assumption about eventual citywide scale. Extending toward the full 418-camera network would require a larger export batch.

Codex ID: PS-20260827-TENSE-COMPLETION

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260827-TENSE-COMPLETION`

| Target | Approved scope | Applied/read back | Skipped/pending | Blocked |
| --- | --- | --- | --- | --- |
| Defense paper | blocks 1–15 and their attached comments | blocks 1–15 and 15 anchored comments, verified 2026-08-27 | — | — |
| ADAS_Paper_Audit plus tracker | no live write proposed; related tracker item 0.13 remains the current live record | — | — | — |
| Standalone comments | none; every comment is attached to its corresponding defense-paper replacement | — | — | — |
