# AI Model Validation — Archival Evidence Summary

**Prepared:** 2026-09-15

**Purpose:** Evidence summary for AI-VAL-001, AI-VAL-005, AI-VAL-006, AI-VAL-008, and AI-VAL-009 in the MEER Test Execution tracker.

This document consolidates recorded repository evidence. It does not represent a fresh rerun. The fresh frozen reference run is documented separately in `report.md`.

## AI-VAL-001 — Recorded frame-level metric

- The v3 full retrain recorded accident-class mAP@0.50 of **0.956 at epoch 50** on 2026-08-09.
- The original training/validation split is not available for rerun. Frame-level incident leakage is disclosed in the source records.
- The value is therefore retained as a **qualified validation-split result**, not as independent operational detection accuracy.

## AI-VAL-005 — Checkpoint selection

- Eight exported v3 checkpoints were evaluated with the labelled-clip event harness.
- `epoch50.pt` matched `best.pt` on recall but produced **3 false positives versus 5** for `best.pt`.
- `epoch50.pt` was selected for the reference pipeline. No fresh checkpoint sweep was performed for this evidence update.

## AI-VAL-006 — Lighting and nighttime conditions

- **8 of 17** labelled clips were identified as night footage.
- Recorded night recall exceeded recorded day recall.
- All **3 residual false positives** occurred at night and involved nearby vehicles.
- The exact per-clip nighttime numerator is not recoverable from the current machine-readable labels, so this evidence does not support a universal nighttime-robustness claim.

## AI-VAL-008 — TensorRT deployed-artifact parity

- The recorded 2026-09-09 parity check matched the epoch50 checkpoint's hit/miss outcome on **all 17 clips**.
- Native-rate TensorRT produced **4 false positives versus 3** for the checkpoint.
- The same engine sampled at 10 FPS produced **3 false positives**, matching the checkpoint.
- No recall regression was observed; the native-rate false-positive drift is retained as a disclosed deviation.

## AI-VAL-009 — Cadence and source-resolution sensitivity

- Reset-aware TensorRT preserved the native per-clip hit/miss pattern at **10, 8, 6, 5, and 3 FPS**.
- At **4 FPS**, `motor-motor-night` was missed; false-positive totals varied by cadence.
- At 720p/640x360 source resolution, recall fell from **8/16 to 6/16**, losing `dpwh-red-car-motor` and `red-car-motor`.
- Source downscaling is therefore not treated as accuracy-neutral; any selected profile requires its own evaluation.

## Source records

- `ai_engine/docs/training_docs/results-and-limitations.md`
- `ai_engine/adas_transfer/SPEC.md`
- `ai_engine/eval/baseline_epoch50.json`
- `paper_sync/findings/2026-09-09-substream-recall-and-poc-capacity.md`
- `paper_sync/findings/2026-09-14-nfr03-five-to-fifteen-fps.md`
