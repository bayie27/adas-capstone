# ADAS detection core — transition spec

**Written 2026-08-10.** For a session working in the **capstone system repo** (FastAPI, React,
SQLite, HITL alert lifecycle, RBAC), which does not have the research repo's history.

This describes the accident detector that was built and measured in the research repo
`adas_detection`, everything needed to run it correctly, and — more importantly — the questions
that are already **closed with evidence** so they are not re-opened.

**Only the runtime crosses.** Training, the datasets, the evaluation harness and the full evidence
stay in the research repo. See §7.

---

## 1. What this is

A **per-frame object detector plus a temporal accumulator. There is no tracker.**

Two classes are trained; **one is alerted on**:

- `0 accident` — the crash and its immediate aftermath
- `1 vehicle` — ordinary cars, motorcycles, buses, trucks, tricycles, jeepneys

**Class 1 is a discriminative foil and is discarded at inference.** It exists only to occupy
training space. This is the single most important design fact.

**Why the foil exists.** Under single-class training an ordinary car is *background*. Almost every
accident image is a crash scene full of vehicles, so "car" and "accident" entangle and the model
degenerates into a vehicle detector. That is not hypothetical — it measurably happened to an
earlier model, `accident_detection.pt`, which reported mAP50 0.986 in validation and then fired
**0.89 confidence on a normally-driving red sedan**. Giving ordinary vehicles an explicit
competing class is what prevents it.

**Recall comes from a low per-frame confidence; precision comes from persistence over time.**
Neither comes from tracking. An earlier detect→track→motion-state-machine prototype scored **0/7**
on real Lipa footage and was deleted.

---

## 2. The pipeline

The entire detection loop is five lines:

```python
t = frame_index / fps                              # or wall-clock seconds for a live stream
net_in = to_gray(frame)                            # ALWAYS grayscale — see §3
r = model.predict(net_in, conf=0.15, imgsz=640, device=0, verbose=False)[0]
boxes, confs = [b for b, c in ... if int(c) == 0]  # class 0 only — discard `vehicle`
events = accumulator.update(t, boxes, confs)       # zero or more alerts
```

Everything else in the research repo's `detect/run.py` — argparse, annotation, video writing, the
display window — is scaffolding.

### 2.1 The grayscale conversion

```python
import cv2

def to_gray(frame):
    """BGR frame -> grayscale replicated back to 3 channels.

    Three channels on purpose: the COCO-pretrained stem expects 3, and a 1-channel input would
    silently reshape it.
    """
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
```

### 2.2 The accumulator

Pure logic — no model, no video, no I/O. Copy verbatim; it has its own test suite in the research
repo (`detect/test_accumulate.py`, 11 assertions).

```python
from dataclasses import dataclass, field

Box = tuple[float, float, float, float]


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


@dataclass
class Region:
    box: Box
    score: float = 0.0          # accumulated evidence, in conf-seconds
    peak_conf: float = 0.0
    first_t: float = 0.0
    last_t: float = 0.0
    fired: bool = False
    cooldown_until: float = -1.0


@dataclass
class Event:
    t: float
    box: Box
    score: float
    peak_conf: float
    age_s: float


@dataclass
class Accumulator:
    iou_link: float = 0.30
    threshold: float = 1.0      # conf-seconds
    decay: float = 0.3          # evidence lost per second with no supporting detection
    ema: float = 0.5            # box smoothing
    cooldown_s: float = 60.0    # ⚠️ DEAD — see §6
    regions: list[Region] = field(default_factory=list)
    _prev_t: float | None = None

    def update(self, t: float, boxes: list[Box], confs: list[float]) -> list[Event]:
        dt = 0.0 if self._prev_t is None else max(0.0, t - self._prev_t)
        self._prev_t = t
        events: list[Event] = []
        matched: set[int] = set()

        for box, conf in zip(boxes, confs):
            best, best_iou = -1, self.iou_link
            for i, r in enumerate(self.regions):
                if i in matched:
                    continue
                v = iou(box, r.box)
                if v >= best_iou:
                    best, best_iou = i, v
            if best < 0:
                self.regions.append(Region(box=box, score=conf * dt, peak_conf=conf,
                                           first_t=t, last_t=t))
                matched.add(len(self.regions) - 1)
                continue
            r = self.regions[best]
            matched.add(best)
            a = self.ema
            r.box = tuple(a * n + (1 - a) * o for n, o in zip(box, r.box))
            r.score += conf * dt
            r.peak_conf = max(r.peak_conf, conf)
            r.last_t = t

        for i, r in enumerate(self.regions):
            if i not in matched:
                r.score = max(0.0, r.score - self.decay * dt)
            if not r.fired and r.score >= self.threshold and t >= r.cooldown_until:
                r.fired = True
                r.cooldown_until = t + self.cooldown_s
                events.append(Event(t=t, box=r.box, score=round(r.score, 3),
                                    peak_conf=round(r.peak_conf, 3),
                                    age_s=round(t - r.first_t, 2)))

        self.regions = [r for r in self.regions if r.score > 0.0 or r.fired]
        return events

    def reset(self) -> None:
        self.regions.clear()
        self._prev_t = None
```

**Two properties are load-bearing, both from the deleted prototype's postmortem:**

1. **Leaky, never an unbroken run.** The old logic required consecutive above-threshold frames and
   reset on a single miss. One clip held 302 candidate frames and 12.35s of dwell yet never
   assembled a 2s unbroken run, so it emitted nothing. Here evidence *decays* instead of
   resetting, so a dropped frame costs progress rather than erasing it.
2. **Linked by position, not identity.** Regions associate frame-to-frame by IoU of the boxes.
   There is no track ID to lose — which matters because **the collision is exactly what breaks
   tracking**. A real wreck stays put so IoU holds it together; a spurious detection that jumps
   around never accumulates.

### 2.3 Frame sources — files and live streams

`cv2.VideoCapture` opens a file path and an `rtsp://` URL with the same call, so supporting both
is not the work. **Computing `t` is the work**, and the two differ completely:

| | File | Live stream |
|---|---|---|
| `t` | `frame_index / fps` | `time.monotonic() - t0` |
| Why | deterministic and reproducible — every recorded result depends on it | a live feed drops frames, so the index stops tracking real time |
| Ends? | yes | never — reconnect instead |
| Buffering | none | OpenCV queues frames; set `CAP_PROP_BUFFERSIZE = 1` or drift behind |
| `fps` reported | reliable | often `0` or nonsense |

**🚨 A reconnect must reset the accumulator.** After a 60-second outage `dt` is 60, and the
accumulator does `score += conf * dt`, so a single detection at conf 0.9 adds **54** against a
threshold of 1.0 — it fires on the first frame back. **Every network blip becomes an accident
alert.** The source signals the discontinuity and the caller resets:

```python
for frame, t, new_segment in source:
    if new_segment:
        acc.reset()          # reconnected — dt across the gap is meaningless
    events = detector.process(frame, t)
```

Resetting is also the honest response: across an outage you do not know what happened.

**Short gaps need no handling at all.** Evidence decays over elapsed time rather than per frame,
so a stream at 12 fps accumulates at the same rate per second as one at 30 fps. Ordinary frame
drops are already correct — this is a property of the design, not an accident.

**Reconnect budget counts *consecutive* failures**, resetting after any successful read. A camera
that drops nightly should get a fresh budget each time rather than exhausting one over a week and
then staying down. Retry-forever is the right default for a deployed alerting system.

The research repo's `detect/sources.py` implements this and travels with the runtime. It is
covered by `detect/test_sources.py` (7 tests, no pytest) which pins the two timestamp rules and
the reconnect signal. ⚠️ **Those tests use a fake capture — the stream path has never been run
against real RTSP hardware.** Verify against an actual camera before the defence.

### 2.4 Suggested seam

```python
class AccidentDetector:
    def __init__(self, weights, *, conf=0.15, imgsz=640, device=0,
                 threshold=1.0, decay=0.30, iou_link=0.30):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.conf, self.imgsz, self.device = conf, imgsz, device
        self.acc = Accumulator(iou_link=iou_link, threshold=threshold, decay=decay)

    def process(self, frame_bgr, t: float) -> list[Event]:
        """One frame plus its timestamp in SECONDS. Returns zero or more alert Events.

        `t` must be seconds and monotonic — a frame index makes it fire ~30x too eagerly,
        silently. One instance per stream; see the defects section.
        """
        r = self.model.predict(to_gray(frame_bgr), conf=self.conf, imgsz=self.imgsz,
                               device=self.device, verbose=False)[0]
        boxes, confs = [], []
        if r.boxes is not None:
            for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(),
                                r.boxes.conf.tolist()):
                if int(c) == 0:                      # accident only
                    boxes.append(tuple(b))
                    confs.append(float(cf))
        return self.acc.update(t, boxes, confs)
```

**Dependencies:** `ultralytics>=8.4` (the weights are YOLO26 — an older ultralytics raises an
unknown-architecture error), `opencv-python`, `numpy`. Install a CUDA build of torch **first**, or
ultralytics pulls a CPU-only one.

---

## 3. Invariants — change these and the detector silently degrades

Each has a measurement behind it. The measurement is stated so it is not "optimised" away.

### Grayscale is mandatory, at inference as well as training

The accident source is 100% grayscale; the vehicle source is ~98% colour. Left alone, the cheapest
rule the model can learn is "colour ⇒ vehicle, grayscale ⇒ accident" — and on colour deployment
footage it would then **never fire**. Training forces every image to grayscale, so inference must
match. Greying only one side swaps one domain mismatch for another.

This also blocks colour shortcuts generally: the broken predecessor reported 0.89 "accident" on a
normally-driving **red** sedan.

### `conf=0.15`. Do not raise it to suppress false alarms

Measured on the previous model: false alarms fired at **0.887 / 0.900 / 0.856**, while genuine
detections elsewhere fired at **0.536 / 0.459 / 0.741**. The adopted model reproduces the pattern —
its three false positives peak at **0.869 / 0.844 / 0.649**, still overlapping the range where real
crashes are detected.

**Any threshold that removes the false alarms deletes real crashes first.** They are unfamiliar
shapes and configurations, not weak detections — a data-coverage problem wearing a tuning
parameter's clothes.

### `imgsz=640`

Matches the training resolution. A 640/960/1280 sweep found recall identical at all three and 1280
*worse* on false positives. Re-tested on 1440p footage: all five universally-missed clips still
miss at 1280. Resolution raises the raw signal substantially — one clip goes from peak conf 0.114
to 0.756 — and **none of it accumulates**.

### Class 0 only

Class 1 `vehicle` is the training foil. Emitting it as an alert makes the system a vehicle
detector. A vehicle-coincidence filter was also considered and is a dead end: all genuine false
positives sit squarely on vehicles.

### 🚨 `t` MUST be in seconds, and must be monotonic

`threshold` is in **conf-seconds**, and the accumulator integrates `conf × dt` where
`dt = t - previous_t`. The unit of `t` is therefore load-bearing, and **passing the wrong one
fails silently — no exception, no warning, just wrong answers.** Measured, same input each time:

| `t` passed as | First fires at | |
|---|---|---|
| **seconds** | **2.00s** | ✅ correct |
| frame index | 0.07s | ❌ ~30× too eager — everything becomes an alert |
| milliseconds | 0.03s | ❌ worse |

Use `frame_index / fps` for recorded video, or a monotonic wall-clock in seconds for a live
stream. `time.monotonic()` is safe; a frame counter is not.

**Dropped frames are handled correctly** and need no special treatment: `dt` simply grows, and
because evidence is integrated over time rather than counted per frame, a stream running at 12 fps
accumulates at the same rate per second as one at 30 fps. This is why the design survives the
frame drops that a live RTSP feed will produce.

### Accumulator `threshold=1.0`, `decay=0.30`, `iou_link=0.30`

**Confirmed, not inherited.** 864 configurations were swept against a pre-registered rule and a
held-out half of the clips. **No improvement.** Recall is flat across the entire `decay` range
(0.45 down to 0.05), loosening `iou_link` does not help, and the configuration the selection rule
picked was *worse* on the half it had not seen. A proposed `max_area` box-size prior is **inert** —
identical recall at every setting.

---

## 4. Measured performance — the numbers a regression would break

**Adopted model: `models/weights_v3/epoch50.pt` in the research repo** (~20.8 MB, YOLO26-nano,
2.4M parameters). Adopted 2026-08-10 after scoring all eight exported checkpoints.

⚠️ **Take `epoch50.pt`, not `best.pt`** — see the warning at the end of this section.

| | Value |
|---|---|
| Standard recall | **8/10 — 80%** |
| Hard recall | 0/6 — 0% |
| Overall | 8/16 — 50% |
| Genuine false positives | **3** |
| **FP per minute** | **0.27** over ~11 min of non-crash footage |
| False positives on the crash-free clip | **0** |
| Median alert latency | **+3.02s** after impact |

Measured on 17 CCTV clips from the deployment city (15.4 min), which are **test-only, permanently**
and live in the research repo. `hard` was declared *before* any model ran, which is what makes the
standard/hard split an honest stratification rather than post-hoc selection.

**Report standard and hard separately.** A blended recall hides which crashes were winnable.

### Per-clip baseline — the same clips this repo will test against

Recorded clip by clip because **the aggregate can hide a compensating change**. If a later run
still scores 8/16 but a *different* eight — one crash gained, one lost — the summary looks
untouched while the behaviour has moved. Diff against this table, not against "50%".

| Clip | Difficulty | `epoch50` |
|---|---|---|
| `car-motor` | standard | **HIT** |
| `dekwatro` | standard | **HIT** |
| `dpwh-red-car-motor` | standard | **HIT** |
| `jeep-motor` | standard | **HIT** |
| `jeep-yellow-car` | standard | **HIT** |
| `motor-motor-night` | standard | **HIT** |
| `red-car-motor` | standard | **HIT** |
| `tric-motor-car` | standard | **HIT** |
| `car-motor-motor` | standard | miss |
| `motor-motor` | standard | miss |
| `armored-car-car` | hard | miss |
| `car-motor-far` | hard | miss |
| `car-uturn-motor` | hard | miss |
| `jeep-car` | hard | miss |
| `truck-car` | hard | miss |
| `truck-student-car` | hard | miss |
| `airbase` | **crash-free** | 0 events ✓ |

Two things this shows that the summary cannot:

1. **Every `hard` clip is missed, without exception.** The 0% is not scattered bad luck, it is a
   clean data-coverage wall — the training source simply never taught the model what those look
   like. Useful when a panel asks why hard recall is zero.
2. **Every non-`hard` crash involving a jeepney or tricycle is a hit** (`jeep-motor`,
   `jeep-yellow-car`, `tric-motor-car`). That is the evidence the Philippine retrain removed the
   false alarms on those vehicles *without* costing recall on crashes involving them — a cost that
   was predicted in advance and did not materialise.

**The three false positives**, for reference — all night, all the proximity mode, none a tricycle
or jeepney:

| Clip | t | What is in the box |
|---|---|---|
| `car-motor` | 58.30s | Small flatbed truck overlapping a red car |
| `car-motor-motor` | 21.66s | White pickup with a motorcycle close behind |
| `motor-motor` | 12.80s | Cluttered roadside — parked van, bunched motorcycles |

⚠️ **`motor-motor` fired at 12.80s against an 18.0s onset** — 5.2s early, outside the 2s lead, so
it scores as a false positive *and* the clip scores as a miss. The detector saw something.
**Do not widen the lead to convert it into a hit**: that is moving the goalposts after seeing the
result, and it would invalidate every model comparison on record.

⚠️ **THE CLIPS ARE TEST-ONLY, PERMANENTLY — this rule must survive the move.** Never train on
them, and never include their ordinary-traffic frames as negatives. They are irreplaceable
deployment footage and the only measurement instrument this project has; training on them destroys
the ability to make any honest claim. They are also gitignored, so `git` cannot restore them —
never delete or overwrite a clip.

### 🚨 Validation mAP is meaningless here — never quote it

The v3 run reported **`accident` mAP50 0.956**. It is **leaked**. The incident-level validation
split failed and was skipped, so near-duplicate frames of the same crash sat in both train and
validation. For scale: the known-*broken* model reported **0.986** the same way.

**The only quotable metrics are event-level recall and FP/min on held-out deployment footage.**
mAP measures per-frame box quality, rewards duplicate frames, and has flattered a broken model in
this project once already.

### Never select a checkpoint by the `best.pt` label

`best.pt` is chosen by that leaked validation metric. Across three training runs it has lost every
time — in v3 it matched `epoch50` on recall with **5 false positives against 3**. Selection is by
scoring every exported checkpoint against real footage.

---

## 5. Closed levers — do not re-open without new evidence

| Lever | Status |
|---|---|
| `imgsz` | **Closed.** All five universal misses re-run end-to-end at 1280 — all five still miss. |
| `conf` | **Closed.** False alarms outscore several true detections; raising it deletes crashes first. |
| The accumulator | **Closed.** 864 configurations swept; no improvement; winner worse on held-out data. |
| Night performance | **Closed.** 8 of 17 clips are night, and night recall *exceeds* day. Night is a **precision** weakness only — all 3 remaining false positives are night. |
| More public accident data | **Closed.** Surveyed well beyond the obvious sources; nothing usable with the right geometry, licence and annotations. |
| Tracking / motion state machines | **Closed and deleted.** Scored 0/7 on real footage. |
| Vehicle-coincidence filtering | **Closed.** All genuine false positives sit on vehicles. |

**Recall is a data-coverage limit, not a tuning problem.** The accident source is the only source
of what a crash looks like. Say that plainly rather than implying more tuning would help.

---

## 6. Known defects you will hit in a live system

These were acceptable for scoring fixed-length clips and are **not** acceptable for a
continuously-running service. They were left unfixed deliberately: changing them would have
invalidated the model comparison that selected the deployed weights. **Fixing them is the system
repo's job.**

### 🚨 Fired regions are retained forever, and `cooldown_s` is dead

`cooldown_until` is never reached in a way that matters: `fired` is never set back to `False`, so
the branch is only evaluated for regions that have never fired, where `cooldown_until` is still
`-1.0` and always passes. **Every region fires exactly once and `cooldown_s` gates nothing.**

What actually suppresses repeat alerts is spatial: the retention filter is
`r.score > 0.0 or r.fired`, so fired regions are kept forever and keep absorbing detections at that
location, preventing a new region forming there.

**Two consequences for a long-running process:**

1. **Every location that alerts goes permanently deaf.** A second crash at the same junction will
   never fire. On a 60-second clip this is correct de-duplication; over days it is blindness.
2. **`self.regions` grows without bound** — a slow memory leak.

**A clip emitting 3 events means 3 distinct places, not 3 repeats.** Any fix must preserve that
de-duplication while letting a region expire. The obvious approach — evict fired regions once
`t - last_t` exceeds some age, and make the cooldown real — is untested here. **Re-measure against
the clips after changing it**, because this alters event counts and therefore every number in §4.

### Latency is ~3s, and it is measured from impact

Alerts land a median **+3.02s** after impact, because the accumulator deliberately requires
evidence to persist. This is a floor, not a bug — it is what buys the precision. Budget for it in
any UI that claims "real-time".

### 🚨 One `Accumulator` per stream — a reused instance goes deaf

This is the defect above, manifesting in the way an integration is most likely to trigger it:
build one detector, loop it over several cameras.

Measured: feed a steady detection until it fires, then feed an **identical** sequence to the same
instance. The second sequence produces **zero events**. The fired region from the first is retained
forever and keeps absorbing the new detections, so no new region can form.

```python
acc.reset()   # between sources — clears regions and the previous timestamp
```

Give each stream its own `AccidentDetector` (or call `reset()` when switching sources). Do not
share one across cameras, and do not share one across a restart boundary without resetting.

### Ultralytics state leaks between videos

Setting `model.predictor = None` does **not** reset it. Construct a fresh `YOLO` per video source.
This silently produced wrong numbers once.

### Model load is not free

Load the model **once** at process start, never per request. Inference is ~3.5–5ms per frame on a
T4 and ~30ms on a GTX 1650; model construction is seconds.

---

## 7. What stayed behind, and where to look

All of this remains in the research repo `adas_detection`. **Do not rebuild any of it from
scratch** — check there first.

| What | Where | Why it stayed |
|---|---|---|
| Training pipeline | `train/`, `dataset/` | Needs Colab, a GPU, and ~20 GB of datasets. |
| Evaluation harness | `eval/` — `run_clips.py`, `score.py`, `sweep.py`, `probe_raw.py` | The measurement instrument. Any claim about detector performance must be re-measured with it. |
| The 17 deployment clips | `prototype/samples/` | **Irreplaceable and gitignored.** Test-only, permanently. Copy them if this repo needs to re-measure — never move them, and never let `git` be your only copy. |
| Evaluation harness, if you re-measure here | `eval/run_clips.py`, `score.py`, `labels.csv` | Only needed if this repo scores the detector itself rather than trusting §4. Copy alongside the clips; the two are useless apart. |
| Full evidence and history | `docs/results.md`, `docs/design/`, the dataset surveys | What the defence document draws on. |
| The postmortem of the deleted tracking prototype | `docs/design/accident-detection.md` | The most valuable document in that repo. Several of its findings are traps a new design walks straight back into. |

### Data-integrity caveats to carry into any write-up

- **The accident training source is heterogeneous and partly synthetic.** It contains
  AI-generated crash images (`Gemini_Generated_Image_*`), Sri Lankan road photos, and PASCAL VOC
  files, plus literal duplicates. No published number is affected — everything is measured on
  deployment footage — but do not describe it as pure fixed-CCTV accident content.
- **Two of the 17 clips are screen recordings of an NVR viewer**, degraded to 720×368 and
  1024×576. A miss on either says more about the capture than the detector.
- **Clip independence is not established.** Some clips may be longer exports of incidents already
  counted. Do not claim "16 independent incidents".

---

## 8. Checklist for the first session in the system repo

1. Copy §2's code into the repo, following its existing conventions.
2. Copy the adopted weights. Confirm `ultralytics>=8.4`.
3. **Prove the port didn't change behaviour**: run the ported code and the research repo's
   `detect/run.py` over the same clip and assert the emitted events are identical. Refactors that
   silently change behaviour are the failure this project has repeatedly caught. Either repo can
   host the comparison — whichever has the clips — but the reference output must come from the
   research repo's `detect/run.py`, not from a re-implementation.
   Then check the per-clip table in §4 clip by clip, not just the 8/16 total.
4. Fix the fired-region lifecycle (§6) **before** running against a live stream, and re-measure
   against the clips afterwards.
5. Wire events into the alert lifecycle. An `Event` carries `t`, `box`, `score`, `peak_conf` and
   `age_s` — enough for an operator-facing alert with a location and a confidence.
6. Keep a human in the loop. At 0.27 false alarms per minute this is a **triage aid, not an
   autonomous dispatcher**, and it misses every crash the source data never taught it to see.
