# 24 — AI pipeline end to end

> **One-liner:** ADAS turns a live RTSP frame into a temporally corroborated,
> human-reviewable alert through bounded capture, fixed-cadence batched inference,
> a per-camera leaky accumulator, and a durable webhook outbox.
> **Panel risk:** high — the panel will challenge the low frame confidence floor,
> the alert delay, and every failure point between a camera and the operator screen.

## 1. What it is

The AI engine is the perception and event-formation half of ADAS. It continuously receives the configured camera streams, selects usable
recent frames, runs the trained YOLO detector, and decides whether a camera has accumulated enough evidence of a vehicle-to-vehicle
collision to create one incident event.

The important distinction is between a **frame detection** and an **alert event**. A frame detection is weak evidence: the model sees an
accident-class region with a confidence score. An alert event is a camera-level decision formed only after matching regions persist in time
and their confidence-weighted evidence crosses the accumulator threshold. The engine therefore does not treat one uncertain frame as a
confirmed accident.

The path is deliberately end to end:

1. An RTSP reader opens and decodes the stream over a pinned transport.
2. The reader publishes the newest decoded frame with a decode timestamp and stream segment marker.
3. A fixed-cadence scheduler collects recent frames from eligible cameras and drops stale or missing samples.
4. The detector applies the deployment preprocessing and performs one batched forward pass for the collected cameras.
5. Only the accident class enters event formation; ordinary vehicle detections are a training foil and do not alert.
6. A separate accumulator for each camera links boxes, adds confidence-seconds, decays unsupported evidence, and emits an event only at the
   persistence threshold.
7. The engine selects the event to report, pauses that camera, creates a colour annotated snapshot, and writes a durable event record before
   network delivery.
8. The outbox retries the authenticated backend webhook until it is acknowledged or the entry is quarantined as a terminal defect.
9. The backend commits the incident idempotently and broadcasts a typed `NEW_DETECTION` message; the operator dashboard renders the
   snapshot, telemetry, and audible alert for human verification.

The operator still makes the Confirm or Dismiss decision. The AI event is an early warning and evidence package, not an automatic dispatch
instruction. The paper places this pipeline inside the Human-in-the-Loop workflow and limits the project to vehicle-to-vehicle collision
events from optical CCTV.

## 2. Where it lives

### In the paper

- **Chapter 1, General Objectives, Objectives 1–3:** the real-time collision-detection pipeline, dashboard alert, and the combined mAP and
  collision-visible-to-decision targets.
- **Chapter 1, Table 3, Performance Requirements:** NFR-01 algorithmic accuracy, NFR-02 inference latency, NFR-03 frame-rate maintenance,
  and NFR-04 alert response. The paper requires analysis and collision marking within 100 milliseconds per frame, an accepted 5–15 FPS
  operating band with 15 FPS as the design target, and dashboard alert plus captured image and alarm within 2 seconds of AI detection.
- **Chapter 1, Table 5, Usability Requirements:** NFR-09 defines the collision-visible-to-operator-decision target of 25 seconds. The target
  includes the human decision and supports faster manual dispatch or endorsement; it does not claim automatic dispatch.
- **Chapter 3, “System Architecture and Design,” Figure 2, Client-Server Architecture:** the AI Engine receives RTSP, selects current
  frames, invokes YOLO in batches, and hands event evidence to the backend.
- **Chapter 3, “System Architecture and Design,” AI Engine subsection:** grayscale input, accident-only alerting, per-camera temporal
  accumulation, camera pause, annotated snapshot, and durable outbox handoff.
- **Chapter 3, Figure 3, Swimlane Diagram:** the automated detection and alert flow ends at operator review; the operator owns verification
  and incident handling.
- **Chapter 3, “Deep Learning Implementation and Training Protocol,” “Inference and Temporal Event Formation”:** the authoritative detector
  and accumulator settings are confidence `0.15`, input size `640`, IoU link `0.30`, decay `0.30`, EMA `0.50`, and firing evidence `1.0`
  confidence-seconds. This section explicitly says the accumulator supplies persistence that the low frame floor alone cannot provide.
- **Chapter 3, Table 23, Test Environment Summary:** the simulated VMS rebroadcasts prerecorded material as RTSP streams for live network
  ingestion and inference on researcher-controlled hardware.
- **Chapter 1, Definition of Terms:** “Batched Inference,” “Durable Outbox,” “Temporal Accumulation,” “Inference Latency,” “RTSP,” and
  “MediaMTX” provide the paper’s short definitions. Use the mechanism below when the panel asks how those definitions are implemented.

The test plan is the operational source for the model and inference configuration, reset seams, accepted cadence, alert-delivery criterion,
and the reconstructed timing budget. The tracker is the source for recorded outcomes, including AI-VAL-001–010, TC-PERF-001–004 and
TC-PERF-007–010, and TC-REL-002 and TC-REL-007–012.

### In the code

The implementation is intentionally split by responsibility:

- `ai_engine/config.py:10` pins OpenCV’s FFmpeg RTSP transport to TCP; `ai_engine/config.py:105`–`155` holds the detector, accumulator,
  cadence-floor, stale-age, and long-gap settings.
- `ai_engine/camera.py:12`–`21` defines the bounded capture timeout constants; `ai_engine/camera.py:157`–`229` performs FFmpeg-backed open,
  read, failure handling, and reconnect. `ai_engine/gpu_camera.py:155`–`192` supplies the optional TCP remux path, while
  `ai_engine/gpu_camera.py:515`–`551` watchdogs a stalled demuxer.
- `ai_engine/camera.py:231`–`245` exposes a destructive newest-frame slot. `ai_engine/gpu_camera.py:382`–`411` exposes the same public
  contract for decoded GPU frames, dropping old queued frames when the bounded queue is full.
- `ai_engine/pipeline.py:19`–`79` owns the per-camera accumulator registry and all four reset seams. `ai_engine/pipeline.py:84`–`127`
  collects frames and rejects stale ones; `ai_engine/pipeline.py:131`–`180` performs batched inference and isolation.
- `ai_engine/pipeline.py:184`–`224` updates accumulators, chooses the event, pauses the camera, and calls the event handler.
  `ai_engine/pipeline.py:228`–`243` runs the fixed-cadence loop and slips after an overrun.
- `ai_engine/detector.py:28`–`38` defines grayscale normalization; `ai_engine/detector.py:70`–`99` performs grayscale-inside-letterbox
  preprocessing; `ai_engine/detector.py:188`–`211` runs a batch; and `ai_engine/detector.py:330`–`345` filters class-0 accident boxes.
- `ai_engine/accumulate.py:27`–`35` computes IoU and `ai_engine/accumulate.py:38`–`73` defines region and event state.
  `ai_engine/accumulate.py:77`–`137` is the leaky-integrator update and firing rule; `ai_engine/accumulate.py:139`–`141` clears the
  accumulator.
- `ai_engine/frames.py:49`–`65` materializes a colour BGR frame for evidence; `ai_engine/accident.py:21`–`35` draws the fired box and
  `ai_engine/accident.py:46`–`97` creates the snapshot and outbox payload.
- `ai_engine/events.py:10`–`13` creates the stable event ID and `ai_engine/events.py:28`–`55` creates the snapshot key and five-field
  webhook payload.
- `ai_engine/outbox.py:52`–`74` atomically writes pending records; `ai_engine/outbox.py:77`–`140` loads, acknowledges, quarantines, and
  schedules retries; and `ai_engine/outbox.py:169`–`219` delivers them from one worker. `ai_engine/backend_client.py:17`–`37` and
  `ai_engine/backend_client.py:73`–`95` define the authenticated webhook and response classification.
- `ai_engine/main.py:73`–`85` drains the outbox before starting new inference and wires the pipeline callback.
  `backend/app/api/routes/internal.py:93`–`136` performs idempotent alert ingestion and broadcasts after commit.
- `frontend/src/components/RealtimeAlertsBridge.tsx:101`–`175` applies `NEW_DETECTION` to the alert store.
  `frontend/src/components/GlobalAlerts.tsx:303`–`313` renders the operator-facing snapshot from the authorized snapshot URL.

## 3. How it works

### 3.1 Startup and authoritative camera state

The engine resolves the configured model before starting camera runtimes. It starts a delivery worker, starts the heartbeat supervisor, and
then runs the inference loop. A heartbeat reports observed connection, AI state, measured FPS, latency, and errors; the backend returns the
authoritative active camera list, RTSP URLs, desired AI state, and configuration version.

The engine does not treat a local restart as permission to resume every camera. The supervisor reconciles the backend snapshot. If an
incident pause is still authoritative or an event remains in the outbox, the camera stays paused until the backend state and delivery state
make resumption safe. This matters when the process restarts while the backend is unaware of a locally queued event.

### 3.2 RTSP ingestion and decoding

The default reader creates `cv2.VideoCapture` with the explicit FFmpeg backend and bounded open and read timeout properties. The process
also requests the smallest available capture buffer. A packet or socket stall therefore becomes a bounded failure that can enter the
reconnect loop instead of blocking the engine forever. [Code: `ai_engine/camera.py:157`–`184`]

RTSP transport is pinned to TCP in configuration and passed explicitly to the FFmpeg reader. The reason is operational: packet loss over UDP
can corrupt the H.264 reference chain on a busy loopback or LAN, while an explicit FFmpeg/TCP path makes the transport choice deterministic.
The test plan’s three-device environment also carries RTSP over TCP. [Paper, Chapter 3, Testing and Validation, Test Environment; Code:
`ai_engine/config.py:10`–`11`, `ai_engine/camera.py:165`–`179`]

On a successful decode, the reader captures `time.monotonic()` at decode time and publishes a `FrameRead` containing the frame, timestamp,
and current `segment_id`. Timestamping at decode avoids charging queueing time to the accumulator’s elapsed-time calculation. A failed open
or read releases the capture, records the failure, and re-enters the configured reconnect loop. The recorded NFR-14 policy is an attempt every
10 seconds. Three consecutive failures make the camera Unresponsive in the recorded reliability behavior; a successful connection clears the
failure state. [Paper, Chapter 1, Table 6, NFR-14; Tracker, TC-REL-007–008; Code: `ai_engine/camera.py:24`–`37`,
`ai_engine/camera.py:181`–`229`]

The opt-in GPU reader preserves the same public camera contract. It remuxes the RTSP bitstream through FFmpeg over TCP without re-encoding,
sends it to NVDEC, and uses a watchdog to terminate a connection that stops producing frames. Unsupported hardware, driver, codec, or pixel
format fails loudly before cameras start; it does not silently switch to a different reader with unknown behavior. [Code:
`ai_engine/gpu_camera.py:118`–`140`, `ai_engine/gpu_camera.py:155`–`192`, `ai_engine/gpu_camera.py:519`–`551`]

### 3.3 Newest-frame exchange and stale-frame dropping

The software reader owns one latest-frame slot. Publishing a new decoded frame replaces the previous slot; `read()` returns the current
value once and clears the slot. If the decoder is slower than the inference tick, the camera contributes fewer samples rather than the same
frame being processed repeatedly. If the decoder is faster, old frames are discarded so latency does not grow into a backlog. [Code:
`ai_engine/camera.py:231`–`245`]

The pipeline checks the decode timestamp against the current monotonic clock. A missing frame is skipped, and a frame older than the
configured maximum frame age is skipped. This prevents a connected-but-frozen stream from being treated as current. The exact age cutoff is
a code configuration detail and should be verified before quoting it to the panel: **[UNSOURCED — verify]**. [Code:
`ai_engine/pipeline.py:111`–`127`, `ai_engine/config.py:129`–`131`]

The GPU reader uses the same destructive read contract while accommodating bursty NVDEC delivery. Its bounded queue drops older decoded
surfaces when full; the consumer still sees each returned `FrameRead` at most once. A resume or reconnect clears queued frames from the old
segment before any of them can enter the new accumulator. [Code: `ai_engine/gpu_camera.py:380`–`411`, `ai_engine/gpu_camera.py:389`–`395`]

### 3.4 Fixed-cadence scheduling that slips

The production target is 15 FPS per camera, with the accepted band and 5 FPS warning floor defined in the paper and tracker. The scheduler
derives one period from its target and ticks the eligible cameras together. A tick reads at most one fresh frame per camera and sends the
collected frames to one batched detector call. [Paper, Chapter 1, Table 3, NFR-03; Tracker, Performance & Load Testing, TC-PERF-002; Code:
`ai_engine/pipeline.py:89`–`105`, `ai_engine/config.py:124`–`127`]

The loop advances its next deadline by one period. If inference and downstream work finish early, it sleeps until that deadline. If they
overrun, it resets the next deadline to the current time and starts the next tick from there. It **slips**; it does not execute a queue of
missed ticks. This bounds latency and avoids processing frames that are already obsolete. [Code: `ai_engine/pipeline.py:228`–`243`]

### 3.5 Preprocessing before YOLO

Every model input is normalized to grayscale and then represented as three identical channels. This is a domain-control decision. The paper
explains that accident imagery and ordinary-vehicle imagery have different colour characteristics; feeding colour through unchanged would
give the classifier an easy but invalid class shortcut. Three channels preserve the input contract of the COCO-pretrained YOLO stem. [Paper,
Chapter 3, Preprocessing and Augmentation; Code: `ai_engine/detector.py:28`–`38`]

The input is resized with the detector’s letterbox rules at image size 640. The optimized software path performs grayscale conversion inside
the letterbox and expands to three channels after resize, avoiding duplicate full-resolution resize work. The result is equivalent to
converting and replicating before letterbox; it is an implementation placement, not a different model input. [Paper, Chapter 3, Table 21,
Data Augmentation Configuration; Tracker, AI Model Validation, AI-VAL-009; Code: `ai_engine/detector.py:70`–`99`]

For the optional GPU path, NV12 surfaces remain on the device while the CUDA preprocessor performs the grayscale and letterbox arithmetic
and produces the model tensor. The software and GPU paths share the shape decision and are checked against the same detection contract.
[Code: `ai_engine/detector.py:268`–`327`, `ai_engine/gpu_preprocess.py:236`–`298`]

### 3.6 Batched inference and isolation

The pipeline hands the detector an ordered list of frames. The detector performs one forward pass for the batch and returns one result in
the same order for each input. Keeping camera/read pairs together lets the pipeline associate every result with the correct camera and
timestamp. [Code: `ai_engine/pipeline.py:131`–`147`, `ai_engine/detector.py:188`–`211`]

If the shared batch call fails, the pipeline retries the collected frames one at a time to identify the failing camera. A camera whose
isolated inference still fails is marked with `INFERENCE_FAILED` and excluded from later batches; the healthy cameras continue. This is the
NFR-15 process-isolation behavior recorded by TC-REL-011. [Tracker, Reliability & Endurance, TC-REL-011; Code:
`ai_engine/pipeline.py:149`–`180`]

### 3.7 Class filtering

The trained detector has two classes: class 0 is accident and class 1 is vehicle. The vehicle class teaches the model that ordinary local
traffic is a non-accident alternative, but it is never alertable. After YOLO post-processing, the conversion function retains only class-0
boxes and their confidences. The accumulator therefore cannot combine an ordinary vehicle box into an accident event. [Paper, Chapter 3,
Inference and Temporal Event Formation; Test plan, Model and Inference Configuration; Code: `ai_engine/detector.py:21`–`26`,
`ai_engine/detector.py:330`–`345`]

### 3.8 Temporal accumulation: the precision layer

The frame confidence threshold is deliberately low: `0.15`. It preserves weak frame-level evidence that might be useful when a collision is
partly occluded or the view is difficult. The threshold is not the alert threshold. Precision comes from the temporal accumulator, which
requires linked evidence to persist. [Paper, Chapter 3, Inference and Temporal Event Formation; Tracker, AI Model Validation,
AI-VAL-001–010]

The accumulator is a **leaky integrator**, not a consecutive-frame counter. For each camera it stores regions with a smoothed box,
accumulated score, peak confidence, first and last timestamps, and a fired flag. There is no dedicated object-tracker ID to lose. [Paper,
Chapter 3, Inference and Temporal Event Formation; Code: `ai_engine/accumulate.py:38`–`46`, `ai_engine/accumulate.py:58`–`75`]

On each processed frame, the update proceeds as follows:

1. It computes `dt` from the current decoded timestamp minus the previous processed timestamp. The first update has no prior timestamp and
   therefore contributes no elapsed evidence.
2. Each incoming box searches the camera’s not-yet-matched regions. The best overlap must meet IoU `0.30`; otherwise a new region starts
   with `confidence × dt` evidence, which is zero on the first update of a fresh accumulator.
3. A matched region adds `confidence × dt` to its score. The score’s unit is confidence-seconds, so evidence is based on elapsed time rather
   than a fixed number of frame hits.
4. A matched box updates `peak_conf`. Its coordinates are smoothed with EMA `0.50`, reducing visible box jitter in the eventual snapshot.
5. Every unmatched region loses `decay × dt`, where decay is `0.30` per second. A brief missed detection costs evidence; it does not erase
   the entire history. Sparse, moving noise therefore tends to decay instead of accumulating indefinitely.
6. A region emits exactly when its score reaches `1.0` confidence-seconds and it has not fired. The event carries the smoothed box, score,
   peak confidence, and region age. The fired region remains at that location so another box in the same pause cycle does not create a
   duplicate event.

These settings are the paper’s stated event-formation configuration: IoU `0.30`, decay `0.30`, EMA `0.50`, and threshold `1.0`
confidence-seconds. The test plan states the consequence directly: one frame cannot trigger an alert. On the first frame, `dt` is zero. On
ordinary cadence, a single weak sample is far below the threshold. Across a long unobserved gap, the fourth reset seam prevents the engine
from pretending that the gap contained observed evidence. [Paper, Chapter 3, Inference and Temporal Event Formation; Test plan, Model and
Inference Configuration; Code: `ai_engine/accumulate.py:77`–`137`]

This is why a low `0.15` frame floor is defensible. Raising the floor would discard weak true-collision evidence before the persistence
mechanism can combine it. Leaving the floor low without temporal accumulation would be reckless; the two decisions are one design. The
tracker’s event-level results and false-positive measurements are the evidence used to describe the behavior, not a claim that the
accumulator eliminates all false alarms.

### 3.9 The four accumulator reset seams

Evidence is valid only within one continuous, observed stream segment. The registry creates a fresh accumulator at four seams:

- **Reconnect:** when a capture or demuxer reconnects, the time across the outage is unknowable. The reader increments `segment_id` and the
  registry replaces the old accumulator.
- **Resume:** after an operator clears or dismisses an incident, `resume()` increments `segment_id`. The old fired region cannot make that
  camera permanently deaf to a new incident.
- **Restart or reapply:** a stopped camera is replaced by a new stream object when configuration is reapplied. The registry checks object
  identity as well as `segment_id`, so a newly constructed stream cannot inherit old evidence merely because its counter starts at the same
  value.
- **Long processed-frame gap:** a connected stream can stall without dropping its socket, so `segment_id` does not change. When the gap
  between processed frames is greater than the configured `0.5` seconds, the registry still replaces the accumulator. This is the seam that
  handles a silent freeze.

The fourth seam is necessary because `accumulate.py` uses elapsed time. Without it, a frame arriving after a long stall could receive all of
the unobserved interval as `confidence × dt`; the new region is tested for firing on that same frame. Removing the seam would therefore
reopen a path where a single post-stall frame fires an alert with no corroboration, precisely when the machine is struggling. The test plan
names the four reset conditions; the code implements the gap without a segment bump because the stream did not actually reconnect. [Test
plan, Model and Inference Configuration; Code: `ai_engine/pipeline.py:34`–`72`, `ai_engine/camera.py:86`–`95`,
`ai_engine/camera.py:185`–`192`, `ai_engine/supervisor.py:193`–`201`]

### 3.10 Event selection and the camera pause

The accumulator can return more than one event in a laboratory clip if distinct regions cross the threshold on the same tick. Live semantics
allow one incident per camera pause cycle, so the pipeline selects the event with the highest peak confidence and logs the fact if several
were present. [Code: `ai_engine/pipeline.py:201`–`220`]

The pipeline pauses the camera **before** it performs snapshot or network work. This is the self-blindfold: once the camera has produced an
alert, it stops contributing more evidence for that same incident while an operator verifies it. The backend also sets the camera’s desired
state to Paused when it commits the incident. A later Confirm, Clear, or terminal Dismiss drives the authoritative resume path. [Paper,
Chapter 1, Functional Requirements, FR-11; Paper, Chapter 3, System Architecture and Design; Code: `ai_engine/pipeline.py:222`–`225`,
`backend/app/services/incidents.py:166`–`206`]

During a software pause, the reader uses `grab()` to keep the capture buffer moving without decoding frames for inference. The GPU reader
keeps decoding to preserve the NVDEC reference chain, but the pipeline stops consuming frames. Both are the same AI-level pause contract: no
paused frame reaches the accumulator. [Code: `ai_engine/camera.py:194`–`209`, `ai_engine/gpu_camera.py:243`–`279`]

### 3.11 Colour annotated snapshot

The model sees grayscale input, but the operator needs a legible scene. The event handler converts the triggering frame back to a colour BGR
image when necessary, copies it, and draws the smoothed fired box in red. The software path uses the decoded BGR frame directly; the GPU
path materializes NV12 to BGR only for this rare event path. This keeps the hot inference path efficient while preserving useful evidence on
screen. [Paper, Chapter 1, FR-06; Code: `ai_engine/frames.py:49`–`65`, `ai_engine/accident.py:21`–`35`]

The snapshot is written to its final UTC-keyed path through a temporary `.jpg` file and an atomic replace. The event payload records the
authorized snapshot key, camera, confidence, detected timestamp, and a new `source_event_id`. The detected timestamp is backdated by the
accumulator’s event age so the incident record approximates when the region began accumulating, rather than only recording the later
disk-write instant. [Code: `ai_engine/accident.py:53`–`91`, `ai_engine/events.py:10`–`55`]

### 3.12 Durable outbox and backend webhook

After the snapshot is safely present, the event payload is written to a directory-backed outbox. The record is serialized to a temporary
JSON file and atomically renamed to its pending filename. A process crash can leave an ignored temporary file, but not a half-written
pending record. The queue is local and inspectable; it does not write the backend database directly. [Paper, Chapter 1, Definition of Terms,
Durable Outbox; Code: `ai_engine/outbox.py:52`–`74`]

At startup the engine drains pending entries before the inference loop begins, then a single worker repeatedly scans the queue oldest-first.
The worker posts to `/api/internal/alert` with the internal API key. A successful new insert or an idempotent replay acknowledges and
removes the file. A transient network or server failure records a bounded exponential backoff. A schema-invalid payload is moved to
`quarantine/` so one defective entry cannot block all later events. Authentication failures remain delayed for configuration repair, while
conflict and camera-gone outcomes are terminal for that queued entry. [Paper, Chapter 3, System Architecture and Design, AI Engine subsection;
Code: `ai_engine/main.py:73`–`76`, `ai_engine/outbox.py:88`–`95`, `ai_engine/outbox.py:143`–`194`, `ai_engine/outbox.py:196`–`219`]

The same UUID is reused on every retry. The backend checks `source_event_id` and returns a successful idempotent response without inserting
a second incident when a previous request actually committed but its response was lost. An open-incident race returns a conflict that the
outbox treats as redundant, while an unavailable camera is acknowledged and removed after the engine is told to stop it. [Paper, Chapter 1,
Definition of Terms, Idempotency; Tracker, TC-REL-002; Code: `ai_engine/events.py:10`–`13`, `ai_engine/backend_client.py:19`–`37`,
`ai_engine/outbox.py:169`–`194`]

The backend route verifies the internal key, commits the incident and camera pause, then broadcasts the typed `NEW_DETECTION` and
camera-status events. It maps the stored snapshot key to an authenticated snapshot route; it never exposes an operating-system path to the
browser. The React WebSocket bridge adds the incident to the alert store, and the alert modal renders the snapshot, camera, timestamp,
confidence, and actions. [Code: `backend/app/api/routes/internal.py:30`–`34`, `backend/app/api/routes/internal.py:93`–`136`,
`backend/app/services/events.py:29`–`56`, `frontend/src/components/RealtimeAlertsBridge.tsx:101`–`175`,
`frontend/src/components/GlobalAlerts.tsx:303`–`313`]

## 4. Why it was built this way

**Low frame floor plus temporal evidence.** The detector threshold and alert threshold answer different questions. A low frame floor
protects recall when a collision is partly hidden; linked confidence-seconds protect precision by requiring persistence. The paper records
that some false positives scored higher on individual frames than genuine crashes, so simply raising the frame floor would remove true
crashes first. The accumulator is the safer place to demand confidence over time. [Paper, Chapter 3, Inference and Temporal Event Formation;
Tracker, AI-VAL-005]

**Leaky integration instead of a consecutive counter.** A consecutive counter resets on one missed frame. That is brittle for a network
camera and for an impact whose box changes shape. Decay lets a short miss cost evidence while preserving a persistent region. IoU linking
uses the boxes themselves, so the design does not depend on an object identity surviving the collision, occlusion, or deformation. [Paper,
Chapter 3, Inference and Temporal Event Formation; Code: `ai_engine/accumulate.py:1`–`18`]

**Newest frames instead of a backlog.** An alert system needs current evidence. Reading old frames in order can produce a technically high
processing rate while the operator is seeing an old scene. The single-slot exchange, stale-age check, and slipped scheduler drop work that
cannot reduce present-time latency. The trade-off is that a camera with poor delivery contributes fewer samples and may reset its evidence
after a long gap.

**One batch per tick.** Batched inference amortizes model work across cameras and keeps the camera loop independent from the detector
implementation. The fixed cadence makes the sampling policy explicit; slipping after an overrun prevents catch-up bursts from turning a slow
tick into an even older queue. [Paper, Chapter 1, Definition of Terms, Batched Inference; Code: `ai_engine/pipeline.py:84`–`105`,
`ai_engine/pipeline.py:228`–`243`]

**Grayscale for the model, colour for the operator.** Grayscale normalization removes the dataset colour shortcut and preserves the model’s
three-channel input contract. Keeping the evidence snapshot in colour makes human review faster and avoids asking an operator to interpret
the model tensor. [Paper, Chapter 3, Preprocessing and Augmentation; Code: `ai_engine/detector.py:28`–`38`, `ai_engine/accident.py:21`–`35`]

**Pause before persistence.** The camera pause happens before disk and network work so the same camera cannot keep producing duplicate
detections while snapshot writing or webhook delivery is in progress. The backend repeats the pause as a durable desired state, while the
operator remains responsible for the later resume decision. [Paper, Chapter 3, System Architecture and Design; Code:
`ai_engine/pipeline.py:222`–`225`, `backend/app/services/incidents.py:166`–`206`]

**Outbox plus idempotent webhook.** A direct HTTP POST would make a network outage a data-loss window. The outbox commits a local durable
handoff first; retries reuse one event ID, and the backend unique key makes ambiguous retries safe. Quarantine isolates payload defects
without taking down the camera loop. [Paper, Chapter 1, Definition of Terms, Durable Outbox and Idempotency; Tracker, TC-REL-002 and
TC-REL-010]

**Four resets instead of only stream-drop resets.** Reconnect, resume, and restart discard state when the stream lifecycle changes. The
long-gap seam covers the less obvious case where the socket remains connected but observed frames stop. Without it, elapsed time would be
credited as if it had been witnessed and one post-stall frame could fire an uncorroborated event. [Test plan, Model and Inference
Configuration; Code: `ai_engine/pipeline.py:57`–`72`]

## 5. What changed since the 28 April defense

The current AI path is substantially more explicit and fault-tolerant than the single-frame style the panel last saw. The changes visible in
the repository history since 28 April include:

- a fixed-cadence, multi-camera batched pipeline with newest-frame exchange and overrun slipping;
- the per-camera IoU-linked leaky accumulator, including the long-gap reset seam;
- explicit FFmpeg capture selection, pinned TCP transport, bounded open/read behavior, and reconnect telemetry;
- grayscale-inside-letterbox preprocessing that preserves the model input while reducing duplicate preprocessing work;
- an opt-in GPU-resident RTSP/NVDEC path with parity-oriented preprocessing and a software-reader rollback;
- event selection followed by pause-before-persistence, colour annotated snapshots, and stable event IDs; and
- the directory-backed durable outbox, startup drain, retry classification, and idempotent backend handoff.

These are implementation changes, not a change to the paper’s responsibility split: the engine detects and packages evidence, the backend
records and broadcasts it, and a human operator verifies the incident. The present paper and tracker describe the pipeline above, including
the low frame floor and the persistence layer. [Git history, `git log --since="2026-04-28" -- ai_engine`; Paper, Chapter 3, System
Architecture and Design; Tracker, AI Model Validation and Reliability & Endurance]

## 6. Limits and honest caveats

- **Demonstration scope:** the paper describes a proof-of-concept on researcher-controlled hardware. MediaMTX simulates the VMS behavior
  during testing; the result is not a production qualification across the city’s full camera estate. The engine has been required to ingest
  live RTSP network streams in the isolated LAN, but that is still a controlled evaluation environment. [Paper, Chapter 1, Scope and
  Delimitations; Chapter 3, Table 23]
- **Accuracy qualification:** the tracker records the formal mAP result as a qualified validation-split result, not independent operational
  detection accuracy. In the frozen event run, overall recall was 8/16, standard recall was 8/10, and hard recall was 0/6. The same run
  recorded 3 false positives over 11.0 clean minutes, or 0.27 FP/min. These figures describe the tested corpus and should not be generalized
  to every shift, camera, or lighting condition. [Tracker, AI-VAL-001–007; Guide 26]
- **Night and proximity behavior:** the tracker records that all three residual false positives occurred at night and involved nearby
  vehicles. The panel answer is that the system keeps human verification in the loop and the project identifies this as a dataset and
  evaluation boundary for future work. [Tracker, AI-VAL-006–007]
- **Detection delay is intentional:** temporal accumulation adds approximately 3 seconds to the reconstructed collision-visible timing
  budget. It is the cost of rejecting isolated noise; the dashboard propagation allowance is approximately 2 seconds, and the paper’s
  end-to-end decision target is 25 seconds. [Test plan, Acceptance Criteria; Paper, Chapter 1, Table 5, NFR-09]
- **Alert-delivery evidence is qualified:** thirty development-injected detections rendered in a controlled browser run with mean 668.2 ms,
  p95 887 ms, and maximum 1,395 ms; all were below the 2-second criterion. This is evidence for the tested configuration, not a universal
  network guarantee. [Tracker, TC-PERF-003]
- **A stream gap loses evidence deliberately:** when a long processed-frame gap occurs, the accumulator starts fresh. That can delay an
  alert after recovery, but preserving stale elapsed time would allow an unobserved interval to manufacture an alert.
- **The pause is a workflow trade-off:** the affected camera does not continue accumulating while the operator handles the incident. This
  avoids duplicate alerts and lets the backend’s desired state keep the pause durable; operators must clear or dismiss the incident for
  analysis to resume.
- **The outbox is local durability:** it protects events through a backend outage or process restart as long as the local storage remains
  available. A corrupt payload is quarantined for diagnosis, and storage loss is outside what a directory queue can repair.
- **GPU decoding is conditional:** the optional path requires supported NVIDIA/NVDEC hardware, drivers, codec, and pixel format. It fails
  loudly when those assumptions are not met; the tested software reader remains the fallback path.
- **No automatic dispatch claim:** the webhook and dashboard shorten notification and verification time. They do not dispatch emergency
  vehicles or replace the operator’s Confirm/Dismiss decision.

## 7. Likely panel questions

### “Why such a low confidence threshold — isn’t that reckless?”

The `0.15` value is only the frame-evidence floor. It preserves weak collision clues; the alert requires spatially linked evidence to
accumulate to `1.0` confidence-seconds, with decay for unsupported regions. A single frame therefore cannot raise an alert; precision comes
from persistence and human verification.

### “How do you avoid alerting on every near-miss?”

Only accident-class boxes enter the accumulator. Boxes must overlap an existing region, evidence must persist long enough to cross the
threshold, unmatched regions decay, and one fired region is retained for the pause cycle. A false alarm is still possible, so the dashboard
presents the snapshot to an operator instead of dispatching automatically.

### “What if the stream stutters or freezes?”

The reader has bounded capture timeouts and reconnects after a failed stream. The collector drops missing or stale frames, and a connected
stream that leaves a long gap gets a fresh accumulator. That reset is essential because otherwise one post-stall frame could receive
unobserved elapsed time and fire without corroboration.

### “How long after a collision does the alert appear?”

The tracker’s timing budget assigns approximately 3 seconds to detector accumulation and up to approximately 2 seconds to alert propagation;
the paper’s complete collision-visible-to-operator-decision target is 25 seconds. In the controlled browser run, 30 injected detections
rendered in a mean 668.2 ms and a maximum 1,395 ms after detection, all below the 2-second dashboard criterion.

### “What happens if a camera disconnects in the middle of an accident?”

If it disconnects before the threshold, the old evidence is discarded on reconnect and the camera starts a new segment; the engine will not
invent corroboration across the outage. If the event already fired, the snapshot and payload are already local in the outbox, so backend
delivery can resume later with the same event ID while the camera remains paused.

### “Why not just count three consecutive frames?”

That would erase all progress on one missed or delayed frame and would make the result depend on the sampling cadence. The leaky integrator
links by IoU, adds confidence weighted by elapsed time, and decays unsupported evidence, so it tolerates brief misses without treating a
long unobserved gap as evidence.

### “Why pin RTSP to TCP and add timeouts?”

The engine needs deterministic transport and a bounded failure path. TCP avoids the packet-loss behavior observed with a UDP fallback on the
busy test path, while the explicit FFmpeg backend and bounded open/read properties prevent a dead stream from blocking every later tick.

### “What if one camera makes the batched inference call fail?”

The pipeline retries the batch one frame at a time to identify the offender. It marks only the failing camera with `INFERENCE_FAILED` and
removes it from later batches; the other cameras keep processing. That is the process-isolation behavior verified in TC-REL-011.

### “What if the backend is down after the camera fires?”

The engine does not discard the event after a failed POST. The snapshot and payload are in the durable outbox, which retries with backoff.
The same `source_event_id` makes an ambiguous retry idempotent, so a backend that already committed the incident does not create a duplicate
row.

### “Why pause the camera immediately?”

It is the self-blindfold that prevents repeated alerts for the same visible incident while an operator reviews it. The pause happens before
snapshot and network work, the backend stores the desired pause, and analysis resumes only through the authoritative operator-driven state
transition.

### “What exactly reaches the operator’s screen?”

After the webhook commits, the backend broadcasts a typed `NEW_DETECTION` event with camera, timestamp, confidence, status, and an
authorized snapshot URL. The frontend WebSocket bridge adds it to the alert store, and the modal displays the annotated image and decision
controls. The operator can then Confirm or Dismiss; the AI does not close the incident by itself.

## 8. Cram summary

- **Input:** bounded FFmpeg RTSP capture over pinned TCP; decode timestamps and stream segments travel with each frame. Failed streams
  reconnect on the NFR-14 interval.
- **Freshness:** one newest frame per software camera; stale or missing frames are skipped, and the GPU queue is bounded so latency does not
  become a backlog.
- **Cadence:** fixed 15 FPS target within the accepted 5–15 FPS band; overruns slip forward instead of executing a backlog.
- **Preprocessing:** grayscale, three-channel replication, and 640 letterbox input; the optional GPU path keeps preprocessing on the device.
- **Batch:** eligible camera frames share one forward pass; a failed batch is isolated per camera so healthy feeds continue.
- **Filter:** class 0 accident boxes enter event formation; class 1 vehicle boxes are a training foil and never alert.
- **Accumulator:** per-camera leaky integrator; IoU link `0.30`, decay `0.30`, EMA `0.50`, firing threshold `1.0` confidence-seconds, frame
  floor `0.15`.
- **Safety claim:** a single frame can never raise an alert. The first frame has no elapsed evidence, and the long-gap reset prevents
  unobserved time from being credited.
- **Four resets:** reconnect, resume, restart/reapply, and processed-frame gap greater than `0.5` seconds. Removing the fourth lets one
  post-stall frame fire uncorroborated.
- **Event:** choose the highest-peak event for the live camera, pause before persistence, and draw the smoothed box on a colour snapshot.
- **Durability:** atomically write the snapshot and outbox record, retry the authenticated webhook, and reuse `source_event_id` for
  idempotency.
- **Screen:** backend commits then broadcasts `NEW_DETECTION`; the WebSocket bridge renders the snapshot, telemetry, and alarm for human
  Confirm/Dismiss.
- **Timing:** approximately 3 seconds for accumulation plus approximately 2 seconds of propagation in the reconstructed 25-second
  collision-visible decision budget; the recorded browser-render run stayed below the 2-second dashboard criterion.
- **Honest scope:** this is a controlled, qualified proof-of-concept with human verification. It reduces notification delay; it does not
  automate dispatch.
