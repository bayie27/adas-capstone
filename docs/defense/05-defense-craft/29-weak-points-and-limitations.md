# 29 — Weak Points and Limitations

> **One-liner:** A prepared, evidence-bounded way to discuss what ADAS demonstrates, what remains qualified, and what the next engineering step is.
> **Panel risk:** High — the panel can turn a limitation into a credibility test if the team overstates a prototype result or treats a qualified Pass as production proof.

## 1. What it is

This guide is the team’s honest answer bank for the questions that are most likely to expose the boundary of the study. A limitation is not an apology. It is a statement of the exact condition under which a result is valid, followed by the mitigation already in the system and the next experiment or deployment step.

The project demonstrates an integrated collision-detection and human-review workflow. It does not claim that every collision on every Lipa camera will be detected, that the software is already installed in the CDRRMO command center, or that the tested host is a citywide production platform.

The panel should hear four things in this order:

1. **The boundary:** what the evidence does and does not establish.
2. **The reason:** which deliberate scope, hardware, access, or time decision created that boundary.
3. **The control:** how the team made the boundary visible and reduced its impact in the tested workflow.
4. **The next step:** the concrete evidence needed before expanding the claim.

Use the qualification in the same sentence as the number. “34.7 minutes” is incomplete; “a 34.7-minute combined performance and thermal window, with an explicit duration qualification” is defensible.

## 2. Where it lives

### In the paper

- **Chapter 1, Scope and Delimitations, p. 14:** the completed work is a proof of concept evaluated on researcher-controlled hardware and simulated or authorized feeds. Live citywide deployment, production-scale capacity, and automated dispatch are outside the completed study.
- **Chapter 3, Research Design and Deployment Architecture, pp. 159–162:** the tested environment and the proposed CDRRMO deployment are separate registers. Figure 34 places the server-side components on one edge host; the production specification is a target design.
- **Chapter 5, Tables 30 and Recommendations, pp. 221–227:** the paper keeps the hard-scene result, performance scale, endurance, and deployment boundary visible, then recommends a limited pilot and new capacity, endurance, security, recovery, and local-data tests.

### In the test plan and tracker

- `docs/Capstone Test Execution and Validation Plan.md`, Purpose, Test Environment, Evaluation Methods, and Acceptance Criteria: results retain simulation, artifact, duration, archival, and reconstructed-timing qualifications.
- `ADAS Test Execution.xlsx`, **AI Model Validation!A2:K9:** qualified mAP, event recall by difficulty, clean-footage false positives, night analysis, checkpoint evidence, parity, and profile sensitivity.
- `ADAS Test Execution.xlsx`, **Performance & Load Testing!A3:H16:** eight-stream cadence, nine-stream step profile, alert delivery, and the deferred fifteen-camera qualification.
- `ADAS Test Execution.xlsx`, **Reliability & Endurance!A1:J16:** availability, accelerated memory evidence, the 34.7-minute performance and thermal window, restart recovery, and injected fault cases.
- `ADAS Test Execution.xlsx`, **Session Control!A14:H18**, **SUS Questionnaire!A4:O19**, **Usability Results!A4:H18**, and **UAT Results!A1:D16:** four participant roles, 33 participant stages, SUS, assistance qualification, readiness, and formal acceptance.

### In the completed guides and code

- [02 — Chapter 1 Introduction](../01-paper/02-chapter1-introduction.md), [05 — Chapter 4 Results](../01-paper/05-chapter4-results.md), and [06 — Chapter 5 Conclusions](../01-paper/06-chapter5-conclusions.md) carry the paper boundary and the result qualifications.
- [09 — System Architecture](../02-architecture/09-system-architecture.md) and [17 — Networking and Deployment](../02-architecture/17-networking-and-deployment.md) distinguish the single-host proof of concept from the proposed on-premises production design.
- [24 — AI Pipeline](../04-ai/24-ai-pipeline.md), [26 — AI Accuracy and Evaluation](../04-ai/26-ai-accuracy-and-evaluation.md), and [27 — AI Performance, FPS, and Latency](../04-ai/27-ai-performance-fps-latency.md) carry the model, event-level, night, capacity, and endurance qualifications.
- `ai_engine/camera.py:40-216` owns camera ingestion, reconnects, segment boundaries, and frame handoff. `ai_engine/pipeline.py:107-245` owns stale-frame handling, batching, scheduling, and inference. `ai_engine/accumulate.py:1-141` enforces corroborating temporal evidence. `ai_engine/supervisor.py:42-240` reconciles camera runtimes and reports health.
- These code seams bound failures within the evaluated host. They are mechanism evidence, not proof that the host has multi-server failover or that an untested camera count will meet the target FPS.

## 3. How it works

### The limitation review method

The team should treat every weak point as a four-part engineering record:

| Part      | What to say                                                  | ADAS example                                                                                |
| --------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Boundary  | State the exact claim that remains qualified.                | “The event run recorded 0/6 hard cases; this is not a universal recall estimate.”           |
| Reason    | Name the decision that limited the evidence.                 | “The capstone used a finite local corpus and did not set a post-hoc hard-recall gate.”      |
| Control   | Identify what was measured or built to prevent overclaiming. | “We report standard and hard strata separately and keep human verification in the loop.”    |
| Next step | Name the test or deployment action that would close the gap. | “Collect authorized hard-scene clips, split by incident, and rerun event-level evaluation.” |

### Three evidence layers

1. **Prototype mechanism:** the detector, temporal accumulator, backend, database, dashboard, WebSocket path, and operator workflow run together in the documented three-device LAN.
2. **Measured evidence:** the tracker records fixed technical cases, event-level clip outcomes, stream profiles, endurance probes, participant stages, SUS responses, and acceptance gates.
3. **Deployment evidence still needed:** a CDRRMO-authorized pilot on the intended network and host, longer and larger capacity runs, broader local footage, and repeated operator evaluation.

These layers answer different panel questions. A passing unit test supports a mechanism. A passing eight-stream run supports that named stream profile. A four-person UAT supports role-based acceptance of the tested workflow. None of those results silently becomes a citywide production claim.

### How the controls reduce the practical impact

- Temporal accumulation requires corroborating evidence, so one weak frame cannot fire an alert. That trades some response time for fewer isolated-frame alerts.
- Human-in-the-loop Confirm or Dismiss keeps an AI event from becoming an operational decision automatically.
- The tracker reports standard and hard recall separately, includes a clean-footage denominator for false positives, and keeps night and source-resolution behavior visible.
- The scheduler drops stale frames and slips when a tick overruns rather than building an unbounded backlog. Telemetry exposes degraded FPS and stale cameras.
- The engine’s outbox protects already-detected events across a backend interruption while the browser can recover active state through REST after a WebSocket reconnect.
- The test plan records whether a row is simulated, accelerated, archival, or reconstructed. A Pass records completion of that defined case; it does not erase the qualification.

## 4. Why it was built this way

### A controlled prototype was the safe study boundary

The team needed an end-to-end system that could be changed, replayed, and inspected without altering active CDRRMO monitoring. MediaMTX and FFmpeg supplied repeatable RTSP behavior on a private three-device LAN. This preserved a real network ingest path while keeping the study away from live CCTV operations and dispatch workflows.

The boundary was therefore a scope and authorization decision. A live rollout would require CDRRMO network access, VMS credentials, operational ownership, privacy controls, production hardware, and a pilot plan. Those are deployment activities, not prerequisites for proving the prototype’s component seams and operator workflow.

### A single edge host kept the first system understandable

The evaluated server-side stack placed the AI engine, FastAPI application, and SQLite database on one Windows host with an RTX 3050 Ti. That made the data path and failure behavior observable for the capstone. The logical separation into engine, backend, and browser still gives a future deployment seams for placement and scaling.

The trade-off is a shared host boundary. If the host fails, inference, API access, and local storage are unavailable together. The paper’s proposed production hardware and multi-GPU specification describe a future capacity design; they are not measurements from the proof of concept.

### The evaluation exposed weak scenes instead of hiding them in an average

The tracker separates the 10 standard clips from the 6 hard clips. It also records the clean-minute denominator for false positives and a night subset. This reporting choice makes the hard and night boundaries visible even when a single aggregate number would sound stronger.

There was no approved hard-recall threshold to retrofit after seeing the result. The correct engineering response is to preserve the baseline, collect more representative scenes, and test controlled changes against the same event-level measures.

### Capacity and endurance need system-level runs

A detector-only batch timing grid cannot answer how many live streams a host can ingest. A live capacity run must include RTSP decode, frame freshness, scheduler behavior, memory, thermal behavior, camera failures, persistence, and alert delivery for a stated duration. The same logic applies to endurance: an accelerated buffer probe can catch a bounded memory-retention defect, but it cannot substitute for a multi-hour or 24-hour operation.

The team chose to report the measured profiles and defer the larger claims. That is a resource and evidence decision: a shorter, named run is more useful than an extrapolated number presented as a qualification.

### Four participants cover roles, not a population

The participant design used three coded Operators, one for each shift, and one coded Administrator. It was intended to exercise both RBAC roles and the defined journeys within the capstone window. It was not designed as a statistically powered survey of every current or future operator.

The correct result is therefore role-based usability and acceptance evidence, with the denominator and assistance condition visible. A broader pilot would test transfer to more people, repeated use, and local operating habits.

## 5. What changed since the 28 April defense

The current defense record is more explicit about the weak points. The tracker now keeps the validation-split mAP qualification separate from event-level recall, identifies standard and hard strata, records the clean false-positive denominator, and adds night, parity, and source-profile analyses.

The performance record names the eight-stream sustained profile and the separate nine-stream step. The plan explicitly defers fifteen-camera qualification and states that the 418-camera figure is a proposed production scope rather than measured capacity.

The reliability record now carries the 34.7-minute combined performance and thermal duration deviation, the accelerated memory qualification, and the restart measurements. The usability and UAT records identify four participants, 33 stages, the assistance condition, the SUS denominator, readiness, and the authorized acceptance decision.

The team should describe these as better-qualified evidence, not as proof that every limitation has disappeared. The honest improvement since April is the clarity and traceability of the evidence boundary.

## 6. Limits and honest caveats

### 6.1 Proof of concept and simulated feeds, not a live CDRRMO deployment

**What the limitation is.** The completed evaluation ran on researcher-controlled hardware in a private three-device LAN. MediaMTX and FFmpeg replayed selected clips as RTSP; the system was not installed on the live CDRRMO CCTV VLAN and did not operate the city’s production camera network.

**Why it exists.** Avoiding live infrastructure was a deliberate scope and authorization decision. The study needed repeatable feeds and an inspectable environment without interrupting active monitoring. A production rollout also requires agency network approval, VMS access, privacy and operational ownership, and a pilot schedule.

**How we bounded the impact.** The server still performed networked RTSP ingestion, decode, inference, durable persistence, WebSocket delivery, and browser review across the three-device path. The paper and test plan label the result as a proof of concept, and UAT acceptance is explicitly limited to the defined prototype scope.

**Next step.** Run a limited CDRRMO-authorized pilot on the intended hardware, network, and RTSP/VMS path. Use go/no-go gates for stream compatibility, event recall, alert delivery, security, recovery, endurance, and operator handover before adding cameras.

**Prepared answer.** “No, the completed study is not a live CDRRMO deployment. We used a private LAN with simulated RTSP so we could exercise the real ingest and alert path without changing active monitoring. The next step is an authorized limited pilot on the intended network and hardware.”

Sources: Defense paper, Chapter 1 Scope and Delimitations, p. 14; Chapter 3 Table 23 and Deployment Architecture; test plan Purpose and Test Environment; tracker UAT Results and Performance & Load Testing.

### 6.2 Single-host architecture and no multi-GPU or multi-server qualification

**What the limitation is.** The evaluated server-side stack runs on one host. That host is a shared availability boundary for inference, the FastAPI service, and the local SQLite file. The current implementation is not built and qualified as a multi-GPU or multi-server deployment: the evidence does not establish a multi-GPU scheduler, multi-server placement, automatic host failover, or a distributed database design.

**Why it exists.** The capstone validated an end-to-end edge workflow on one available GPU host. Building and validating distributed orchestration would add hardware, deployment, data-consistency, and failover work beyond the prototype objective. The paper’s enterprise multi-GPU production specification is a target design, not a completed measurement.

**How we bounded the impact.** The logical components have clear ownership; per-camera runtimes are supervised, inference uses bounded scheduling and batching, the backend owns durable state, WAL supports local reads and writes, and the outbox protects queued events through a backend interruption. Those controls reduce component-level failure impact but do not remove host loss.

**Next step.** Define GPU assignment and TensorRT-artifact management, decide whether cameras are sharded by worker or host, choose a database and queue strategy for multiple hosts, and run failure and capacity tests on the intended production topology. Rebuild and remeasure the engine for each GPU class.

**Prepared answer.** “The evaluated implementation is a single-host edge prototype, so we have not claimed multi-GPU or multi-server failover. That was a deliberate way to prove the full workflow with the hardware available. The production next step is to implement and measure camera sharding, host recovery, artifact management, and shared-state behavior on the intended enterprise hardware.”

Sources: Defense paper, Chapter 3 Deployment Architecture, pp. 159–162; [09 — System Architecture](../02-architecture/09-system-architecture.md); [17 — Networking and Deployment](../02-architecture/17-networking-and-deployment.md); `ai_engine/pipeline.py:107-245`; `ai_engine/supervisor.py:42-240`.

### 6.3 The 0.956 mAP is a qualified validation-split result

**What the limitation is.** The tracker records accident mAP@0.50 of **0.956** for `epoch50.pt`, above the paper’s 0.85 validation target. The original split was not available for a fresh rerun, and frame-level incident leakage is disclosed. This is not an independent operational detection-accuracy percentage.

**Why it exists.** The mAP number answers the paper’s predefined model-validation gate using the recorded split. The incident-level safeguard and a fresh rerun were not completed within the study evidence update, so the team keeps the archival result qualified rather than treating it as a new independent test-set estimate.

**How we bounded the impact.** We report the separate 17-clip event-level run, its standard and hard strata, false positives per clean minute, and profile sensitivity. The team does not translate mAP into “the system detects 95.6% of accidents.”

**Next step.** Build an incident-level split before training or checkpoint selection, obtain an authorized fresh evaluation set, rerun the frame metric, and report it beside event recall and false alarms.

**Prepared answer.** “Yes, the 0.956 value clears the paper’s validation-split target, but it is qualified evidence because the original split could not be rerun and frame-level leakage is disclosed. We use the separate event-level results to discuss what an operator would receive: 8/16 overall, 8/10 standard, and 0/6 hard.”

Sources: tracker AI Model Validation!A2:K4; [26 — AI Accuracy and Evaluation](../04-ai/26-ai-accuracy-and-evaluation.md); Defense paper, Chapter 3 dataset preparation and Chapter 5 Table 30.

### 6.4 Hard-difficulty event recall is 0/6

**What the limitation is.** The frozen event run detected **8/16** clips overall, **8/10** standard clips, and **0/6** hard clips. The hard result is a real observed limitation even though no hard-recall acceptance threshold was approved before the run.

**Why it exists.** The project had a finite local evaluation corpus and treated difficulty as a reporting stratum rather than inventing a threshold after seeing the outcome. The set identifies difficult cases, including a far-camera collision, but does not establish one shared visual cause for all six misses.

**How we bounded the impact.** The team preserves the hard denominator instead of allowing the 8/16 aggregate to hide it. Alerts require temporal corroboration and remain subject to Confirm or Dismiss; the system is not presented as an autonomous dispatch decision-maker.

**Next step.** Collect more authorized local hard-scene footage, group and split it by incident, label the failure conditions, then compare controlled model, resolution, confidence, and accumulation changes using event recall, false positives, and latency together.

**Prepared answer.** “Hard recall is currently 0/6, and we state that plainly. The result comes from a finite, project-specific hard stratum, so we do not generalize it to every scene or claim that one cause explains all six misses. We would expand and diagnose that stratum before claiming improvement.”

Sources: tracker AI Model Validation!A3:K5; `ai_engine/eval/labels.csv`; [26 — AI Accuracy and Evaluation](../04-ai/26-ai-accuracy-and-evaluation.md); Defense paper, Chapter 5 Table 30 and Recommendations, p. 227.

### 6.5 Night and nearby-vehicle false positives

**What the limitation is.** The night analysis covers **8 of 17** clips. It reports higher night recall than day recall in the archival analysis, but the exact night hit numerator is not recoverable from the current machine-readable labels. All **3** residual false positives occurred at night and involved nearby vehicles. The overall false-positive observation was **0.27 per minute over 11.0 clean minutes**.

**Why it exists.** Night lighting, vehicle proximity, occlusion, and camera-specific appearance are environmental conditions that a finite mixed corpus cannot represent completely. No universal night threshold was approved, so the team reports the tested subset rather than converting it into a promise about every 2 a.m. shift.

**How we bounded the impact.** The tracker names the subset, clean denominator, and visible false-positive condition. Temporal accumulation suppresses isolated frames, and human verification prevents a visual alert from becoming an automatic dispatch. The system does not claim universal nighttime robustness.

**Next step.** Obtain authorized night and close-vehicle footage across cameras, label the actual scene conditions, and run controlled threshold and temporal-accumulation experiments. Compare night recall, proximity false positives, hard-scene recall, and decision delay so a gain in one subset does not hide a regression in another.

**Prepared answer.** “The evidence does not support a blanket claim that the system is robust at night. In the tested subset, all three residual false positives were nighttime cases involving nearby vehicles, while the archival night subset had higher recall than the day subset. We keep the operator in the loop and would target this condition with more local data and controlled experiments.”

Sources: tracker AI Model Validation!A3:K7; [26 — AI Accuracy and Evaluation](../04-ai/26-ai-accuracy-and-evaluation.md); Defense paper, Chapter 5 Recommendations, p. 227.

### 6.6 Fifteen-camera qualification is deferred

**What the limitation is.** The clean sustained cadence run exercised **8** streams for **900.031 seconds**; its minimum FPS was **5.15** and mean FPS **6.778**. A separate nine-stream step held about **12–13.6 FPS** with **20–24 ms** latency. The immediate test target is up to 10 streams, and there is no fifteen-camera live qualification.

**Why it exists.** Fifteen live streams require more than detector throughput: RTSP decode, frame arrival, scheduling, memory, thermal behavior, camera faults, persistence, and alert delivery must all be measured on the declared artifact and host for a stated duration. The capstone did not have that complete profile, so deferral preserves evidence discipline.

**How we bounded the impact.** The scheduler drops stale frames and slips rather than accumulating an unbounded backlog. Telemetry exposes degraded FPS and the 5 FPS warning floor. The team reports eight and nine as named profiles and does not extrapolate them to the paper’s **418-camera** network.

**Next step.** Run a fifteen-stream qualification with the intended stream sources, rebuilt TensorRT artifact, stated duration, resource and thermal capture, fault injection, and alert-delivery checks. Expand only after the measured profile clears an agreed go/no-go gate.

**Prepared answer.** “No, fifteen cameras were not qualified. We measured eight streams in the clean sustained run and a separate nine-stream degradation step; a fifteen-stream run must include decode, scheduling, thermals, failures, and delivery, not just detector timing. We therefore defer that number and will measure it on the intended host before scaling.”

Sources: tracker Performance & Load Testing!A3:H11; test plan Model and Inference Configuration; [27 — AI Performance, FPS, and Latency](../04-ai/27-ai-performance-fps-latency.md); [05 — Chapter 4 Results](../01-paper/05-chapter4-results.md).

### 6.7 Endurance evidence is shorter than the intended operating window

**What the limitation is.** The combined real performance and thermal run lasted **34.7 minutes** and carries an explicit duration deviation from the one-hour criterion. The memory case used accelerated frame replacement; the test plan claims no multi-hour or 24-hour endurance result.

**Why it exists.** The capstone test window allowed the team to exercise thermal behavior, memory retention, availability, restart, and injected faults, but not continuous full-duration operation. An accelerated memory probe answers a narrow retention question; it cannot establish long-run thermal drift, storage growth, or stream stability.

**How we bounded the impact.** The run recorded the actual duration and resource conditions rather than rounding it into a 24-hour claim. Separate cases covered restart, camera recovery, process isolation, health sampling, and fault injection. The tracker keeps those cases distinct from endurance duration.

**Next step.** Repeat the integrated workload on the intended deployment host for the required multi-hour and 24-hour windows, recording GPU temperature, VRAM, RAM, disk growth, FPS, reconnects, alert delivery, and operator-visible degradation.

**Prepared answer.** “The 34.7-minute run is real evidence about the tested host during that window; it is not a 24-hour qualification. We also used an accelerated memory probe, which has a narrower meaning. A deployment pilot must repeat the full workload for the intended duration and record resource and reliability trends.”

Sources: tracker Reliability & Endurance!A1:J16 and Performance & Load Testing!A10:H16; test plan Evaluation Methods → Fault tolerance and endurance; [05 — Chapter 4 Results](../01-paper/05-chapter4-results.md); [27 — AI Performance, FPS, and Latency](../04-ai/27-ai-performance-fps-latency.md).

### 6.8 Four participants support role coverage, not a population estimate

**What the limitation is.** Usability and UAT used **3** coded Operators, one assigned to each shift, and **1** coded Administrator. They completed **33** participant-stage executions: 27 Operator stages and 6 Administrator stages. All stages passed and the SUS mean was **89.375**, but four respondents are a small role-based sample.

**Why it exists.** The participant plan prioritized coverage of both access roles and the defined journeys within the capstone schedule. It was not a statistically powered survey of every CDRRMO operator, shift pattern, or future deployment site.

**How we bounded the impact.** The team reports the denominator, individual SUS scores, role-specific stages, standardized briefing, and assistance events. All participants completed the timed task in five minutes, but prompts were recorded, so the result is briefed and assisted task completion rather than unaided learnability.

**Next step.** In a pilot, include more operators across shifts, repeat tasks over time, compare first-use and routine-use performance, collect inter-rater feedback on alert decisions, and analyze SUS by role and experience.

**Prepared answer.** “Four people are enough for a small role-based usability and acceptance check: three Operators and one Administrator completed the defined journeys. They are not enough for a population-level claim, so we report the 89.375 SUS mean with its four-person denominator and assistance qualification. A larger pilot should test more operators and repeated use.”

Sources: test plan Test Participants and Acceptance Criteria; tracker Session Control!A14:H18, SUS Questionnaire!A4:O19, Execution Log!A1:H34, Usability Results!A4:H18, and UAT Results!A1:D16; [05 — Chapter 4 Results](../01-paper/05-chapter4-results.md).

### 6.9 The 25-second figure is a reconstructed operator-decision estimate

**What the limitation is.** UAT observed alert-to-decision times of **16, 9, and 15 seconds** after the alert appeared in the browser. The tracker adds approximately **3 seconds** for detector accumulation and **2 seconds** for propagation, producing an estimated mean of **18.333 seconds** and worst case **21 seconds** against the 25-second target. No automatic dispatch time was measured.

**Why it exists.** The approved UAT method started the stopwatch at dashboard alert appearance, while the paper’s objective starts when the collision becomes visible. The declared allowances bridge those boundaries; timing the first visible collision frame through every live camera and network path was outside this controlled participant run.

**How we bounded the impact.** The raw observations and the derived estimate remain separate in the tracker. The endpoint is an authorized human Confirm or Dismiss decision, which keeps dispatch and field response outside the claim.

**Next step.** In the authorized pilot, instrument collision visibility, detector event creation, backend commit, browser render, operator decision, and any approved dispatch handoff as separate timestamps.

**Prepared answer.** “The raw UAT measurements began when the browser alert appeared. We transparently added about three seconds for accumulation and two for propagation to reconstruct the collision-visible estimate: 18.333 seconds mean and 21 seconds worst case, both within 25 seconds. That endpoint is operator decision, not automatic dispatch.”

Sources: tracker Usability Results!A15:C16 and Execution Log!A1:H34; test plan Evaluation Methods → Operational efficiency; Defense paper, Chapter 1 Table 5 and NFR-09.

### 6.10 Acceptance and 100% Pass do not erase the qualifications

**What the limitation is.** The tracker records **194/194** technical cases as Pass, **33/33** participant stages as Pass, **9/9** readiness items Ready, and formal UAT as Accepted. Those denominators describe the declared test plan and prototype scope; they are not 100% model recall, citywide availability, or production certification.

**Why it exists.** A fixed case set is how the team made functional and workflow evidence auditable. Some rows intentionally test a simulated fault, an accelerated interval, an archival model result, or a reconstructed timing. The test plan says those qualifications remain attached after a Pass.

**How we bounded the impact.** Each result is reported with its denominator, evidence location, artifact or hardware condition, and qualification. The weakest operational claims remain visible: hard recall 0/6, no fifteen-camera qualification, 34.7-minute endurance, and no live rollout.

**Next step.** Use the accepted prototype as the baseline for a limited pilot. Define new production gates before deployment and preserve the same evidence and qualification fields for every expanded test.

**Prepared answer.** “The pass rate means every declared technical and participant-stage case completed successfully in the tested scope. It does not mean 100% accident recall or production readiness; for example, the event run was 8/16 and hard recall was 0/6. A pilot must close the scale, endurance, local-data, and deployment evidence gaps.”

Sources: tracker Summary!A5:G16 and UAT Results!A1:D16; test plan Acceptance Criteria introduction; [05 — Chapter 4 Results](../01-paper/05-chapter4-results.md); [06 — Chapter 5 Conclusions](../01-paper/06-chapter5-conclusions.md).

## 7. Likely panel questions

These are the hostile forms in which the limitations are likely to arrive. Keep each answer short, give the qualification before the defense, and end with the next step.

### “So this is not actually deployed at CDRRMO, is it?”

Correct: the completed study is a proof of concept on researcher-controlled hardware and a private LAN with simulated RTSP. That boundary protected live monitoring while we tested the real ingest, alert, persistence, and operator path. The next step is a CDRRMO-authorized limited pilot on the intended network and host.

### “Your architecture dies if one server dies. Why should anyone call it scalable?”

The evaluated topology is single-host, so we do not claim multi-server failover or multi-GPU capacity. We did separate component responsibilities, supervise camera runtimes, bound queues, and persist events locally, which supports the prototype’s failure behavior. Production scaling requires a measured sharding, artifact, shared-state, and failover design on enterprise hardware.

### “Isn’t 0.956 mAP just an inflated number?”

It is a valid recorded validation-split result above the paper’s threshold, but it is qualified because the original split could not be rerun and frame-level incident leakage is disclosed. We do not call it operational accuracy; the separate event result is 8/16 overall and 0/6 hard. A fresh incident-level split is the next validation step.

### “Zero out of six hard cases means the system does not work.”

It means the current hard stratum produced no event in those six clips, and that is the least-supported detection claim. We report it instead of hiding it inside the 8/16 aggregate, and no hard threshold was invented after the run. More authorized hard-scene data and controlled diagnosis are required before claiming improvement.

### “So it does not really work at night?”

The evidence is conditional. Eight of 17 clips were labelled night; archival analysis reported higher night recall than day recall, while all three residual false positives occurred at night around nearby vehicles. We do not promise universal 2 a.m. robustness; we would target night and proximity with more local footage and controlled experiments.

### “Why did you not test fifteen cameras if fifteen is in your design?”

Because a design target and a live qualification answer different questions. We measured eight streams in the clean sustained run and nine in a separate step; fifteen requires decode, scheduling, memory, thermals, failures, persistence, and delivery for a stated duration. The correct next step is that complete fifteen-stream run on the intended artifact and host.

### “How can 34.7 minutes prove an endurance system?”

It cannot prove 24-hour operation. It is a real short-window performance and thermal result with an explicit duration deviation, paired with a narrower accelerated memory probe. The deployment pilot must run the integrated workload for the required multi-hour and 24-hour windows and retain the resource trends.

### “Four participants are meaningless. Why report SUS at all?”

Four participants support a small role-based usability check: three Operators and one Administrator completed the defined journeys. The 89.375 mean describes those respondents, not every operator, and assistance was recorded for the timed task. A broader pilot should test more people and repeated use.

### “Did you really meet the 25-second objective, or did you add numbers afterward?”

The raw alert-to-decision observations were 16, 9, and 15 seconds. The approved method adds declared allowances of about three seconds for accumulation and two for propagation to align the browser start with collision visibility, producing 18.333 seconds mean and 21 seconds worst case. We report both raw and reconstructed values and do not call them dispatch time.

### “If UAT says Accepted and every row passed, why not deploy tomorrow?”

Accepted means the defined prototype UAT gates were met in the tested environment. The plan explicitly retains qualifications after Pass, including hard recall, deferred fifteen-camera capacity, short endurance, and simulated feeds. A limited pilot with production gates is still required before expansion.

### “How often will operators be disturbed by false alarms?”

The measured observation was 0.27 false positives per minute over 11.0 clean minutes, including the tested negative and clean portions of crash clips. That is not a shift-length forecast, and the residual false positives were night cases involving nearby vehicles. We would measure longer, representative clean footage during the pilot.

### “What happens when the single host is unavailable?”

New inference, API access, and local database access stop together because the current design has a shared host boundary. The engine’s outbox can protect events already written locally through a backend interruption, but it cannot repair total host or storage loss. Multi-host failover and recovery are production design work that still needs implementation and testing.

### “What did you actually prove about the 418 cameras?”

The paper uses 418 as the proposed CDRRMO production scope, not as a measured capacity result. The tracker only qualifies the named eight-stream and nine-stream profiles and defers fifteen cameras. We would expand from a measured pilot in controlled stages rather than extrapolate to all 418.

### “If prompts were needed, how can you call the system learnable?”

All four first-time participants completed the timed task in five minutes after the standardized briefing, but prompts were recorded. Therefore we call it briefed and assisted task completion, not unaided learning. The SUS result and role journeys still provide a useful first usability baseline for a larger pilot.

### “Who is accountable when the model misses a hard or nighttime accident?”

ADAS is a decision-support tool with human verification; it does not replace the authorized operator or dispatch authority. The hard and night limitations are why the workflow presents evidence for Confirm or Dismiss and why we do not promise autonomous coverage. A pilot must define escalation, monitoring, retraining, and incident-review ownership before operational use.

## 8. Cram summary

- Say **“proof of concept evaluated on researcher-controlled hardware and simulated or authorized feeds”**; do not say live citywide deployment.
- The tested server-side stack is **single-host**. It has no demonstrated multi-GPU scheduler, multi-server failover, or 418-camera capacity result.
- The qualified mAP result is **0.956 at IoU 0.50** on the recorded validation split. It is not operational accuracy.
- Event recall is **8/16 overall, 8/10 standard, 0/6 hard**. Keep the hard denominator visible.
- The night subset is **8/17**; all **3** residual false positives were night cases involving nearby vehicles. Do not promise universal night robustness.
- The measured false-positive observation is **0.27 per minute over 11.0 clean minutes**; do not turn it into a shift forecast.
- Capacity evidence is **8 streams sustained for 900.031 seconds** and a separate nine-stream step. **Fifteen cameras are deferred.**
- The combined performance and thermal window was **34.7 minutes**, with an explicit duration qualification; no 24-hour endurance claim exists.
- Usability and UAT used **3 Operators plus 1 Administrator**, with **33/33** stages passing and **89.375** mean SUS. This is role-based evidence, not a population estimate.
- The reconstructed decision estimate is **18.333 seconds mean, 21 seconds worst case**, from raw browser observations plus declared allowances. It is not dispatch time.
- The answer pattern is always: **boundary → deliberate reason → mitigation → next step**.
- The strongest next step is a **limited pilot on the intended hardware, authorized network, and RTSP/VMS path**, followed by broader local-data, capacity, endurance, recovery, security, and operator evidence.
