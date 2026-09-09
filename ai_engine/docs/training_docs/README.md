# Paper Preparation Notes: ADAS Training and Evaluation

These notes are an internal working set for writing the ADAS accident-detection paper. They
separate the training history, the AI detection core/model harness, the evaluation harness, and
the results so that a paper draft can reuse the material without turning an implementation detail
into an unsupported performance claim.

## Reading order

1. [Training run manifest](training-run-manifest.md) — what actually ran, what did not, and which
   counts are supported by saved evidence.
2. [Training methodology](training-methodology.md) — the data, preprocessing, model design, and
   rationale for each iteration.
3. [Evaluation harness](evaluation-harness.md) — how the AI detection core produced events, how
   those events were scored, and how checkpoints and accumulator settings were compared.
4. [Results and limitations](results-and-limitations.md) — the chronological outcomes, current
   comparison, failure analysis, and paper-safe boundaries.

## Short project conclusion

The project has evidence for four actual training-related executions: three full model runs
(v1, v2, and v3) and one three-epoch v3 smoke test. The smoke test validated the revised data
pipeline and is not a fourth full model version. The adopted model is
`models/weights_v3/epoch50.pt`.

The AI detection core/model harness is the two-class YOLO detector plus the surrounding inference
logic: grayscale preprocessing, accident-class filtering, the spatial-temporal accumulator, and
event emission. The evaluation harness then runs that complete core against labeled video windows.
The current headline comparison is event-level recall and false-positive rate on the 17-clip
evaluation set—not standalone YOLO box output.

## Evidence-status labels

| Label             | Meaning                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| **Verified**      | Directly supported by an executed notebook, saved run artifact, repository record, or measured harness output. |
| **Inferred**      | A bounded interpretation supported by multiple records, but not printed as a single primary-run output.        |
| **Not recovered** | The project needs the value, but the exact original artifact is unavailable; no estimate is supplied.          |
| **Smoke test**    | A deliberately small execution used to validate the pipeline, not to establish model performance.              |
| **Skipped**       | Planned or implemented work that did not execute or did not produce a usable measurement.                      |
| **Superseded**    | A historical result or design retained for context but no longer the active method.                            |
| **Excluded**      | An unexecuted draft, source-pool count, or other item that must not be counted as a run/result.                |

## Primary source records

- [Project state and caveats](../CLAUDE.md)
- [Existing detection results](../docs/results.md)
- [Training notebook source](../train/adas_train_colab.ipynb)
- [Detector-first design](../docs/design/detector-first-accident-detection.md)
- [Original tracker prototype postmortem](../docs/design/accident-detection.md)
- [Accumulator sweep record](../docs/accumulator-sweep.md)
- [Philippine vehicle-data investigation](../docs/philippine-vehicle-gap.md)
- [Recovered Drive run folders](https://drive.google.com/drive/folders/142WuVB8smOkILl-UMGLjUOrET8HCQQRK)

## Reporting boundary

The legacy seven/five-clip evaluation and the current 17-clip evaluation are documented in
separate sections. The footage and labels changed, so their percentages and false-positive
rates are historical measurements rather than one directly comparable time series.

The validation mAP values are retained only as training-progress observations. The incident-level
validation guard did not complete for the recorded retrains, so frame-level validation mAP is not
treated as operational accuracy.
