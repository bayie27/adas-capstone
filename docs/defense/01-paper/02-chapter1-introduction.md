# 02 — Chapter 1: Introduction

> **One-liner:** Chapter 1 explains why Lipa CDRRMO needs an automated collision alert to complement manual CCTV monitoring, and draws a clear boundary around what ADAS does and does not do.
> **Panel risk:** high — the operational need is easy to overstate as a live deployment, automatic dispatch, or proven improvement in emergency outcomes.

## 1. What it is

### The problem in one sentence

Lipa CDRRMO already has extensive CCTV coverage, but camera coverage is not the same as immediate awareness of every road collision.
Operators still need to notice an incident on a feed or receive a report from someone who noticed it.
That leaves a notification gap between the collision and the point when CDRRMO knows to review it.
ADAS is intended to shorten that gap by detecting vehicle-to-vehicle collisions in configured CCTV streams and showing operators an alert.
It supports an operator's review and decision; it does not dispatch responders on its own.
The Chapter 1 problem is therefore not “Lipa has no cameras.”
It is “Lipa has no automated, real-time collision alert to support operators watching a large camera network.”

### Why road-safety monitoring matters

The paper opens with the public-health stakes of road traffic injuries.
It cites the World Health Organization estimate of approximately 1.19 million road-crash deaths each year.
It notes that road traffic injuries are a leading cause of death for people aged 5 to 29.
It also cites tens of millions of non-fatal injuries each year and economic losses of about 3% of most countries’ gross domestic product.
These figures establish that crash detection is a safety and social concern, not just a camera-management feature.
The paper then connects timely detection to access to emergency care after a crash.
The operational argument is that a delay before notification can delay the start of a response.
The paper does not claim ADAS itself provides medical care or dispatches an ambulance.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)
For the Philippine context, the paper says road traffic injuries are a leading cause of mortality among Filipino youth aged 15 to 29.
It describes national modernization efforts while noting that automated accident detection remains minimal or absent in the surveillance framework.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)

### Why the local case is Lipa City

Lipa City is the specific operating context for this study.
The paper states that Lipa CDRRMO manages 418 CCTV cameras across major roads and intersections.
It describes monitoring as predominantly manual across three 8-hour shifts.
The paper's point is that operators cannot guarantee real-time awareness of every collision by watching hundreds of feeds at once.
Surveillance hardware is present, but automated detection is not.
The local incident records make the problem concrete.
From 2023 through February 2026, CDRRMO recorded 3,219 emergency accidents.
Of those, 1,858 were classified as vehicular accidents, approximately 57% of all recorded emergencies in that period.
The annual vehicular-accident counts in the paper are 379 in 2023, 626 in 2024, and 732 in 2025.
The paper reports those as increases of 65.2% from 2023 to 2024 and 16.9% from 2024 to 2025.
The 2026 data are preliminary and cover only part of the year; do not compare them as if they were a full-year count.
For 2025–2026, the five barangays named in the paper together account for about 21.9% of recorded vehicular accidents.
The named barangays are Inosluban, Tambo, Dagatan, Antipolo del Norte, and Marawoy L.C.
These records show why a Lipa-focused alerting proof of concept is locally relevant.
They are context about Lipa's incident burden, not model-accuracy results.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)

### The notification gap, in plain language

The current notification chain often begins with a person seeing the crash.
That person may call the Traffic Management Division or a police officer.
The information is then relayed to CDRRMO.
The paper notes that direct reports to CDRRMO occur in rare instances.
The elapsed time therefore depends on who sees the collision and how the report is passed along.
The CDRRMO operations representative interviewed for the paper said that some cases take about 5 minutes to reach the agency.
The same account says that CDRRMO sometimes learns about an incident after it has ended or after a barangay has already responded.
The interview also says that CCTV observation can produce a faster response when the incident is seen there.
The 5-minute statement is an example reported in a personal communication, not a measured average or a guaranteed delay for every incident.
The paper identifies the gap as the lack of automated detection, not the lack of surveillance equipment.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12; personal communication dated September 3, 2026.)

### The three problems the study addresses

The Problem Statement names three connected problems.
First, the volume of CCTV feeds makes it difficult for operators to monitor all areas continuously, so a road accident can be missed.
Second, without automated alerts, CDRRMO depends heavily on delayed reports and inter-agency endorsements.
Third, delayed notification can slow the start of emergency response and worsen the consequences the paper names: injury, property damage, and traffic congestion.
Keep the sequence straight:
collision occurs;
someone notices it or an operator happens to see it;
the information reaches CDRRMO;
CDRRMO can then review and coordinate a response.
ADAS inserts an automated detection and alert step earlier in that chain.
It does not remove the operator's decision or the existing dispatch procedure.
(Defense paper, Chapter 1, “Problem Statement,” p. 12.)

### What Chapter 1 sets as the intended contribution

The paper's first objective is a real-time vehicle-to-vehicle collision detection pipeline with a custom-trained YOLO detector at its core.
The second objective is a real-time dashboard with visual and audible notifications for operators.
The third objective sets an mAP target of at least 85% at IoU ≥ 0.50 and a 25-second collision-to-operator-decision target.
The 25-second target concerns a collision becoming visible to the operator and the operator making a decision.
It is not a target for an ambulance to arrive, for an emergency dispatch to complete, or for an injury outcome to improve.
The stated purpose is to reduce the notification gap and support faster initiation of the CDRRMO's dispatch or endorsement procedures.
(Defense paper, Chapter 1, “Objectives of the Study,” p. 13.)

## 2. Where it lives

### In the paper

- **Chapter 1, “Background of the Study,” pp. 8–12:** global and Philippine context, Lipa CDRRMO's camera network, local incident records, and the reported notification delay.
- **Chapter 1, “Problem Statement,” p. 12:** the three linked operational problems.
- **Chapter 1, “Objectives of the Study,” p. 13:** the detection pipeline, dashboard alert, and collision-to-operator-decision objectives.
- **Chapter 1, “Scope and Delimitations,” p. 14:** the proof-of-concept boundary and the explicit exclusions.
- **Chapter 1, “Significance of the Study,” p. 15:** the stakeholder groups and their intended benefits.

When defending a local statistic, cite the Background section.
When asked whether ADAS dispatches automatically, cite Scope and Delimitations and the second and third objectives.
When asked who benefits, cite Significance of the Study.
Use section names and page locations; the claims in this guide do not depend on a Chapter 1 table or figure.

### In the code

#### Detection event creation

The AI pipeline updates per-camera collision evidence and calls its event handler when an event is produced: **ai_engine/pipeline.py:201**, **ai_engine/pipeline.py:206**, **ai_engine/pipeline.py:224**.
The pipeline pauses that camera before doing snapshot or network work: **ai_engine/pipeline.py:222**, **ai_engine/pipeline.py:223**.
The event handler creates an annotated snapshot and builds the incident payload: **ai_engine/accident.py:46**, **ai_engine/accident.py:75**, **ai_engine/accident.py:85**.
The payload is queued for delivery: **ai_engine/accident.py:92**.
The engine sends it to the backend's internal alert endpoint: **ai_engine/backend_client.py:73**, **ai_engine/backend_client.py:79**.

#### Incident intake and alert delivery

The backend's internal alert route receives the AI event: **backend/app/api/routes/internal.py:93**, **backend/app/api/routes/internal.py:111**.
The incident service records the detection and applies the camera's paused state as part of ingest: **backend/app/services/incidents.py:124**, **backend/app/services/incidents.py:158**, **backend/app/services/incidents.py:206**.
The backend broadcasts the newly committed detection to connected dashboards: **backend/app/api/routes/internal.py:130**, **backend/app/api/routes/internal.py:132**.
The event payload exposes the incident snapshot to the operator-facing application: **backend/app/services/events.py:29**, **backend/app/services/events.py:40**.

#### Operator notification and decision

The dashboard bridge receives alert events over the WebSocket hook: **frontend/src/components/RealtimeAlertsBridge.tsx:338**.
The global alert view shows an unverified detection and its snapshot: **frontend/src/components/GlobalAlerts.tsx:48**, **frontend/src/components/GlobalAlerts.tsx:308**.
The alert store starts the configured alarm when the active unverified queue becomes non-empty: **frontend/src/store/useAlertStore.ts:118**.
The operator's confirm and dismiss actions are available in the alert view: **frontend/src/components/GlobalAlerts.tsx:401**, **frontend/src/components/GlobalAlerts.tsx:408**.
The corresponding backend routes are **backend/app/api/routes/alerts.py:464** for confirmation and **backend/app/api/routes/alerts.py:517** for dismissal.
These code references explain the present mechanism.
The paper remains the authority for the problem framing, intended users, and study scope.

## 3. How it works

### The alert path

1. The system reads a configured RTSP video feed from a camera source.

   The study's scope says MediaMTX is used only to simulate VMS streams during development and testing.

   The project does not integrate its user interface with, modify, or administer the Lipa CDRRMO Dahua DSS Video Management System.

2. The AI engine processes the configured optical CCTV stream.

   The study's detection scope is vehicle-to-vehicle collision events.

   It does not analyze every event visible on camera.

3. The pipeline turns a collision event into an operator-facing record.

   It prepares an annotated snapshot and event metadata.

   This gives the operator visual evidence to review rather than an instruction to dispatch automatically.

4. The AI engine queues the event for backend delivery.

   The backend accepts the event and stores an incident record.

   The camera is paused for that incident cycle so it does not keep producing the same open alert.

5. After the record is committed, the backend broadcasts the alert to connected dashboards.

   The order matters: the dashboard should not be told an incident exists before the record is durable.

6. The dashboard presents the unverified alert with its snapshot and an audible notification.

   The operator can review the evidence and choose the appropriate next action.

7. The operator confirms or dismisses the detection.

   A confirmed incident remains part of the human-led CDRRMO workflow.

   The system supports the operator's decision and dispatch preparation; it does not initiate the dispatch itself.

### Where the notification gap changes

Before ADAS, awareness may depend on a witness, a TMD or police report, or an operator noticing the correct feed at the right time.
With ADAS, the system can identify a candidate collision in a configured stream and surface it to the dashboard.
The intended improvement is earlier CDRRMO awareness and an earlier operator decision.
The system does not promise that every crash is detected or that every response is faster.
The Chapter 1 target is collision-to-operator-decision, not collision-to-arrival of responders.
(Defense paper, Chapter 1, “Objectives of the Study,” p. 13; “Scope and Delimitations,” p. 14.)

### The human remains in the loop

ADAS changes how an operator may learn about a candidate incident.
It does not make the operator unnecessary.
The alert is an AI-generated detection that a human must review.
The operator remains responsible for deciding whether the detection is valid and what CDRRMO procedure follows.
This distinction is central to the Chapter 1 scope and to the answer about accountability.

## 4. Why it was built this way

### Why add automated detection when cameras already exist?

The paper identifies the existing CCTV network as the primary visual surveillance infrastructure.
The operational issue is the attention burden created by a large number of feeds.
Manual monitoring cannot guarantee that every incident is noticed in real time.
An automated alert adds an attention cue to the existing monitoring workflow.
It is a support layer for the operators, not a replacement for cameras or staff.

### Why focus on Lipa City?

The problem is documented in the same local operating context the study aims to support.
Lipa CDRRMO has a large camera network, a manual observation process, and locally recorded vehicular-accident data.
The paper also reports a direct account from the CDRRMO Operations and Warning Division about how external reports reach the agency.
This makes Lipa a grounded case for a local proof of concept.
Do not claim that the study proves the same notification pattern for every Philippine city.
Do not claim that the Lipa figures make the city statistically representative of all local governments.

### Why alerts instead of automatic dispatch?

The paper defines ADAS as decision support for CDRRMO operators.
Its objectives focus on detection, notification, and the operator's decision.
Dispatch and endorsement procedures remain with the CDRRMO and its partner agencies.
The system does not initiate a dispatch, route an emergency vehicle, or replace field responders.
The defensible rationale is that the study addresses the notification and operator-awareness step, not the whole emergency-response chain.

### Why keep the prototype independent of the existing VMS interface?

The paper explicitly says the system is a separate proof-of-concept layer that receives configured RTSP feeds.
It also explicitly gives the reason: prevent scope creep and avoid disruption to Lipa City's active monitoring operations.
This lets the study evaluate collision alerts without changing how the CDRRMO administers its Dahua DSS environment.
The project therefore does not claim to have modified, administered, or integrated the DSS user interface.

### Why use the existing camera medium?

The paper's significance section describes retrofitting passive CCTV with an active AI capability as a possible local-government contribution.
That frames the intended value as building on existing visual infrastructure rather than requiring a new camera system.
The project still limits its input to standard optical CCTV footage.
The paper does not report a comparative trial of CCTV against thermal, radar, or other sensor modalities.
Say this is the study's selected input scope, not a proven claim that other sensors are inferior.

### Why the proof-of-concept boundary is part of the design

The study evaluates a Python AI engine, FastAPI backend, local SQLite database, and React dashboard on researcher-controlled edge or test hardware.
It uses simulated or authorized test feeds rather than the live citywide monitoring infrastructure.
That boundary protects active operations while the team evaluates detection, system timing, and operator workflow in the documented demonstration environment.
The study's result is a working proof of concept, not a completed production deployment across Lipa.

### What alternatives did the paper actually evaluate?

The paper describes manual monitoring and external reporting as the existing operational baseline.
Chapter 1 does not describe a controlled head-to-head experiment comparing ADAS with alternative dispatch systems.
Do not claim a formal A/B comparison against VMS vendors, radar systems, or other AI architectures as part of Chapter 1.
When asked why an alternative was not included, connect the answer to the stated local problem and the boundaries in Scope and Delimitations.

## 5. What changed since the 28 April defense

The current Chapter 1 reports CDRRMO accident records through February 2026.
Because those records end before the April defense, do not call them newly collected since then unless the archived April copy confirms that.
The clearest dated post-defense evidence in this chapter is a personal communication from the CDRRMO Operations and Warning Division dated September 3, 2026.
That later account describes variable reporting delays, including cases reported at about 5 minutes and cases learned only after an incident or barangay response.
Use it as a source-grounded description of the notification problem, not as a measured average.
The current scope states directly that the completed study is a proof of concept evaluated on researcher-controlled hardware.
It states that the project is not a production-scale deployment and does not claim unmeasured operational outcomes.
The current boundary makes the distinction between an evaluated ADAS prototype and any future CDRRMO deployment explicit.
It also makes clear that the system supports operator review but does not initiate dispatch.
If asked for the exact wording the panel saw in April, verify the archived April presentation before quoting it.
Do not reconstruct an older Chapter 1 claim from memory.
For this defense, state the current evaluated boundary plainly.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12; “Scope and Delimitations,” p. 14.)

## 6. Limits and honest caveats

### Explicit delimitations and the reason to give

The paper gives a shared explicit rationale for the VMS and live-operations boundary: avoid scope creep and avoid disrupting active Lipa CDRRMO monitoring.
For several other exclusions, the paper states the boundary without assigning a separate technical rationale to each item.
Use the study's stated focus—collision detection, alerting, timing, and operator workflow—to explain those boundaries.
Do not invent a separate experiment, approval decision, or technical limitation that the paper does not report.

### What the study includes

The project spans three semesters across the 2025–2026 and 2026–2027 academic years.
It implements a custom-trained YOLO-based model using publicly available annotated datasets.
It separately evaluates event-level performance using held-out Lipa CDRRMO CCTV footage.
The application consists of a Python AI engine, a FastAPI backend, a local SQLite database, and a React dashboard.
The completed prototype runs on researcher-controlled edge or test hardware.
Operators and Administrators review AI-generated alerts through a Human-in-the-Loop workflow.
They can manage camera configurations, view dashboard analytics and system health, and review historical detections.
Administrators also manage user accounts, audit logs, backup and restore functions, and AI-performance reports.
The evaluation focuses on detection performance, system timing, and operator workflow efficiency in the documented demonstration environment.
(Defense paper, Chapter 1, “Scope and Delimitations,” p. 14.)

| Explicitly out of scope                                                                                     | Paper-grounded reason to give                                                                                                                     |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Integrating the ADAS user interface with Dahua DSS, modifying DSS, or administering it                      | The study uses an independent RTSP-consuming proof of concept; the paper says this avoids scope creep and disruption to active monitoring.        |
| Testing on the live citywide monitoring infrastructure                                                      | Evaluation uses researcher-controlled hardware with simulated or authorized test feeds; the live citywide system is protected from study changes. |
| Maintaining or repairing the city's CCTV network                                                            | These are city infrastructure operations, not part of the study's defined prototype evaluation.                                                   |
| Optimizing city network bandwidth or scaling the city's 418-camera network                                  | The study evaluates its documented demonstration environment; full city-network scaling is explicitly outside scope.                              |
| Automated emergency dispatch or emergency-vehicle routing                                                   | ADAS supports operator review and decision-making; the paper explicitly says it does not initiate dispatch.                                       |
| Public-facing applications                                                                                  | The stated user is the internal Lipa CDRRMO operation, not the public.                                                                            |
| Direct workflow support for on-ground traffic enforcers, other municipal departments, or neighboring cities | These users and networks are outside the defined internal Lipa CDRRMO scope.                                                                      |
| Thermal, radar, or other non-optical inputs                                                                 | The defined input is standard optical CCTV footage.                                                                                               |
| Pedestrian accidents, traffic violations, theft, fire, infrastructure damage, or other non-collision events | The AI objective is limited to vehicle-to-vehicle collision events.                                                                               |
| Production-scale deployment and unmeasured operational outcomes                                             | The completed study is a proof of concept evaluated in its documented demonstration environment.                                                  |

(Defense paper, Chapter 1, “Scope and Delimitations,” p. 14.)

The infrastructure and workflow exclusions are not accidental omissions.
They preserve a manageable study boundary and prevent the prototype from changing live CDRRMO operations.
The model-class and sensor exclusions define the question this project chose to study.
The project does not establish performance on excluded event classes or sensor types.
(Defense paper, Chapter 1, “Scope and Delimitations,” p. 14.)

### Do not overstate the numbers

The 418 figure describes the CDRRMO camera network; it is not the number of simultaneous cameras processed in the completed proof of concept.
The paper explicitly excludes hardware scaling for that citywide network from this study.
The 5-minute report is a case described by a CDRRMO representative; it is not the average notification delay for all crashes.
The 3,219 emergency records and 1,858 vehicular classifications describe the local operational context; they are not detections from the ADAS test set.
The mAP target and the 25-second operator-decision target are Chapter 1 objectives; neither is a clinical outcome or dispatch-arrival measurement.
The five-barangay concentration is a spatial context finding; it is not a promise that the system covers every high-risk location.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12; “Objectives of the Study,” p. 13; “Scope and Delimitations,” p. 14.)

### Intended benefit versus measured result

The Significance section identifies benefits for operators, responders and partner agencies, accident victims, citizens, local government units, and future researchers.
Those are the study's intended contributions and stakeholder value.
The scope says evaluation focuses on model detection, system timing, and operator workflow in the documented demonstration environment.
It does not claim a production-scale deployment or unmeasured operational outcomes.
Do not say ADAS has been proven to reduce mortality, injury severity, property damage, congestion, or agency spending.
Do say the system is designed to support earlier awareness and faster operator decision-making within the study's evaluated workflow.

### Stakeholder benefits, stated carefully

**Lipa CDRRMO Command Center Operators:** the paper expects automated collision alerts to reduce cognitive load from continuous surveillance and help operators move from passive observation to active response coordination.
This does not mean ADAS removes the need for operator attention or judgment.
**First Responders and Partner Agencies:** the paper expects a faster verified visual handoff to support coordination and resource allocation.
ADAS does not send them a dispatch order automatically.
**Accident Victims:** the paper describes reducing the notification gap from minutes to seconds as a way to support more timely medical intervention.
The study does not measure patient outcomes or survival.
**Citizens of Lipa City:** the paper presents improved safety awareness and civic trust as longer-term community value.
These outcomes are not reported as measured study results.
**Local Government Units:** the paper presents the project as a possible cost-efficient model for adding AI to existing CCTV infrastructure.
Do not claim that this study measured savings or demonstrated full-network scale.
**Future Researchers and Developers:** the study provides a technical reference for localized edge-based collision detection and human-reviewed alerts.
This is the most directly evidenced benefit beyond the prototype itself.
(Defense paper, Chapter 1, “Significance of the Study,” p. 15; “Scope and Delimitations,” p. 14.)

## 7. Likely panel questions

### “What exactly is the gap you are closing?”

Lipa CDRRMO has CCTV coverage, but it lacks automated real-time collision detection to help operators notice incidents across that network.
ADAS turns a candidate collision in a configured feed into an alert with visual evidence for operator review.
It shortens the notification path; it does not dispatch responders automatically.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12; “Scope and Delimitations,” p. 14.)

### “Why can't CDRRMO just watch the monitors?”

That is the current process, but the paper says operators must watch hundreds of feeds at once across three 8-hour shifts.
The issue is the scale of continuous attention required, not operator effort or commitment.
An automated alert gives the operator another way to learn about a collision while keeping human review in the loop.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)

### “Why did you choose Lipa City?”

The project addresses a documented local problem: Lipa CDRRMO manages 418 cameras, and vehicular accidents made up about 57% of its recorded emergency cases from 2023 through February 2026.
The paper also includes a CDRRMO account of variable notification delays.
That makes Lipa an appropriate case for a local proof of concept, not a claim that every city has the same conditions.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)

### “Is the five-minute figure the average delay?”

No. It is an example the CDRRMO representative gave for some cases, depending on whether someone sees the collision and reports it.
The paper's point is that the notification interval varies and that CDRRMO can sometimes learn of an incident after it has ended.
(Defense paper, Chapter 1, “Background of the Study,” pp. 8–12.)

### “What did you deliberately leave out, and why?”

We excluded direct Dahua DSS integration and live citywide testing to avoid scope creep and disruption to active CDRRMO monitoring.
We also limited the study to vehicle-to-vehicle collisions from optical CCTV and to operator alerting, rather than dispatch, routing, public apps, or other agencies.
Those boundaries keep the evaluation focused on the detection and notification problem defined in Chapter 1.
(Defense paper, Chapter 1, “Scope and Delimitations,” p. 14.)

### “So does ADAS send an ambulance when it detects a crash?”

No. ADAS sends the collision alert to a CDRRMO operator, who reviews the evidence and decides what procedure to follow.
The system supports faster awareness and dispatch preparation; it does not initiate dispatch or route an emergency vehicle.
(Defense paper, Chapter 1, “Objectives of the Study,” p. 13; “Scope and Delimitations,” p. 14.)

### “Is this already running on Lipa CDRRMO's citywide cameras?”

No. The completed work is a proof of concept evaluated on researcher-controlled hardware with simulated or authorized test feeds.
The paper does not claim installation in the command center or production-scale operation across the 418-camera network.
(Defense paper, Chapter 1, “Scope and Delimitations,” p. 14.)

### “You say this helps victims and citizens. Did you measure that?”

Those are the intended stakeholder benefits in the Significance section.
The study evaluates detection performance, timing, and operator workflow in its demonstration environment; it does not measure mortality, patient recovery, public trust, or citywide cost savings.
(Defense paper, Chapter 1, “Significance of the Study,” p. 15; “Scope and Delimitations,” p. 14.)

### “Why only vehicle-to-vehicle collisions?”

That is the detection objective the study defines for this proof of concept.
Pedestrian incidents, violations, fires, theft, infrastructure damage, and other sensor types are explicitly outside its AI scope.
We should not claim that this project detects those cases.
(Defense paper, Chapter 1, “Objectives of the Study,” p. 13; “Scope and Delimitations,” p. 14.)

## 8. Cram summary

- The gap is delayed CDRRMO awareness, not missing CCTV.
- Manual monitoring and external reports cannot guarantee immediate notice of every collision.
- Lipa CDRRMO manages 418 cameras and its local records show a substantial vehicular-accident burden.
- A CDRRMO representative described variable reporting delays, including cases of about 5 minutes.
- Treat that 5-minute account as an example, not an average.
- ADAS detects candidate vehicle-to-vehicle collisions in configured optical CCTV feeds.
- It stores the incident, sends a dashboard alert with a snapshot, and gives the operator a review step.
- The alert supports the current human-led response workflow.
- ADAS does not dispatch, route emergency vehicles, or replace CDRRMO judgment.
- The study is a proof of concept on researcher-controlled hardware.
- Testing uses simulated or authorized feeds, not the live citywide camera infrastructure.
- Direct Dahua DSS integration, city-network maintenance, repair, optimization, and 418-camera scaling are out of scope.
- The model does not cover pedestrian events, violations, theft, fire, infrastructure damage, or non-optical sensors.
- The 25-second objective ends at the operator's decision; it is not an ambulance-arrival target.
- The stakeholder benefits are intended contributions; do not present unmeasured outcomes as study results.

(Sources: Defense paper, Chapter 1, “Background of the Study,” pp. 8–12; “Objectives of the Study,” p. 13; “Scope and Delimitations,” p. 14; “Significance of the Study,” p. 15.)
