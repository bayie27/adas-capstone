# Paper edits required by the detection core port

**Date:** 2026-08-10
**Applies to:** `ai_engine/docs/Final-Paper.pdf`
**Companion:** `ai_engine/docs/2026-08-10-detection-core-port-design.md`

The AI engine is being replaced with the detector actually built and measured in the research repo (see `ai_engine/adas_transfer/SPEC.md`). Several passages in the paper describe the *previous* detection design — a single-frame decision behind a high confidence gate. Against the ported detector those passages are either untestable, wrong, or would fail a criterion the system actually meets.

Edits are grouped by priority. Each gives the location, what it says now, what it should say, and why.

---

## Priority 1 — Integrity

### 1.1 Remove mAP as an acceptance criterion — TC-AI-101, p.95

**Currently:** *"achieving an operational accuracy that meets or exceeds the strictly defined 85% mAP and 0.50 IoU baseline thresholds."*

**Change to:** an event-level criterion measured on held-out deployment footage. Suggested wording:

> The system achieves event-level recall of at least 75% on standard-difficulty collisions in held-out Lipa CCTV footage, with a false-alarm rate at or below 0.5 events per minute of ordinary traffic.

**Why.** `SPEC.md` §4 records that the v3 training run's mAP50 of 0.956 is **leaked**: the incident-level validation split failed and was skipped, so near-duplicate frames of the same crash appeared in both training and validation. For scale, a model already known to be broken — one that fired 0.89 confidence on a normally-driving red sedan — scored 0.986 by the same measure.

Quoting mAP as an acceptance threshold commits the study to a number its own evidence rejects. If a panel member asks how the validation split was constructed, that is a difficult moment.

The replacement is stronger, not weaker: recall and false-alarms-per-minute on real deployment footage from the target city is a more demanding and more relevant claim than a benchmark score, and the reasoning for rejecting mAP is itself a defensible research finding.

**Numbers available to quote** (SPEC §4, native frame rate): 8/10 standard recall (80%), 0/6 hard recall, 3 false positives over ~11 minutes (0.27/min), 0 false positives on the crash-free clip, +3.02s median alert latency. Report standard and hard **separately** — a blended 8/16 hides which crashes were winnable.

### 1.2 Report the hard-difficulty result honestly — new text, near TC-AI-101

**Add.** The clip set was stratified into `standard` and `hard` *before any model was run*. Every `hard` clip is missed, without exception. This is a data-coverage limit — the training source never contained crashes of that geometry — not a tuning shortfall.

**Why.** Stating it plainly, with the pre-registration, converts an apparent weakness into evidence of honest methodology. Discovered by a panel instead, it looks like a concealed failure.

---

## Priority 2 — Test cases that contradict the ported design

### 2.1 Confidence thresholding — TC-U-302, p.89

**Currently:** *"YOLO mock outputs [0.45, 0.88, 0.60] against a set threshold of 0.75. Expected: the filtering function strips out the 0.45 and 0.60 values, returning only the 0.88 detection object."*

**Change to:** a test of class filtering and accumulator hand-off, not confidence gating. Suggested:

> A mock YOLO output containing both `accident` (class 0) and `vehicle` (class 1) boxes is passed to the filter. Expected: all class-1 boxes are discarded, and every class-0 box above the 0.15 detector confidence is forwarded to the accumulator regardless of its individual score.

**Why.** The ported design uses `conf = 0.15` and derives precision from evidence persisting over time, not from a per-frame threshold. Under it, all three mock values pass through. More importantly the old expectation is backwards: SPEC §3 measures genuine crash detections at **0.536 / 0.459 / 0.741** and false alarms at **0.869 / 0.844 / 0.649**. A 0.75 gate removes real crashes before it removes any false alarm.

### 2.2 Sub-threshold false-positive suppression — TC-AI-301, p.96

**Currently:** *"System threshold is 75%. Video shows a 'near-miss' or heavy braking, yielding a 60% AI confidence score. Expected: the threshold filter successfully intercepts the detection and drops it."*

**Change to:** a persistence test. Suggested:

> A near-miss produces intermittent `accident` detections that do not persist in one location. Expected: accumulated evidence decays below the firing threshold and no alert is emitted.

**Why.** This test currently describes dropping a 60% detection as correct behaviour. 60% is squarely inside the range where the model's genuine crash detections live. The mechanism that actually suppresses near-misses is temporal — a transient detection never accumulates the ~2 seconds of evidence needed to fire — not a confidence cutoff.

### 2.3 Sustained tracking / flicker — TC-AI-103, p.95

**Currently:** *"The model consistently outputs bounding box coordinates across the entire 10-second sequence without the detection 'flickering' or dropping."*

**Change to:** a test of the accumulator's tolerance for gaps. Suggested:

> Across a 10-second sequence of a stationary wreck, the accumulator maintains a single linked region and fires exactly one event, despite intermittent frames in which the detector produces no box.

**Why.** The detector *does* flicker, and the design assumes it will. The postmortem in the research repo records a clip holding 302 candidate frames and 12.35s of dwell that never assembled an unbroken run under the old logic, and emitted nothing. The accumulator replaced that logic precisely so a dropped frame costs progress rather than erasing it. Requiring no flicker asks for a property the system neither has nor needs.

### 2.4 Environmental robustness claims — TC-AI-202 / 203 / 204, pp.95–96

**Currently:** expected true-positive detection under heavy rain (202), correct rejection of headlight glare (203), and successful detection with 30% line-of-sight occlusion (204).

**Change to:** either remove, or restate as untested limitations.

**Why.** None of the 17 evaluation clips cover rain, glare, or partial occlusion, so there is no evidence supporting any of these expected results. TC-AI-204 is the most exposed: a fully-occluded clip was **deliberately excluded** from the label set on the grounds that no camera-based system could detect it, which makes a 30%-occlusion success claim hard to defend.

Night is the exception and is worth keeping — 8 of 17 clips are night footage, and night recall *exceeds* day recall. Night is a precision weakness only: all three false positives are night-time.

---

## Priority 3 — Timing anchors

Both were written when detection was a single frame, so "the moment of detection" and "the moment of impact" were the same instant. The accumulator separates them by ~3 seconds. They must now be anchored differently.

### 3.1 UI alert latency — TC-R-201, p.98

**Currently:** *"A stopwatch is initiated at the moment of detection... in strictly under 2.0 seconds."*

**Change to:** *"A stopwatch is initiated at the moment the alert is emitted by the AI engine... in strictly under 2.0 seconds."*

**Why.** This test measures backend → WebSocket → UI plumbing. Anchoring it to impact folds ~3 seconds of AI accumulation into a 2-second budget, failing a path that is genuinely fast. This is a clarification of what the test always measured, not a relaxation of it.

### 3.2 Operator response time — TC-S-103, p.100

**Currently:** *"...click 'Confirm' in strictly under 15 seconds from the moment of actual detection."*

**Change to:** *"...click 'Confirm' in strictly under 15 seconds from the moment of collision."*

**Why.** This is the metric that supports the study's central claim of reducing the notification gap from minutes to seconds (p.8), so it should honestly include the detector's own latency. After the port, `detected_at` in the database *is* the estimated collision time, so this becomes directly measurable as `verified_at − detected_at`.

**Budget check:** ~3s accumulating + <2s plumbing leaves ~10s of operator time. Achievable, but tighter than the original wording implies — confirm during live testing before committing to the 15s figure.

---

## Priority 4 — Descriptive corrections

### 4.1 Grayscale inference is not mentioned anywhere

**Add** to the AI Engine Layer description (p.79) and to the model training discussion.

> All frames are converted to grayscale and replicated to three channels before inference, matching the training pipeline. The accident source is 100% grayscale and the vehicle source ~98% colour, so without this normalisation the cheapest rule available to the model is "colour ⇒ vehicle, grayscale ⇒ accident" — which on colour deployment footage means it never fires.

**Why.** This is the single most consequential preprocessing decision in the system and it is currently undocumented. It is also a good defence answer: it shows a shortcut was anticipated and eliminated.

### 4.2 The two-class design and the discarded foil

**Add** to the model description.

> The model is trained on two classes, `accident` and `vehicle`, but only `accident` is alerted on. The `vehicle` class is a discriminative foil, discarded at inference. Under single-class training an ordinary car is background, and since nearly every accident image is a crash scene full of vehicles, the two concepts entangle and the model degenerates into a vehicle detector — which measurably happened to an earlier model that reported 0.986 mAP50 and then fired 0.89 confidence on a normally-driving red sedan.

**Why.** Currently the paper describes a YOLO model detecting collisions without explaining the class structure. The foil is the core design insight and reads well as a research contribution.

### 4.3 Alert latency is a designed floor, not a shortfall

**Add** wherever detection latency is discussed.

> Alerts land a median 3.02 seconds after impact. This is a deliberate consequence of requiring evidence to persist before firing, and is what buys the system's precision. It is a floor, not a defect.

**Why.** Pre-empts "why isn't it instant?" with the trade-off, rather than leaving it looking like a performance limitation.

### 4.4 State the operator-facing false-alarm rate

**Add** to the significance or limitations discussion.

> At 0.27 false alarms per minute per camera, an operator monitoring a single camera can expect roughly 16 false alerts per hour. The system is a triage aid that keeps a human in the loop, not an autonomous dispatcher.

**Why.** This number is a design input for the HITL workflow, and the paper's own click-efficiency criteria (TC-S-105, ≤3 clicks per incident) exist because of it. Stating it makes those requirements look derived rather than arbitrary, and it is far better volunteered than extracted under questioning.

---

## Not changing

These were checked against the ported design and are correct as written:

- **p.74** — 10–15 FPS per camera. The ported scheduler targets this band explicitly.
- **TC-AI-402**, p.97 — steady 10–15 FPS under a continuous feed.
- **TC-AI-401**, p.97 — under 100ms per frame. The engine's per-camera latency reporting is being corrected specifically so this is measured correctly; whole-batch reporting would have overstated it by the batch size.
- **p.84** — TensorRT `half=True`, `dynamic=True`, `batch=8`. Dynamic shapes mean a batch shrinking as cameras pause needs no special handling.
- **TC-R-301**, p.98 — 10-second reconnection loop. Matches `RECONNECT_INTERVAL_SECONDS`.
- **TC-I-203**, p.92 — 60-second dismiss cooldown.
- **p.73** — deployment hardware.
