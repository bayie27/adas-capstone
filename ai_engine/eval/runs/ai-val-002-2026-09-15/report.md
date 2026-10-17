# AI-VAL-002 — Frozen Reference Pipeline Evaluation

**Execution date:** 2026-09-15

**Status:** Completed

**Model:** `ai_engine/epoch50.pt`

**Pipeline:** grayscale preprocessing → YOLO inference → accident-class filtering → spatial-temporal accumulator

## Frozen configuration

| Setting               | Value                             |
| --------------------- | --------------------------------- |
| Confidence floor      | `0.15`                            |
| Model input size      | `640`                             |
| Accumulator threshold | `1.0` conf-seconds                |
| Accumulator decay     | `0.30`                            |
| Device                | CUDA device `0`                   |
| Scoring lead          | `2` seconds before labelled onset |
| Scoring tail          | `15` seconds after labelled onset |
| Retuning              | None                              |

## Scoring rule

A crash is a **hit** when at least one emitted event falls within `[onset - 2s, end + 15s]`. A crash with no event in that window is a **miss**. Events outside every crash window are counted as false positives. The complete raw event records are the JSON files in this directory.

## Per-clip results

| Clip                 | Difficulty | Source           | Outcome  | False-positive event(s) |
| -------------------- | ---------- | ---------------- | -------- | ----------------------- |
| `airbase`            | Negative   | NVR export       | No event | None                    |
| `armored-car-car`    | Hard       | NVR export       | Miss     | None                    |
| `car-motor-far`      | Hard       | NVR export       | Miss     | None                    |
| `car-motor-motor`    | Standard   | NVR export       | Miss     | `21.66s`                |
| `car-motor`          | Standard   | NVR export       | Hit      | `58.30s`                |
| `car-uturn-motor`    | Hard       | NVR export       | Miss     | None                    |
| `dekwatro`           | Standard   | NVR export       | Hit      | None                    |
| `dpwh-red-car-motor` | Standard   | NVR export       | Hit      | None                    |
| `jeep-car`           | Hard       | NVR export       | Miss     | None                    |
| `jeep-motor`         | Standard   | NVR export       | Hit      | None                    |
| `jeep-yellow-car`    | Standard   | Screen recording | Hit      | None                    |
| `motor-motor-night`  | Standard   | NVR export       | Hit      | None                    |
| `motor-motor`        | Standard   | Screen recording | Miss     | `12.70s`                |
| `red-car-motor`      | Standard   | NVR export       | Hit      | None                    |
| `tric-motor-car`     | Standard   | NVR export       | Hit      | None                    |
| `truck-car`          | Hard       | NVR export       | Miss     | None                    |
| `truck-student-car`  | Hard       | NVR export       | Miss     | None                    |

## Aggregate results

| Measure                           | Result           |
| --------------------------------- | ---------------- |
| Standard recall                   | **8/10 (80%)**   |
| Hard recall                       | **0/6 (0%)**     |
| Overall crash recall              | **8/16 (50%)**   |
| Genuine false positives           | **3**            |
| Clean-footage denominator         | **11.0 minutes** |
| False positives per minute        | **0.27**         |
| Events on declared negative clip  | **0**            |
| Standard recall, NVR exports only | **7/8 (87.5%)**  |

## Interpretation

The frozen reference run completed all 17 labelled clips and reproduced the reference hit/miss pattern: every standard hit was retained, all six preclassified hard clips were missed, and the declared negative clip produced no event. The three false positives occurred in ordinary footage outside crash windows and are retained for the false-positive analysis.

This is an event-level end-to-end pipeline result, not a formal frame-level precision, F1, specificity, or independent test-set estimate. The evaluation set is project-specific, and independence from earlier footage is not fully established.

## Reproduction

Run from the repository root:

```text
uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt --events-dir ai_engine/eval/runs/ai-val-002-2026-09-15 --conf 0.15 --imgsz 640 --threshold 1.0 --decay 0.3 --device 0 --lead 2 --tail 15
```

The raw event files in this directory were produced by that run. Do not overwrite them when performing a retest; create a new dated evidence directory.
