# 06 — Chapter 5: Conclusions and Recommendations

> **One-liner:** Chapter 5 closes the study by connecting the three objectives to the measured results, stating what the prototype demonstrates, and laying out the evidence and operational work needed before broader use.
> **Panel risk:** High — the conclusions are mixed: the workflow evidence is strong in the tested environment, while event-level detection and production-scale readiness remain bounded.

## 1. What it is

Chapter 5 is the paper’s close-out chapter.

It summarizes the completed ADAS prototype, restates the conclusions supported by testing, and assigns next steps to the stakeholder groups named in Chapter 1.

The core conclusion is deliberately scoped: ADAS functioned as a localized proof of concept, its operator workflows were demonstrated in a staging environment, and its AI evidence has clear scene and validation limits.

The chapter does not claim that ADAS is ready for immediate citywide integration.

It also does not claim that the prototype has already improved emergency response, public safety, or community confidence.

Those outcomes require long-term operational evidence.

Chapter 5 is titled “Summary and Recommendations.”

It has no separate section headed “Conclusions.”

The objective-by-objective conclusions are explicit in the “Conclusion” column of Table 30, “Summary of Findings.”

Use Table 30 to make the chain clear:

- Objective → what evidence answers it → what the result supports → what still needs work.

Do not give one blanket “the objectives were achieved” answer.

Objective 1 has functional implementation evidence and bounded event-level detection results.

Objective 2 has workflow, alerting, and user-acceptance evidence in the tested environment.

Objective 3 has a qualified frame-level mAP result, a measured UAT timing estimate, and event-level results that still expose a hard-scene coverage limit.

The recommendations are part of the conclusion, not a claim that those actions have already been completed.

## 2. Where it lives

### In the paper

- Chapter 1, “Objectives of the Study,” p. 13: the three objectives and the 85% mAP and 25-second timing targets.
- Chapter 1, “Scope and Delimitations,” pp. 14–15: proof-of-concept scope and exclusions.
- Chapter 5, Table 30, “Summary of Findings,” pp. 221–222: objective, indicator, measurement, supporting evidence, and conclusion in one place.
- Chapter 5, “Summary,” pp. 223–224: overall interpretation and the qualifications attached to the results.
- Chapter 5, “Recommendations,” pp. 225–227: actions for operators and partner agencies, citizens, LGUs, and future researchers/developers.
- Chapter 1, “Significance of the Study,” pp. 15–16: the stakeholder groups used to organize the recommendations.

The recommendations for future researchers and developers are the paper’s future-work section in substance.

There is no separate heading called “Future Work.”

### In the test record

- `ADAS Test Execution.xlsx`, **Summary!A5:C16**: technical pass counts and participant-stage totals.
- `ADAS Test Execution.xlsx`, **AI Model Validation!A2:K10**: qualified mAP, event recall, false-positive, night-scene, checkpoint, artifact, and profile evidence.
- `ADAS Test Execution.xlsx`, **Performance & Load Testing!A3:H4**: the eight-stream FPS result and alert-rendering qualification.
- `ADAS Test Execution.xlsx`, **UAT Results!A4:D14**: completed participant-stage executions, readiness, defects, and recorded acceptance decision.
- `ADAS Test Execution.xlsx`, **Usability Results!A4:H18**: participant scores, raw alert-to-decision timing, estimated end-to-end timing, and learnability.
- The test plan’s “Acceptance Criteria” table defines how qualified results must be described; its “Purpose” and “Test Environment” sections state the staging and deployment limits.

### In the code

Chapter 5’s conclusions and recommendations are prose, not code behavior.

These files identify the mechanisms behind the objective claims:

- Temporal evidence accumulation that forms an event: `ai_engine/accumulate.py:59`.
- Event handling, incident time, snapshot, and alert handoff: `ai_engine/accident.py:46`.
- Multi-camera inference entry point: `ai_engine/main.py:33`.
- Backend intake for an AI alert: `backend/app/api/routes/internal.py:93`.
- Backend WebSocket alert channel: `backend/app/main.py:442`.
- Operator confirm and dismiss actions: `backend/app/api/routes/alerts.py:465` and `backend/app/api/routes/alerts.py:518`.
- Dashboard alert presentation: `frontend/src/components/GlobalAlerts.tsx:48`.
- Browser WebSocket connection and message handling: `frontend/src/hooks/useAdasWebSocket.ts:30`.

Code references explain where the system behavior lives.

Use the paper and tracker for what was concluded and measured.

## 3. How it works

### The objective-to-conclusion chain

For each objective, state the target before the result.

Then name the evidence that directly addresses that target.

Keep the evidence’s denominator and qualification with the number.

State the conclusion at the same scope as the evidence.

End by naming the next action that follows from any remaining limit.

This is the short form:

1. “The objective was …”
2. “We assessed it using …”
3. “The result was … under these conditions …”
4. “So the conclusion is …, and the next step is …”

### Objective 1 — develop the real-time collision-detection pipeline

**Objective in the paper:** develop a real-time vehicle-to-vehicle collision pipeline, centered on a custom-trained YOLO detector, able to identify collision events across multiple camera streams and reduce reliance on manual monitoring.

Paper location: Chapter 1, “Objectives of the Study,” p. 13.

**Functional evidence:** the paper reports 68/68 unit tests, 23/23 integration tests, and 21/21 system end-to-end cases as Pass.

Table 30 also says the pipeline was exercised on eight concurrent 2K streams.

Paper location: Chapter 5, Table 30, pp. 221–222, and “Summary,” p. 223.

Tracker location: **Summary!A5:C7**.

**Detection evidence:** on the project-labeled crash clips, the frozen reference pipeline detected 8/16 crash events overall (50%), including 8/10 standard-condition events (80%) and 0/6 hard-condition events (0%).

It produced three false positives over 11.0 clean minutes, or 0.27 false positives per minute.

Paper location: Chapter 5, Table 30, pp. 221–222, and “Summary,” p. 224.

Tracker location: **AI Model Validation!A3:K5**.

**Conclusion to defend:** the pipeline was functionally implemented and exercised across multiple streams, but the event-level evidence is descriptive and bounded by difficult scenes.

The result supports the existence and tested operation of a detection pipeline.

It does not support a claim that the system detects every collision or is ready to replace operator monitoring.

### Objective 2 — develop the real-time alert dashboard

**Objective in the paper:** deliver immediate visual and audible notifications to operators through a dashboard, reducing dependence on delayed inter-agency endorsements.

Paper location: Chapter 1, “Objectives of the Study,” p. 13.

**Workflow evidence:** system testing exercised the flow from detection to snapshot, alert delivery, operator review, incident-state transition, camera pause/resume, audit recording, reporting, administration, and recovery.

The paper reports that the measured UAT completed all 33 participant-stage executions; the overall SUS mean was 89.375.

Paper location: Chapter 5, “Summary,” pp. 223–224, and Table 30, pp. 221–222.

Tracker location: **UAT Results!A4:D14**, **Usability Results!A4:H18**, and **Summary!A13:C15**.

**Timing evidence:** the estimated mean alert-to-decision time was 18.3 seconds and the estimated worst case was 21.0 seconds, within the 25-second objective.

Those are reconstructed collision-visible-to-decision estimates: raw alert-to-decision observations plus approximately three seconds for detector accumulation and two seconds for alert propagation.

Paper location: Chapter 5, Table 30, p. 222, and “Summary,” p. 224.

Tracker location: **Usability Results!A15:C16** and **UAT Traceability!A30:G30**.

**Conclusion to defend:** the dashboard and operator workflow were supported in the tested environment, with final incident verification and dispatch decisions remaining under authorized human supervision.

The tracker records the formal UAT decision as “Accepted” (**UAT Results!A14:D14**).

That status is a staging-environment acceptance result, not proof of production deployment.

### Objective 3 — validate mAP and end-to-end decision timing

**Objective in the paper:** achieve at least 85% mAP at IoU ≥ 0.50 and a 25-second collision-to-operator-decision latency.

Paper location: Chapter 1, “Objectives of the Study,” p. 13.

**mAP evidence:** the reported accident mAP@0.50 was 0.956 at epoch 50, above the numeric 0.85 threshold.

The evidence is a qualified frame-level validation-split result; it is not independent operational accuracy.

Paper location: Chapter 5, Table 30, p. 221, and “Summary,” p. 224.

Tracker location: **AI Model Validation!A2:K2**.

The tracker says the original validation split was not available for a fresh rerun and that frame-level incident leakage is disclosed.

It records the result as archival and limits its validity.

**Event-level evidence:** the crash-clip run detected 8/16 events overall, 8/10 standard events, and 0/6 hard events.

Table 30 calls this a descriptive operational baseline and says hard-scene performance needs further validation and improvement.

Paper location: Chapter 5, Table 30, pp. 221–222.

Tracker location: **AI Model Validation!A3:K5**.

**Timing evidence:** the estimated mean was 18.3 seconds and the estimated worst case was 21.0 seconds against the 25-second objective.

The estimate includes the stated allowances for detector accumulation and alert propagation.

Tracker location: **Usability Results!A15:C16**.

**Conclusion to defend:** the numerical mAP threshold was exceeded as a qualified frame-level result, and the measured UAT estimate met the timing target.

The event-level evidence remains limited, especially on hard scenes.

Do not collapse these into “85% accurate in real operation.”

### Keep adjacent performance claims distinct

The eight-stream performance run reported a 5.15 FPS minimum on the tested setup.

Table 30 says the five-FPS floor was supported on that setup, while the 15-FPS design target and production-scale capacity were not established.

Paper location: Chapter 5, Table 30, p. 222.

Tracker location: **Performance & Load Testing!A3:H3**.

The 887 ms alert-render p95 came from a controlled browser simulation.

That run is useful evidence about dashboard rendering, not a real collision-to-render measurement.

Tracker location: **Performance & Load Testing!A4:H4**.

Keep these three timing ideas separate when answering:

- Alert render time measures browser presentation in the controlled test.
- Alert-to-decision timing measures the operator’s observed task interval.
- Collision-visible-to-decision timing is the estimate after the documented allowances are added.

## 4. Why it was built this way

The recommendations turn measured limits into controlled next steps.

They keep the prototype’s useful evidence while requiring new operational proof before broader use.

The paper frames ADAS as a proof-of-concept design project and explicitly calls for controlled adoption and future evaluation.

Paper location: Chapter 5, “Recommendations,” pp. 225–227.

No alternatives matrix is provided in this chapter.

Do not invent a rejected design or say the panel approved a particular deployment choice.

Explain the choices visible in the paper: human oversight, a limited pilot, more representative evidence, and new validation before expansion or automation.

### Lipa CDRRMO operators, first responders, and partner agencies

#### Train operators on the actual workflow

The paper asks for training on snapshot review, confirming and dismissing alerts, alarm management, camera status, and system health. To act, prepare role-appropriate materials, a practice environment, and a way to confirm each task; explain what an AI alert does and does not authorize. Paper: Chapter 5, “Recommendations,” p. 225.

#### Document the partner-agency handoff

The paper asks for a documented procedure to share operator-confirmed incidents with police, traffic-management personnel, EMS, and other partners. To act, agree on contact points, the information to pass, the handoff trigger, and a receipt record; have participating agencies approve the procedure. Paper: Chapter 5, “Recommendations,” p. 225.

#### Keep AI evidence under human authority

The paper says alerts and snapshots are supplementary evidence, not dispatch authorization. To act, the operating procedure must identify who verifies an alert and who decides on dispatch; training and dashboard guidance should reinforce that boundary. Paper: Chapter 5, “Recommendations,” p. 225.

#### Record the errors and workflow friction

The paper asks operators to record false alarms, missed incidents, confusing alerts, and workflow difficulties. To act, keep the clip/incident context and operator interpretation with each report, then use the log to prioritize alert clarity and fatigue reduction. Paper: Chapter 5, “Recommendations,” p. 225.

### Accident victims and citizens of Lipa City

#### Prioritize the full notification gap

The paper asks stakeholders to reduce the time from collision to operator verification and manual response. To act, measure those stages in an approved pilot and coordinate the operator-to-response procedure; the prototype timing estimate alone does not measure an operational dispatch outcome. Paper: Chapter 5, “Recommendations,” p. 226.

#### Protect CCTV footage and incident information

The paper calls for access controls, retention policies, and privacy procedures. To act, assign responsibility for access, storage, retention, deletion, and incident review before handling operational footage, and align the rules across the system and partner agencies. Paper: Chapter 5, “Recommendations,” p. 226.

#### Explain the system and its data practices

The paper asks for clear communication of the system’s purpose, human oversight, and data management. To act, explain what is detected, who reviews alerts, what information is kept, and how it is protected in channels the community can access. Paper: Chapter 5, “Recommendations,” p. 226.

#### Evaluate real-world benefits instead of assuming them

The paper asks for long-term operational evidence about response, safety, and community confidence. To act, agree on baseline measures and collection responsibilities before a pilot, then review the results over time; do not present the prototype evaluation as proof of improved outcomes. Paper: Chapter 5, “Recommendations,” p. 226.

### Local government units

#### Start with a limited pilot

The paper recommends a pilot using the intended hardware, network, and authorized RTSP/VMS path. To act, secure the site, stream authorization, network access, hardware, and an operational owner; keep the scope bounded until performance is stable. Paper: Chapter 5, “Recommendations,” p. 226.

#### Complete the required readiness tests before expanding

The paper names multi-camera capacity, endurance, resource use, stream reconnection, backup/restoration, security, and alert delivery. To act, define acceptance criteria, test the intended setup, and retain evidence and limitations; review the results before expanding. Paper: Chapter 5, “Recommendations,” p. 226.

#### Prepare a sustainability plan

The paper asks for a plan covering hardware procurement, technical staffing, maintenance, cybersecurity, data storage, and model updates. To act, assign an owner and resources to each area, including service maintenance, data protection, and review of future model changes. Paper: Chapter 5, “Recommendations,” p. 226.

#### Gate gradual expansion on stable performance

The paper says to expand only after stable performance under selected operating conditions. To act, review pilot evidence at a go/no-go gate and add cameras in controlled steps after approval; the proof of concept does not establish citywide readiness. Paper: Chapter 5, “Recommendations,” p. 226.

### Future researchers and developers

#### Expand the local dataset and evaluation set

The paper calls for local CCTV footage covering hard collisions, night scenes, close vehicles, weather, camera angles, and traffic densities. To act, obtain authorized footage, label incidents consistently, and keep conditions needed to analyze errors; do not count adjacent frames as independent incidents. Paper: Chapter 5, “Recommendations,” p. 227.

#### Split data by incident and report event metrics

The paper asks for incident-level training/evaluation separation and reports of event recall, false positives, false positives per minute, and latency. To act, define incident groups before training/model selection and report clean-footage duration with false-positive rates. Paper: Chapter 5, “Recommendations,” p. 227.

#### Investigate hard misses and remaining false alarms

The paper asks for controlled model, threshold, and temporal-accumulation experiments on hard misses and night/proximity false alarms. To act, preserve a baseline, document the protocol, and compare event hits, false alarms, and latency by subset so a gain in one scene does not hide a regression in another. Paper: Chapter 5, “Recommendations,” p. 227.

#### Preserve reproducibility materials

The paper names source code, deployment instructions, model/engine provenance, evaluation labels, test evidence, configuration, and limitations. To act, version and archive these materials with the results they produced, giving the next team a reproducible baseline. Paper: Chapter 5, “Recommendations,” p. 227.

#### Keep broader scope as separate projects

The paper treats broader accident categories, more sensors, deeper VMS integration, and automated dispatch as separate future projects. To act, define new requirements, validation, and a safety review for each extension; do not describe them as part of the current validated system. Paper: Chapter 5, “Recommendations,” p. 227.

## 5. What changed since the 28 April defense

Chapter 5 does not provide a side-by-side revision history against the April defense.

Use the current paper’s Summary and Table 30 as the results for this defense.

If asked what specifically changed since the earlier presentation, name only changes that can be tied to an earlier paper version, dated test evidence, or a documented development record.

Do not infer that a new recommendation or result changed because of panel feedback unless the team can show that history.

The evidence the current Chapter 5 emphasizes is the measured system workflow, the project-specific event-level AI baseline, the estimated operator timing, and the stakeholder actions that follow from those results.

## 6. Limits and honest caveats

The system remains a proof-of-concept evaluated in a staging environment.

The paper and test plan do not establish a completed live CDRRMO deployment or production-scale capacity.

Source: Chapter 1, “Scope and Delimitations,” p. 14; test plan, “Purpose” and “Test Environment.”

The AI event results are a descriptive, project-specific baseline, not a general estimate of accuracy on all Lipa roads or cameras.

The event-level run detected 8/16 crash events overall, 8/10 standard events, and 0/6 hard events.

The false-positive rate was 0.27 per minute over 11.0 clean minutes; one negative-control clip producing no event does not prove deployment-wide specificity.

Source: Chapter 5, Table 30, pp. 221–222; **AI Model Validation!A3:K5**.

The mAP@0.50 result of 0.956 is qualified frame-level validation evidence.

The tracker records that the split was archival, the original split could not be freshly rerun, and frame-level incident leakage limits the result.

It is not independent operational detection accuracy.

Source: **AI Model Validation!A2:K2** and Chapter 5, “Summary,” p. 224.

The 18.3-second mean and 21.0-second worst-case figures are estimates.

They add documented detector-accumulation and alert-propagation allowances to raw UAT alert-to-decision observations.

They are not direct measurements of real-world collision-to-dispatch time.

Source: **Usability Results!A15:C16** and **UAT Traceability!A30:G30**.

The 887 ms alert-render p95 came from a controlled browser simulation.

It supports the browser-rendering result under that test, not an end-to-end real collision measurement.

Source: **Performance & Load Testing!A4:H4**.

The 5.15 FPS minimum was measured on an eight-stream demonstration setup.

The paper says that this supports the five-FPS floor on the tested setup, while the 15-FPS design target and production-scale capacity were not established.

Source: **Performance & Load Testing!A3:H3** and Chapter 5, Table 30, p. 222.

UAT demonstrates usability and acceptance of the evaluated workflows.

It does not prove broad public benefit, citywide readiness, or that operators should dispatch automatically from an AI alert.

The paper keeps final verification and dispatch decisions with authorized people.

Recommendations are proposed next steps.

They are not completed deployments, test results, or funded commitments.

## 7. Likely panel questions

### “Which objective is least well supported by your conclusions?”

Objective 3 is least supported as a claim about operational detection performance.

Its mAP threshold was exceeded in a qualified frame-level result and the UAT timing estimate met the target, but the event-level run detected none of the hard clips.

That is why our conclusion is limited to the tested evidence and calls for broader event-level validation.

_Source: Chapter 5, Table 30, pp. 221–222; **AI Model Validation!A2:K5**; **Usability Results!A15:C16**._

### “What is the single most important next step?”

Run a limited pilot on the intended hardware, network, and authorized RTSP/VMS path.

Use that pilot to validate event-level detection and complete the capacity, endurance, recovery, security, and alert-delivery checks before adding cameras.

_Source: Chapter 5, “Recommendations,” p. 226._

### “If you had another semester, what would you do?”

I would expand the locally representative footage and evaluation set, separate training and evaluation by incident, and investigate hard misses and night/proximity false alarms.

Then I would compare controlled model and temporal-accumulation changes on the intended pilot setup.

_Source: Chapter 5, “Recommendations,” p. 227._

### “You met the 85% mAP target. Why are you still cautious about accuracy?”

The 0.956 result is a qualified frame-level validation-split result, not independent operational accuracy.

Our event-level run was 8/16 overall and 0/6 on hard scenes, so the mAP number cannot stand in for real-world event recall.

_Source: Chapter 5, Table 30, p. 221; **AI Model Validation!A2:K5**._

### “Did you really measure the 25-second collision-to-decision time?”

We recorded raw alert-to-decision observations during UAT, then added the documented detector-accumulation and alert-propagation allowances.

The resulting estimates were 18.3 seconds mean and 21.0 seconds worst case; we describe them as estimates, not direct collision-to-dispatch measurements.

_Source: **Usability Results!A15:C16**; **UAT Traceability!A30:G30**._

### “Does 33/33 UAT mean the system is ready for citywide deployment?”

No. It means all planned participant-stage executions were completed and passed in the tested staging environment.

The paper still recommends a limited pilot and further capacity, endurance, security, recovery, and alert-delivery testing before expansion.

_Source: **UAT Results!A4:D14**; Chapter 5, “Recommendations,” p. 226._

### “Why not let the system dispatch automatically?”

The paper defines alerts and snapshots as supplementary evidence, with final verification and dispatch decisions under authorized human supervision.

Automated dispatch is listed as a separate future project requiring new requirements, validation, and safety review.

_Source: Chapter 5, “Recommendations,” pp. 225, 227._

### “What does the false-positive result actually tell you?”

The frozen reference run recorded 0.27 false positives per minute over 11.0 clean minutes, and the negative-control clip produced no event.

That is a descriptive result on the tested footage, not proof of specificity across a live camera network.

_Source: Chapter 5, Table 30, pp. 221–222; **AI Model Validation!A3:K5**._

## 8. Cram summary

- Chapter 5’s main finding: ADAS functioned as a localized proof of concept in the tested staging environment. (Chapter 5, “Summary,” pp. 223–224.)
- Objective 1: pipeline implemented and exercised across multiple streams; event-level recall remained bounded. (Chapter 5, Table 30, pp. 221–222.)
- Objective 1 evidence: unit 68/68, integration 23/23, and system end-to-end 21/21 passed; eight concurrent 2K streams were exercised. (**Summary!A5:C7**; Chapter 5, Table 30, pp. 221–222.)
- Objective 1 AI evidence: 8/16 overall, 8/10 standard, 0/6 hard; 0.27 false positives per minute over 11.0 clean minutes. (**AI Model Validation!A3:K5**; Chapter 5, Table 30, pp. 221–222.)
- Objective 2: alert and operator workflows were supported in the tested environment; authorized people retain final verification and dispatch decisions. (Chapter 5, “Summary,” pp. 223–224; **UAT Results!A14:D14**.)
- UAT: all 33 participant-stage executions completed; the SUS mean was 89.375; the tracker records “Accepted.” (**UAT Results!A4:D14**; **Usability Results!A11:C12**.)
- Objective 3 mAP target: 0.956 at IoU 0.50 exceeded the 0.85 threshold as qualified frame-level validation evidence. (**AI Model Validation!A2:K2**; Chapter 5, Table 30, p. 221.)
- Objective 3 timing: estimated mean 18.3 seconds and worst case 21.0 seconds were within the 25-second target; both are reconstructed estimates. (**Usability Results!A15:C16**; **UAT Traceability!A30:G30**.)
- Performance: 5.15 FPS minimum on the eight-stream test setup supported the five-FPS floor there; the 15-FPS target and production scale were not established. (**Performance & Load Testing!A3:H3**; Chapter 5, Table 30, p. 222.)
- Alert render: 887 ms p95 in a controlled browser simulation; do not call it real collision-to-render time. (**Performance & Load Testing!A4:H4**.)
- The least-supported claim is operational detection effectiveness on hard scenes; the next step is a limited, measured pilot.
- Recommendations cover operator training, inter-agency handoff, human oversight, privacy, long-term outcome measurement, pilot testing, sustainability, data, reproducibility, and separately validated future scope.
- Do not claim citywide deployment, automated dispatch, universal night robustness, or proven public-safety impact.
