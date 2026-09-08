# Training Methodology and Evolution

This document describes how the accident detector was built, why the design changed, and what
each training iteration was intended to fix. It is written as an internal paper-preparation note;
the [run manifest](training-run-manifest.md) is the source of truth for execution counts and
dataset membership.

## 1. Problem framing

The system is designed to detect an accident as a persistent event in fixed-camera traffic video.
The model is a two-class object detector:

- `accident` (`class 0`) represents the crash and its immediate aftermath and is the only class
  that can raise an alert.
- `vehicle` (`class 1`) represents ordinary vehicles and acts as a discriminative foil. It gives
  the model a labeled explanation for a normal traffic scene instead of forcing every vehicle in
  a crash image to remain background.

At inference, the `vehicle` detections are discarded. The model is therefore not a vehicle-counting
system; the vehicle class exists to reduce the shortcut in which ordinary vehicles become evidence
of an accident.

## 2. Architecture pivot

### 2.1 Superseded tracker-first prototype

The first detection-core design followed a conventional idea:

```text
vehicle detection → tracking → motion state machine → crash event
```

It attempted to identify a moving vehicle that slowed or stopped abnormally, then persisted the
candidate before emitting an event. On the real seven-clip sample set it produced **0/7
detections** at the default configuration. Relaxed settings reached only 3/7 while creating an
unmeasurable false-positive risk.

The postmortem identified two immediate defects:

1. Strict persistence reset on one sub-threshold frame, so flickering evidence never completed
   the persistence window.
2. A high detector confidence threshold starved ByteTrack of low-confidence candidates and caused
   short, fragmented track identities.

More importantly, the design depended on one track ID surviving the exact impact sequence that
causes occlusion, box overlap, deformation, and identity switches. The crash therefore broke the
state history needed to prove the crash. This was treated as a structural design failure, not a
parameter-tuning problem.

The tracker-first prototype is historical context only. It is not part of the final training run
count or the final evaluation harness.

### 2.2 Detector-first pipeline

The implemented design removed vehicle tracking and used a per-frame accident detector followed by
a spatial-temporal evidence accumulator:

```text
video frames
    ↓
grayscale preprocessing
    ↓
YOLO detections at a low confidence floor
    ↓
keep class-0 accident boxes
    ↓
IoU-linked leaky accumulator
    ↓
persisted detection events
```

The detector supplies recall-oriented frame evidence. The accumulator supplies temporal and spatial
persistence so that a one-frame or wandering box does not immediately become an alert.

## 3. Dataset roles

| Source                            | Training role                           | What it contributed                                                                | Important limitation                                                                |
| --------------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Nyanko                            | Accident source plus some vehicle boxes | The only source of labeled accident appearance in the final retrains               | Heterogeneous source; includes grayscale imagery and discovered AI-generated images |
| BMD-45                            | Vehicle-only foil                       | Dense ordinary traffic; intended to teach the model that road scenes can be normal | Indian traffic, not Philippine traffic; no accident labels                          |
| `traffic-vehicle-detection-e6kgi` | Philippine vehicle-only foil            | Tricycle and motorcycle coverage from fixed-camera traffic                         | No jeepney coverage in the audited class list; limited scene diversity              |
| `vehicle-5kcdl`                   | Philippine vehicle-only foil            | Jeepney, tricycle, car, and night imagery                                          | Essentially concentrated around one camera position; limited scene diversity        |

The final v3 run retained Nyanko as the accident source and used all other sources as normal-vehicle
foil data. No Philippine accident images were added. That distinction matters: the Philippine sets
were intended to reduce false alarms on vehicle appearance, not to increase accident recall.

## 4. Dataset preparation

### 4.1 Class collapsing

Source-specific labels were mapped into the two training classes. Accident-related labels became
`accident`; ordinary vehicle labels became `vehicle`; negation labels such as `no-accident` were
excluded rather than matched by a naive substring rule. The shared helpers are implemented in
[`dataset/collapse_classes.py`](../dataset/collapse_classes.py) and
[`dataset/pipeline.py`](../dataset/pipeline.py).

### 4.2 Geometry filtering

The accident source contained many close-up images whose accident boxes were much larger than the
objects in the deployment footage. The recorded preparation measured a median accident box area of
26.7% of the frame, while the Lipa footage generally contained boxes around 2–10% of the frame.
Images whose largest accident box exceeded 25% of the frame were removed; the recorded v1
preparation dropped 7,069 close-ups. This made the training geometry more representative of a
fixed road camera.

### 4.3 Vehicle-to-accident quota

The target was an 8:1 vehicle-box-to-accident-box ratio. The purpose was to provide ordinary-traffic
foil data without allowing vehicle images to dominate so heavily that the model learned to predict
`vehicle` everywhere and `accident` nowhere.

The v1 run exposed a quota failure: Nyanko's own vehicle boxes consumed the assignable budget before
the BMD-45 step, so BMD-45 contributed zero images. The v2 pipeline added a reserved BMD share. The
v3 pipeline added a separate Philippine share that displaced part of the same assignable vehicle
budget rather than silently increasing the ratio.

The tested arithmetic is in [`dataset/pipeline.py`](../dataset/pipeline.py):

- `reserve_quota(...)` splits the assignable vehicle allowance between Nyanko and BMD-45.
- `reserve_quota_ph(...)` splits it between Nyanko, the Philippine sources, and BMD-45.
- `scan(...)` counts labels from disk instead of trusting a stale count from an earlier notebook
  cell.

### 4.4 Grayscale preprocessing

Every training image was converted to grayscale and replicated back to three channels for the
COCO-pretrained network. Inference applies the same conversion in [`detect/run.py`](../detect/run.py).

This was a domain-control decision, not a visual-style choice. Nyanko is essentially grayscale
while BMD-45 is mostly color. Leaving the sources unchanged would make color a cheap class shortcut:
`color → vehicle`, `grayscale → accident`. Applying grayscale at both stages prevents that specific
shortcut from deciding whether a color deployment frame can produce an accident detection.

The paper should describe grayscale as **preprocessing**, not as random grayscale augmentation.

### 4.5 Incident-split safeguard

The project implemented filename-based incident grouping and a guard intended to keep consecutive
frames of one crash together. The guard did not complete for the recorded v2 and v3 validation
passes because the source filenames did not satisfy the safety checks. Consequently, the reported
validation mAP remained a frame-level training-progress signal rather than an independent estimate
of deployment performance. The real comparison was made on held-out video events through the
evaluation harness.

## 5. Training configuration

| Parameter            |                                     Full runs |                             v3 smoke test |
| -------------------- | --------------------------------------------: | ----------------------------------------: |
| Base weights         |                             YOLO26n from COCO |                         YOLO26n from COCO |
| Input size           |                                           640 |                                       640 |
| Batch size           |                                            64 |                                        64 |
| Epochs               |                                            60 |                                         3 |
| Training environment |                          Google Colab, T4 GPU |                          Google Colab GPU |
| Model input          |        Grayscale replicated to three channels |                                      Same |
| Class balance target |           8:1 vehicle boxes to accident boxes | Capped source budgets; not representative |
| Exported checkpoints | Periodic checkpoints plus `best.pt`/`last.pt` |                  Short-run artifacts only |

The exact final dataset membership for each execution is recorded in the
[training-run manifest](training-run-manifest.md), rather than repeated here with competing
counts.

## 6. Run-by-run rationale

### v1 — establish a baseline

The baseline used the prepared Nyanko source for both classes. It applied geometry filtering,
grayscale preprocessing, and class-ratio control. The intended ordinary-traffic foil was present
only through Nyanko's own vehicle boxes; BMD-45 was allocated zero images by the faulty budget
calculation.

This run established the first detector-first baseline and exposed the need for ordinary traffic
that resembles the deployment domain.

### v2 — add ordinary road-scene foil data

The v2 retrain fixed the allocation failure and inserted a prepared BMD-45 subset into the vehicle
class. This directly tested whether normal traffic from a fixed-camera road domain would reduce
false alarms.

The prediction was partly confirmed: the false positive on a jeepney-context clip disappeared and
the model became quieter. On the original five-clip comparison, however, the selected v2 checkpoint
lost one crash relative to v1, so v1 was initially retained under the old adoption rule. On the
expanded 17-clip evaluation, v2 later became the temporary deployed model before v3 replaced it.

### v3 smoke test — validate the revised data path

The v3 notebook was first run with `SMOKE=True`. It used capped source budgets and three epochs so
the new Philippine-source download, quota, class checks, grayscale conversion, dataset export, and
training call could be exercised without spending the full training time.

The smoke run is evidence that the revised pipeline executed. It is not a performance result and
its reduced class composition must not be presented as the final v3 dataset.

### v3 — add Philippine vehicle coverage

The full v3 run kept Nyanko and BMD-45, then added `e6kgi` and `5kcdl` as vehicle-only sources. The
new data targeted the false-positive failure mode identified after v2: ordinary tricycles,
jeepneys, and night traffic were absent from the original sources.

No accident source was added, so the expected benefit was precision rather than improved recall on
the hardest crashes. The run lasted 60 epochs, exported eight checkpoints, and used the event-level
checkpoint sweep to select `epoch50.pt` rather than trusting `best.pt`.

## 7. Provenance and limitations to carry into the paper

- The source and licensing details should be copied from the audited records in
  [`docs/accident-data-survey.md`](../docs/accident-data-survey.md),
  [`docs/philippine-vehicle-gap.md`](../docs/philippine-vehicle-gap.md), and
  [`dataset/audit_report.md`](../dataset/audit_report.md). If a source's exact license is not in
  those records, mark it as unrecovered rather than assume it.
- Nyanko was found to contain AI-generated accident images identifiable by
  `Gemini_Generated_Image_*` filenames. This is a limitation of the accident source and should be
  disclosed, not silently removed from the history.
- The 17 evaluation clips were kept separate from training. They are the measurement instrument,
  not an additional training source.
- Validation mAP is not the paper's operational metric because the incident-level guard did not
  complete for the recorded retrains.
