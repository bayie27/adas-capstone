# Cadence measurement — detection behaviour vs. sampling rate

**Measured:** 2026-08-11, NVIDIA GTX 1650, `epoch50.pt`, all 17 Lipa clips per rate.
**Command:** `uv run --no-sync python ai_engine/eval/sweep_cadence.py --weights ai_engine/epoch50.pt`
**Companion:** `2026-08-10-detection-core-port-design.md` §4.2 (which this settles) and §9.

---

## Why this was measured

The design doc recorded **two hypotheses** about sampling rate, both introduced by that document rather than by any prior evidence, and both flagged as unmeasured:

1. **Variance.** Fewer samples per unit time might mean a short run of spurious detections carries proportionally more weight, raising false alarms.
2. **A low-rate floor.** Regions link frame-to-frame by IoU of their boxes, so sampling too slowly might stop boxes overlapping between samples and prevent evidence accumulating at all.

`adas_transfer/SPEC.md` says the opposite, twice: _"a stream running at 12 fps accumulates at the same rate per second as one at 30 fps"_ (§2.3, §3). It documents no minimum frame rate anywhere. The paper's 10–15 FPS band (p.74) is justified by **GPU thermal management**, not by detection.

Designing around unmeasured hypotheses is exactly what SPEC.md's "closed levers" discipline exists to prevent, so they were measured.

---

## Results

Every row is all 17 clips, scored with the same `eval/score.py` and `labels.csv`.

| Effective FPS  | Stride | Recall   | Standard | Hard | False positives | FP/min |
| -------------- | ------ | -------- | -------- | ---- | --------------- | ------ |
| 29.92 (native) | 1      | 8/16     | 8/10     | 0/6  | 3               | 0.27   |
| 14.96          | 2      | **7/16** | 7/10     | 0/6  | 5               | 0.46   |
| 14.96 (dup)    | 2      | **7/16** | 7/10     | 0/6  | 5               | 0.46   |
| 9.97           | 3      | 8/16     | 8/10     | 0/6  | 3               | 0.27   |
| 5.98           | 5      | 8/16     | 8/10     | 0/6  | **2**           | 0.18   |
| 2.99           | 10     | 8/16     | 8/10     | 0/6  | 5               | 0.46   |

**Hard recall is 0/6 at every rate.** That limit is data coverage, not cadence, and nothing here moves it.

---

## Conclusion: both hypotheses are refuted

**Recall is flat from 3 to 30 FPS.** 8/16 at every rate except one. Even at a _tenth_ of native rate, every crash the detector can find is still found.

**False positives show no relationship to rate.** They run 3, 5, 5, 3, 2, 5 as rate falls. The _fewest_ false positives (2, at 5.98 FPS) occur at nearly the lowest rate tested — the opposite of hypothesis 1.

**The variation is sampling phase, not sampling rate.** The single recall dip is at stride 2, and the sequence is not monotonic: quality would have to degrade steadily as rate falls for a rate effect to exist, and instead 9.97 and 5.98 FPS match or beat native. At stride 2 versus stride 3 the run simply lands on different frames. With 16 crashes and 2–5 false positives in the entire corpus, one crash and two false positives flipping is comfortably inside the noise of _which_ frames were sampled.

**SPEC.md was right and the design doc's hypotheses were wrong.** Rate-independence is a real, measured property of integrating `conf × dt` over elapsed time rather than counting frames.

---

## What this changes

1. **The 10–15 FPS band is a compute/thermal constraint only.** The paper's own justification (p.74, thermal throttling) is the correct and complete one. There is no detection-side reason for the floor, so it must not be described as one.

2. **Weak machines carry far more cameras than the design assumed.** Camera capacity is `sustainable_inference_rate / required_per_camera_rate`. If the required rate can drop to ~5 FPS with no measured detection cost, capacity roughly triples versus the 15 FPS assumption. Design doc §6.4's capability table is too pessimistic and should be revised after `calibrate.py` produces real numbers.

3. **The CPU-only verdict needs revisiting.** §6.4 calls CPU-only "effectively zero capacity" at the 10 FPS lower bound. At ~5 FPS that conclusion no longer follows automatically. It remains untested — this sweep measured _sampling_ rate on a GPU, not CPU throughput — but the reasoning that produced the verdict is gone.

4. **Degrading to the band floor when over capacity is safe**, and the floor could go lower than 10 FPS if capacity demanded it.

---

## Limits of this measurement — read before quoting it

- **Small sample.** 16 crashes and 2–5 false positives per run. A ±1 crash or ±2 false-positive difference between rows is noise, not signal. Do not read the 5.98 FPS row as evidence that sampling less _improves_ precision.
- **One corpus, one machine, one model.** 17 clips from one city on one day, on a GTX 1650.
- **Nothing below 3 FPS was tested.** A floor certainly exists somewhere — a single frame per crash cannot accumulate 1.0 conf-seconds of evidence — but it is below 3 FPS and this sweep does not locate it.
- **Sampling rate is not CPU throughput.** Every run here used the GPU; frame decode was unchanged.
- **The requested-rate grid is misleading and should be replaced by strides.** `stride = round(native_fps / requested_fps)`, so at 29.92 fps native both 15 and 12 resolve to stride 2 — the "12 FPS" row is a duplicate of the 15 FPS configuration, not an independent point. Four distinct rates were tested, not five. Future sweeps should specify strides directly.

---

## Reproducing

```bash
uv run --no-sync python ai_engine/eval/sweep_cadence.py --weights ai_engine/epoch50.pt
```

About an hour on a GTX 1650. Per-rate event JSON lands in `ai_engine/eval/_sweep_<rate>/`; re-score any completed run without re-inferring:

```bash
uv run --no-sync python ai_engine/eval/score.py --events-dir ai_engine/eval/_sweep_10
```
