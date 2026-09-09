# Evaluation Harness

This document describes the two layers that are sometimes both called a “harness”:

1. The **AI detection core/model harness**: grayscale preprocessing, YOLO inference, accident-class
   filtering, the spatial-temporal accumulator, and event emission.
2. The **evaluation harness**: labeled-clip execution, event scoring, checkpoint comparison, and
   accumulator sweeps.

The reported recall, false positives, FP/min, and latency are measurements of the complete AI
detection core/model harness. They are not standalone YOLO frame-level results.

## 1. End-to-end data flow

```text
AI DETECTION CORE / MODEL HARNESS
video or stream
      ↓
grayscale preprocessing
      ↓
YOLO inference at low confidence
      ↓
keep class-0 accident boxes
      ↓
IoU-linked leaky spatial-temporal accumulator
      ↓
detection-event JSON
      ↓
EVALUATION HARNESS
event-level scorer against eval/labels.csv
      ↓
recall, misses, false positives, FP/min, latency
```

The AI detection core contains no vehicle tracker. The old tracker-first prototype is documented as
a [superseded design](../docs/design/accident-detection.md), not as part of this measurement path.

## 2. AI detection core/model harness: `detect/run.py` + accumulator

[`detect/run.py`](../detect/run.py), together with
[`detect/accumulate.py`](../detect/accumulate.py), is the single-video or live-stream AI detection
core. Its important behavior is:

1. Accept a video path through `--source` or the compatibility alias `--video`, or accept a live
   stream URL.
2. Resolve the device and instantiate a fresh YOLO model.
3. Convert each frame to grayscale and replicate the channel back to BGR unless `--color` is
   explicitly used for a failure demonstration.
4. Run inference with the default `conf=0.15` and `imgsz=640`.
5. Keep only detections whose class is `0` (`accident`). The `vehicle` class is not passed to the
   alert accumulator.
6. Update the accumulator with the timestamp, boxes, and confidences.
7. Optionally write an annotated video and/or an event JSON file.

The low confidence floor is intentional: frame-level recall comes from retaining weak evidence;
temporal persistence is responsible for rejecting short noise. This complete detector-plus-
accumulator path is what produced the event files later consumed by the evaluation harness.

### Event JSON contract

An event file records the metadata needed to reproduce the scoring denominator and the detections
needed to score the clip:

```json
{
  "video": "example.mp4",
  "fps": 30.0,
  "frames": 1800,
  "gray": true,
  "conf": 0.15,
  "imgsz": 640,
  "device": "cuda:0",
  "events": [
    {
      "t": 12.8,
      "box": [100.0, 120.0, 300.0, 360.0],
      "score": 1.02,
      "peak_conf": 0.71,
      "age_s": 2.1
    }
  ]
}
```

The file-level fields are `video`, `fps`, `frames`, `gray`, `conf`, `imgsz`, `device`, and
`events`. Each event contains the emission time `t`, smoothed box, accumulated evidence `score`,
highest supporting confidence `peak_conf`, and region age `age_s`. For a file source, duration is
derived from `frames / fps`; this is why both fields are load-bearing rather than decorative.

## 3. Accumulator component: `detect/accumulate.py`

[`detect/accumulate.py`](../detect/accumulate.py) is pure logic: it has no model, video, or file
I/O. It maps `(timestamp, boxes, confidences)` to zero or more events.

### Linking and evidence

- A new box is matched to an existing region by intersection-over-union (IoU), with the deployed
  link threshold at `0.30`.
- A matched region receives evidence proportional to confidence and elapsed time:
  `score += confidence × dt`.
- An unmatched region loses evidence through decay:
  `score = max(0, score − decay × dt)`.
- Box coordinates are smoothed with an EMA of `0.5`.
- The deployed threshold is `1.0` confidence-seconds. A stable detection near confidence `0.5`
  therefore takes roughly two seconds to fire at 30 FPS.

This is a leaky integrator rather than an unbroken-consecutive-frame rule. A missed frame costs
progress but does not erase the whole history. A detection that jumps around the image does not
accumulate in one spatial region.

### Reproducibility behavior

The `fired` flag remains set for the lifetime of a region. As a result, each spatial region fires
once; the `cooldown_s` field does not reset that region for repeat alerts. This is a known behavior
of the recorded harness, and changing it would invalidate the historical model comparison. It is
documented here so a future implementation does not mistake the intended name of the parameter for
the measured behavior.

## 4. Evaluation harness: clip runner `eval/run_clips.py`

[`eval/run_clips.py`](../eval/run_clips.py) is the batch boundary for real-footage evaluation.

- The clip list comes from `eval/labels.csv`, not from a hardcoded tuple.
- Every clip runs in its own subprocess so Ultralytics state cannot leak between videos.
- Rows with `onset_s=none` are declared negative clips. They are still run so they can contribute
  false positives, but they do not contribute a crash to recall.
- The current labels file describes 17 clips: 16 crash-labeled clips and one declared negative.
- The earlier seven-clip set is historical and is not silently mixed into the current run.

The runner passes the same confidence, image size, accumulator threshold, decay, and device to each
clip. It writes one event JSON per clip and then invokes the scorer.

## 5. Evaluation harness: event-level scorer `eval/score.py`

[`eval/score.py`](../eval/score.py) uses the label file as ground truth:

- A crash is a **hit** when at least one event timestamp is in
  `[onset_s − 2 seconds, end_s + 15 seconds]`.
- A labeled crash with no event in that window is a **miss**.
- An event outside every crash window is a **false positive**.
- FP/min uses the non-crash duration, including declared negative footage and the clean portions of
  crash clips, as the denominator.

The current comparison separates standard and hard crashes where the label file marks difficulty.
The scorer reports event-level recall rather than frame-level box metrics. It also reports the
number of clean minutes behind FP/min so the rate is not mistaken for a deployment-wide average.

## 6. Evaluation harness: checkpoint sweep `eval/sweep.py`

[`eval/sweep.py`](../eval/sweep.py) evaluates every `.pt` file in a model directory against the
labeled clips. This is necessary because the `best.pt` name comes from validation mAP, and that mAP
was produced by a frame-level split with near-duplicate frames. In the field, a checkpoint labeled
`best.pt` can lose to an epoch checkpoint.

The selection procedure is therefore:

1. Run every exported checkpoint through the same clip runner.
2. Parse the event-level recall, false-positive count/rate, and latency.
3. Select using the pre-registered evaluation rule and inspect the full checkpoint table.
4. Adopt the checkpoint supported by held-out event behavior, not by the filename `best.pt`.

For v3, eight checkpoints were exported and `epoch50.pt` was selected. It matched `best.pt` on
recall but produced fewer false positives.

## 7. Evaluation harness: cached inference and accumulator sweep

The accumulator can be tested independently of GPU inference:

1. [`eval/cache_detections.py`](../eval/cache_detections.py) runs inference once per labeled clip
   at a low confidence floor (`0.05`) and saves raw class-0 boxes.
2. [`eval/sweep_accumulator.py`](../eval/sweep_accumulator.py) replays those boxes through the
   accumulator across parameter combinations.
3. The pre-registered split uses eight tune clips plus one declared negative and eight verify clips,
   stratified by difficulty and lighting. The verify half is not used to re-select a configuration.
4. The recorded grid tested **864 configurations** across threshold, decay, confidence, IoU link,
   and maximum box-area settings.

The replay was first validated against the deployed `detect/run.py` events. The final result was
that no configuration demonstrated a reliable held-out improvement over the deployed configuration,
so the deployed accumulator settings were retained.

## 8. Reproduction commands

The project uses the environment-specific interpreter documented in
[`prototype/README.md`](../prototype/README.md).

### Run one clip

```bash
# Linux
./prototype/.venv/bin/python detect/run.py \
  --video prototype/samples/dekwatro.mp4 \
  --weights models/weights_v3/epoch50.pt \
  --events runs/events_v3/dekwatro.json

# Windows
./prototype/.venv/Scripts/python.exe detect/run.py \
  --video prototype/samples/dekwatro.mp4 \
  --weights models/weights_v3/epoch50.pt \
  --events runs/events_v3/dekwatro.json
```

### Run and score all labeled clips

```bash
./prototype/.venv/bin/python eval/run_clips.py \
  --weights models/weights_v3/epoch50.pt \
  --events-dir runs/events_v3
```

### Sweep every checkpoint

```bash
./prototype/.venv/bin/python eval/sweep.py \
  --weights-dir models/weights_v3
```

### Cache and replay accumulator settings

```bash
./prototype/.venv/bin/python eval/cache_detections.py --imgsz 640
./prototype/.venv/bin/python eval/sweep_accumulator.py \
  --cache runs/cache_640 \
  --validate runs/events_cdrrmo_v2best_640
./prototype/.venv/bin/python eval/sweep_accumulator.py \
  --cache runs/cache_640 \
  --out runs/sweep_curve_640.csv
```

On Windows, replace `./prototype/.venv/bin/python` with
`./prototype/.venv/Scripts/python.exe`.

## 9. Test evidence versus field evidence

The repository tests establish local logic and interface behavior; they do not prove that the model
detects crashes:

| Test                                                        | What it proves                                                                                         |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [`detect/test_accumulate.py`](../detect/test_accumulate.py) | IoU linking, leaky persistence, decay, wandering-box rejection, and one-time region firing             |
| [`detect/test_run.py`](../detect/test_run.py)               | Source/device forwarding and event-file boundary behavior with mocked model/source objects             |
| [`detect/test_sources.py`](../detect/test_sources.py)       | File/stream classification, timestamps, reconnect signaling, and bounded reconnect behavior            |
| [`dataset/test_pipeline.py`](../dataset/test_pipeline.py)   | Quota conservation, v1 regression guard, incident grouping, deterministic splitting, and disk scanning |

Only a real-footage run of the complete AI detection core through `eval/run_clips.py` and
`eval/score.py` establishes the reported recall and false-positive measurements. The unit tests
are supporting evidence for the core/evaluation harness behavior, not substitutes for held-out
video evaluation.

## 10. Evaluation limitations

- The current 17-clip set is one project-specific camera/footage collection, not a deployment-wide
  sample.
- The legacy seven/five-clip results use different footage and labels and must remain separate.
- The incident-level validation guard did not complete for v2 or v3, so validation mAP is not a
  held-out operational metric.
- A declared negative clip is useful for false-positive measurement, but it does not establish an
  all-day alert rate.
- The recorded harness's spatial one-fire behavior and inactive repeat cooldown are part of the
  measured implementation and should be stated if the harness is reproduced exactly.
