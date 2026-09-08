# Results, Interpretation, and Limitations

This document collects the outcomes of the training iterations and the complete AI detection core.
The [training-run manifest](training-run-manifest.md) contains the authoritative execution and
dataset inventory; the [evaluation harness](evaluation-harness.md) explains how the core was
measured.

## Executive summary

The final adopted checkpoint is `models/weights_v3/epoch50.pt`. It was selected by evaluating all
exported v3 checkpoints through the complete AI detection core—YOLO plus preprocessing, accident-
class filtering, and accumulator—and its event-level evaluation harness, not by trusting the
`best.pt` filename.

## What the reported results include

Every v1, v2, and v3 recall, false-positive, FP/min, and latency value in this document comes from
the full AI detection core/model harness:

```text
grayscale frame → YOLO detections → accident-class filter
                 → spatial-temporal accumulator → emitted event
```

The evaluation harness then runs that core over the labeled clips and applies the hit-window and
false-positive rules. These are therefore **end-to-end core-pipeline results**, not raw YOLO
frame-level detection results. The validation mAP values are the only standalone model-stage
numbers retained, and they are explicitly non-quotable because the validation split leaked.

On the current 17-clip evaluation set, v3 epoch50 achieved:

- **8/10 standard-crash recall (80%)**;
- **0/6 hard-crash recall**;
- **8/16 overall crash recall (50%)**;
- **3 false positives**, all retained after inspection;
- **0.27 false positives per minute** as scored and after inspection;
- **+3.02 seconds median detection latency**.

Compared with the temporarily deployed v2 checkpoint, v3 improved standard recall from 70% to 80%
and reduced as-scored FP/min from 0.55 to 0.27. It also increased median latency from +1.37 to
+3.02 seconds. The adoption decision favored the simultaneous recall and false-positive improvement;
latency remained a real regression and must be reported.

## 1. Chronological run summary

| Run              | Purpose and data                                                | Training result                                                                          | Evaluation/adoption result                                                                                                                                                                                                        |
| ---------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v1 full baseline | 11,095 Nyanko images; BMD-45 budget resolved to zero            | Established the detector-first baseline; 60 epochs                                       | Historical incumbent. On the legacy set, v1 `last.pt` reached 4/5 standard crashes with 2 false positives. On the current set, the recorded baseline was 50% overall recall with a 1.00 FP/min rate.                              |
| v2 full retrain  | Added 2,072 BMD-45 vehicle-only images and 21,386 vehicle boxes | Tested whether ordinary fixed-camera traffic would reduce vehicle-related false alarms   | On the legacy five-clip comparison, selected v2 scored 3/5 versus v1's 4/5 and was initially rejected. On the current set it became the temporary deployed model at 7/10 standard recall, 0.55 FP/min, and +1.37s median latency. |
| v3 smoke test    | Capped source budgets and three epochs under `adas_v3_smoke`    | Validated the revised data-download, quota, source, grayscale, export, and training path | Smoke-only. No recall, FP/min, or checkpoint-quality claim is taken from it.                                                                                                                                                      |
| v3 full retrain  | 11,413 images: Nyanko, BMD-45, `e6kgi`, and `5kcdl`; 60 epochs  | Added Philippine vehicle and night-traffic foil data while retaining the accident source | `epoch50.pt` adopted after checkpoint sweep: 8/10 standard recall, 0.27 FP/min, +3.02s median latency.                                                                                                                            |

The smoke test is a real execution but not a fourth full model version. The original tracker-first
prototype is also excluded from this table's training-run count because it was a superseded
architecture experiment rather than one of the four recorded model-training executions.

## 2. Legacy evaluation: seven-clip history and five-clip comparison

The legacy record combines the original seven-clip sample history with the later five-clip verified
comparison. It is retained because it explains why v2 was initially rejected and why the harness
rules changed.

### 2.1 Superseded tracker-first design

The original detector → tracker → motion-state design produced **0/7 detections** at its default
configuration on the real clips. Relaxed settings reached at most 3/7 while leaving precision
unmeasurable because the sample set did not contain labeled normal-traffic footage. The failure was
structural: the impact disrupted the track history and strict persistence reset on intermittent
evidence.

This result motivated the detector-first model plus leaky accumulator. It is not evidence about the
performance of v1, v2, or v3.

### 2.2 v1 versus v2 on the legacy verified clips

| Checkpoint      | Standard recall | False positives |
| --------------- | --------------: | --------------: |
| v1 `last.pt`    |       4/5 (80%) |               2 |
| v2 `last.pt`    |       3/5 (60%) |               0 |
| v2 `best.pt`    |       3/5 (60%) |               0 |
| v2 `epoch40.pt` |       4/5 (80%) |               1 |
| v2 `epoch50.pt` |       4/5 (80%) |               1 |

The pre-registered adoption rule required at least the incumbent recall without new genuine false
positives, so v1 `last.pt` was retained at that point. The BMD-45 prediction nevertheless held:
the jeepney-context false positive disappeared. The tradeoff was that the selected v2 checkpoint
also lost one crash on that small comparison.

## 3. Current evaluation: 17 clips

The current labels contain 17 clips: 16 crash-labeled clips and one declared negative. Recall is
calculated over the 10 standard and 6 hard crash windows; the negative clip and clean portions of
the crash clips contribute to false-positive measurement. The current set contains approximately
15.4 minutes of footage.

### 3.1 Model comparison

| Metric                            | v2 `best.pt` | v3 `epoch50.pt` |
| --------------------------------- | -----------: | --------------: |
| Standard recall                   |   7/10 (70%) |  **8/10 (80%)** |
| Hard recall                       |     0/6 (0%) |        0/6 (0%) |
| Overall recall                    |   7/16 (44%) |  **8/16 (50%)** |
| False positives, as scored        |            6 |           **3** |
| False positives, after inspection |    4 genuine |   **3 genuine** |
| FP/min, as scored                 |         0.55 |        **0.27** |
| FP/min, genuine                   |         0.36 |        **0.27** |
| Crash-free clip false positives   |            0 |               0 |
| Median latency                    |       +1.37s |          +3.02s |

The table is an event-level comparison. It is not an image-level accuracy table and does not use
validation mAP.

### 3.2 Why v3 epoch50 was selected

The v3 run exported eight checkpoints. `best.pt` was selected by the leaked validation mAP and
was therefore not treated as the field winner. The event-level sweep found that `epoch50.pt`
matched `best.pt` on recall but produced **3 false positives instead of 5**. The final deployment
choice was therefore `epoch50.pt`.

### 3.3 False-positive analysis

The v2 false-positive pattern included ordinary tricycles and a jeepney—vehicle silhouettes that
were absent from the original training sources. v3 added Philippine vehicle-only data specifically
to break that association.

The v3 inspection found:

- none of the three remaining false positives was a tricycle or jeepney;
- all three occurred at night;
- the remaining failure mode was proximity: several vehicles close together were interpreted as a
  collision.

This supports the intended precision mechanism of the Philippine vehicle foil. It does not mean
that v3 solved night-time precision or general traffic-scene ambiguity.

### 3.4 Recall and latency interpretation

The v3 retrain did not add accident images, so it was not expected to repair the hard crash misses.
Its measured gain was primarily precision and ordinary-vehicle coverage. Standard recall increased
on the current set, but hard recall remained 0/6.

Latency regressed from +1.37 to +3.02 seconds. Latency was not part of the pre-registered adoption
rule, so it did not block adoption, but it must remain in any honest system description.

## 4. Accumulator sweep result

The project cached raw detections once and replayed them through **864 accumulator configurations**.
The split and selection rule were registered before the sweep:

- tune on eight clips plus the declared negative;
- verify on eight separate crash clips;
- maximize standard recall subject to FP/min ≤ 0.55 on tune;
- break ties by latency and then FP/min;
- run the selected configuration once on verify and do not re-select from that result.

The sweep did not demonstrate a reliable held-out improvement over the deployed configuration. A
configuration that looked better on tune was worse on verify, so the deployed accumulator settings
were retained. The practical conclusion is **no improvement demonstrated**, not that the deployed
settings are mathematically optimal.

## 5. Claim-status register

| Claim or number                                                       | Status                                  | How to use it                                                                                   |
| --------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Four training-related executions: v1, v2, v3 smoke, v3 full           | **Verified**                            | Count the smoke test separately from the three full model runs                                  |
| v3 final composition: 11,413 images                                   | **Verified**                            | Use the per-source counts in the [manifest](training-run-manifest.md)                           |
| v3 epoch50: 80% standard recall, 0.27 FP/min                          | **Verified**                            | Current event-level result on the 17-clip set                                                   |
| v3 hard recall: 0/6                                                   | **Verified**                            | Report as a current limitation                                                                  |
| v2 false alarms reduced by BMD-45                                     | **Verified**                            | Explain as an ordinary-traffic precision effect, not an accident-recall gain                    |
| v3 removed tricycle/jeepney false-positive mode                       | **Verified after inspection**           | Report with the remaining night/proximity caveat                                                |
| The exact full v2 per-source image total                              | **Not recovered**                       | Do not derive it from BMD/source-pool counts                                                    |
| The exact v1 execution date                                           | **Not recovered**                       | Report it as before 2026-08-03 unless the original log is found                                 |
| v3 validation accident mAP50 = 0.956                                  | **Verified but non-quotable**           | It is a leaked frame-level training-progress value, not operational accuracy                    |
| Pre-registered v3 per-frame firing-rate check on the Philippine sets  | **Skipped**                             | State that it was not run; false-positive inspection supplied the direct field evidence instead |
| Legacy seven/five-clip percentages versus current 17-clip percentages | **Historical, not directly comparable** | Keep in separate sections because footage and labels changed                                    |
| “The model is accurate”                                               | **Unsupported wording**                 | Replace with event-level recall and FP/min with their evaluation-set scope                      |

## 6. Limitations

### Validation leakage

The recorded v1, v2, and v3 validation splits were frame-level in practice. Consecutive frames from
one incident can appear on both sides, and the incident-level guard did not complete. Validation mAP
therefore measures training progress under a contaminated split; it is not the paper's operational
performance metric.

### Training-data provenance

Nyanko is heterogeneous and contains filenames indicating AI-generated images. The project should
disclose that limitation and avoid describing the entire source as uniform real CCTV accident data.

### Evaluation coverage

The current result comes from one 17-clip project-specific set. It is useful held-out evidence for
this comparison, but it is not a deployment-wide estimate across cameras, weather, traffic density,
or geography.

### Hard crashes

The final model detected 0/6 hard crashes in the current set. This is the clearest boundary on what
the current training and harness demonstrate.

### Night and proximity false positives

All three remaining v3 false positives were at night and involved several nearby vehicles. The
Philippine foil addressed vehicle-shape confusion, but it did not eliminate all scene-level
ambiguity.

### Legacy reproducibility

The old seven-clip footage is no longer on disk. Its recorded metrics can be cited as historical
results, but they cannot be re-run from the current sample directory and must not be silently
compared with the current 17-clip results.

## 7. Internal paper-writing summary

The defensible narrative is:

> The project moved from a tracker-first prototype that failed on real crash footage to a detector-
> first two-class model with a spatial-temporal evidence accumulator. The first full run established
> a Nyanko-only baseline; the second added ordinary BMD-45 traffic to reduce vehicle-related false
> alarms; and the final full retrain added Philippine tricycle, jeepney, and night-traffic vehicle
> coverage. The final checkpoint was selected by event-level evaluation on held-out labeled video,
> not by leaked validation mAP. The adopted v3 checkpoint improved standard-crash recall and
> reduced false positives relative to v2, while retaining zero hard-crash recall and increasing
> median latency.

This wording should be paired with the dataset-count and harness details rather than presented as a
generic accuracy claim.

## Source records

- [Existing results record](../docs/results.md)
- [Project state and caveats](../CLAUDE.md)
- [Training run manifest](training-run-manifest.md)
- [Evaluation harness](evaluation-harness.md)
- [Accumulator sweep](../docs/accumulator-sweep.md)
- [Original tracker postmortem](../docs/design/accident-detection.md)
- [Drive run archive](https://drive.google.com/drive/folders/142WuVB8smOkILl-UMGLjUOrET8HCQQRK)
