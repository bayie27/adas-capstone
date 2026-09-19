# 30 — Anticipated Panel Q&A

This is a rehearsal bank for the final defense. The questions are grouped by the kind of challenge they invite, rather than by the guide where the detail first appeared. Each question has a **detail tag** pointing to the guide to open when a panelist asks a follow-up. The answer is the spoken version: keep the qualification in the answer and do not replace it with a stronger claim during the defense.

## 1. Objectives and scope

### 1. What exactly is the gap ADAS is closing?

**Detail:** [Guide 02 — Chapter 1 introduction](../01-paper/02-chapter1-introduction.md)

Lipa CDRRMO has CCTV coverage, but operators still need to notice collisions across a large set of feeds and start the notification process. ADAS turns a candidate collision in a configured feed into an alert with visual evidence for operator review; it shortens the notification path but does not dispatch responders automatically.

### 2. Why did you choose Lipa City?

**Detail:** [Guide 02 — Chapter 1 introduction](../01-paper/02-chapter1-introduction.md)

Lipa is the local case for a documented command-center problem: the paper describes 418 cameras and vehicular accidents as about 57% of recorded emergency cases from 2023 through February 2026. That makes it an appropriate setting for a local proof of concept, not evidence that every city has identical traffic or operating conditions.

### 3. Did you weaken your objectives to make them easier to hit?

**Detail:** [Guide 01 — Objectives](../01-paper/01-objectives.md)

The 25-second boundary is wider than the earlier sub-15-second wording because it covers the actual path from a visible collision through accumulation, alert delivery, and a recorded operator decision. The current paper and test plan use that boundary, and we show the raw human timing and the added system allowances separately.

### 4. Why did Objective 1 move from “a YOLO model” to “a detection pipeline”?

**Detail:** [Guide 01 — Objectives](../01-paper/01-objectives.md)

YOLO produces frame-level candidates, but the deliverable also has to collect and schedule frames, accumulate evidence, create an event, and deliver it to the backend. The revised wording keeps YOLO at the core while describing the full stream-to-alert unit the team actually developed.

### 5. What exactly does Objective 2 guarantee?

**Detail:** [Guide 01 — Objectives](../01-paper/01-objectives.md)

It commits us to a dashboard that presents visual and audible alerts to an operator and supports the operator’s decision. It does not claim automatic dispatch, responder routing, or that every collision will be detected in every environment.

### 6. Why did you limit the AI to vehicle-to-vehicle collisions?

**Detail:** [Guide 02 — Chapter 1 introduction](../01-paper/02-chapter1-introduction.md)

That is the detection objective defined for this proof of concept and the one for which we prepared the data and evaluation. Pedestrian incidents, fires, theft, violations, infrastructure damage, and other sensor types remain outside this project’s AI claim.

### 7. So does ADAS send an ambulance when it detects a crash?

**Detail:** [Guide 02 — Chapter 1 introduction](../01-paper/02-chapter1-introduction.md)

No. ADAS sends the collision alert and evidence to a CDRRMO operator, who reviews it and decides which procedure to follow. The system supports faster awareness and dispatch preparation; it does not initiate dispatch or route an emergency vehicle.

## 2. The literature and justification

### 8. What accuracy do comparable systems report, and how does ADAS compare?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

Chapter 2 reports mAP values from 60.9%–67.4% for Minh et al., 82.4% for Li et al., 83.3% for Ahmed et al., and 88.7% for Gurusamy et al. ADAS records 95.6% mAP@0.50 on a qualified validation split, while its local event recall is 8/16 overall and 0/6 on hard clips, so those figures answer different questions.

### 9. Which paper justifies your 85% target and your runtime threshold?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

No single paper mathematically sets the 85% target; the cited detector results frame a plausible comparison range. The runtime confidence floor of 0.15 is an engineering choice used with temporal accumulation, not a value prescribed by one literature source.

### 10. Did any study contradict your approach?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

Yes, the literature shows that useful results can occur below our target depending on the task, dataset, and metric; Minh et al. report 60.9%–67.4% mAP@0.50. That is why we use the studies for design rationale and report local event evidence separately instead of treating the literature as a guarantee.

### 11. How do you know published findings transfer to Lipa traffic?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

We do not claim that transfer is automatic. The local footage is the relevant evidence, and it records 8/16 event recall overall and 0/6 on hard clips, which shows where a foreign benchmark does not settle the Lipa-specific question.

### 12. Why YOLO instead of Faster R-CNN or a transformer?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

The paper presents YOLO as a single-stage detector that balances accuracy and speed for live feeds on the intended hardware. The alternatives have different metrics and compute costs, so our claim is a reasoned fit for this edge prototype, not that every other detector is incapable of working.

### 13. Is your literature already out of date?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md)

The review includes work from 2021 through 2026, including recent detector studies. The human-attention findings remain relevant to the operator problem, but detector comparisons should be refreshed before choosing a production-scale model.

### 14. Why keep a human in the loop if the literature supports automation?

**Detail:** [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md) and [Guide 07 — Definition of terms](../01-paper/07-definition-of-terms.md)

The detector raises a candidate and the authorized operator confirms or dismisses it, which keeps an accountable human decision in the workflow. HITL does not remove false alerts; it limits the consequence of an uncertain candidate and avoids treating a model score as a dispatch order.

## 3. The AI model and its accuracy

### 15. Did you meet the 85% accuracy target?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

Yes, the tracker records 0.956 mAP@0.50 against the paper’s 0.85 target. It is a qualified validation-split result; the local event run records 8/16 overall, including 8/10 standard clips and 0/6 hard clips.

### 16. Is 95.6% mAP proof that ADAS catches 95.6% of crashes?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

No. The number is accident-class mAP@0.50 on the recorded validation split, with the incident-leakage limitation disclosed. Event-level local evidence is different: 8 of 16 labelled collision clips produced an event, and none of the six hard clips did.

### 17. What does “qualified validation-split result” actually mean?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

It means the score is valid for the recorded frame-level split and its stated evidence, but the whole-incident separation safeguard did not complete and the original split was unavailable for a fresh run. It meets the stated split threshold without becoming a claim of independent operational accuracy.

### 18. Why is hard-case recall zero?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

All six clips preclassified as hard produced no event inside their scoring windows, including a far-camera collision among the difficult cases. We report 0/6 as the observed limitation and would expand representative hard-scene footage before claiming that a change improved it.

### 19. Why report recall by difficulty instead of one overall number?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

The 8/16 total would hide the difference between 8/10 standard cases and 0/6 hard cases. The strata were set before execution, so showing the denominators makes the boundary of the evidence visible instead of allowing the average to conceal the misses.

### 20. “Why should CDRRMO trust an AI that misses the hard cases?”

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md) and [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

CDRRMO should treat the current system as decision support, not as a sole authority for hard scenes or dispatch. The operator still reviews every candidate, and our honest position is that the 0/6 hard result requires better local data and pilot validation before broader reliance.

### 21. “So it doesn’t really work at night?” / “Would you trust this at 2 a.m.?”

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

The tested subset included 8 of 17 clips labelled night; night recall exceeded day recall, but all three residual false positives occurred at night around nearby vehicles. That is evidence about this sample, not universal nighttime robustness, so nighttime alerts still require operator verification.

### 22. Why is the confidence threshold only 0.15 — isn’t that reckless?

**Detail:** [Guide 24 — AI pipeline](../04-ai/24-ai-pipeline.md)

0.15 is only the frame-evidence floor, chosen to preserve weak collision clues. An alert requires spatially linked evidence to accumulate to 1.0 confidence-seconds with decay, so one weak frame cannot fire an alert by itself; persistence and human review supply the next controls.

### 23. How do you avoid alerting on every near-miss?

**Detail:** [Guide 24 — AI pipeline](../04-ai/24-ai-pipeline.md)

Only accident-class boxes enter the accumulator, boxes must overlap an existing region, unsupported evidence decays, and one fired region is retained during the pause cycle. False alarms remain possible, which is why the result is shown to an operator instead of being converted directly into an automatic dispatch.

## 4. Performance and capacity

### 24. How many cameras can this really handle?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

The evidence qualifies the named demonstration host at tested profiles, not a universal camera count. Eight streams have the clean maximum-count qualification, a nine-stream step held about 12–13.6 FPS with 20–24 ms latency, and fifteen-camera qualification is deferred; we do not extrapolate those results to 418 cameras.

### 25. Why is fifteen-camera qualification deferred?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

A synthetic batch benchmark is not fifteen live RTSP streams. The missing qualification must include the declared artifact, stream count, hardware, duration, decode, scheduling, memory, thermals, and alert path on the intended host.

### 26. What is the bottleneck: the model or the hardware?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

The batch profile shows shared inference becoming cheaper per frame as the tested batch grows, reaching 10.84 ms per frame at batch 16. Live capacity also includes decoding, scheduling, memory, network, and thermal effects, so the evidence supports a hardware-and-artifact result rather than one universal model-only bottleneck.

### 27. What happens when you exceed capacity?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

The scheduler keeps the newest usable frames, drops stale frames, and slips when a tick overruns instead of building an unbounded backlog. Telemetry exposes lower FPS and warns when processing falls below 5 FPS; behavior beyond the measured profiles still needs a dedicated run.

### 28. Are the batch numbers your production FPS?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

No. The batch harness is inference-only, using replicated synthetic frames and timed detector calls. Production uses a fixed scheduler and live streams, so batch throughput cannot replace a qualification that includes decode, hardware, duration, and delivery.

### 29. Does the ≤100 ms inference target mean an operator sees an alert in ≤100 ms?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

No. The ≤100 ms figure is detector analysis time per frame after dividing a measured batch time; alert rendering has a separate ≤2-second budget. The operator’s decision is part of the separate ≤25-second collision-visible-to-decision objective.

### 30. What exactly did you measure for alert delivery?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

Thirty controlled browser-injected detections rendered the real modal and snapshot in a mean 668.2 ms, p95 887 ms, and maximum 1,395 ms, below the 2-second criterion; audio was instrumented separately. A live two-client trial also measured 24 ms from one client’s commit to the other client’s WebSocket update, which is delivery evidence rather than a full human decision measurement.

### 31. How do you get 18.333 seconds if the target is 25 seconds?

**Detail:** [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

The three raw alert-to-decision observations were 16, 9, and 15 seconds. The tracker adds approximately 3 seconds for detector accumulation and approximately 2 seconds for propagation, producing an estimated mean of 18.333 seconds and a worst case of 21 seconds; both remain below 25 seconds, and the raw observations stay visible.

### 32. Can you lower resolution or frame rate to increase capacity?

**Detail:** [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

The tested 720p profile reduced event recall from 8/16 to 6/16, so downscaling is not accuracy-neutral. The cadence run preserved the native hit/miss pattern at 10, 8, 6, 5, and 3 FPS but missed one named clip at 4 FPS; each operating profile needs its own evaluation.

## 5. System design and architecture

### 33. Why split the system into three processes instead of one app?

**Detail:** [Guide 09 — System architecture](../02-architecture/09-system-architecture.md)

The three responsibilities are continuous video inference, authoritative data and workflow, and the operator interface. Separating them keeps heavy processing away from the browser and lets the backend own state changes while still allowing a production installation on one edge host.

### 34. Could this run on one machine, and does it?

**Detail:** [Guide 09 — System architecture](../02-architecture/09-system-architecture.md)

Yes. The target design places the AI engine, FastAPI/React application, and SQLite on one on-premises edge server, with browser workstations on the LAN. The proof of concept was evaluated on researcher-controlled hardware, so that topology is a design target, not a claim of a completed CDRRMO installation.

### 35. What happens if the AI engine, backend, or browser goes down?

**Detail:** [Guide 09 — System architecture](../02-architecture/09-system-architecture.md)

If the AI engine stops, no new detections are created and the backend can show stale heartbeats; buffered events can resume when it returns. If the backend stops, the engine keeps detected events in its disk-backed outbox, while a disconnected browser rebuilds active state from REST after reconnecting.

### 36. Why FastAPI, React, and SQLite specifically?

**Detail:** [Guide 09 — System architecture](../02-architecture/09-system-architecture.md)

FastAPI with Uvicorn supports ordinary requests, engine heartbeats, and long-lived WebSockets without making idle sockets block a worker. React provides a component-based dashboard, while SQLite avoids a separate edge database service and WAL lets readers work while records are written.

### 37. Why enforce important rules in the database instead of only in Python?

**Detail:** [Guide 10 — Data model](../02-architecture/10-data-model.md)

Python validation gives early, readable errors, but it cannot protect every write path or resolve a race between requests. Database constraints enforce uniqueness, allowed values, and relationships at commit time, including the rule that only one Unverified or Ongoing incident can be open for a camera.

### 38. Your schema grew from five to ten tables. Was the original design wrong?

**Detail:** [Guide 11 — Five to ten tables](../02-architecture/11-five-to-ten-tables.md)

The original five remain the core account, camera, incident, and telemetry entities; the added tables persist sessions, settings, audit history, resumable exports, and searchable help. The exact physical schema could have been different, but the additional workflows required durable state and were refinements against the stated requirements.

### 39. Walk me through the data flow, and why does the browser not receive RTSP?

**Detail:** [Guide 18 — Diagrams, swimlane, DFD and ERD](../02-architecture/18-diagrams-swimlane-dfd-erd.md)

CCTV or the VMS sends the stream to the AI engine, the engine forms an event for the backend, and the backend sends the operator a committed alert and receives the decision. RTSP terminates at the AI engine; the browser uses REST and WebSocket JSON events, so it does not need raw video for the alert workflow.

### 40. What if the same alert arrives twice, or two operators act at once?

**Detail:** [Guide 12 — Design decisions](../02-architecture/12-design-decisions.md) and [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

Retries reuse `source_event_id`, so the backend returns the existing incident and does not broadcast a second creation event. Operator transitions use the expected current status in the database predicate; one action wins and a competing action receives a state conflict instead of overwriting it.

## 6. Security and access

### 41. How is the session protected, and what happens if the cookie leaks?

**Detail:** [Guide 13 — Security architecture](../02-architecture/13-security-architecture.md)

The session is in an HttpOnly cookie, Secure is used with HTTPS, SameSite is Strict, and the server checks a revocable session row. A stolen cookie is still a credential until revocation or its eight-hour expiry, so logout and administrator actions revoke the row and close the matching WebSocket.

### 42. Why use cookies instead of Bearer tokens?

**Detail:** [Guide 13 — Security architecture](../02-architecture/13-security-architecture.md)

An HttpOnly cookie keeps the session token out of JavaScript and is attached by the browser to both API and WebSocket requests. Because cookies are automatic, the design also requires SameSite, Origin checks, and TLS; it does not claim that cookies are intrinsically safe from CSRF or theft.

### 43. What stops a script on the same LAN from faking an accident alert?

**Detail:** [Guide 13 — Security architecture](../02-architecture/13-security-architecture.md)

The internal webhook requires `INTERNAL_API_KEY`, and the backend compares it in constant time before ingesting the alert; the recorded security test rejects a wrong key. If that secret is exposed, it must be treated as compromised and rotated under the deployment procedure.

### 44. Did moving to cookies reintroduce CSRF, and is CORS enough?

**Detail:** [Guide 13 — Security architecture](../02-architecture/13-security-architecture.md)

Cookies are sent automatically, so we do not claim Bearer-style structural immunity. SameSite=Strict limits cross-site sending and the server rejects unsafe requests from an unapproved Origin; CORS controls browser behavior but is not the only state-change check.

### 45. Where is role-based access actually enforced: the frontend or backend?

**Detail:** [Guide 14 — RBAC and roles](../02-architecture/14-rbac-and-roles.md)

The backend enforces it through authenticated dependencies and explicit route checks. React hides destinations and redirects for usability, but a direct API request still receives the backend’s authorization result rather than bypassing the boundary.

### 46. What if an Administrator changes a user’s role while that user is logged in?

**Detail:** [Guide 14 — RBAC and roles](../02-architecture/14-rbac-and-roles.md)

The role-change path revokes that user’s active sessions and closes their live connections. The next request fails, and authorization reloads the current database role, so a stale token claim cannot preserve old Administrator access.

### 47. What can an Operator not do, and can the AI impersonate an Administrator?

**Detail:** [Guide 14 — RBAC and roles](../02-architecture/14-rbac-and-roles.md)

An Operator cannot manage accounts or roles, read or export the audit trail, access AI-performance administration, request retraining, or run backup and restore; those boundaries are rejected with 403. The AI engine uses an internal API key for service routes, not a browser session, so it does not receive Administrator permissions.

### 48. A self-signed certificate is insecure, isn’t it?

**Detail:** [Guide 13 — Security architecture](../02-architecture/13-security-architecture.md)

Self-signed means clients do not trust the certificate automatically; it does not mean the LAN traffic is plaintext. In the controlled demo, clients install the `adas.local` certificate into their trust store and the private key stays on the server, preserving encryption and server identity when the trust setup is followed.

## 7. Data, audit, and recovery

### 49. How do you handle time zones?

**Detail:** [Guide 10 — Data model](../02-architecture/10-data-model.md)

Stored timestamps are normalized to UTC, and an aware value is converted before storage and returned as an aware UTC value. A naive datetime raises an error instead of being silently guessed as local time.

### 50. What stops two incidents opening on the same camera?

**Detail:** [Guide 10 — Data model](../02-architecture/10-data-model.md)

The database has a unique partial index on `camera_id` while the incident is Unverified or Ongoing. That constraint protects the invariant even when two requests arrive at nearly the same time and race through application code.

### 51. Can an Administrator delete an audit entry?

**Detail:** [Guide 15 — Audit trail](../02-architecture/15-audit-trail.md)

No. There is no application edit or delete endpoint, and database triggers abort UPDATE and DELETE statements against the audit table. The tracker also records rejected API mutation attempts, so the viewer’s hidden controls are not the only protection.

### 52. What happens if the audit write fails?

**Detail:** [Guide 15 — Audit trail](../02-architecture/15-audit-trail.md)

For a successful state change, the action and its audit row share one transaction, so a failed audit insert rolls back the state change. A denied or failed attempt is written after that rollback in a short separate transaction; if that write also fails, the system logs a critical error and keeps the original response.

### 53. What exactly is recorded when an operator dismisses an alert or login fails?

**Detail:** [Guide 15 — Audit trail](../02-architecture/15-audit-trail.md)

The dismissal row records the actor, action, incident target, camera context, source IP when available, request ID, and UTC time, while the incident keeps its lifecycle state. Wrong-password, unknown-user, and deactivated-account attempts are recorded as denied login failures without storing the submitted password or other credential material.

### 54. Can you back up while the system is actively detecting?

**Detail:** [Guide 16 — Backup and restore](../02-architecture/16-backup-and-restore.md)

Yes. SQLite’s online backup API keeps the live database available to readers and writers; the recorded protected backup ran during active detection, and the detection still reached the dashboard in that run. The result is a measured controlled test, not a claim that every storage device behaves identically.

### 55. Why not just copy the database file?

**Detail:** [Guide 16 — Backup and restore](../02-architecture/16-backup-and-restore.md)

A raw copy can separate the SQLite main file from active WAL state and produce an incoherent snapshot. The online backup API creates a coherent page-level snapshot while the service continues writing; a file copy is reserved for a verified restore point after services have stopped.

### 56. What stops a bad restore, path traversal, or failed rollback from being reported as success?

**Detail:** [Guide 16 — Backup and restore](../02-architecture/16-backup-and-restore.md)

Restore requires an Administrator, the current password, the exact confirmation phrase, a validated backup identifier, a valid manifest, and an idle coordinator; the identifier is checked as UUID hex before any path helper runs. Integrity and foreign-key checks occur before replacement, and if rollback fails the coordinator records manual intervention instead of claiming success.

## 8. Operations and the operator experience

### 57. What exactly reaches the operator’s screen after a detection?

**Detail:** [Guide 24 — AI pipeline](../04-ai/24-ai-pipeline.md)

After the webhook commits, the backend broadcasts a typed `NEW_DETECTION` event with the camera, time, confidence, status, and an authorized snapshot URL. The frontend adds it to the alert store and shows the annotated image and decision controls; the AI does not close the incident on its own.

### 58. What if the operator never responds?

**Detail:** [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

The incident remains Unverified and the camera remains paused until a permitted action changes the state. The audible alarm can re-sound after the configured unverified interval, with 30 seconds used as the paper’s example, so the alert is not silently discarded.

### 59. Can an operator undo a mistaken confirmation?

**Detail:** [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

Yes, while the incident is still Ongoing, the operator can dismiss it as a human correction, which is recorded and resumes an enabled camera immediately. Cleared and Dismissed records are terminal in the ordinary workflow and are not casually reopened.

### 60. Why is there a cooldown after a dismissal?

**Detail:** [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

A false positive can be caused by environmental noise that remains in the next frames. The one-minute pause prevents an immediate repeat alert from the same camera and reduces notification fatigue; an Ongoing correction follows a different path and resumes immediately.

### 61. If one operator snoozes, does everyone go quiet, and can it be indefinite?

**Detail:** [Guide 20 — Alarm snooze](../03-behaviour/20-alarm-snooze.md)

The affected Unverified incident shares one snooze deadline across connected dashboards, but it remains visible and a later incident is not silently muted. Each snooze is bounded to 15–60 seconds and expiry restores the alarm when the incident is still Unverified; operators may repeat it, so the guarantee is repeated prompts rather than a lifetime count limit.

### 62. What if two operators click at once?

**Detail:** [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md)

Both requests require the same expected current status in the database. One update wins; the other receives HTTP 409 with the winning action, operator, time, and current status, so the second click cannot overwrite the first decision.

### 63. What if the WebSocket drops during an alert?

**Detail:** [Guide 21 — Realtime WebSocket](../03-behaviour/21-realtime-websocket.md)

The incident is committed in the database before it is broadcast, so losing the socket does not remove the alert. The browser reconnects with backoff, reads current Unverified and Ongoing incidents through REST, then applies buffered live events with version checks so an older recovery snapshot cannot undo a newer change.

### 64. How does an operator know the system is unhealthy, and how are records handed over?

**Detail:** [Guide 23 — System health telemetry](../03-behaviour/23-system-health-telemetry.md) and [Guide 22 — Reports and exports](../03-behaviour/22-reports-and-exports.md)

The System Health page shows resource and AI-processing cards, stale or offline states, camera unresponsiveness, warnings, and historical trends; readiness probes separately serve host automation. For handover, staff generate filtered incident reports for the relevant shift and pass the downloadable file to PDRRMO; ADAS does not transfer it or dispatch automatically.

## 9. Testing and evidence

### 65. A 100% pass rate sounds unbelievable. Why should we believe it?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md)

The 100% figures apply to the 194 tracked technical cases and, separately, the 33 planned participant-stage executions, each with an expected result, actual result, and evidence reference. It is not 100% model recall: the event corpus is 8/16 with 0/6 hard cases, and qualified rows remain qualified.

### 66. Four participants — is that enough?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md)

It is enough for the defined small role-based UAT sample: three Operators across shifts and one Administrator completed the specified journeys. It is not enough for a population-level statistical claim, so we report the SUS mean and the four-person denominator together.

### 67. Which criteria did you not fully prove?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md)

We did not prove 24-hour endurance, fifteen-camera capacity, independent post-selection accuracy, or annual availability. Those limits are carried into the conclusions and recommend a controlled pilot with broader capacity, endurance, recovery, security, and operational evidence before production expansion.

### 68. Why is 34.7 minutes evidence for a 24-hour system?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md)

It is not evidence of 24-hour operation. It is a real short-window performance and thermal observation paired with an accelerated memory probe; a full-duration endurance run remains a deployment-evidence task.

### 69. What does “Accepted” authorize?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md) and [Guide 06 — Chapter 5 conclusions](../01-paper/06-chapter5-conclusions.md)

It records the authorized representative’s decision for the defined UAT and prototype scope. It does not authorize citywide deployment or prove untested operating conditions; the paper still recommends a limited pilot and further capacity, endurance, security, recovery, and alert-delivery checks.

### 70. NFR-10 is missing from the traceability sheet. How do you know it works?

**Detail:** [Guide 08 — Requirements FR/NFR](../01-paper/08-requirements-fr-nfr.md)

That is a real documentation gap in the traceability sheet. TC-SYS-009 separately names NFR-10 and passes: the alert dialog exposes Confirm and Dismiss as one-action choices without intermediate navigation, so we should show that test rather than pretend the row exists in the sheet.

### 71. Show me a requirement you only partly met.

**Detail:** [Guide 08 — Requirements FR/NFR](../01-paper/08-requirements-fr-nfr.md)

NFR-16 is marked Pass, but its restart note records backend readiness at 5.11 seconds and a fresh AI heartbeat at 12.672 seconds. We should report those separate measurements and say the tracker verified restart and camera recovery while the full-stack timing is qualified against the 10-second wording.

### 72. Did you really measure the 25-second collision-to-decision time?

**Detail:** [Guide 05 — Chapter 4 results](../01-paper/05-chapter4-results.md) and [Guide 27 — AI performance, FPS and latency](../04-ai/27-ai-performance-fps-latency.md)

We recorded raw browser alert-to-decision observations during UAT, then added the documented approximately 3-second accumulation and 2-second propagation allowances. That gives an estimated mean of 18.333 seconds and a worst case of 21 seconds; it is an estimate of the stated endpoint, not a direct collision-to-dispatch stopwatch.

## 10. Deployment and future work

### 73. “Is this actually deployed, or just a demo?”

**Detail:** [Guide 17 — Networking and deployment](../02-architecture/17-networking-and-deployment.md)

It is a functioning proof of concept evaluated on researcher-controlled hardware in a private LAN, with simulated or authorized test feeds. It is not installed in the Lipa CDRRMO command center or validated across the 418-camera production network, so “demo” would be incomplete but “deployed citywide” would be inaccurate.

### 74. Why simulate the cameras instead of using real CDRRMO feeds?

**Detail:** [Guide 17 — Networking and deployment](../02-architecture/17-networking-and-deployment.md)

The team needed a real RTSP network path without disrupting active command-center monitoring or dispatch. MediaMTX replayed prerecorded clips, so the server still had to ingest and decode network streams in a repeatable private-LAN test.

### 75. What changes when you move to real CCTV?

**Detail:** [Guide 17 — Networking and deployment](../02-architecture/17-networking-and-deployment.md)

The approved Dahua DSS Pro feed, credentials, address, and network route replace the simulator, and CDRRMO must authorize and validate those conditions. The team must then measure stream compatibility, stability, security, capacity, and alert delivery on the intended hardware before adding cameras.

### 76. Why put it on-premises instead of in the cloud?

**Detail:** [Guide 17 — Networking and deployment](../02-architecture/17-networking-and-deployment.md)

The target architecture keeps the AI engine, database, API, and web application on an edge server inside the command center. That keeps video and alert traffic local and supports operation without the external ISP when the internal camera and LAN paths are healthy.

### 77. What must be approved before this can go live?

**Detail:** [Guide 17 — Networking and deployment](../02-architecture/17-networking-and-deployment.md)

CDRRMO must authorize the edge server’s connection to the CCTV network, provide approved VMS credentials and feed details, and validate routing, stream, security, and capacity conditions. Pilot activation, scaling, handover, training, retraining, and hardware maintenance remain implementation work after the capstone evaluation.

### 78. “Who is accountable when it misses an accident?”

**Detail:** [Guide 07 — Definition of terms](../01-paper/07-definition-of-terms.md), [Guide 19 — HITL state machine](../03-behaviour/19-hitl-state-machine.md), and [Guide 06 — Chapter 5 conclusions](../01-paper/06-chapter5-conclusions.md)

We would not treat an unverified model output as the dispatch authority: ADAS is designed for an authorized operator to review, confirm, or dismiss the candidate under CDRRMO procedure. The team is accountable for stating the measured limits, preserving the audit trail, and not presenting 0/6 hard-case recall as production reliability; pilot operations must define the agency’s own responsibility and escalation rules.

### 79. “What did you personally build?”

**Detail:** [Guide 04 — Chapter 3 methodology](../01-paper/04-chapter3-methodology.md)

I would name my own tracked contribution, the files or tests that evidence it, and one design decision I can explain under follow-up. I would connect that work to the shared AI-to-backend-to-dashboard path without claiming another member’s contribution; the panel should hear an accountable individual answer, not a memorized team summary.

### 80. “What would you do differently?”

**Detail:** [Guide 06 — Chapter 5 conclusions](../01-paper/06-chapter5-conclusions.md), [Guide 25 — AI training and dataset](../04-ai/25-ai-training-and-dataset.md), and [Guide 26 — AI accuracy and evaluation](../04-ai/26-ai-accuracy-and-evaluation.md)

I would collect more locally representative accident footage, separate training and evaluation by incident, and investigate the hard misses and night or proximity false positives. Then I would run a limited pilot on the intended hardware and network, and measure capacity, endurance, recovery, security, and alert delivery before expanding the camera count or considering automated dispatch.
