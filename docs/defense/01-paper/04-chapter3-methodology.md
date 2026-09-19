# 04 — Chapter 3: Methodology, Research Design, and Development Model

> **One-liner:** ADAS used applied research and a Hybrid Dual-Track Development Framework to develop the AI detection engine and command-center application against a stable scope, while refining each through evaluation.
> **Panel risk:** **Medium-high** — the panel can probe why this model fit both tracks, what counted as phase completion, and whether the planned deployment milestones were actually achieved.

## 1. What it is

ADAS is an applied research project. It addresses a concrete operational gap in the Lipa CDRRMO workflow: vehicle collisions were not automatically detected and presented to command-center personnel. The study applies established computer-vision techniques and software-engineering practices to build and evaluate a functional proof of concept; it does not propose a new general theory. [Paper: Chapter 3, Research Design, p. 49]

The chosen project development model is the **Hybrid Dual-Track Development Framework**. The name captures two decisions:

- There are two technical workstreams: an AI detection engine and a web application.
- Each workstream keeps a planned, predictive structure for scope and design, then uses controlled iteration where implementation or testing reveals a need to refine.

The AI track is called the **Hybrid Machine Learning Development Life Cycle (MLDLC)** in the paper. The application track is the **Hybrid Software Development Life Cycle (SDLC)**. Both use one shared sequence of five project phases, but their tasks proceed in parallel where their inputs allow. The tracks formally converge for integration and system-level evaluation. [Paper: Chapter 3, Project Development Model, Figure 1]

In plain terms, the team fixed the operational problem and core requirements early, then allowed the parts that needed evidence-based tuning to improve through test cycles. The AI model could be retrained when evaluation exposed a weakness; the application could be refined when a module or workflow test exposed a defect. Neither kind of refinement required reopening the agreed project purpose each time. [Paper: Chapter 3, Project Development Model; Track 1; Track 2]

### Research design in one minute

- **Purpose:** solve an identified command-center problem by applying existing methods.
- **Artifact:** a functional, AI-assisted accident-detection and alert system.
- **Evaluation setting:** researcher-controlled hardware and an isolated staging environment.
- **Human role:** operators review and decide on presented alerts; the system does not automate dispatch.
- **Research claim:** the study evaluates a proof of concept within its defined scope, not a live citywide deployment. [Paper: Chapter 3, Research Design and Project Scope]

The method must be described as both structured and iterative. Calling it only “Waterfall” would miss the repeated AI and software refinement. Calling it only “Agile” would miss that the operational requirements and boundaries were established early and kept stable. The hybrid label is the paper's explanation of how both properties were used together. [Paper: Chapter 3, Project Development Model]

## 2. Where it lives

### In the paper

- **Chapter 3, Methodology, Research Design** states that the study is applied research and defines the proof-of-concept evaluation context. The section begins on page 49. [Paper: Chapter 3, Research Design, p. 49]
- **Chapter 3, Project Development Model** names the Hybrid Dual-Track Development Framework and explains the alternatives considered. **Figure 1** is titled “Hybrid Dual-Track Framework Diagram.” [Paper: Chapter 3, Project Development Model, Figure 1]
- **Track 1. Hybrid Machine Learning Development Life Cycle** explains the AI track's train, evaluate, failure-analysis, and refinement loop. [Paper: Chapter 3, Track 1]
- **Track 2. Hybrid Software Development Life Cycle** explains how the application was built against the stable requirements and refined incrementally. [Paper: Chapter 3, Track 2]
- **Phase 1** is Planning and Requirements Analysis; **Phase 2** is Design and Data Preparation; **Phase 3** is Development and Model Engineering; **Phase 4** is Testing and System Integration; **Phase 5** is Deployment and Implementation. [Paper: Chapter 3, Phases 1–5]
- **Table 1, Timelines and Milestones** gives the planned phase schedule, milestone names, and separate task columns for MLDLC and SDLC. Use it when asked how the parallel work was scheduled. [Paper: Chapter 3, Timelines and Milestones, Table 1]
- **Chapter 3, Project Scope and Boundaries** limits the research evaluation to researcher-controlled hardware and held-out Lipa CCTV clips used for event-level evaluation, not model training. [Paper: Chapter 3, Project Scope and Boundaries]
- **Capstone Test Execution and Validation Plan**, “Acceptance Criteria,” defines the test gates used in Phase 4. The workbook **ADAS Test Execution.xlsx** records execution and formal acceptance in its `UAT Results` tab and maps coverage in `UAT Traceability`.

The useful page anchors are Research Design on page 49 and Project Development Model beginning on page 54. The five phase descriptions span pages 57–59. Table and figure names are the safest references when the panel has a different PDF pagination. [Paper: Chapter 3 contents and section headings]

### In the code

The repository shows how the two tracks meet in the running system. The training and research rationale belongs to the paper; these code locations anchor the deployed inference and application integration path.

**AI runtime and event path**

- `ai_engine/main.py:33` starts multi-camera inference, resolves the model artifact, and wires the detector, camera supervisor, and inference pipeline.
- `ai_engine/pipeline.py:111` collects the newest eligible camera frames; `ai_engine/pipeline.py:184` runs one inference tick across them.
- `ai_engine/pipeline.py:222` pauses the camera before handing an event to the callback, keeping event formation connected to the operator-alert workflow.
- `ai_engine/accident.py:46` turns a fired event into an annotated snapshot and a durable event-outbox entry.
- `ai_engine/eval/run_clips.py:69` is an event-evaluation entry point that runs the clip evaluation harness.

**Application and integration path**

- `backend/app/api/routes/internal.py:93` receives an AI alert at the internal API boundary; the route persists a new incident and broadcasts after the database action succeeds.
- `backend/app/services/incidents.py:124` owns the backend incident-ingest operation used by that route.
- `backend/app/main.py:442` serves the authenticated `/ws/alerts` WebSocket endpoint.
- `frontend/src/hooks/useAdasWebSocket.ts:30` connects the dashboard to that event channel and handles reconnection.

**Tests around the seam**

- `ai_engine/tests/test_pipeline.py:321` checks that an event pauses its camera before the callback runs.
- `backend/tests/test_internal.py:47` groups tests for the AI-alert receive path.
- `frontend/src/hooks/useAdasWebSocket.test.ts:45` covers the dashboard's WebSocket behavior.

These code references support the mechanism explanation. They do not replace the paper's account of why the method was chosen, nor the tracker’s acceptance criteria and recorded results.

## 3. How it works

### Two tracks, one phase backbone

The framework divides work by the kind of uncertainty each team needs to resolve:

- The **AI track** reduces uncertainty about whether a model and event-formation pipeline can detect collision evidence from the available video conditions.
- The **application track** implements the agreed operator and administrator workflows, data handling, and system interfaces.
- The **shared phase sequence** keeps both tracks oriented toward the same deliverables and review points.
- **Phase 4** is the explicit convergence point: the finalized model is integrated with the application and tested through the full event-to-dashboard path.

The phases are ordered as a project plan, but the tracks do not have to wait for one another at every task. For example, application modules can be built and unit-tested while model experiments continue, as long as each side respects the requirements and interface decisions already established. [Paper: Chapter 3, Project Development Model and Phases 1–4; Figure 1]

### Phase 1 — Planning and Requirements Analysis

**AI track (MLDLC)**

- Define the model’s target detection parameters.
- Set the model-validation baseline at **85% mAP**.
- Examine the intended CCTV conditions that affect data and inference, including variable lighting, frame rates, and camera angles.
- Set data collection and annotation protocols to match those constraints. [Paper: Chapter 3, Phase 1]

**Application track (SDLC)**

- Gather needs from Lipa CDRRMO command-center personnel through interviews and brainstorming.
- Document the functional and non-functional requirements.
- Define the client-server architecture.
- Finalize the operator workflow for human verification and the role-based access-control roles. [Paper: Chapter 3, Phase 1]

**Phase output**

- Model target parameters and data protocols.
- A validated requirements specification and an agreed system boundary.
- A stable starting architecture and defined operator/administrator responsibilities.

**Exit evidence**

- Table 1 lists **Project Proposal Approved** as the first milestone, targeted for Week 2.
- It lists **Requirements Validated** as the second milestone, targeted for Week 4.
- The phase text describes the AI targets and the complete application requirements, architecture, HITL workflow, and RBAC roles as the work completed in this phase. [Paper: Chapter 3, Phase 1; Table 1, Phase 1]

The purpose of this gate was to make the intended problem and scope clear before design and implementation work expanded. A model experiment could refine the way the target was reached, but it was not a reason to change the operator problem that the project had agreed to address. [Paper: Chapter 3, Project Development Model; Phase 1]

### Phase 2 — Design and Data Preparation

**AI track (MLDLC)**

- Curate the hybrid training dataset from publicly available vehicular-accident image repositories and archival Lipa CDRRMO CCTV footage.
- Remap class labels and apply dataset-quality gating.
- Prepare augmented training inputs, including mosaic composition, brightness adjustment, and slight rotation to represent the lighting and camera-angle variation described in the paper.
- Keep the separately held-out Lipa CCTV clips for event-level evaluation; Chapter 3’s scope says those clips are not included in model training. [Paper: Chapter 3, Phase 2 and Project Scope and Boundaries]

**Application track (SDLC)**

- Finalize the database design in third normal form.
- Specify the API endpoints required by the system.
- Produce and approve wireframes for operator and administrator dashboard views. [Paper: Chapter 3, Phase 2]

**Phase output**

- A quality-gated, prepared dataset and documented augmentation approach.
- A finalized schema, endpoint specification, and approved UI/UX design artifacts.
- Inputs clear enough for model engineering and incremental application development to proceed against the same design. [Paper: Chapter 3, Phase 2; Table 1, Phase 2]

**Exit evidence**

- Table 1 lists **Architecture Finalized** as the milestone targeted for Week 7.
- It lists **Design Complete** as the milestone targeted for Week 9.
- The phase descriptions identify the prepared dataset and completed schema, API, and wireframe work as the handoff into development. [Paper: Chapter 3, Phase 2; Table 1, Phase 2]

This gate is also where to explain data separation clearly. The paper describes archival Lipa CCTV footage as part of the training-data preparation and identifies held-out clips separately as evaluation data. Do not imply that the held-out evaluation clips were added to training. [Paper: Chapter 3, Phase 2 and Project Scope and Boundaries]

### Phase 3 — Development and Model Engineering

**AI track (MLDLC)**

- Configure and train the YOLO model on the prepared hybrid dataset.
- Evaluate it against the targets established in Phase 1.
- Analyze failures, such as reduced detections under nighttime glare or vehicle occlusion.
- Refine dataset curation or augmentation and retrain when analysis identifies a fixable failure mode.
- Lock the model weights after the validation targets are met, then export and optimize the inference engine for the localized edge-server design. [Paper: Chapter 3, Phase 3]

The paper describes this as a repeating **train → evaluate → analyze failures → refine** loop. The model gate is **85% mAP and IoU of at least 0.50**. The test plan states the primary validation criterion as **mAP at IoU 0.50 of at least 0.85 on the validation split**. These are the predefined checks for the model-development phase, not a substitute for event-level or whole-system evaluation. [Paper: Chapter 3, Phase 1 and Phase 3; Capstone Test Execution and Validation Plan, Acceptance Criteria — AI Model Validation]

**Application track (SDLC)**

- Implement individual software modules against the requirements and design artifacts from Phases 1 and 2.
- Unit-test modules and integrate them incrementally.
- Refine the React dashboard, FastAPI backend, SQLite operations, camera management, incident logging, reporting, and real-time alert workflow as component tests reveal issues. [Paper: Chapter 3, Project Development Model and Phase 3]

**Phase output**

- A validated, locked model artifact and optimized inference engine.
- A working application whose modules have been built, unit-tested, and integrated incrementally.
- A core prototype, a feature-complete system, and completed development milestones in Table 1. [Paper: Chapter 3, Phase 3; Table 1, Phase 3]

**Exit evidence**

- Table 1 schedules **Core Prototype Functional** for Week 14.
- It schedules **Feature-Complete System** for Week 19.
- It schedules **Final Model Locked & Development Completion** for Week 22.
- The model-development text says the weights are locked and the inference engine is exported after the stated model metrics are validated; the software text says modules are tested and integrated incrementally. [Paper: Chapter 3, Phase 3; Table 1, Phase 3]

A key defense point: “done” here did not mean the model stopped improving because the calendar ended. The paper defines a model gate and says the model weights are locked once that gate is validated. Application development used incremental module checks and the feature-completion milestone. [Paper: Chapter 3, Phase 3; Table 1, Phase 3]

### Phase 4 — Testing and System Integration

**How the tracks converge**

- Integrate the finalized YOLO model into the AI engine and FastAPI backend.
- Run the assembled system in a simulated local-area network rather than against live CDRRMO operations.
- Send simulated live RTSP video through the inference pipeline.
- Follow detections through SQLite persistence and WebSocket delivery to the dashboard.
- Exercise the full human-in-the-loop workflow and verify operator/administrator routing. [Paper: Chapter 3, Phase 4]

**Phase output**

- An integrated proof-of-concept stack.
- End-to-end test evidence for inference, alert delivery, database recording, dashboard presentation, HITL handling, RBAC, and hardware-resource behavior.
- A formal UAT record based on dispatcher interaction in a staging environment. [Paper: Chapter 3, Phase 4]

**Exit evidence**

- Table 1 schedules **Integration Complete** for Week 24.
- It schedules **UAT Sign-Off** for Week 26.
- The test plan defines UAT acceptance gates: all **33** planned applicable participant-stage executions must have a final Pass or Fail result; at least **95%** must pass; there must be **zero** open Critical or Major defects; mean SUS must be at least **68**; all **nine** readiness items must be Ready; and an authorized CDRRMO representative must sign the decision. [Paper: Chapter 3, Phase 4; Table 1, Phase 4; Capstone Test Execution and Validation Plan, Acceptance Criteria — UAT]

The test tracker separates this UAT decision from technical test results. The `UAT Results` tab records the gate status; `UAT Traceability` maps participant journeys or technical activities to requirements. That distinction makes the phase exit reviewable: the team can show both what passed and where its evidence came from. [Tracker: `UAT Results` and `UAT Traceability` tabs]

**How the code reflects the convergence**

- The AI pipeline collects current frames and makes batched predictions, then turns accumulated evidence into a camera event. [Code: `ai_engine/pipeline.py:111`; `ai_engine/pipeline.py:184`]
- The AI event handler saves a snapshot and enqueues a durable event for backend delivery. [Code: `ai_engine/accident.py:46`]
- The backend receives the internal alert, records the incident, and broadcasts the new event after persistence. [Code: `backend/app/api/routes/internal.py:93`; `backend/app/services/incidents.py:124`]
- The dashboard listens on `/ws/alerts` and reconnects after a dropped connection. [Code: `backend/app/main.py:442`; `frontend/src/hooks/useAdasWebSocket.ts:30`]

That path is why Phase 4 is more than “the model works” plus “the website works.” It verifies that the AI and application tracks form one operator-facing workflow. [Paper: Chapter 3, Phase 4; Code: `backend/app/api/routes/internal.py:93`]

### Phase 5 — Deployment and Implementation

**Joint work**

- Unify the two tracks in a target production deployment plan.
- Define how a completed proof of concept could be adopted later, subject to CDRRMO authorization and post-capstone implementation.
- Keep pilot activation, expanded camera monitoring, formal handover, staff training, AI retraining, and hardware maintenance outside the completed capstone work. [Paper: Chapter 3, Phase 5]

**Phase output**

- A completed proof of concept evaluated on researcher-controlled hardware.
- A target production plan that explains the path from that proof of concept to possible agency adoption.
- A clear handoff boundary: the future deployment activities require separate authorization. [Paper: Chapter 3, Phase 5]

**Exit evidence**

- Table 1 lists **Production Launch** and **Final Operational Handoff** as planned Phase 5 milestones, targeted for Week 28 and Week 30.
- The final Phase 5 paragraph defines the completed study’s actual boundary: the prototype was evaluated on researcher-controlled hardware; it was not installed at the CDRRMO command center and was not connected to the agency CCTV VLAN.
- Therefore, for this study, the defensible exit is a tested proof of concept plus a unified target-deployment plan. It is not a claim that the production installation, citywide rollout, or agency handover happened. [Paper: Chapter 3, Phase 5; Table 1, Phase 5]

### The synchronization contract between tracks

The two tracks stayed aligned through shared phase gates and a defined integration boundary:

- **Same project purpose:** both tracks addressed the agreed command-center accident-alert problem.
- **Same requirements baseline:** the AI target parameters and software requirements were set in Phase 1.
- **Same design handoff:** Phase 2 delivered the data preparation for the AI track and the schema/API/UI design for the application track.
- **Parallel implementation:** Phase 3 allowed the model to iterate while application modules were built and tested against the documented requirements.
- **Explicit model handoff:** Phase 3 locked the model artifact after its validation criteria were met.
- **One convergence gate:** Phase 4 connected the model, backend, database, and dashboard and tested the end-to-end path.
- **One deployment boundary:** Phase 5 combined both tracks in a target production plan while retaining the proof-of-concept scope. [Paper: Chapter 3, Project Development Model and Phases 1–5; Figure 1; Table 1]

In the running code, the operator-facing seam is an event contract. The model pipeline raises an event, the AI handler turns it into a snapshot-backed payload, the backend stores it, and the frontend receives a typed WebSocket notification. This is the practical point where separate development tracks become one application. [Code: `ai_engine/pipeline.py:222`; `ai_engine/accident.py:46`; `backend/app/api/routes/internal.py:93`; `frontend/src/hooks/useAdasWebSocket.ts:30`]

## 4. Why it was built this way

### Why the hybrid framework fit ADAS

The framework balanced two facts about the project:

- The intended user problem, emergency-response workflow, roles, database needs, security rules, and deployment boundary were established early with Lipa CDRRMO input.
- Important technical behavior could only be learned by building and testing: model behavior across datasets and viewing conditions, edge-hardware constraints, interface usability, API behavior, database operations, WebSocket delivery, and whole-system integration. [Paper: Chapter 3, Project Development Model]

The predictive part protected scope and made the work plan reviewable. The iterative part gave the team a way to respond when evidence from model evaluation or software testing showed what should be refined. The AI and application tracks shared the same lifecycle shape while using different iteration loops. [Paper: Chapter 3, Project Development Model; Tracks 1–2]

### Why not Waterfall alone

The paper recognizes that Waterfall gives a clear sequential process and can fit fixed requirements. It was not sufficient by itself because ADAS components needed repeated technical refinement after their first implementation. The paper specifically names the AI model, dashboard, backend APIs, database operations, WebSocket alert delivery, and system integration as areas needing iteration. [Paper: Chapter 3, Project Development Model]

A strictly one-pass sequence would have made it harder to apply what the team learned from model failures, module tests, or integration tests without treating that feedback as an exception to the method. The hybrid model keeps the sequence of major phases while allowing refinement inside them. [Paper: Chapter 3, Project Development Model and Phase 3]

### Why not pure Agile

The paper says pure Agile was considered but not chosen because it relies on frequent stakeholder feedback and changing requirements across iterations. The core ADAS requirements had already been established early through consultation with the Lipa CDRRMO. [Paper: Chapter 3, Project Development Model]

The project also depended on stable emergency workflows, role-based permissions, database design, security rules, and deployment boundaries. Reopening those requirements every sprint was not needed to improve the technical components and could have disrupted the defined operational scope. [Paper: Chapter 3, Project Development Model]

### Why two tracks

The model work and the application work have different uncertainty patterns:

- Model performance depends on data quality, environmental conditions, camera perspectives, and available edge hardware. The consequences of those variables become clearer after training and evaluation.
- Application behavior depends on documented workflows and interfaces, then benefits from incremental implementation and test feedback.
- A single undifferentiated workstream would make the shared milestones less clear: the team needs to know whether a delay belongs to model validation, software feature completion, or their integration. [Paper: Chapter 3, Project Development Model; Track 1; Track 2]

The two-track structure lets each side use the feedback most relevant to it, while the phase plan and Phase 4 gate keep both accountable to the same system outcome. It is a coordination decision as much as a development decision. [Paper: Chapter 3, Project Development Model; Figure 1]

### Why these phase exit checks

- **Phase 1** closes once the project problem, scope, model targets, requirements, workflows, and roles have been specified and validated.
- **Phase 2** closes once the AI data inputs and application design artifacts are ready for implementation.
- **Phase 3** closes once the model validation gate is met and locked, and the application has reached its planned development-completion milestone.
- **Phase 4** closes with integration evidence and UAT sign-off under the test plan’s acceptance rules.
- **Phase 5** closes with the tested proof of concept and an agreed target production plan, not a live deployment. [Paper: Chapter 3, Phases 1–5; Table 1; Capstone Test Execution and Validation Plan, Acceptance Criteria — UAT]

The phase gates are not arbitrary calendar cutoffs. The paper ties them to concrete artifacts or evidence: approved requirements, finalized design, validated model and completed modules, end-to-end integration and UAT, then a production target plan. The target weeks in Table 1 are schedule milestones; the artifacts and acceptance criteria explain what the team should show at each gate. [Paper: Chapter 3, Table 1 and Phases 1–5]

## 5. What changed since the 28 April defense

The key point to carry into this defense is the explicit Phase 5 boundary. The current paper describes production installation as a target plan and states that the completed proof of concept was evaluated on researcher-controlled hardware. It was not installed in the CDRRMO command center or connected to the agency CCTV VLAN. [Paper: Chapter 3, Phase 5]

This distinction matters because Table 1 includes planned Phase 5 milestones named **Production Launch** and **Final Operational Handoff**. Those are schedule entries for the target implementation path; the final Phase 5 description states what was completed for the study. Present the prototype and evaluation as completed work, and describe live installation, pilot activation, scaling, training, and operational handoff as future work requiring separate authorization. [Paper: Chapter 3, Phase 5; Table 1, Phase 5]

The Hybrid Dual-Track Development Framework is the current paper’s named methodology. Emphasize the separation between the intended production route and the proof-of-concept boundary; the study does not claim a live deployment. [Paper: Chapter 3, Project Development Model and Phase 5]

## 6. Limits and honest caveats

- **Proof-of-concept scope:** the completed system was evaluated on researcher-controlled hardware. The study does not claim that ADAS was installed in the CDRRMO command center or connected to its CCTV VLAN. [Paper: Chapter 3, Research Design and Phase 5]
- **Staging evaluation:** the test plan describes a private, simulated LAN environment. The testing setup supports networked, simulated RTSP evaluation without interrupting CDRRMO live operations; it is not evidence of a completed live deployment. [Paper: Chapter 3, Phase 4; Capstone Test Execution and Validation Plan, Purpose and Test Environment]
- **Operational boundary:** the alert workflow supports operator decision-making and incident lifecycle management. Emergency dispatch and inter-agency response coordination remain outside the system scope. [Paper: Chapter 3, Project Scope and Boundaries]
- **Model gate versus field claim:** the **85% mAP / IoU 0.50** criterion is a predefined validation gate in the model-development method. It does not by itself claim that every real-world collision will be detected. The test plan and tracker keep model validation, event-level evidence, and whole-system tests as separate evidence categories. [Paper: Chapter 3, Phase 3; Capstone Test Execution and Validation Plan, Acceptance Criteria; Tracker: `AI Model Validation` and `UAT Traceability` tabs]
- **Planned milestones versus completion:** Table 1 provides a planned schedule. For Phase 5, use the final narrative statement about completed work to describe the actual project boundary. Do not present the schedule milestones as proof of field installation. [Paper: Chapter 3, Phase 5; Table 1, Phase 5]
- **Track synchronization:** the model and application were coordinated through requirements, design, interfaces, and system integration. Their iteration loops differ; the paper does not claim that every task on each track happened at the exact same time. [Paper: Chapter 3, Project Development Model and Phases 1–4]

A safe one-sentence scope answer is: **“We developed and evaluated an integrated proof of concept in a researcher-controlled staging environment, and documented how it could be deployed later with CDRRMO authorization.”** [Paper: Chapter 3, Research Design; Phase 5]

## 7. Likely panel questions

### “Why this development model?”

The core CDRRMO requirements and operational boundaries were clear early, but both the AI model and application needed refinement through testing. The hybrid dual-track framework kept the scope stable while allowing controlled iteration in the two technical workstreams. [Paper: Chapter 3, Project Development Model]

### “Why not use Waterfall from start to finish?”

Waterfall gives a clear sequence, but a one-pass approach did not fit the repeated work needed on model behavior, dashboard modules, APIs, database operations, WebSocket delivery, and integration. We kept the phase sequence and added iterative improvement inside the phases. [Paper: Chapter 3, Project Development Model]

### “Why not go fully Agile?”

The operational requirements were established early with Lipa CDRRMO, including workflows, roles, data, security, and deployment boundaries. The project needed technical refinement, but it did not need constant requirement changes each sprint. [Paper: Chapter 3, Project Development Model]

### “How did you decide a phase was done?”

Each phase had a tangible output and a milestone: validated requirements, completed design, validated model plus working modules, integrated testing with UAT sign-off, then a proof of concept with a target deployment plan. The model phase used the predefined mAP and IoU gate; Phase 4 used the test plan’s UAT acceptance rules. [Paper: Chapter 3, Phases 1–5 and Table 1; Capstone Test Execution and Validation Plan, Acceptance Criteria — UAT]

### “How did the AI and application work stay aligned?”

Both tracks used the same five-phase backbone and a shared requirements/design baseline. They could iterate independently during development, then Phase 4 required the finalized model to pass through the same backend, database, alert channel, and dashboard that operators use. [Paper: Chapter 3, Project Development Model and Phase 4; Figure 1]

### “So was this deployed at the CDRRMO?”

No. The completed proof of concept was evaluated on researcher-controlled hardware and was not installed in the command center or connected to the agency’s CCTV VLAN. The paper describes production installation and handoff as a target path requiring separate authorization. [Paper: Chapter 3, Phase 5]

### “Does meeting the model threshold prove the system is operationally ready?”

The model threshold is one exit criterion for the AI development track. Phase 4 separately checks integration, system behavior, operator workflow, and UAT, and the project boundary remains a proof-of-concept evaluation rather than a live deployment. [Paper: Chapter 3, Phase 3 and Phase 4; Capstone Test Execution and Validation Plan, Acceptance Criteria]

### “What do you mean by applied research?”

We addressed an existing command-center workflow gap by applying established computer-vision and software-engineering methods to create and evaluate a functional system. The goal was a bounded proof of concept, not a new general theory. [Paper: Chapter 3, Research Design]

## 8. Cram summary

- ADAS is applied research: it applies established methods to a concrete Lipa CDRRMO workflow gap and evaluates a functional proof of concept.
- The development model is the **Hybrid Dual-Track Development Framework**: an AI/MLDLC track and an application/SDLC track share one five-phase plan.
- Phase 1 sets scope, requirements, AI targets, workflows, and roles; Phase 2 prepares data and finalizes schema, API, and UI designs.
- Phase 3 iterates and validates the model while software modules are built, unit-tested, and integrated; the paper sets **85% mAP and IoU ≥ 0.50** as the model gate.
- Phase 4 brings the tracks together and validates the complete simulated RTSP-to-dashboard workflow; UAT sign-off follows the test plan’s acceptance criteria.
- Phase 5 produces a tested proof of concept and target production plan. The system was **not** installed at the CDRRMO or connected to the agency CCTV VLAN.
- Waterfall alone could not support the needed technical refinement; pure Agile would change requirements that were already defined. The hybrid model preserves stable scope and controlled iteration.
