# 27 — AI performance, frame rate, and capacity

> **One-liner:** ADAS has a 15 FPS processing target, a 5 FPS warning floor, a ≤100 ms per-frame inference target, a ≤2 second alert-rendering budget, and a ≤25 second collision-visible-to-operator-decision target; the recorded evidence is qualified to the declared artifact, stream profile, hardware, and test duration.
> **Panel risk:** high — capacity evidence is easy to overstate as a production camera count, and the 25-second figure combines a reconstructed detector and network allowance with raw human decision timings.

## 1. What it is

Performance here means how quickly the running pipeline turns camera frames into usable operator evidence.

It has four related but separate questions.

- **Cadence:** how many successfully analysed frames each connected stream receives.
- **Inference latency:** how long the detector takes to analyse a frame within a batch.
- **Alert delivery:** how quickly the dashboard receives and renders the alert, snapshot, and alarm after detection.
- **Operational timing:** how long it takes from the collision becoming visible to an operator recording a Confirm or Dismiss decision.

The paper defines the accepted processing band as **5–15 FPS per connected stream**.

The target end of that band is **15 FPS**.

The warning floor is **5 FPS**.

Fifteen FPS means the scheduler is meeting its design cadence for a stream.

Between 5 and 15 FPS means the stream is still inside the accepted operating band, although it may be below the preferred target.

Below 5 FPS means the system should surface a performance warning and the result is outside the accepted floor.

The band is therefore an operating decision, not a claim that every frame must arrive at one perfectly fixed rate.

It gives the panel a nominal target and a visible degradation boundary.

The paper’s NFR-02 target is **≤100 ms per frame** for finishing frame analysis and marking a detected collision.

That is a detector timing target.

It is not the complete time from a physical collision to an operator decision.

The paper’s NFR-04 target is **≤2 seconds** for the alert, captured image, and audible alarm to be presented on the dashboard after AI detection.

The paper’s NFR-09 target is **≤25 seconds** from the accident first becoming visible in the monitored feed to the operator recording a Confirm or Dismiss decision.

The 25-second figure includes human review.

The evidence record adds an approximately **3-second detector-accumulation allowance** and an approximately **2-second alert-propagation allowance** to the raw UAT alert-to-decision observation.

The recorded estimate is **18.333 seconds mean** and **21 seconds worst case**.

Those values are inside the 25-second target, with the raw observations shown separately below.

Capacity is deliberately stated as an evidence envelope, not as a number that can be inferred from the model alone.

The current test plan sets an immediate operating target of up to **10 concurrent streams**.

The paper’s Table 23 records a dynamic TensorRT export profile at **batch 15**, with an intended operating point of **10 concurrent streams at 15 FPS**.

The test plan explicitly defers a fifteen-camera qualification.

The current tracker records clean multi-stream evidence at eight streams and a nine-stream step-load run.

It does not establish capacity for the full CDRRMO network of **418 cameras**.

The defensible answer is therefore: the prototype evidence supports the tested stream profiles on the named demonstration hardware, not a citywide camera count.

## 2. Where it lives

### In the paper

- **Chapter 1, Objectives of the Study, Objective 1:** a real-time collision pipeline operating across multiple camera streams.
- **Chapter 1, Objective 2:** a real-time alert dashboard delivering immediate visual and audible notifications.
- **Chapter 1, Objective 3:** the 25-second end-to-end collision-to-operator-decision objective. [Paper, Chapter 1, pp. 13–14]
- **Chapter 1, Scope and Delimitations:** a proof-of-concept evaluated on researcher-controlled hardware and simulated or authorized feeds, with no production-scale or automated-dispatch claim.
- **Chapter 2, “Deep Learning Architectures for Real-Time Traffic Accident Detection”:** why a single-stage YOLO design is appropriate when inference speed matters.
- **Chapter 2, “Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision”:** the accuracy, latency, hardware, memory, and thermal trade-offs that motivate edge co-design.
- **Chapter 3, Requirements Analysis, Table 3, Performance Requirements:** NFR-02 ≤100 ms, NFR-03 5–15 FPS, and NFR-04 ≤2 seconds. The FPS target and warning floor appear on the paper’s NFRS pages around p. 74.
- **Chapter 3, Requirements Analysis, Table 4, Scalability Requirements:** NFR-07, which permits more cameras through server-hardware upgrades without changing program code.
- **Chapter 3, Requirements Analysis, Table 5, Usability Requirements:** NFR-09, the collision-visible-to-operator-decision limit of 25 seconds.
- **Chapter 3, Deep Learning Implementation and Training Protocol, Runtime Optimization and TensorRT Export:** the adopted checkpoint, TensorRT export, dynamic shapes, FP16 profile, and 640-pixel inference size.
- **Chapter 3, Testing and Validation, Test Environment, Table 23:** the demonstration host, client, RTSP simulation, network, and AI batch configuration. [Paper, p. 188]
- **Chapter 3, Testing and Validation, Performance & Load Testing:** the performance activity covers per-frame latency, sustained frame rate, alert delivery, dashboard queries, and exports under simulated streams.
- **Chapter 3, Testing and Validation, User Acceptance Testing:** the operator scenario records raw alert-to-decision observations and uses the reconstructed 25-second estimate.

### In the code

- `ai_engine/config.py:124`–`ai_engine/config.py:127` defines the 15 FPS target and 5 FPS warning floor.
- `ai_engine/pipeline.py:84`–`ai_engine/pipeline.py:105` creates the fixed-cadence batched inference pipeline and derives the tick period from the target FPS.
- `ai_engine/pipeline.py:111`–`ai_engine/pipeline.py:127` collects the newest eligible frame for each camera and drops frames that are too old to be useful.
- `ai_engine/pipeline.py:149`–`ai_engine/pipeline.py:180` times one batched detector call and isolates a failing camera by retrying frames individually.
- `ai_engine/pipeline.py:184`–`ai_engine/pipeline.py:202` divides the measured batch time by the number of frames in that batch before reporting per-camera inference latency.
- `ai_engine/pipeline.py:228`–`ai_engine/pipeline.py:243` runs the scheduler and slips the next tick when inference overruns instead of building an unbounded backlog.
- `ai_engine/camera.py:125`–`ai_engine/camera.py:151` records successful inference samples and computes the per-camera cadence used by telemetry.
- `ai_engine/camera.py:247`–`ai_engine/camera.py:279` packages measured FPS, inference latency, connection state, and a below-floor diagnostic for the heartbeat.
- `ai_engine/detector.py:164`–`ai_engine/detector.py:195` owns the YOLO artifact and performs one batched forward pass for the frames supplied by the pipeline.
- `ai_engine/detector.py:268`–`ai_engine/detector.py:326` contains the optional GPU-resident batch path.
- `ai_engine/capacity.py:1`–`ai_engine/capacity.py:12` describes the standalone inference-only capacity diagnostic.
- `ai_engine/capacity.py:44`–`ai_engine/capacity.py:72` times repeated batches and converts a measured latency grid into a rough estimate.
- `ai_engine/capacity.py:76`–`ai_engine/capacity.py:133` makes clear that the diagnostic starts no RTSP streams and never changes production scheduling.
- `ai_engine/supervisor.py:216`–`ai_engine/supervisor.py:239` sends the observed camera metrics to the backend and applies the authoritative camera configuration returned by heartbeat.
- `ai_engine/backend_client.py:73`–`ai_engine/backend_client.py:93` posts a fired event to the backend webhook and classifies acknowledgement, retry, and terminal outcomes.
- `backend/app/api/routes/internal.py:93`–`backend/app/api/routes/internal.py:134` commits an incoming AI event before broadcasting the new detection and camera pause.
- `backend/app/services/realtime.py:132`–`backend/app/services/realtime.py:181` puts each event on per-connection queues so one slow socket does not hold up every other operator.
- `backend/app/main.py:443`–`backend/app/main.py:527` authenticates and manages the `/ws/alerts` connection.
- `frontend/src/components/RealtimeAlertsBridge.tsx:101`–`frontend/src/components/RealtimeAlertsBridge.tsx:170` turns a `NEW_DETECTION` or status update into dashboard alert state.
- `frontend/src/store/useAlertStore.ts:117`–`frontend/src/store/useAlertStore.ts:234` starts or stops the audible alarm as the active Unverified queue changes.
- `frontend/src/components/GlobalAlerts.tsx:219`–`frontend/src/components/GlobalAlerts.tsx:309` renders the alert dialog and its captured snapshot for operator review.

## 3. How it works

### A. The runtime cadence

1. Each enabled camera has a reader thread receiving its RTSP stream.
2. The reader publishes only the newest decoded frame, so old frames do not form an unbounded queue.
3. The inference pipeline wakes at the configured 15 FPS target cadence.
4. On each tick, it collects the newest frame available from every eligible camera.
5. Paused cameras and isolated failing cameras are excluded from that batch.
6. A stale frame is skipped rather than treated as current.
7. The detector receives the collected frames as one batch.
8. The returned detections are mapped back to cameras in input order.
9. Each successful camera inference increments its cadence measurement.
10. If a collision event is formed, the camera is paused before the snapshot and network handoff.

The loop uses a fixed target cadence rather than waiting for each camera sequentially.

If a tick finishes early, the scheduler waits for the next target tick.

If a tick overruns, it slips the next tick forward.

That slip policy prevents work from accumulating until the system is processing stale frames.

The result is a best-effort current view of each stream, with telemetry making degradation visible.

### B. How the latency number is defined

The pipeline starts a high-resolution timer immediately before the detector call.

It stops the timer when the batched detector call returns.

The measured batch time is divided by the number of frames in that batch before it is reported as each camera’s inference latency.

This is the fair comparison to the paper’s per-frame ≤100 ms target.

Reporting the whole batch time against every camera would charge every stream for the work shared by the batch.

The reported number is still only detector analysis time.

It does not include RTSP decode, temporal accumulation, JPEG encoding, outbox persistence, HTTP delivery, WebSocket transport, browser rendering, or human decision time.

The camera heartbeat carries both `measured_fps` and `inference_latency_ms`.

The backend stores those observations for the authenticated system-health views.

TC-PERF-001 selected `epoch50.engine` and sampled the health endpoint with one to eight concurrent 2K streams on the Lenovo demonstration host over several minutes.

The tracker records that the declared TensorRT artifact was present and selected, and that the ≤100 ms criterion passed on the tested configuration.

The tracker does not give a numeric mean, p95, or maximum for that health-sample run, so those exact summary values are not quoted here.

### C. What batching changes

Batching lets one detector call process the newest frame from several cameras together.

The tracker’s micro-benchmark used the production detector path rather than a stub.

It measured batch sizes 1, 2, 4, 8, and 16 using one synthetic 1920×1080 frame replicated into each batch.

Each batch size had two warm-up calls and eight timed iterations with CUDA synchronization around the measured call.

The recorded mean batch and derived per-frame values were:

| Batch / stream-equivalent count | Mean batch time | Derived per-frame time | Evidence conditions                                                                                                                                                                                                       |
| ------------------------------- | --------------: | ---------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1                               |        54.42 ms |         54.42 ms/frame | `epoch50.engine` production detector path; Lenovo IdeaPad Gaming 3i 15IAH7, RTX 3050 Ti 4 GB; synthetic 1920×1080 frame; two warm-ups plus eight timed iterations; duration beyond those iterations [UNSOURCED — verify]. |
| 2                               |        58.89 ms |         29.45 ms/frame | Same artifact, hardware, synthetic frame, and two-plus-eight iteration protocol; duration [UNSOURCED — verify].                                                                                                           |
| 4                               |        99.95 ms |         24.99 ms/frame | Same artifact, hardware, synthetic frame, and two-plus-eight iteration protocol; duration [UNSOURCED — verify].                                                                                                           |
| 8                               |       102.20 ms |         12.78 ms/frame | Same artifact, hardware, synthetic frame, and two-plus-eight iteration protocol; duration [UNSOURCED — verify].                                                                                                           |
| 16                              |       173.52 ms |         10.84 ms/frame | Same artifact, hardware, synthetic frame, and two-plus-eight iteration protocol; duration [UNSOURCED — verify].                                                                                                           |

The trend improves as batch size increases over the tested grid.

The run does not identify a plateau inside batch sizes 1–16.

The batch profile is supporting evidence for shared inference cost.

It is not evidence that 16 live cameras can be scheduled at the target cadence.

The benchmark does not include RTSP decode, network contention, frame freshness, camera reconnects, persistence, thermal duration, or browser traffic.

### D. The live stream evidence

The clean sustained frame-rate qualification was TC-PERF-002.

It used `epoch50.engine` on the Lenovo demonstration host with an eight-channel MediaMTX profile.

The run lasted **900.031 seconds** and collected **61** authenticated health samples every **15 seconds**.

All samples reported eight cameras.

The minimum average FPS was **5.15**.

The mean average FPS was **6.778**.

There were zero samples and zero seconds below the 5 FPS warning floor.

The final inventory showed eight connected and active cameras.

This is a clean eight-stream cadence qualification for the stated duration and artifact.

It is below the preferred 15 FPS target on average, but it remained above the accepted 5 FPS floor.

The tracker separately records TC-PERF-008 at **eight concurrent 2K streams** on the same `epoch50.engine` and Lenovo host.

That run reported **20–31 ms** AI analysis delay and **11.4–14.8 FPS** per camera.

The tracker does not record an elapsed duration for that steady-state step [UNSOURCED — verify].

The nine-stream step-load TC-PERF-010 used a real ninth MediaMTX channel on the same artifact and host.

It held about **12–13.6 FPS** with **20–24 ms** latency.

The tracker does not record an elapsed duration for that nine-stream step [UNSOURCED — verify].

The eight-stream record is the highest count explicitly described as actually exercised in TC-PERF-008.

The nine-stream run is a degradation-profile step, not a fifteen-camera qualification.

### E. Why fifteen cameras are deferred

A batch timing grid and a live camera qualification answer different questions.

The batch grid asks how long the detector call takes for synthetic frames.

A live qualification must also carry RTSP decoding, frame arrival, scheduler behavior, memory pressure, thermal behavior, camera failures, event persistence, alert delivery, and the declared duration.

The test plan requires every FPS result to state its stream count, artifact, hardware, duration, and whether it is a clean qualification or a qualified deviation.

The test plan’s immediate target is up to ten concurrent streams.

The tracker records eight streams for the clean maximum-count case and nine for the one-step degradation profile.

The tracker does not contain a fifteen-camera result.

The deployed TensorRT artifact is tied to the GPU host that built it.

Moving it to another GPU requires a new artifact and a new measurement.

The correct reason for deferral is evidence discipline: fifteen cameras require a real multi-stream run on the intended artifact and hardware for the required duration.

Until that run exists, the team must not turn the batch profile or the 418-camera network size into a capacity promise.

### F. Alert delivery path

When the accumulator raises an event, the AI engine annotates a snapshot and writes a durable outbox record.

The outbox worker posts the event to the authenticated backend webhook.

The backend commits the incident and the camera pause before it broadcasts `NEW_DETECTION`.

The WebSocket manager places the event in each eligible connection’s bounded queue.

The browser bridge converts that event into an active Unverified alert.

The alert store starts the audible alarm when the active Unverified count changes from zero to nonzero.

The alert dialog renders the snapshot and the Confirm or Dismiss controls.

This ordering keeps the dashboard event durable before it is announced and lets each operator receive the same event without one slow socket blocking every other socket.

The tracker’s TC-PERF-003 controlled browser result used **30 dev-injected detections**.

The same isolated instance produced the real Accident Detected modal and snapshot.

Mean render time was **668.2 ms**.

The 95th percentile was **887 ms**.

The maximum was **1,395 ms**.

All 30 were below the paper’s 2-second alert budget.

The browser run was a controlled simulation; the audio portion used component-level instrumentation.

The wall duration of the 30-event run is [UNSOURCED — verify].

TC-PERF-004 supplies a separate live WebSocket broadcast measurement.

Two independent dashboard clients received the same `NEW_DETECTION` event from a labelled 2K collision clip.

After Operator A’s confirm committed, Operator B’s untouched socket received `ALERT_STATUS_UPDATE` **24 ms** later.

That was one live trial with two connected clients; its total trial duration is [UNSOURCED — verify].

The 24 ms value is post-commit broadcast delay, not the full collision-visible-to-operator-decision time.

The two-client result also does not establish the documented command-center workstation count.

### G. Collision-visible to operator decision

The operator timing starts when the alert appears in the dashboard during UAT.

It stops when the participant records Confirm Accident for a genuine alert, or the corresponding Dismiss decision for a false alert.

The test plan then adds the detector-accumulation and alert-propagation allowances to reconstruct the paper’s collision-visible start point.

The component budget is:

| Component                         | Allowance or observation | Conditions and source                                                                                                         |
| --------------------------------- | -----------------------: | ----------------------------------------------------------------------------------------------------------------------------- |
| Detector accumulation             |  Approximately 3 seconds | Allowance added only for the reconstructed estimate; UAT timing method, Test Plan Evaluation Methods and OP-J05.              |
| Alert propagation                 |  Approximately 2 seconds | Allowance tied to the NFR-04 delivery budget; added only for the reconstructed estimate, not measured as human decision time. |
| Operator alert-to-decision, OP-01 |           16 seconds raw | One participant-stage UAT observation on the isolated LAN staging system; tracker, Execution Log OP-01 / OP-J05.              |
| Operator alert-to-decision, OP-02 |            9 seconds raw | One participant-stage UAT observation on the isolated LAN staging system; tracker, Execution Log OP-02 / OP-J05.              |
| Operator alert-to-decision, OP-03 |           15 seconds raw | One participant-stage UAT observation on the isolated LAN staging system; tracker, Execution Log OP-03 / OP-J05.              |
| Reconstructed mean                |           18.333 seconds | Tracker, Usability Results row 15; raw mean plus approximately 3 seconds plus approximately 2 seconds.                        |
| Reconstructed worst case          |               21 seconds | Tracker, Usability Results row 16; worst raw observation plus approximately 3 seconds plus approximately 2 seconds.           |
| Requirement                       |              ≤25 seconds | Paper, Table 5 NFR-09 and Chapter 1 Objective 3.                                                                              |

The three raw observations have a derived raw mean of approximately 13.333 seconds.

Adding the two declared allowances gives the tracker’s 18.333-second estimated mean.

The worst raw observation is 16 seconds, so the reconstructed worst case is 21 seconds.

Both reconstructed values remain below the 25-second requirement.

This is a timing estimate for collision-visible-to-decision.

It is not a measurement of automatic emergency dispatch.

The paper and test plan explicitly stop the ADAS timing boundary at operator decision and manual dispatch or endorsement initiation.

## 4. Why it was built this way

### Target 15 FPS with a 5 FPS floor

The system needs frequent enough samples to catch a collision while leaving room for multi-stream processing on an edge host.

The paper therefore defines an accepted band rather than a single brittle pass/fail number.

Fifteen FPS is the design target for responsive monitoring.

Five FPS is the warning floor at which the operator should know that processing has degraded.

The band lets the system report gradual degradation instead of hiding it behind a binary connected/disconnected state.

The tracker’s eight-stream run demonstrates why this matters: it stayed above the floor while averaging below the preferred target.

### Batch instead of one forward pass per camera

The detector can share model work across frames from multiple cameras.

The batch profile shows lower derived per-frame cost as the tested batch grows.

The runtime still measures each live batch because the active camera set can change.

This design gives the scheduler a common inference point while preserving a per-camera cadence and latency report.

### Slip instead of backlog

If the detector takes longer than the target tick, replaying every missed tick would make the system increasingly stale.

The scheduler therefore drops stale frames and slips the next tick.

For collision alerting, a current frame is more useful than a queue of old frames.

This choice also makes the warning floor observable in telemetry.

### Hardware-specific evidence

The model artifact, GPU, driver, TensorRT build, input resolution, stream count, and duration all affect capacity.

The test plan therefore requires those conditions beside each performance figure.

The paper’s test environment uses the Lenovo IdeaPad Gaming 3i 15IAH7 with an Intel Core i5-12500H, an NVIDIA RTX 3050 Ti with 4 GB VRAM, 16 GB RAM, and Windows 11.

The same environment is the basis for the tracker’s performance evidence.

This is why the team must answer “on this demonstration host” rather than “the model can handle exactly N cameras.”

### Human review remains in the budget

The detector is an early-warning mechanism, not an autonomous dispatch decision.

The paper’s operating workflow requires the operator to inspect the snapshot and available CCTV or DSS evidence.

The 25-second budget therefore includes human decision time and names the detector and propagation allowances explicitly.

That makes the performance claim match the actual responsibility boundary.

## 5. What changed since the 28 April defense

The current code has a fixed-cadence, batched multi-camera pipeline in `ai_engine/pipeline.py`, rather than a per-camera sequential inference explanation.

The current engine reports observed inference FPS and latency through heartbeat telemetry in `ai_engine/camera.py` and `ai_engine/supervisor.py`.

The current detector supports the declared batched path and an optional GPU-resident path in `ai_engine/detector.py`.

The repository now includes the standalone `ai_engine/capacity.py` diagnostic for a declared artifact and machine.

The RTSP reader is explicitly pinned to the FFmpeg backend with bounded open and read timeouts in `ai_engine/camera.py`.

The event handoff now uses a durable outbox before backend delivery in `ai_engine/accident.py` and `ai_engine/outbox.py`.

The backend now commits an incoming alert before broadcasting `NEW_DETECTION` in `backend/app/api/routes/internal.py`.

Realtime delivery now uses authenticated WebSockets with per-connection queues in `backend/app/main.py` and `backend/app/services/realtime.py`.

The test record now contains qualified performance evidence for eight-stream cadence, the nine-stream degradation step, detector batch timing, controlled alert rendering, and the UAT decision estimate.

These changes make the current panel answer evidence-based, but they do not turn the proof-of-concept into a production-scale capacity result.

## 6. Limits and honest caveats

- The performance evidence is from researcher-controlled demonstration hardware, not the live CDRRMO production server.
- MediaMTX and FFmpeg provide simulated or authorized RTSP feeds; the record does not prove behavior on every live VMS encoder, network path, or camera.
- The paper’s Table 23 describes a ten-stream target operating point, while the current tracker’s clean maximum-count case explicitly records eight streams and a separate nine-stream step; fifteen-camera qualification remains deferred.
- No measured result authorizes extrapolation to the CDRRMO’s 418-camera network.
- The `capacity.py` result is inference-only supporting evidence; it does not start RTSP streams, account for decode or network load, write a production configuration, or change the scheduler.
- The batch profile uses replicated synthetic input frames and timed detector calls; it is not a live multi-camera qualification.
- The tracker’s TC-PERF-001 result records that the declared TensorRT artifact was selected and that the criterion passed, but it does not include the numeric mean, 95th percentile, and maximum latency values requested by the test case. Those exact summary values are [UNSOURCED — verify].
- The eight-stream cadence run lasted 900.031 seconds, which is a 15-minute qualification, not a multi-hour or annual availability claim.
- The resource/endurance evidence includes a 34.7-minute combined window with an explicit duration deviation from the one-hour requirement; it is supporting evidence about stability, not a full-duration proof.
- The 30-event alert-render result used controlled browser simulation, and its audio measurement used component-level instrumentation.
- The 24 ms WebSocket figure is one live two-client broadcast trial and measures post-commit delivery to the second socket.
- The 25-second figure is reconstructed from raw alert-to-decision UAT timings by adding declared allowances; it does not measure automated dispatch, vehicle routing, or direct DSS timing.
- No separate throughput qualification is recorded for rain, night, or every camera angle.
- Night and rain can change detection quality and temporal evidence, but this guide has no source-backed FPS or latency result for those conditions. A specific numeric environmental performance claim is [UNSOURCED — verify].
- A TensorRT engine is tied to the GPU and software stack that built it, so another deployment host needs a fresh artifact and fresh measurements.

## 7. Likely panel questions

### “How many cameras can this really handle?”

The evidence proves the named demonstration host at the tested profiles, not a universal camera count. Eight streams have the clean maximum-count qualification, and a nine-stream step held about 12–13.6 FPS with 20–24 ms latency; ten streams are the target operating point, while fifteen-camera qualification is deferred. We do not extrapolate that result to 418 cameras.

### “Why is fifteen cameras deferred?”

A synthetic batch benchmark is not the same as fifteen live RTSP streams. The live result must include the declared artifact, stream count, hardware, duration, decode, scheduling, memory, thermals, and delivery path; that fifteen-stream record does not exist yet. The next step is a measured run on the intended host and rebuilt TensorRT artifact.

### “What is the bottleneck — the model or the hardware?”

The batch profile shows shared inference becomes cheaper per frame as the tested batch grows, reaching 10.84 ms per frame at batch 16 on the benchmark. The live stream result also includes decode, scheduling, memory, network, and thermal effects, so the evidence does not isolate one universal bottleneck. Capacity is therefore reported as a hardware-and-artifact result, not as a model-only property.

### “What happens if you exceed capacity?”

The scheduler keeps the newest usable frames, drops stale frames, and slips when a tick overruns instead of building a backlog. Telemetry reports lower FPS and raises the below-floor warning when a camera falls below 5 FPS; the nine-stream step showed gradual degradation while remaining above that floor. Behavior beyond the tested profiles still requires a measured run.

### “Why is the frame rate a band rather than a fixed number?”

Fifteen FPS is the target, but real streams and shared hardware vary. Five FPS is the warning floor that tells the operator processing has degraded while still distinguishing it from a disconnected camera. That gives us a clear operating target and an honest observable boundary.

### “Does the ≤100 ms inference target mean an operator sees an alert in ≤100 ms?”

No. The ≤100 ms figure is detector analysis time per frame after the measured batch time is divided across its frames. Alert rendering has a separate ≤2-second budget, and operator decision time is included in the separate ≤25-second collision-visible-to-decision figure.

### “Are the batch numbers your production FPS?”

No. The batch harness is inference-only supporting evidence using replicated synthetic frames and timed detector calls. Production uses the fixed scheduler and live telemetry, so the batch result cannot replace a qualification that includes streams, decode, hardware, and duration.

### “What exactly was measured for alert delivery?”

Thirty controlled browser-injected detections rendered the real modal and snapshot in a mean 668.2 ms, p95 887 ms, and maximum 1,395 ms, all under 2 seconds; audio used component-level instrumentation. A separate live two-client trial measured 24 ms from one client’s commit to the other client’s WebSocket update. Those are delivery measurements, not the full human decision interval.

### “How do you get 18.333 seconds if the target is 25 seconds?”

The three raw alert-to-decision observations were 16, 9, and 15 seconds. The tracker adds approximately 3 seconds for detector accumulation and approximately 2 seconds for propagation, producing an estimated mean of 18.333 seconds and a worst case of 21 seconds. Both are below 25 seconds, and the raw observations remain visible rather than being hidden inside the estimate.

### “What happens at night or in rain?”

This guide has no source-backed night-or-rain throughput figure. Those conditions can affect visual evidence and detection quality, while the FPS and latency measures are hardware and scheduling measures; the panel should use the accuracy guide for the recorded night-condition analysis and treat an unmeasured rain claim as [UNSOURCED — verify].

### “If the GPU is fast enough, why not just enable fifteen cameras?”

Because detector-only throughput is only one part of the system. Fifteen live streams add decoding, frame freshness, scheduler contention, memory and thermal duration, event persistence, and alert traffic, and the TensorRT artifact is host-specific. The qualification must be run and recorded under those conditions before that operating point is accepted.

### “Is the 25-second number dispatch time?”

No. It ends when an authorized operator records Confirm or Dismiss. ADAS supports the manual dispatch or endorsement workflow after that decision; it does not automatically dispatch vehicles or measure direct DSS or field-response time.

## 8. Cram summary

- The paper’s performance targets are ≤100 ms inference per frame, 5–15 FPS per connected stream, ≤2 seconds for the alert plus snapshot and alarm, and ≤25 seconds from collision visibility to operator decision.
- Fifteen FPS is the target end of the accepted band; 5 FPS is the warning floor.
- The runtime batches the newest eligible frame from each camera, reports latency as batch time divided by batch count, drops stale frames, and slips when a tick overruns.
- The measured batch profile on `epoch50.engine` and the Lenovo RTX 3050 Ti host is 54.42, 58.89, 99.95, 102.20, and 173.52 ms for batches 1, 2, 4, 8, and 16, or 54.42, 29.45, 24.99, 12.78, and 10.84 ms per frame.
- The batch profile is supporting evidence only; `capacity.py` does not start streams and never configures production.
- The clean sustained cadence run used eight MediaMTX streams for 900.031 seconds with `epoch50.engine`; minimum FPS was 5.15, mean FPS 6.778, and zero samples fell below 5 FPS.
- The nine-stream step held about 12–13.6 FPS and 20–24 ms latency; fifteen-camera qualification is deferred because no fifteen-stream live record with all required conditions exists.
- Thirty controlled browser detections rendered in mean 668.2 ms, p95 887 ms, and maximum 1,395 ms; the separate live two-client WebSocket broadcast delay was 24 ms.
- The decision estimate is approximately 3 seconds detector accumulation + approximately 2 seconds propagation + raw operator decision, giving 18.333 seconds mean and 21 seconds worst case against the 25-second target.
- Say “qualified on the named demonstration artifact and hardware,” never “proven for 418 cameras.”
