# Training Run Manifest

This file is the factual index for the training history. It distinguishes completed model runs,
the v3 smoke test, the discarded pre-training prototype, and notebook copies that were never
executed. Counts in this file describe images that entered an executed training dataset whenever
that count is recoverable; public-source totals and planning budgets are not substituted for
run counts.

## Counting rule

The project has **four actual training-related executions**:

- three full model runs: v1, v2, and v3;
- one three-epoch v3 smoke test.

For paper reporting, the smoke test is a pipeline-validation execution, not a fourth full model
version. The two additional Colab notebook copies found in Drive have no execution counts or
saved outputs and are excluded.

## Evidence-status legend

| Status            | Use in this manifest                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Verified**      | Directly visible in a saved output, run directory, tracked checkpoint, or dated project record.                          |
| **Inferred**      | Reconciled from multiple records, with the inference stated explicitly.                                                  |
| **Not recovered** | The exact value or date is not present in the surviving artifacts. It is intentionally left blank or described in words. |
| **Smoke test**    | A deliberately reduced execution whose outputs are not a performance result.                                             |
| **Superseded**    | A real historical result or design that is no longer the adopted system.                                                 |
| **Excluded**      | A notebook draft or source artifact that did not constitute a completed training run.                                    |

## Run inventory

| Record                       | Date / timing                                             | Run name                       | What executed                                                                          | Main data change                                                                                         | Output / status                                                                                                                                                                                                                                                  |
| ---------------------------- | --------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Historical tracker prototype | 2026-07-26                                                | N/A                            | Vehicle detection → tracking → motion-state machine; no full YOLO retrain counted here | Historical detection-core design, not the final detector-first pipeline                                  | **Superseded** after 0/7 detections on the real seven-clip set; see the [postmortem](../docs/design/accident-detection.md)                                                                                                                                       |
| v1 full baseline             | Before 2026-08-03; exact execution date **not recovered** | Historical `adas` / v1 weights | YOLO26n, 60 epochs                                                                     | Nyanko only; BMD-45 contributed zero images because the vehicle budget was consumed first                | `models/weights_v1/best.pt` and `last.pt`; **Verified, superseded**. The historical Drive `adas` folder is currently empty, so the tracked weights and results record are the surviving evidence.                                                                |
| v2 full retrain              | 2026-08-03                                                | `adas_v2`                      | YOLO26n, 60 epochs                                                                     | Fixed the vehicle-budget failure and inserted BMD-45 ordinary-traffic images into the `vehicle` class    | `models/weights_v2/`; **Verified, superseded**. [Drive output folder](https://drive.google.com/drive/folders/1BMJKPCS4ZjDknYD2BVNfRh9cuWARV6wJ) · [executed Colab notebook](https://colab.research.google.com/drive/1xuddLqUbpQpZVna-Wa-lO7ybKDgvFs1R)           |
| v3 smoke test                | 2026-08-09                                                | `adas_v3_smoke`                | Revised notebook with `SMOKE=True`, three epochs, and capped source budgets            | Exercised the new BMD/Philippine-vehicle data flow cheaply before the full run                           | **Smoke test**; not used for model comparison. [Drive output folder](https://drive.google.com/drive/folders/1aDwCRLrIe8vjNjaBpTw8_8kY5gAnIlyi)                                                                                                                   |
| v3 full retrain              | 2026-08-09; adopted 2026-08-10                            | `adas_v3`                      | Revised notebook with `SMOKE=False`, 60 epochs, and eight exported checkpoints         | Retained the vehicle foil and added Philippine tricycle, motorcycle, jeepney, and night-traffic coverage | `models/weights_v3/epoch50.pt`; **Verified and adopted**. [Drive output folder](https://drive.google.com/drive/folders/1nTZaBu8Zr9dzCkZz0ukeWvwC3nbRUp9u) · [executed Colab notebook](https://colab.research.google.com/drive/1amq2-0_qbVAavjZqdgvidtvASQ3ycoll) |

## Training configuration

| Setting              |                               Full runs |            v3 smoke test | Evidence status                                                                                     |
| -------------------- | --------------------------------------: | -----------------------: | --------------------------------------------------------------------------------------------------- |
| Base model           |   YOLO26n initialized from COCO weights |                     Same | **Verified** in the results record and notebook                                                     |
| Image size           |                                     640 |                      640 | **Verified**                                                                                        |
| Batch size           |                                      64 |                       64 | **Verified** for the controlled retrain configuration; this matched the recorded v1 setting         |
| Epochs               |                                      60 |                        3 | **Verified** from the notebook and saved `results.csv` lengths                                      |
| Device               | Colab T4 for the recorded full training |                Colab GPU | **Verified** in the run notes; exact smoke hardware details are not separately recovered            |
| Input preprocessing  |   Grayscale converted to three channels |                     Same | **Verified**; training and inference were kept consistent                                           |
| Class balance target |        8 vehicle boxes per accident box | Capped/reduced for smoke | **Verified** in `dataset/pipeline.py` and the notebook; the smoke composition is not representative |

## Dataset composition by executed run

### v1 — baseline dataset

The recorded v1 training dataset contained **11,095 images**, all from Nyanko:

| Source / class role        | Images used |                Boxes | Notes                                                     |
| -------------------------- | ----------: | -------------------: | --------------------------------------------------------- |
| Nyanko accident images     |       5,751 | 6,215 accident boxes | Accident class after preparation                          |
| Nyanko vehicle-only images |       5,344 | 49,744 vehicle boxes | Vehicle foil from the same source                         |
| **Total**                  |  **11,095** |           **55,959** | 8.0:1 vehicle-to-accident box ratio                       |
| BMD-45                     |       **0** |                **0** | The v1 budget calculation silently left no BMD allocation |

These are executed v1 counts, not the Nyanko source-pool total. The source was grayscaled and
geometry-filtered before training.

### v2 — BMD-45 retrain

The surviving v2 records verify the BMD portion precisely:

| Source / class role         |                                          Images used |                                                               Boxes | Evidence status                               |
| --------------------------- | ---------------------------------------------------: | ------------------------------------------------------------------: | --------------------------------------------- |
| BMD-45 vehicle-only subset  |                                            **2,072** |                                            **21,386 vehicle boxes** | **Verified**; 1,678 train / 394 validation    |
| Nyanko                      | Exact final per-source image count **not recovered** |                        Included in the accident and vehicle classes | Do not reconstruct from the source-pool total |
| Assembled vehicle class     |         Not separately recoverable as an image total | **54,671 vehicle boxes**, of which BMD-45 supplied 21,386 (**39%**) | **Verified**                                  |
| Assembled total image count |                                    **Not recovered** |                                                                   — | Leave unrecovered rather than estimate        |

The BMD subset was prepared as grayscale 640×360 JPEGs and matches the v2 run record. The full
v2 output is preserved in the [Drive `adas_v2` folder](https://drive.google.com/drive/folders/1BMJKPCS4ZjDknYD2BVNfRh9cuWARV6wJ).

### v3 smoke test

The smoke run intentionally capped the source budgets and trained for only three epochs. It
confirmed that the revised notebook could build the dataset, include the new vehicle sources,
and complete training. Its exact reduced image composition is not used as a final training-count
claim; the saved `adas_v3_smoke` artifacts are the evidence for execution, not performance.

### v3 — final retrain

The final v3 dataset contained **11,413 images**:

| Source                                      | Class role                                           | Images used |
| ------------------------------------------- | ---------------------------------------------------- | ----------: |
| Nyanko                                      | Accident + vehicle                                   |   **8,664** |
| BMD-45                                      | Vehicle-only ordinary traffic                        |   **1,687** |
| `traffic-vehicle-detection-e6kgi` (`e6kgi`) | Vehicle-only Philippine tricycle/motorcycle coverage |     **374** |
| `vehicle-5kcdl` (`5kcdl`)                   | Vehicle-only jeepney and night coverage              |     **688** |
| **Total**                                   | —                                                    |  **11,413** |

The two Philippine sources were given space inside the existing vehicle budget; they were not
appended on top of the 8:1 cap. These counts are the final v3 executed-run composition recovered
from the saved Colab/Drive evidence.

## Checkpoint and adoption record

| Run      | Checkpoints                                       | Selection decision                                                                                                                 |
| -------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| v1       | `best.pt`, `last.pt`                              | v1 `last.pt` was the historical incumbent; its `best.pt` and `last.pt` were not equivalent                                         |
| v2       | `best.pt`, `last.pt`, and saved epoch checkpoints | v2 `best.pt`/`last.pt` were temporarily adopted after the expanded current-set evaluation; the two files contain identical weights |
| v3 smoke | Short-run artifacts only                          | No checkpoint selection; smoke-only                                                                                                |
| v3       | Eight checkpoints including `epoch50.pt`          | `epoch50.pt` was selected by event-level checkpoint sweep and adopted on 2026-08-10; the `best.pt` label was not trusted           |

## Excluded or non-counting artifacts

- Two additional `adas_train_colab.ipynb` copies in Drive have no execution counts and no saved
  outputs. They are **Excluded**, not additional runs.
- The empty historical Drive `adas` folder is not evidence that v1 did not run; v1 weights and
  measured results survive in the repository.
- `accident_detection.pt` is a broken historical detector used in the postmortem and is not one
  of the four recorded training executions in this run inventory.
- Dataset downloads, preprocessing cells, validation-only inference, checkpoint sweeps, and the
  864-configuration accumulator sweep are not counted as additional model-training runs.

## Source records

- [Project state and run caveats](../CLAUDE.md)
- [Chronological detection results](../docs/results.md)
- [Training notebook source](../train/adas_train_colab.ipynb)
- [Shared quota and incident helpers](../dataset/pipeline.py)
- [Drive run archive](https://drive.google.com/drive/folders/142WuVB8smOkILl-UMGLjUOrET8HCQQRK)
